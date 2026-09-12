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
                      current_confirmatory_identity, load_fixtures, run_experiment,
                      summarize_designer_review, write_json)
from .openrouter import (OpenRouterError, OpenRouterProvider, credential_status,
                         discover_free_models, validate_frozen_models)
from .study import (SpendLedger, StudyError, analyze_confirmatory, confirmatory_blockers,
                    create_publication_bundle, digest, plan_paired_power,
                    read_json as read_study_json, seal_review_set,
                    validate_declaration, validate_freeze_receipt,
                    validate_spend_ledger, verify_publication_safe)


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
    run.add_argument("--models", help="comma-separated OpenRouter model IDs (exploratory only)")
    run.add_argument("--mode", choices=("exploratory", "confirmatory"), default="exploratory",
                     help="confirmatory execution is fail-closed on external freeze, routes, reviewers, and budget")
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
    run.add_argument("--declaration", type=Path,
                     help="required frozen protocol 0.5 declaration for confirmatory execution")
    run.add_argument("--freeze-receipt", type=Path,
                     help="required externally timestamped receipt for confirmatory execution")
    run.add_argument("--snapshot", type=Path,
                     help="use this already-frozen catalogue instead of live discovery")
    run.add_argument("--spend-ledger", type=Path,
                     help="persistent cumulative GBP ledger; required for confirmatory execution")
    run.add_argument("--worst-case-call-cost-gbp", type=float, default=0,
                     help="development call reservation; confirmatory value comes from the declaration")
    run.add_argument("--usd-to-gbp-rate", type=float, default=1,
                     help="frozen conversion used to settle provider-reported USD cost")
    run.add_argument("--resume", action="store_true",
                     help="resume the exact frozen matrix in --out without retrying an in-flight cell")
    run.add_argument("--ui-root", type=Path, default=EVALUATION_ROOT.parents[1] / "standards-ui")
    run.add_argument("--out", type=Path)

    smoke = commands.add_parser("smoke", help="run a non-inferential free-model smoke comparison")
    smoke.add_argument("--model-limit", type=int, default=2)
    smoke.add_argument("--ui-root", type=Path, default=EVALUATION_ROOT.parents[1] / "standards-ui")
    smoke.add_argument("--out", type=Path)
    smoke.add_argument("--case", default="dev-archive-digitisation")
    smoke.add_argument("--spend-ledger", type=Path)

    review = commands.add_parser("review-summary", help="unblind a completed designer review")
    review.add_argument("--run", type=Path, required=True)

    declaration = commands.add_parser(
        "validate-declaration", help="validate a strict protocol 0.5 declaration without network access")
    declaration.add_argument("--declaration", type=Path, required=True)
    declaration.add_argument("--freeze-receipt", type=Path)
    declaration.add_argument("--snapshot", type=Path)
    declaration.add_argument("--spend-ledger", type=Path)

    freeze = commands.add_parser(
        "validate-freeze", help="verify an external freeze receipt binds a declaration and snapshot")
    freeze.add_argument("--declaration", type=Path, required=True)
    freeze.add_argument("--freeze-receipt", type=Path, required=True)
    freeze.add_argument("--snapshot", type=Path, required=True)
    freeze.add_argument("--spend-ledger", type=Path, required=True)

    power = commands.add_parser("power", help="plan paired binary repetitions deterministically")
    power.add_argument("--baseline-rate", type=float, required=True)
    power.add_argument("--treatment-rate", type=float, required=True)
    power.add_argument("--pair-correlation", type=float, required=True)
    power.add_argument("--alpha", type=float, default=.05)
    power.add_argument("--power", type=float, default=.9)
    power.add_argument("--routes", type=int, required=True)
    power.add_argument("--fixtures", type=int, default=8)
    power.add_argument("--max-repetitions", type=int, default=50)
    power.add_argument("--simulations", type=int, default=10000)
    power.add_argument("--seed", type=int, default=20260912)
    power.add_argument("--estimated-cost-per-cell-gbp", type=float, default=0)
    power.add_argument("--conditions", type=int, default=5)
    power.add_argument("--maximum-budget-gbp", type=float, default=500)

    ledger = commands.add_parser("ledger-init", help="create a cumulative £500 spend ledger")
    ledger.add_argument("--out", type=Path, required=True)
    ledger.add_argument("--id", required=True)
    ledger.add_argument("--cap-gbp", type=float, default=500)

    ledger_status = commands.add_parser("ledger-status", help="validate and summarize a spend ledger")
    ledger_status.add_argument("--ledger", type=Path, required=True)

    seal = commands.add_parser("review-seal", help="seal declared reviewer files and compute agreement")
    seal.add_argument("--run", type=Path, required=True)
    seal.add_argument("--declaration", type=Path, required=True)
    seal.add_argument("--reviews", type=Path, nargs="+", required=True)
    seal.add_argument("--out", type=Path, required=True)

    analyze = commands.add_parser("analyze", help="run the frozen paired confirmatory analysis")
    analyze.add_argument("--run", type=Path, required=True)
    analyze.add_argument("--declaration", type=Path, required=True)
    analyze.add_argument("--review-set", type=Path)
    analyze.add_argument("--out", type=Path)

    bundle = commands.add_parser("bundle", help="copy and verify a publication-safe evidence bundle")
    bundle.add_argument("--run", type=Path, required=True)
    bundle.add_argument("--out", type=Path, required=True)
    bundle.add_argument("--include-unblinding-key", action="store_true")

    verify = commands.add_parser("bundle-verify", help="verify retained evidence against its manifest")
    verify.add_argument("--bundle", type=Path, required=True)
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
    if args.command == "ledger-init":
        ledger = SpendLedger.create(args.out.resolve(), args.id, cap_gbp=args.cap_gbp)
        _print({"schemaVersion": "0.5.0", "ledgerId": ledger.value["ledgerId"],
                "chargedGbp": ledger.charged_gbp, "remainingGbp": ledger.remaining_gbp,
                "automaticTopUp": False})
        return 0
    if args.command == "ledger-status":
        ledger = SpendLedger.load(args.ledger.resolve())
        validate_spend_ledger(ledger.value)
        _print({"schemaVersion": "0.5.0", "ledgerId": ledger.value["ledgerId"],
                "chargedGbp": ledger.charged_gbp, "remainingGbp": ledger.remaining_gbp,
                "entries": len(ledger.value["entries"]), "automaticTopUp": False})
        return 0
    if args.command in {"validate-declaration", "validate-freeze"}:
        declaration = validate_declaration(read_study_json(args.declaration.resolve()))
        receipt = (validate_freeze_receipt(read_study_json(args.freeze_receipt.resolve()))
                   if args.freeze_receipt else None)
        snapshot = read_study_json(args.snapshot.resolve()) if args.snapshot else None
        spend = (SpendLedger.load(args.spend_ledger.resolve()).snapshot()
                 if args.spend_ledger else None)
        blockers = confirmatory_blockers(
            declaration, receipt, snapshot=snapshot, spend_ledger=spend)
        result = {"schemaVersion": "0.5.0", "studyId": declaration["studyId"],
                  "declarationSha256": digest(declaration), "ready": not blockers,
                  "blockers": blockers}
        _print(result)
        return 0 if not blockers else 2
    if args.command == "power":
        _print(plan_paired_power(
            baseline_rate=args.baseline_rate, treatment_rate=args.treatment_rate,
            within_pair_correlation=args.pair_correlation, alpha=args.alpha,
            power=args.power, routes=args.routes, fixtures=args.fixtures,
            maximum_repetitions=args.max_repetitions,
            simulations=args.simulations, seed=args.seed,
            estimated_cost_per_cell_gbp=args.estimated_cost_per_cell_gbp,
            conditions=args.conditions, maximum_budget_gbp=args.maximum_budget_gbp))
        return 0
    if args.command == "review-seal":
        _print(seal_review_set(
            args.run.resolve(), read_study_json(args.declaration.resolve()),
            [path.resolve() for path in args.reviews], args.out.resolve()))
        return 0
    if args.command == "analyze":
        declaration = read_study_json(args.declaration.resolve())
        review_set = read_study_json(args.review_set.resolve()) if args.review_set else None
        result = analyze_confirmatory(args.run.resolve(), declaration, review_set)
        if args.out:
            write_json(args.out.resolve(), result, exclusive=True)
        _print(result)
        return 0
    if args.command == "bundle":
        _print(create_publication_bundle(
            args.run.resolve(), args.out.resolve(),
            include_unblinding_key=args.include_unblinding_key))
        return 0
    if args.command == "bundle-verify":
        _print(verify_publication_safe(args.bundle.resolve()))
        return 0

    declaration_record = None
    freeze_receipt = None
    frozen_snapshot = None
    spend_ledger = (SpendLedger.load(args.spend_ledger.resolve())
                    if getattr(args, "spend_ledger", None) else None)
    if args.command == "run" and args.mode == "confirmatory":
        if not args.declaration or not args.freeze_receipt or not args.snapshot or spend_ledger is None:
            raise EvaluationError(
                "confirmatory execution requires --declaration, --freeze-receipt, --snapshot, and --spend-ledger"
            )
        declaration_record = validate_declaration(read_study_json(args.declaration.resolve()))
        freeze_receipt = validate_freeze_receipt(read_study_json(args.freeze_receipt.resolve()))
        frozen_snapshot = read_study_json(args.snapshot.resolve())
        blockers = confirmatory_blockers(
            declaration_record, freeze_receipt, snapshot=frozen_snapshot,
            spend_ledger=spend_ledger.snapshot())
        if blockers:
            raise EvaluationError("confirmatory execution blocked: " + " | ".join(blockers))
    if args.command in {"run", "smoke"} and spend_ledger is None:
        raise EvaluationError("live evaluation requires --spend-ledger for cumulative GBP reservations")

    snapshot = frozen_snapshot if frozen_snapshot is not None else discover_free_models()
    renderer = UIRenderer(args.ui_root)
    if declaration_record is not None:
        blockers = confirmatory_blockers(
            declaration_record, freeze_receipt, snapshot=snapshot,
            spend_ledger=spend_ledger.snapshot() if spend_ledger else None,
            current_identity=current_confirmatory_identity(
                renderer, load_fixtures("held-out")))
        if blockers:
            raise EvaluationError("confirmatory execution blocked: " + " | ".join(blockers))
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
            label="smoke-non-inferential", study_mode="smoke",
            spend_ledger=spend_ledger, worst_case_call_cost_gbp=0,
            usd_to_gbp_rate=1)
    else:
        models = ([route["modelId"] for route in declaration_record["routes"]]
                  if declaration_record is not None else _csv(args.models or ""))
        if not models:
            raise EvaluationError("at least one model is required")
        validate_frozen_models(snapshot, models,
                               require_zero_price=declaration_record is None)
        reasoning_effort = (declaration_record["generation"]["reasoningEffort"]
                            if declaration_record is not None else
                            "none" if args.reasoning == "off" else "provider-default")
        provider = OpenRouterProvider(
            snapshot, reasoning_effort="none" if reasoning_effort == "none" else None,
            provider_pins=({route["modelId"]: route["underlyingProvider"]
                            for route in declaration_record["routes"]}
                           if declaration_record is not None else None),
            require_zero_price=declaration_record is None,
        )
        conditions = (declaration_record["conditions"] if declaration_record is not None
                      else _csv(args.conditions))
        unknown = sorted(set(conditions) - set(CONDITIONS))
        if unknown:
            raise EvaluationError("unknown conditions: " + ", ".join(unknown))
        output = (args.out or _default_output("comparison")).resolve()
        run_split = declaration_record["split"] if declaration_record is not None else args.split
        run_repetitions = (declaration_record["repetitions"]
                           if declaration_record is not None else args.repetitions)
        generation = declaration_record["generation"] if declaration_record is not None else None
        result = run_experiment(output=output, provider=provider, models=models,
            renderer=renderer, conditions=conditions, split=run_split,
            case_ids=set(_csv(args.cases)) if args.cases else None,
            repetitions=run_repetitions,
            max_repairs=generation["maxRepairs"] if generation else args.max_repairs,
            max_tokens=generation["maxTokens"] if generation else args.max_tokens,
            temperature=generation["temperature"] if generation else args.temperature,
            model_snapshot=snapshot,
            label=("confirmatory-comparative-evaluation" if declaration_record is not None
                   else "exploratory-comparative-evaluation"),
            study_mode=args.mode, declaration=declaration_record,
            freeze_receipt=freeze_receipt, spend_ledger=spend_ledger,
            worst_case_call_cost_gbp=(generation["worstCaseCallCostGbp"]
                                      if generation else args.worst_case_call_cost_gbp),
            usd_to_gbp_rate=(generation["usdToGbpRate"]
                             if generation else args.usd_to_gbp_rate),
            resume=args.resume)
    result["outputDirectory"] = str(output)
    _print(result)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EvaluationError, OpenRouterError, StudyError, OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
