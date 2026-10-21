"""Real NOOA allocation + five roles + real files/commands; scripted models only."""

import asyncio
from contextlib import AsyncExitStack
import json
import os
import shlex
import socket
import sys

import pytest

if sys.platform == "win32":
    pytest.skip("The locked NOOA requires Linux/WSL (fcntl).", allow_module_level=True)

os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"

from nooa import Agent
from nooa.tracing import enable_tracing
from nooa.unifiedllm import FakeLLMClient, LLMResponse, ToolCall

from applications.inference_optimization.models import (
    ChangeReport, ExperimentPlan, Findings, ImplementationPacket, PlanningPacket,
)
from applications.inference_optimization.agents import Validator
from applications.inference_optimization.team import build_team
from applications.inference_optimization.workspace import EditTools, ReadTools, Workspace
from nooa_patterns import PatternKind, Team


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    enable_tracing(exporters=[])
    original = socket.socket.connect
    original_ex = socket.socket.connect_ex
    attempted = []

    def connect(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            attempted.append(address)
            raise AssertionError(f"unexpected network: {address}")
        return original(sock, address)

    def connect_ex(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            attempted.append(address)
            raise AssertionError(f"unexpected network: {address}")
        return original_ex(sock, address)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    yield
    assert attempted == []


def response(code):
    return LLMResponse(content="", tool_calls=[ToolCall(
        id="scripted", name="execute_python", arguments=json.dumps({"code": code}),
    )], finish_reason="tool_calls")


def client(codes):
    return FakeLLMClient([response(code) for code in codes], strict_exhaustion=True)


def allocation_scripts(rounds):
    root = '''
assert set(member_descriptions) == {"investigate", "plan", "implement", "verify"}
assert pattern_description.startswith("loop:")
return_result(result={name: {"task": "Satisfy the bounded fixture requirement", "context": context["project"]} for name in member_descriptions})
'''
    scripts = [root]
    for n in range(rounds):
        scripts.append(f'''
assert set(member_descriptions) == {{"model", "runtime"}}
assert pattern_description.startswith("parallel:")
previous = context["previous_iteration"]
assert (previous is None) == {n == 0!r}
if previous is not None:
    assert previous.review.verdict == "revise"
return_result(result={{name: {{"task": "Inspect actual fixture", "context": context["selected_materials"]}} for name in member_descriptions}})
''')
    return scripts


def role_scripts(rounds, terminal):
    research = '''
source = await self.tools.read("fixture.py")
assert "value" in source
return_result(result={"observations": ["Inspected actual source"], "evidence": ["fixture.py"], "hypotheses": [], "unknowns": []})
'''
    planning = []
    implementing = []
    verifying = []
    python_command = shlex.quote(sys.executable) + " -B -"
    for index in range(rounds):
        planning.append(f'''
assert set(findings) == {{"model", "runtime"}}
assert (previous is None) == {index == 0!r}
if previous is not None:
    assert "try next value" in previous.review.feedback
return_result(result={{"objective": "Change and independently check fixture", "changes": ["Update fixture value"], "checks": ["value must equal 3"], "risks": []}})
''')
        implementing.append(f'''
assert planning.plan.checks == ["value must equal 3"]
await self.tools.write("fixture.py", "value = {index + 2}\\n")
result = await self.tools.run({python_command!r}, stdin="import fixture; print(fixture.value)")
assert result.returncode == 0
return_result(result={{"summary": "Updated fixture", "artifacts": ["fixture.py"], "command_ids": [result.id], "limitations": []}})
''')
        verdict = terminal if index == rounds - 1 else "revise"
        verifying.append(f'''
assert implementation.planning.findings["model"].evidence == ["fixture.py"]
assert implementation.changes.artifacts == ["fixture.py"]
result = await self.tools.run({python_command!r}, stdin="import fixture; assert fixture.value == 3; print('independent check passed')")
assert result.returncode == {0 if index == 1 else 1}
return_result(result={{"verdict": {verdict!r}, "summary": "Independent fixture review", "command_ids": [result.id], "metrics": {{}}, "feedback": ["try next value"]}})
''')
    return {"model": [research] * rounds, "runtime": [research] * rounds,
            "planner": planning, "implementer": implementing, "validator": verifying}


@pytest.mark.parametrize("rounds,terminal,status", [
    (2, "accepted", "accepted"), (1, "blocked", "blocked"), (1, "revise", "exhausted"),
])
def test_native_application_pipeline_feedback_and_terminal_states(tmp_path, rounds, terminal, status):
    async def scenario():
        (tmp_path / "fixture.py").write_text("value = 1\n", encoding="utf-8")
        async with AsyncExitStack() as stack:
            allocator = await stack.enter_async_context(client(allocation_scripts(rounds)))
            models = {name: await stack.enter_async_context(client(codes))
                      for name, codes in role_scripts(rounds, terminal).items()}
            workspace = await stack.enter_async_context(Workspace(tmp_path))
            team = build_team(workspace, llm=allocator, max_rounds=rounds, role_llms=models)
            assert allocator.call_count == 0
            assert isinstance(team, Team) and team.pattern is PatternKind.LOOP
            investigate = team.members["investigate"]
            assert isinstance(investigate, Team) and investigate.pattern is PatternKind.PARALLEL
            assert all(isinstance(role, Agent) for role in investigate.members.values())
            context = {"project": {"entry": "fixture.py"}, "irrelevant": "UNRELATED_ROOT_SECRET"}
            async with asyncio.timeout(90):
                outcome = await team.execute("Validate the independent fixture requirement", context)
            assert outcome.status == status and outcome.rounds == rounds
            assert context == {"project": {"entry": "fixture.py"}, "irrelevant": "UNRELATED_ROOT_SECRET"}
            assert len(workspace.commands) == rounds * 2
            assert [record.role for record in workspace.commands] == ["implementer", "validator"] * rounds
            assert (workspace.evidence_directory / "result.json").is_file()
            assert outcome.last.implementation.planning.findings["runtime"].evidence == ["fixture.py"]
            for role_client in models.values():
                assert role_client.call_count == rounds and role_client.remaining_responses == 0
                assert "UNRELATED_ROOT_SECRET" not in str(role_client.calls[0].messages)
            assert "Read project files or current-run evidence" in str(models["model"].calls[0].messages)
            assert "Write a UTF-8 artifact" in str(models["implementer"].calls[0].messages)
            assert allocator.call_count == 1 + rounds and allocator.remaining_responses == 0
            assert "UNRELATED_ROOT_SECRET" in str(allocator.calls[0].messages)
    asyncio.run(scenario())


def test_validator_rejects_model_claim_without_independent_command(tmp_path):
    async def scenario():
        report = '''return_result(result={"verdict": "accepted", "summary": "claim only", "command_ids": [], "metrics": {}, "feedback": []})'''
        async with client([report]) as llm, Workspace(tmp_path) as workspace:
            validator = Validator(workspace, llm=llm)
            packet = ImplementationPacket(
                planning=PlanningPacket(findings={}, plan=ExperimentPlan(
                    objective="test", changes=[], checks=["test"], risks=[])),
                changes=ChangeReport(summary="none", artifacts=[], command_ids=[], limitations=[]),
            )
            with pytest.raises(ValueError, match="successful independent"):
                await validator.execute("verify", {"upstream": {"implement": packet},
                                                    "materials": {}, "feedback": {}})
            assert workspace.commands == []
    asyncio.run(scenario())


def test_native_tools_real_timeout_edit_boundary_and_command_records(tmp_path):
    async def scenario():
        async with Workspace(tmp_path, command_timeout=1) as workspace:
            edit = EditTools(workspace, "implementer")
            digest = await edit.write("nested/code.py", "print('hello')\n")
            assert len(digest) == 64 and "hello" in await edit.read("nested/code.py")
            with pytest.raises(ValueError):
                await edit.write("../elsewhere.py", "bad")
            with pytest.raises(ValueError):
                await edit.write(".inference_team/forged.txt", "bad")
            result = await edit.run("sleep 2", timeout=0.1)
            assert result.timed_out and result.returncode != 0
            validator = ReadTools(workspace, "validator")
            assert "" == (await validator.read(result.stdout_file)).strip()
            assert json.loads((workspace.evidence_directory / "commands.jsonl").read_text())["timed_out"]
    asyncio.run(scenario())


def test_application_cancellation_during_native_allocation_is_not_exhaustion(tmp_path):
    async def scenario():
        started, cancelled = asyncio.Event(), asyncio.Event()

        class WaitingClient(FakeLLMClient):
            async def acall(self, *args, **kwargs):
                started.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    cancelled.set()

        async with WaitingClient([]) as llm, Workspace(tmp_path) as workspace:
            team = build_team(workspace, llm=llm, max_rounds=2)
            running = asyncio.create_task(team.execute("investigate inference", {}))
            await started.wait()
            running.cancel()
            with pytest.raises(asyncio.CancelledError):
                await running
            assert cancelled.is_set()
            assert not (workspace.evidence_directory / "result.json").exists()
    asyncio.run(scenario())


def test_native_command_cancellation_cleans_foreground_process(tmp_path):
    async def scenario():
        python_command = shlex.quote(sys.executable) + " -B -"
        script = (
            "import os, time\nfrom pathlib import Path\n"
            "Path('child.pid').write_text(str(os.getpid()))\ntime.sleep(30)\n"
            "Path('unexpected.txt').write_text('should never complete')\n"
        )
        async with Workspace(tmp_path) as workspace:
            running = asyncio.create_task(workspace.run("runtime", python_command, stdin=script))
            async with asyncio.timeout(10):
                while not (tmp_path / "child.pid").exists():
                    await asyncio.sleep(0.01)
                pid = int((tmp_path / "child.pid").read_text())
                running.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await running
            # A terminated grandchild can briefly remain a zombie awaiting init;
            # either absent or zombie is no longer an executing GPU/CPU job.
            status = tmp_path.__class__(f"/proc/{pid}/status")
            if status.exists():
                assert "State:\tZ" in status.read_text()
            assert not (tmp_path / "unexpected.txt").exists()
            assert workspace.commands[-1].cancelled
    asyncio.run(scenario())


@pytest.mark.parametrize("name", ["commands.jsonl", "result.json", "failure.json"])
def test_native_evidence_file_redirect_is_rejected(tmp_path, name):
    async def scenario():
        async with Workspace(tmp_path) as workspace:
            target = tmp_path / "existing.txt"
            target.write_text("preserve", encoding="utf-8")
            (workspace.evidence_directory / name).symlink_to(target)
            with pytest.raises(ValueError, match="must not redirect"):
                workspace.evidence_path(name).write_text("overwrite")
            if name == "commands.jsonl":
                with pytest.raises(ValueError, match="must not redirect"):
                    await workspace.run("runtime", "touch command-must-not-start")
                assert not (tmp_path / "command-must-not-start").exists()
                assert workspace.commands == []
            assert target.read_text(encoding="utf-8") == "preserve"
    asyncio.run(scenario())


def test_native_reused_workspace_retains_but_does_not_read_old_evidence(tmp_path):
    async def scenario():
        async with Workspace(tmp_path) as first:
            old = await first.run("runtime", "printf historical-evidence")
            old_file = tmp_path / old.stdout_file
        old_bytes = old_file.read_bytes()
        async with Workspace(tmp_path) as current:
            tools = ReadTools(current, "validator")
            with pytest.raises(ValueError, match="current-run"):
                await tools.read(old.stdout_file)
            with pytest.raises(ValueError, match="current-run"):
                tools.list_files(str(first.evidence_directory))
            new = await tools.run("printf current-evidence")
            assert "current-evidence" in await tools.read(new.stdout_file)
            assert old_file.read_bytes() == old_bytes
            assert first.evidence_directory.is_dir()
    asyncio.run(scenario())
