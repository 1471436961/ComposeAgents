"""Native CodeAct allocation: real NOOA, scripted models, live material references."""

import asyncio
import os
import socket
import sys
from dataclasses import dataclass

import pytest

if sys.platform == "win32":
    pytest.skip("The locked NOOA imports fcntl; native allocation runs on Linux/WSL.", allow_module_level=True)

os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"

from nooa import Agent, strategy
from nooa.config import PredictConfig
from nooa.strategies import PredictStrategy
from nooa.tracing import enable_tracing
from nooa.unifiedllm import FakeLLMClient
from pydantic import BaseModel

from nooa_patterns import AllocationError, PatternKind, Team, as_member


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    enable_tracing(exporters=[])
    original = socket.socket.connect
    original_ex = socket.socket.connect_ex
    attempted = []
    def connect(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            attempted.append(address)
            raise AssertionError(f"Unexpected IP connection: {address}")
        return original(sock, address)
    def connect_ex(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            attempted.append(address)
            raise AssertionError(f"Unexpected IP connection: {address}")
        return original_ex(sock, address)
    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    yield
    assert attempted == []


@dataclass
class Material:
    value: str


class Worker(Agent):
    """NATIVE_MEMBER_ROLE: evaluate only evidence relevant to latency."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.received = []

    async def execute(self, task: str, context: dict) -> object:
        """NATIVE_MEMBER_METHOD: return the selected evidence as the business result."""
        self.received.append((task, context))
        return context["materials"]


class LeafResult(BaseModel):
    summary: str


class EvidenceAgent(Agent):
    """Summarize the selected evidence without depending on other agents' history."""

    @strategy(PredictStrategy(config=PredictConfig(max_retries=1)))
    async def execute(self, task: str, context: dict) -> LeafResult:
        """Follow the local task and use only its supplied context materials."""
        ...


class EvidenceTeam(Team):
    """NESTED_REVIEW_CAPABILITY: summarize latency evidence as a LeafResult."""


def client_for(code):
    return FakeLLMClient.with_tool_call("execute_python", {"code": code}, strict_exhaustion=True)


def test_native_allocate_describes_members_and_returns_live_materials_without_execution():
    async def scenario():
        async with client_for(
            'return_result(result={name: {"task": "analyze selected evidence", "context": context["selected"]} '
            'for name in member_descriptions})'
        ) as client:
            worker = Worker(llm=client)
            material = Material("selected evidence")
            root = {"selected": material, "irrelevant": Material("unrelated")}
            team = Team({"worker": worker, "bound": as_member(worker.execute)}, PatternKind.SEQUENTIAL, llm=client)
            result = await team.allocate("review latency", root)
            assert result["worker"]["context"] is material
            assert result["bound"]["context"] is material
            assert worker.received == [] and client.call_count == 1 and client.remaining_responses == 0
            messages = str(client.calls[0].messages)
            assert "NATIVE_MEMBER_ROLE" in messages and "NATIVE_MEMBER_METHOD" in messages
            assert "review latency" in messages and "sequential" in messages
            assert root["selected"] is material and set(root) == {"selected", "irrelevant"}
    asyncio.run(scenario())


def test_native_execute_uses_allocated_inputs_and_adapter_business_docs():
    async def scenario():
        received = []
        async def risk(task: str, context: dict) -> object:
            """BOUND_CAPABILITY: assess security constraints and return selected material."""
            received.append((task, context))
            return context["materials"]
        async with client_for(
            'return_result(result={"risk": {"task": "risk-only instructions", "context": context["risk"]}})'
        ) as client:
            selected = Material("risk evidence")
            team = Team({"risk": as_member(risk)}, PatternKind.PARALLEL, llm=client)
            result = await team.execute("overall goal", {"risk": selected, "noise": "ignore"})
            assert result == {"risk": selected} and result["risk"] is selected
            assert received[0][0] == "risk-only instructions"
            assert received[0][1] == {"materials": selected, "upstream": {}, "feedback": {}}
            assert client.call_count == 1 and client.remaining_responses == 0
            assert "BOUND_CAPABILITY" in str(client.calls[0].messages)
    asyncio.run(scenario())


def test_native_invalid_allocation_is_classified_before_any_member_runs():
    async def scenario():
        async with client_for('return_result(result={"wrong": {"task": "x", "context": None}})') as client:
            worker = Worker(llm=client)
            team = Team({"worker": worker}, PatternKind.SEQUENTIAL, llm=client)
            with pytest.raises(AllocationError) as caught:
                await team.execute("goal", {})
            assert caught.value.team is team and isinstance(caught.value.__cause__, ValueError)
            assert worker.received == [] and client.call_count == 1
    asyncio.run(scenario())


def test_actual_leaf_model_request_contains_selected_material_and_excludes_root_noise():
    async def scenario():
        async with client_for(
            'return_result(result={"evidence": {"task": "Summarize latency evidence", "context": context["selected"]}})'
        ) as allocator, FakeLLMClient.simple_message(
            '{"summary": "Latency improved"}', strict_exhaustion=True
        ) as leaf_client:
            leaf = EvidenceAgent(llm=leaf_client)
            original_prompt_context = leaf.context
            team = Team({"evidence": leaf}, PatternKind.SEQUENTIAL, llm=allocator)
            result = await team.execute("global review", {
                "selected": {"evidence": "SELECTED_LATENCY_EVIDENCE_120_TO_90"},
                "unrelated": "UNRELATED_ROOT_NOISE_93812",
            })
            assert result == LeafResult(summary="Latency improved")
            messages = str(leaf_client.calls[0].messages)
            assert "SELECTED_LATENCY_EVIDENCE_120_TO_90" in messages
            assert "UNRELATED_ROOT_NOISE_93812" not in messages
            assert "Summarize latency evidence" in messages
            assert allocator.call_count == leaf_client.call_count == 1
            assert allocator.remaining_responses == leaf_client.remaining_responses == 0
            assert leaf.context is original_prompt_context
            assert len(leaf.events.query(type="LLMResponse")) == 1
    asyncio.run(scenario())


def test_native_nested_allocation_passes_only_selected_material_to_child_and_leaf():
    async def scenario():
        async with client_for(
            'assert set(member_descriptions) == {"review"}\n'
            'assert "NESTED_REVIEW_CAPABILITY" in member_descriptions["review"]\n'
            'return_result(result={"review": {"task": "Review selected latency evidence", '
            '"context": {"evidence": context["selected"]}}})'
        ) as parent_client, client_for(
            'assert task == "Review selected latency evidence"\n'
            'assert set(member_descriptions) == {"evidence"}\n'
            'assert set(context) == {"materials", "upstream", "feedback"}\n'
            'assert set(context["materials"]) == {"evidence"}\n'
            'assert context["upstream"] == context["feedback"] == {}\n'
            'return_result(result={"evidence": {"task": "Summarize selected latency", '
            '"context": context["materials"]["evidence"]}})'
        ) as child_client, FakeLLMClient.simple_message(
            '{"summary": "Selected nested evidence"}', strict_exhaustion=True
        ) as leaf_client:
            selected = Material("NESTED_SELECTED_LATENCY_EVIDENCE")
            root = {"selected": selected, "unrelated": "NESTED_UNRELATED_ROOT_NOISE"}
            received = []
            leaf = EvidenceAgent(llm=leaf_client)

            async def evidence(task: str, context: dict) -> LeafResult:
                """Summarize the selected latency material using the evidence Agent."""
                received.append((task, context))
                return await leaf.execute(task, context)

            child = EvidenceTeam(
                {"evidence": as_member(evidence)}, PatternKind.SEQUENTIAL, llm=child_client
            )
            parent = Team({"review": child}, PatternKind.SEQUENTIAL, llm=parent_client)
            result = await parent.execute("Review all supplied information", root)

            assert result == LeafResult(summary="Selected nested evidence")
            assert len(received) == 1
            assert received[0][0] == "Summarize selected latency"
            assert received[0][1] == {"materials": selected, "upstream": {}, "feedback": {}}
            assert received[0][1]["materials"] is selected
            parent_messages = str(parent_client.calls[0].messages)
            child_messages = str(child_client.calls[0].messages)
            leaf_messages = str(leaf_client.calls[0].messages)
            assert "NESTED_REVIEW_CAPABILITY" in parent_messages
            assert "NESTED_UNRELATED_ROOT_NOISE" in parent_messages
            for messages in (child_messages, leaf_messages):
                assert "NESTED_SELECTED_LATENCY_EVIDENCE" in messages
                assert "NESTED_UNRELATED_ROOT_NOISE" not in messages
            assert root == {"selected": selected, "unrelated": "NESTED_UNRELATED_ROOT_NOISE"}
            for client in (parent_client, child_client, leaf_client):
                assert client.call_count == 1 and client.remaining_responses == 0
    asyncio.run(scenario())


@pytest.mark.parametrize("pattern", [PatternKind.ROUTER, PatternKind.LOOP], ids=["router", "loop"])
def test_native_allocation_receives_mode_contract_and_is_not_repeated_by_execution(pattern):
    async def scenario():
        received = []
        decisions = []
        result = object()
        root = {"selected": Material("mode-specific evidence")}

        async def selected(task: str, context: dict) -> object:
            """Return a result from the locally assigned evidence."""
            received.append((task, context))
            return result

        async def unused(task: str, context: dict) -> object:
            raise AssertionError("Router must not execute an unselected member")

        def selector(task, context):
            """NATIVE_ROUTER_RULE: select the evidence reviewer."""
            decisions.append((task, context))
            return "selected"

        def until(value, context):
            """NATIVE_LOOP_RULE: complete exactly two full review rounds."""
            decisions.append((value, context))
            return len(decisions) == 2

        if pattern is PatternKind.ROUTER:
            code = (
                'assert pattern_description.startswith("router:")\n'
                'assert "NATIVE_ROUTER_RULE" in pattern_description\n'
                'assert set(member_descriptions) == {"selected", "unused"}\n'
            )
            members = {"selected": as_member(selected), "unused": as_member(unused)}
            config = {"selector": selector}
        else:
            code = (
                'assert pattern_description.startswith("loop:")\n'
                'assert "NATIVE_LOOP_RULE" in pattern_description\n'
                'assert "max_iterations=2" in pattern_description\n'
                'assert set(member_descriptions) == {"selected"}\n'
            )
            members = {"selected": as_member(selected)}
            config = {"until": until, "max_iterations": 2}
        code += (
            'return_result(result={name: {"task": "Review local evidence", '
            '"context": context["selected"]} for name in member_descriptions})'
        )
        async with client_for(code) as client:
            team = Team(members, pattern, llm=client, **config)
            assert await team.execute("Overall review", root) is result
            assert client.call_count == 1 and client.remaining_responses == 0
            expected_rounds = 1 if pattern is PatternKind.ROUTER else 2
            assert len(received) == len(decisions) == expected_rounds
            for task, context in received:
                assert task == "Review local evidence"
                assert context["materials"] is root["selected"]
                assert context["upstream"] == {}
            assert received[0][1]["feedback"] == {}
            assert all(context is root for _, context in decisions)
            if pattern is PatternKind.ROUTER:
                assert decisions[0][0] == "Overall review"
            else:
                assert received[1][1]["feedback"]["result"] is result
                assert all(value is result for value, _ in decisions)
            assert set(root) == {"selected"}
    asyncio.run(scenario())


def test_native_model_wait_cancellation_propagates_without_allocation_error():
    async def scenario():
        started, cancelled = asyncio.Event(), asyncio.Event()
        class WaitingClient(FakeLLMClient):
            async def acall(self, *args, **kwargs):
                started.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    cancelled.set()
        async with WaitingClient(scripted_responses=[]) as client:
            worker = Worker(llm=client)
            team = Team({"worker": worker}, PatternKind.SEQUENTIAL, llm=client)
            async with asyncio.timeout(10):
                running = asyncio.create_task(team.execute("goal", {}))
                await started.wait()
                running.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await running
            assert cancelled.is_set() and worker.received == []
    asyncio.run(scenario())
