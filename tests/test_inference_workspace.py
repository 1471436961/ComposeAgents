"""Portable application boundaries; no NOOA import, shell, GPU or model."""

import asyncio
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from applications.inference_optimization.__main__ import parser
from applications.inference_optimization.workspace import ReadTools, Workspace


def directory_link(link, target):
    """Exercise native Windows junctions without requiring symlink privileges."""
    if sys.platform == "win32":
        subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
                       check=True, capture_output=True)
    else:
        link.symlink_to(target, target_is_directory=True)


def test_workspace_file_boundary_and_evidence_ownership(tmp_path):
    workspace = Workspace(tmp_path)
    assert workspace.path("nested/file.py") == tmp_path / "nested" / "file.py"
    for bad in ("../outside.py", str(tmp_path.parent / "elsewhere.py"), ".inference_team/record"):
        with pytest.raises(ValueError):
            workspace.path(bad)
    current = workspace.evidence_directory / "record"
    assert workspace.path(str(current), evidence_read=True) == current
    with pytest.raises(ValueError, match="current-run"):
        workspace.path(".inference_team/old/record", evidence_read=True)


@pytest.mark.parametrize("inside", [False, True], ids=["external", "internal"])
def test_redirected_evidence_root_is_rejected_before_entering(tmp_path, inside):
    root = tmp_path / "workspace"
    root.mkdir()
    target = root / "archive" if inside else tmp_path / "outside"
    target.mkdir()
    sentinel = target / "keep.txt"
    sentinel.write_text("preserve", encoding="utf-8")
    workspace = Workspace(root)
    directory_link(root / ".inference_team", target)
    with pytest.raises(ValueError, match="symlinks or junctions"):
        asyncio.run(workspace.__aenter__())
    assert workspace._shell is None
    assert list(target.iterdir()) == [sentinel]
    assert sentinel.read_text(encoding="utf-8") == "preserve"


def test_redirected_current_run_is_rejected_without_writing(tmp_path):
    workspace = Workspace(tmp_path)
    run = workspace.evidence_directory
    run.parent.mkdir()
    target = tmp_path / "other-run"
    target.mkdir()
    directory_link(run, target)
    with pytest.raises(ValueError, match="symlinks or junctions"):
        workspace.evidence_path("result.json").write_text("must not write")
    assert list(target.iterdir()) == []


def test_replaced_run_directory_fails_before_command_starts(tmp_path):
    async def scenario():
        workspace = Workspace(tmp_path)
        run = workspace.evidence_directory
        run.mkdir(parents=True)

        class Shell:
            calls = 0

            async def run(self, *args, **kwargs):
                self.calls += 1
                raise AssertionError("must not run with redirected evidence")

        shell = Shell()
        workspace._shell = shell
        run.rmdir()  # Empty directory owned by this test; do not remove old evidence.
        target = tmp_path / "redirect"
        target.mkdir()
        directory_link(run, target)
        with pytest.raises(ValueError, match="symlinks or junctions"):
            await workspace.run("runtime", "must not start")
        assert shell.calls == 0 and workspace.commands == []
        assert list(target.iterdir()) == []
    asyncio.run(scenario())


def test_file_tools_read_only_current_evidence_and_preserve_old_run(tmp_path):
    async def scenario():
        previous, current = Workspace(tmp_path), Workspace(tmp_path)
        previous.evidence_directory.mkdir(parents=True)
        old = previous.evidence_path("old.txt")
        old.write_text("historical evidence", encoding="utf-8")
        current.evidence_directory.mkdir()
        new = current.evidence_path("new.txt")
        new.write_text("current evidence", encoding="utf-8")
        project = tmp_path / "project.txt"
        project.write_text("project source", encoding="utf-8")
        reads = []

        class Shell:
            async def read(self, path, **kwargs):
                reads.append(path)
                return Path(path).read_text(encoding="utf-8")

        current._shell = Shell()
        tools = ReadTools(current, "validator")
        assert await tools.read(str(new.relative_to(tmp_path))) == "current evidence"
        assert await tools.read("project.txt") == "project source"
        assert tools.list_files(str(current.evidence_directory)) == [str(new.relative_to(tmp_path))]
        assert ".inference_team" not in tools.list_files()
        for old_path in (str(old), str(old.relative_to(tmp_path))):
            with pytest.raises(ValueError, match="current-run"):
                await tools.read(old_path)
        for directory in (str(previous.evidence_directory), ".inference_team"):
            with pytest.raises(ValueError, match="current-run"):
                tools.list_files(directory)
        assert len(reads) == 2
        assert old.read_text(encoding="utf-8") == "historical evidence"
    asyncio.run(scenario())


def test_directory_alias_does_not_expose_old_evidence(tmp_path):
    previous, current = Workspace(tmp_path), Workspace(tmp_path)
    previous.evidence_directory.mkdir(parents=True)
    old = previous.evidence_path("old.txt")
    old.write_text("old", encoding="utf-8")
    current.evidence_directory.mkdir()
    directory_link(tmp_path / "alias", previous.evidence_directory)
    tools = ReadTools(current, "model")
    with pytest.raises(ValueError, match="current-run"):
        current.path("alias/old.txt", evidence_read=True)
    with pytest.raises(ValueError, match="current-run"):
        tools.list_files("alias")
    with pytest.raises(ValueError, match="not an editable artifact"):
        current.path("alias/old.txt")
    assert old.read_text(encoding="utf-8") == "old"


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan")])
def test_command_limit_must_be_finite_and_positive(tmp_path, timeout):
    with pytest.raises(ValueError):
        Workspace(tmp_path, command_timeout=timeout)


def test_recording_lock_timeout_and_independent_evidence(tmp_path):
    async def scenario():
        workspace = Workspace(tmp_path, command_timeout=1)
        workspace.evidence_directory.mkdir(parents=True)
        entered, release = asyncio.Event(), asyncio.Event()
        calls = []

        class Shell:
            async def run(self, command, **kwargs):
                calls.append((command, kwargs))
                if command == "first":
                    entered.set()
                    await release.wait()
                return SimpleNamespace(stdout="output", stderr="", returncode=0, timed_out=False)

        workspace._shell = Shell()
        first = asyncio.create_task(workspace.run("implementer", "first", stdin="script"))
        await entered.wait()
        second = asyncio.create_task(workspace.run("validator", "second"))
        await asyncio.sleep(0)
        assert [cmd for cmd, _ in calls] == ["first"]
        release.set()
        a, b = await asyncio.gather(first, second)
        assert len(workspace.commands) == 2
        assert all(kwargs["cwd"] == str(tmp_path) for _, kwargs in calls)
        assert (tmp_path / a.stdin_file).read_text() == "script"
        rows = [json.loads(line) for line in
                (workspace.evidence_directory / "commands.jsonl").read_text().splitlines()]
        assert [row["role"] for row in rows] == ["implementer", "validator"]
        workspace.verify_evidence([b.id], role="validator", after=1, success_required=True)
        for ids, after in (([a.id], 0), ([b.id], 2), (["invented"], 0)):
            with pytest.raises(ValueError):
                workspace.verify_evidence(ids, role="validator", after=after)
        with pytest.raises(ValueError, match="successful independent"):
            workspace.verify_evidence([], success_required=True)
        with pytest.raises(ValueError):
            await workspace.run("validator", "invalid", timeout=2)
        assert len(calls) == 2
    asyncio.run(scenario())


def test_cancelled_command_is_closed_recorded_and_propagated(tmp_path):
    async def scenario():
        workspace = Workspace(tmp_path)
        workspace.evidence_directory.mkdir(parents=True)
        started = asyncio.Event()

        class Shell:
            closed = False

            async def run(self, *args, **kwargs):
                started.set()
                await asyncio.Event().wait()

            async def close(self):
                self.closed = True

        shell = Shell()
        workspace._shell = shell
        running = asyncio.create_task(workspace.run("runtime", "waiting"))
        await started.wait()
        running.cancel()
        with pytest.raises(asyncio.CancelledError):
            await running
        assert shell.closed
        assert workspace.commands[0].cancelled
        assert workspace.commands[0].returncode is None
        assert not (workspace.evidence_directory / "result.json").exists()
    asyncio.run(scenario())


def test_command_failure_preserves_trigger_if_cleanup_also_fails(tmp_path):
    async def scenario():
        workspace = Workspace(tmp_path)
        workspace.evidence_directory.mkdir(parents=True)
        original = RuntimeError("command failed")

        class Shell:
            async def run(self, *args, **kwargs):
                raise original

            async def close(self):
                raise ValueError("secondary cleanup failure")

        workspace._shell = Shell()
        with pytest.raises(RuntimeError) as caught:
            await workspace.run("runtime", "broken")
        assert caught.value is original
        assert "secondary cleanup failure" in workspace.commands[0].stderr
        assert workspace.commands[0].returncode is None
    asyncio.run(scenario())


def test_cli_requires_explicit_model_workspace_and_bounds():
    parsed = parser().parse_args([
        "--requirements", "input.md", "--workspace", "work", "--model", "chosen-model",
        "--max-rounds", "2", "--timeout", "300",
    ])
    assert parsed.model == "chosen-model" and parsed.max_rounds == 2
    assert parsed.workspace == Path("work")
    with pytest.raises(SystemExit):
        parser().parse_args([])
