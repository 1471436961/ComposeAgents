"""Small evidence wrapper around NOOA ShellTools, not a shell execution engine.

The caller supplies an isolated, disposable workspace and owns OS containment.
Path checks below constrain file tools; arbitrary shell/CodeAct is NOT sandboxed.
All commands share one lock so profiling/build/GPU measurements cannot overlap
inside this application. This cannot exclude unrelated processes on the host.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True)
class CommandEvidence:
    id: str
    role: str
    command: str
    returncode: int | None
    timed_out: bool
    cancelled: bool
    elapsed_seconds: float
    stdout: str
    stderr: str
    stdout_file: str
    stderr_file: str
    stdin_file: str | None


class Workspace:
    """Own a native shell and durable evidence for exactly one application run."""

    def __init__(self, root: Path, *, command_timeout: float = 120, init_command: str | None = None):
        self.root = root.resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("workspace must be an existing directory")
        if not math.isfinite(command_timeout) or command_timeout <= 0:
            raise ValueError("command_timeout must be finite and positive")
        self.command_timeout = command_timeout
        self._init_command = init_command
        self._shell = None
        self._lock = asyncio.Lock()
        self.commands: list[CommandEvidence] = []
        self._evidence_root = self.root / ".inference_team"
        self._evidence_directory = self._evidence_root / uuid4().hex

    @property
    def evidence_directory(self) -> Path:
        """The checked current-run directory; reject symlink/junction redirection.

        Recheck on access, including after shell commands. These path checks do
        not provide race-free containment against an adversarial process.
        """
        for directory in (self._evidence_root, self._evidence_directory):
            if directory.is_symlink() or directory.is_junction():
                raise ValueError("evidence directories must not be symlinks or junctions")
            if not directory.resolve().is_relative_to(self.root):
                raise ValueError("evidence directory escapes the workspace")
        return self._evidence_directory

    def evidence_path(self, name: str) -> Path:
        """Check an internal evidence write target within the current run only."""
        if name in {"", ".", ".."} or Path(name).name != name:
            raise ValueError("evidence filename must be a single path component")
        directory = self.evidence_directory
        path = directory / name
        if path.is_symlink() or path.is_junction() or not path.resolve().is_relative_to(directory):
            raise ValueError("evidence files must not redirect outside their write target")
        return path

    def path(self, relative: str, *, evidence_read: bool = False) -> Path:
        directory = self.evidence_directory
        requested = Path(os.path.abspath(self.root / relative))
        path = requested.resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("file path escapes the workspace")
        if requested.is_relative_to(self._evidence_root) or path.is_relative_to(self._evidence_root):
            if not evidence_read:
                raise ValueError("application evidence is not an editable artifact")
            if not path.is_relative_to(directory):
                raise ValueError("only current-run evidence is readable through file tools")
        return path

    async def __aenter__(self) -> Workspace:
        if self._shell is not None:
            raise RuntimeError("workspace is already open")
        directory = self.evidence_directory
        from nooa.tools.shell_tools import ShellTools

        directory.parent.mkdir(exist_ok=True)
        self.evidence_directory.mkdir()  # Never adopt or delete an existing run.
        self._shell = ShellTools(cwd=str(self.root), init_command=self._init_command)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._shell is not None:
            try:
                await self._shell.close()
            finally:
                self._shell = None

    def _require_shell(self):
        if self._shell is None:
            raise RuntimeError("use Workspace as an async context manager")
        return self._shell

    async def run(self, role: str, command: str, *, stdin: str | None = None,
                  timeout: float | None = None) -> CommandEvidence:
        limit = self.command_timeout if timeout is None else timeout
        if not math.isfinite(limit) or not 0 < limit <= self.command_timeout:
            raise ValueError("timeout must be positive and within command_timeout")
        async with self._lock:
            shell = self._require_shell()
            self.evidence_path("commands.jsonl")  # Fail before running if redirected.
            start, ident = time.perf_counter(), uuid4().hex
            stdout, stderr, code, timed_out, cancelled = "", "", None, False, False
            try:
                result = await shell.run(command, stdin=stdin, timeout=limit, cwd=str(self.root))
                stdout, stderr = result.stdout, result.stderr
                code, timed_out = result.returncode, result.timed_out
            except BaseException as error:
                cancelled = isinstance(error, asyncio.CancelledError)
                stderr = f"{type(error).__name__}: {error}"
                # NOOA owns process cleanup. Do not leave a cancelled persistent
                # command running while the next stage acquires the shared lock.
                try:
                    await shell.close()
                except Exception as cleanup_error:
                    stderr += f"\ncleanup failed: {cleanup_error}"
                raise
            finally:
                out = self.evidence_path(f"{ident}.stdout.txt")
                err = self.evidence_path(f"{ident}.stderr.txt")
                input_file = None
                if stdin is not None:
                    source = self.evidence_path(f"{ident}.stdin.txt")
                    source.write_text(stdin, encoding="utf-8")
                    input_file = str(source.relative_to(self.root))
                out.write_text(stdout, encoding="utf-8")
                err.write_text(stderr, encoding="utf-8")
                record = CommandEvidence(
                    ident, role, command, code, timed_out, cancelled,
                    time.perf_counter() - start, stdout[-8000:], stderr[-8000:],
                    str(out.relative_to(self.root)), str(err.relative_to(self.root)),
                    input_file,
                )
                self.commands.append(record)
                with self.evidence_path("commands.jsonl").open("a", encoding="utf-8") as file:
                    file.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
            return record

    def verify_evidence(self, ids: list[str], *, role: str | None = None,
                        after: int = 0, success_required: bool = False) -> None:
        available = {item.id: item for item in self.commands[after:]}
        for ident in ids:
            item = available.get(ident)
            if item is None or (role is not None and item.role != role):
                raise ValueError(f"unknown or non-independent command evidence: {ident!r}")
        if success_required and not any(
            available[i].returncode == 0 and not available[i].timed_out
            and not available[i].cancelled for i in ids
        ):
            raise ValueError("accepted requires a successful independent verification command")


class ReadTools:
    """Read workspace artifacts and run recorded investigations/checks.

    Commands run in the supplied environment, can have side effects, and are
    serialized across roles. Do not install software, change system settings,
    remove unrelated processes/files, access secrets, or start background jobs.
    Analysts/validators must not modify implementation source. Use commands via
    run rather than Python subprocess; do not put credentials in command text.
    Windows tools may be invoked from WSL using caller-supplied executable paths.
    """

    def __init__(self, workspace: Workspace, role: str):
        self._workspace = workspace
        self._role = role

    def list_files(self, directory: str = ".") -> list[str]:
        """List project files or current-run evidence; old runs are not browsable."""
        path = self._workspace.path(directory, evidence_read=True)
        return sorted(str(p.relative_to(self._workspace.root)) for p in path.iterdir()
                      if p.name != ".inference_team")

    async def read(self, path: str, start: int = 1, stop: int = 200) -> str:
        """Read project files or current-run evidence (1-based bounded UTF-8 lines).

        Previous runs are retained for external audit, not exposed by file tools.
        """
        if not 1 <= start <= stop or stop - start >= 1000:
            raise ValueError("read at most 1000 lines with 1 <= start <= stop")
        return str(await self._workspace._require_shell().read(
            str(self._workspace.path(path, evidence_read=True)), lines=(start, stop)))

    async def run(self, command: str, stdin: str | None = None,
                  timeout: float | None = None) -> CommandEvidence:
        """Run a foreground command; inspect exit code and cite its ID in reports.

        stdout/stderr previews are bounded; complete output paths are returned.
        Use stdin for Python/script payloads. Timeout is capped by the caller.
        Hardware timings require warmup, repeats and checks for competing loads.
        """
        return await self._workspace.run(self._role, command, stdin=stdin, timeout=timeout)


class EditTools(ReadTools):
    """Implementation tools; all writes must remain in the supplied workspace."""

    async def write(self, path: str, content: str) -> str:
        """Write a UTF-8 artifact with native ShellTools; return its SHA-256."""
        resolved = self._workspace.path(path)
        await self._workspace._require_shell().write_file(str(resolved), content)
        return hashlib.sha256(resolved.read_bytes()).hexdigest()
