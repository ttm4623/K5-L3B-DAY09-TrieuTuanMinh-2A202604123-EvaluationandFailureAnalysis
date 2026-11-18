"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, aggregate, load_spec, per_item
from lab9.graders import GRADERS


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems = []
    row_metric_ids = [
        metric["id"] for metric in spec.get("metrics", [])
        if metric.get("grader") != "lab8.metrics.summarize"
    ]

    def inspect_report(report: dict, name: str) -> tuple[list[tuple], dict]:
        manifest = report.get("manifest")
        if not isinstance(manifest, dict):
            problems.append(f"{name} report has no manifest")
            manifest = {}
        rows = report.get("rows")
        if not isinstance(rows, list):
            problems.append(f"{name} report rows are missing or invalid")
            rows = []

        items = manifest.get("items")
        seeds = manifest.get("seeds")
        if (not isinstance(items, int) or isinstance(items, bool) or items < 0
                or not isinstance(seeds, list)):
            problems.append(f"{name} manifest has invalid items or seeds")
        elif len(rows) != items * len(seeds):
            problems.append(
                f"{name} row count {len(rows)} != manifest items × seeds ({items} × {len(seeds)})"
            )

        row_keys = []
        slices_by_item = {}
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                problems.append(f"{name} row {index} is not an object")
                continue
            item_id, seed = row.get("item_id"), row.get("seed")
            key = (item_id, seed)
            try:
                hash(key)
            except TypeError:
                problems.append(f"{name} row {index} has an invalid item_id/seed")
                continue
            row_keys.append(key)

            tags = row.get("slices") or []
            if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
                problems.append(f"{name} row {index} has invalid slice tags")
                continue
            item_tags = tuple(sorted(set(tags)))
            if item_id in slices_by_item and slices_by_item[item_id] != item_tags:
                problems.append(f"{name} item {item_id} has inconsistent slice tags across rows")
            else:
                slices_by_item[item_id] = item_tags

            for metric_id in row_metric_ids:
                if metric_id not in row:
                    problems.append(f"{name} row {key} is missing graded metric {metric_id}")
                elif row[metric_id] is None:
                    problems.append(f"{name} row {key} has null graded metric {metric_id}")
                elif not isinstance(row[metric_id], (int, float)) or not math.isfinite(row[metric_id]):
                    problems.append(f"{name} row {key} has invalid graded metric {metric_id}")
            if "cost" in row and (
                not isinstance(row["cost"], (int, float))
                or isinstance(row["cost"], bool)
                or not math.isfinite(row["cost"])
            ):
                problems.append(f"{name} row {key} has invalid cost")

        duplicate_keys = [key for key, count in Counter(row_keys).items() if count > 1]
        if duplicate_keys:
            problems.append(f"{name} report has duplicate (item_id, seed) rows")

        metrics = report.get("metrics")
        if not isinstance(metrics, dict):
            problems.append(f"{name} report metrics are missing or invalid")
        else:
            for metric_id, value in metrics.items():
                if not isinstance(value, (int, float)) or not math.isfinite(value):
                    problems.append(f"{name} metric {metric_id} is missing or non-finite")
            spec_metric_ids = {metric["id"] for metric in spec.get("metrics", [])}
            metric_ids = [metric_id for metric_id in spec_metric_ids if metric_id in GRADERS]
            can_recompute = bool(rows) and all(
                isinstance(row, dict)
                and isinstance(row.get("item_id"), str)
                and isinstance(row.get("seed"), int)
                and not isinstance(row.get("seed"), bool)
                and isinstance(row.get("cost"), (int, float))
                and not isinstance(row.get("cost"), bool)
                and math.isfinite(row["cost"])
                and all(
                    metric_id in row
                    and isinstance(row[metric_id], (int, float))
                    and math.isfinite(row[metric_id])
                    for metric_id in metric_ids
                )
                for row in rows
            )
            if can_recompute:
                recomputed = aggregate(rows, metric_ids, k_values=spec.get("pass_k", []))
                allowed_metric_ids = set(recomputed)
                for metric_id in metrics.keys() - allowed_metric_ids:
                    problems.append(f"{name} report has unexpected metric {metric_id}")
                for metric_id, expected in recomputed.items():
                    if metric_id not in metrics:
                        if metric_id in spec_metric_ids:
                            problems.append(f"{name} report is missing metric {metric_id}")
                    elif expected is not None and isinstance(metrics[metric_id], (int, float)):
                        if not math.isclose(metrics[metric_id], expected, rel_tol=0, abs_tol=1e-9):
                            problems.append(f"{name} metric {metric_id} does not match row aggregates")
        failures = report.get("evaluator_failures")
        if not isinstance(failures, list):
            problems.append(f"{name} report evaluator_failures is missing or invalid")
        elif failures:
            problems.append(f"{name} report has evaluator_failures")
        return row_keys, slices_by_item

    pr_keys, pr_slices = inspect_report(pr, "PR")
    base_keys, base_slices = inspect_report(base, "baseline")
    if set(pr_keys) != set(base_keys):
        problems.append("PR (item_id, seed) set differs from baseline")
    for item_id in set(pr_slices) & set(base_slices):
        if pr_slices[item_id] != base_slices[item_id]:
            problems.append(f"slice tags differ for item {item_id}")

    if base_spec and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        def check_ratchet(current_entries, old_entries, key_fn, kind: str) -> None:
            current_by_key = {key_fn(entry): entry for entry in current_entries}
            old_by_key = {key_fn(entry): entry for entry in old_entries}
            for key, old_entry in old_by_key.items():
                entry = current_by_key.get(key)
                if entry is None:
                    problems.append(f"{kind} {key} was removed")
                    continue
                if old_entry.get("blocking") and not entry.get("blocking"):
                    problems.append(f"{kind} {key} is no longer blocking")
                old_threshold = old_entry.get("threshold", old_entry)
                threshold = entry.get("threshold", entry)
                for bound in ("min", "max"):
                    if bound not in old_threshold:
                        continue
                    if bound not in threshold:
                        problems.append(f"{kind} {key} removed {bound} threshold")
                    elif bound == "min" and threshold[bound] < old_threshold[bound]:
                        problems.append(f"{kind} {key} loosened min threshold")
                    elif bound == "max" and threshold[bound] > old_threshold[bound]:
                        problems.append(f"{kind} {key} loosened max threshold")
                if old_threshold.get("no_significant_drop") and not threshold.get("no_significant_drop"):
                    problems.append(f"{kind} {key} removed no_significant_drop")

        check_ratchet(
            spec.get("metrics", []), base_spec.get("metrics", []),
            lambda metric: metric["id"], "metric",
        )
        check_ratchet(
            spec.get("slices", []), base_spec.get("slices", []),
            lambda slice_spec: (slice_spec["name"], slice_spec["metric"]), "slice",
        )
    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for slice_spec in spec.get("slices") or []:
        name, metric = slice_spec["name"], slice_spec["metric"]
        metric_id = f"slice:{name}/{metric}"
        pr_means = per_item(pr, metric, slice_name=name)
        base_means = per_item(base, metric, slice_name=name)
        keys = sorted(set(pr_means) & set(base_means))
        value = sum(pr_means.values()) / len(pr_means) if pr_means else None
        verdict, note = "ok", ""

        if not keys or len(keys) != len(pr_means) or len(keys) != len(base_means):
            verdict = "missing"
            note = "paired slice items missing or differ"
        else:
            if "min" in slice_spec and value is not None and value < slice_spec["min"]:
                verdict = "fail"
            if slice_spec.get("no_significant_drop"):
                delta, lo, hi = stats.paired_bootstrap(
                    [pr_means[key] for key in keys],
                    [base_means[key] for key in keys],
                    n_resamples=bs.get("n_resamples", 1000),
                    rng=bs.get("rng", 2027),
                    confidence=bs.get("confidence", 0.95),
                )
                note = f"Δ {delta:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    verdict = "fail"

        if verdict != "ok" and slice_spec.get("blocking"):
            blocked.append(metric_id)
        label = {"ok": "ok", "missing": "MISSING"}.get(
            verdict, "BLOCK" if slice_spec.get("blocking") else "warn"
        )
        lines.append(
            f"  {metric_id:<42} {value!s:<8} "
            f"{json.dumps({k: slice_spec[k] for k in ('min', 'no_significant_drop') if k in slice_spec}):<40} "
            f"{note:<28} {label}"
        )
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
