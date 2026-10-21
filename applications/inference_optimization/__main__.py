"""Explicit opt-in runner. --help never imports NOOA or contacts a model."""

import argparse
import asyncio
import json
import sys
from pathlib import Path


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Run the inference optimization R&D team in Linux/WSL")
    result.add_argument("--requirements", type=Path, required=True, help="UTF-8 business requirements file")
    result.add_argument("--workspace", type=Path, required=True, help="Existing disposable project workspace")
    result.add_argument("--model", required=True, help="NOOA UnifiedLLM/LiteLLM model; credentials via environment")
    result.add_argument("--context", type=Path, help="Optional JSON environment/constraints; no secrets")
    result.add_argument("--max-rounds", type=int, required=True)
    result.add_argument("--timeout", type=float, required=True, help="Whole run deadline in seconds")
    result.add_argument("--command-timeout", type=float, default=120)
    return result


async def run(args) -> int:
    import math

    if not math.isfinite(args.timeout) or args.timeout <= 0:
        raise ValueError("timeout must be finite and positive")
    if args.max_rounds <= 0:
        raise ValueError("max-rounds must be positive")
    task = args.requirements.read_text(encoding="utf-8")
    context = {} if args.context is None else json.loads(args.context.read_text(encoding="utf-8"))
    if not isinstance(context, dict):
        raise ValueError("context JSON must be an object")
    from nooa.tracing import enable_tracing
    from nooa.unifiedllm import UnifiedLLM

    from .team import build_team
    from .workspace import Workspace

    enable_tracing(exporters=[])
    async with UnifiedLLM(model=args.model) as client, Workspace(
        args.workspace, command_timeout=args.command_timeout,
    ) as workspace:
        team = build_team(workspace, llm=client, max_rounds=args.max_rounds)
        try:
            async with asyncio.timeout(args.timeout):
                outcome = await team.execute(task, context)
        except BaseException as exc:
            workspace.evidence_path("failure.json").write_text(
                json.dumps({"type": type(exc).__name__, "message": str(exc)}, ensure_ascii=False),
                encoding="utf-8",
            )
            raise
        print(outcome.model_dump_json(indent=2))
        return 0 if outcome.status == "accepted" else 2


def main() -> int:
    args = parser().parse_args()
    if sys.platform == "win32":
        raise SystemExit("The locked NOOA requires Linux/WSL (upstream fcntl).")
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
