"""Real NOOA calls, with scripted model responses and no external connections."""

import asyncio
import os
import socket
import sys
from collections.abc import Iterator

import pytest

if sys.platform == "win32":
    pytest.skip(
        "The locked NOOA revision imports Unix fcntl; run integration in Linux/WSL.",
        allow_module_level=True,
    )

# Keep LiteLLM's import-time model metadata local, before importing NOOA strategies.
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"

from nooa import Agent, GenerationError, strategy
from nooa.config import PredictConfig
from nooa.strategies import PredictStrategy
from nooa.tracing import enable_tracing
from nooa.unifiedllm import FakeLLMClient
from pydantic import BaseModel, Field, ValidationError

from nooa_patterns import PatternKind, as_member
from conftest import ScriptedTeam


class ScoreCard(BaseModel):
    summary: str
    score: int = Field(strict=True, ge=0, le=10)


class ScoringAgent(Agent):
    @strategy(PredictStrategy(config=PredictConfig(max_retries=1)))
    async def score(self, task: str) -> ScoreCard:
        """Assess the supplied text and give a short summary and a score from 0 to 10."""
        ...


@pytest.fixture(scope="module", autouse=True)
def local_tracing() -> None:
    # Public configuration avoids the automatic localhost viewer probe/exporter.
    enable_tracing(exporters=[])


@pytest.fixture(autouse=True)
def no_external_connections(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Reject IP connections while retaining asyncio's local socketpair support."""
    attempted: list[object] = []
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def connect(sock: socket.socket, address: object) -> None:
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            attempted.append(address)
            raise AssertionError(f"Unexpected network connection: {address}")
        return original_connect(sock, address)

    def connect_ex(sock: socket.socket, address: object) -> int:
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            attempted.append(address)
            raise AssertionError(f"Unexpected network connection: {address}")
        return original_connect_ex(sock, address)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    yield
    assert attempted == []


async def _invoke(
    agent: ScoringAgent, task: str, context: list[str], *, adapted: bool
) -> ScoreCard:
    if not adapted:
        return await agent.score(task)

    async def score_bridge(value: str, local: dict) -> ScoreCard:
        local["materials"].append("score")
        return await agent.score(value)

    team = ScriptedTeam({"score": as_member(score_bridge)}, PatternKind.SEQUENTIAL)
    return await team.execute(task, context)


def test_nooa_native_call_chain_survives_team_adaptation() -> None:
    task = "The proposal includes a focused regression test."

    async def scenario() -> None:
        results: list[ScoreCard] = []
        for adapted in (False, True):
            async with FakeLLMClient.simple_message(
                '{"summary": "Testable proposal", "score": 8}', strict_exhaustion=True
            ) as client:
                agent = ScoringAgent(llm=client)
                prompt_context = agent.context
                context: list[str] = []
                result = await _invoke(agent, task, context, adapted=adapted)

                assert result == ScoreCard(summary="Testable proposal", score=8)
                assert client.call_count == 1
                assert client.remaining_responses == 0
                assert client.calls[0].output_model is ScoreCard
                assert task in str(client.calls[0].messages)
                assert agent.events.query(type="Task")
                assert len(agent.events.query(type="LLMResponse")) == 1
                assert agent.context is prompt_context
                assert context == (["score"] if adapted else [])
                results.append(result)

        assert results[0] == results[1]

    asyncio.run(scenario())


def test_adapter_preserves_native_argument_validation() -> None:
    async def scenario() -> None:
        messages: list[str] = []
        for adapted in (False, True):
            async with FakeLLMClient.simple_message(
                '{"summary": "Unused", "score": 8}', strict_exhaustion=True
            ) as client:
                agent = ScoringAgent(llm=client)
                context: list[str] = []
                with pytest.raises(TypeError) as caught:
                    # Deliberately violate the concrete NOOA method's input type.
                    await _invoke(agent, 42, context, adapted=adapted)  # type: ignore[arg-type]

                assert "task" in str(caught.value)
                assert "expected str, got int" in str(caught.value)
                assert client.call_count == 0
                assert client.remaining_responses == 1
                assert context == (["score"] if adapted else [])
                messages.append(str(caught.value))

        assert messages[0] == messages[1]

    asyncio.run(scenario())


def test_adapter_preserves_native_output_validation() -> None:
    async def scenario() -> None:
        validation_errors: list[list[dict[str, object]]] = []
        for adapted in (False, True):
            async with FakeLLMClient.simple_message(
                '{"summary": "Invalid score", "score": "not-an-integer"}',
                strict_exhaustion=True,
            ) as client:
                agent = ScoringAgent(llm=client)
                context: list[str] = []
                with pytest.raises(GenerationError) as caught:
                    await _invoke(agent, "Assess this proposal.", context, adapted=adapted)

                cause = caught.value.__cause__
                assert isinstance(cause, ValidationError)
                errors = cause.errors(include_url=False)
                assert errors[0]["loc"] == ("score",)
                assert errors[0]["type"] == "int_type"
                assert client.call_count == 1  # Native retry limit is one attempt.
                assert client.remaining_responses == 0
                assert client.calls[0].output_model is ScoreCard
                assert len(agent.events.query(type="LLMResponse")) == 1
                assert context == (["score"] if adapted else [])
                validation_errors.append(errors)

        assert validation_errors[0] == validation_errors[1]

    asyncio.run(scenario())
