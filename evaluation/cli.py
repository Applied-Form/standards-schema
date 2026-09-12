#!/usr/bin/env python3
"""Run or inspect the public Standards comparative evaluation."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile

from .harness import (CONDITIONS, EVALUATION_ROOT, EvaluationError, UIRenderer,
                      run_experiment, summarize_designer_review, write_json)
from .openrouter import (OpenRouterError, OpenRouterProvider, credential_status,
                         discover_free_models, validate_frozen_models)


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _default_output(label: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return EVALUATION_ROOT / "runs" / f"{stamp}-{label}"


def _smoke_output(requested: Path | None) -> Path:
    if requested is None:
        return Path(tempfile.mkdtemp(prefix="standards-evaluation-smoke-"))
    output = requested.resolve()
    try:
        output.relative_to(EVALUATION_ROOT.parents[0])
    except ValueError:
        return output
    raise EvaluationError("smoke output must be outside the repository")


def _select_free(snapshot, limit: int) -> list[str]:
    candidates = [model for model in snapshot["models"]
                  if model.get("freeVariant") and model["id"] != "openrouter/free"]
    if limit < 1:
        raise EvaluationError("free model limit must be positive")
    return [model["id"] for model in candidates[:limit]]


def _print(value) -> None:
    print(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2))


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(description=__doc__)
    commands = top.add_subparsers(dest="command", required=True)

    commands.add_parser("credentials", help="report availability and source without printing the key")

    models = commands.add_parser("models", help="discover current exact zero-price text models")
    models.add_argument("--out", type=Path)
    models.add_argument("--ids-only", action="store_true")

    run = commands.add_parser("run", help="run a precommitted comparison matrix")
    run.add_argument("--models", required=True, help="comma-separated OpenRouter model IDs")
    run.add_argument("--mode", choices=("exploratory", "confirmatory"), default="exploratory",
                     help="confirmatory execution remains gated until its analysis plan is implemented")
    run.add_argument("--conditions", default=",".join(CONDITIONS),
                     help="comma-separated condition IDs")
    run.add_argument("--split", choices=("dev", "held-out", "all"), default="dev")
    run.add_argument("--cases", help="optional comma-separated case IDs")
    run.add_argument("--repetitions", type=int, default=3)
    run.add_argument("--max-repairs", type=int, default=2)
    run.add_argument("--max-tokens", type=int, default=6000)
    run.add_argument("--temperature", type=float, default=0)
    run.add_argument("--reasoning", choices=("off", "default"), default="off",
                     help="freeze reasoning off or retain the provider/model default")
    run.add_argument("--ui-root", type=Path, default=EVALUATION_ROOT.parents[1] / "standards-ui")
    run.add_argument("--out", type=Path)

    smoke = commands.add_parser("smoke", help="run a non-inferential free-model smoke comparison")
    smoke.add_argument("--model-limit", type=int, default=2)
    smoke.add_argument("--ui-root", type=Path, default=EVALUATION_ROOT.parents[1] / "standards-ui")
    smoke.add_argument("--out", type=Path)
    smoke.add_argument("--case", default="dev-archive-digitisation")

    review = commands.add_parser("review-summary", help="unblind a completed designer review")
    review.add_argument("--run", type=Path, required=True)
    return top


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    if args.command == "credentials":
        _print(credential_status())
        return 0
    if args.command == "models":
        snapshot = discover_free_models()
        if args.out:
            write_json(args.out, snapshot)
        _print([model["id"] for model in snapshot["models"]] if args.ids_only else snapshot)
        return 0
    if args.command == "review-summary":
        _print(summarize_designer_review(args.run.resolve()))
        return 0
    if args.command == "run" and args.mode == "confirmatory":
        raise EvaluationError(
            "confirmatory execution is disabled: first implement and freeze the paired estimator, "
            "interval method, non-inferiority margin, multi-reviewer agreement, and held-out declaration"
        )

    snapshot = discover_free_models()
    renderer = UIRenderer(args.ui_root)
    if args.command == "smoke":
        models = _select_free(snapshot, args.model_limit)
        if not models:
            raise EvaluationError("OpenRouter returned no exact zero-price text model routes")
        validate_frozen_models(snapshot, models)
        provider = OpenRouterProvider(snapshot, reasoning_effort="none")
        output = _smoke_output(args.out).resolve()
        result = run_experiment(output=output, provider=provider, models=models,
            renderer=renderer, conditions=["raw_brief", "selected_context", "deterministic_component"],
            split="dev", case_ids={args.case}, repetitions=1, max_repairs=0,
            max_tokens=6000, temperature=0, model_snapshot=snapshot,
            label="smoke-non-inferential", study_mode="smoke")
    else:
        models = _csv(args.models)
        if not models:
            raise EvaluationError("at least one model is required")
        validate_frozen_models(snapshot, models)
        provider = OpenRouterProvider(
            snapshot, reasoning_effort="none" if args.reasoning == "off" else None
        )
        conditions = _csv(args.conditions)
        unknown = sorted(set(conditions) - set(CONDITIONS))
        if unknown:
            raise EvaluationError("unknown conditions: " + ", ".join(unknown))
        output = (args.out or _default_output("comparison")).resolve()
        result = run_experiment(output=output, provider=provider, models=models,
            renderer=renderer, conditions=conditions, split=args.split,
            case_ids=set(_csv(args.cases)) if args.cases else None,
            repetitions=args.repetitions, max_repairs=args.max_repairs,
            max_tokens=args.max_tokens, temperature=args.temperature,
            model_snapshot=snapshot, label="exploratory-comparative-evaluation",
            study_mode="exploratory")
    result["outputDirectory"] = str(output)
    _print(result)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EvaluationError, OpenRouterError, OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
