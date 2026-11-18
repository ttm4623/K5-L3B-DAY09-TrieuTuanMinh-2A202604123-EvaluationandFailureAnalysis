"""M5-M7 self-check (Advanced/Expert). Run: python -m pytest -q -m student -o addopts= -k advanced
Public vectors only; the instructor grades with hidden ones."""
import copy
import math

import pytest

pytestmark = pytest.mark.student


@pytest.fixture(scope="module")
def stats():
    from lab9 import stats

    return stats


@pytest.mark.parametrize("n,c,k,want", [(5, 5, 5, 1.0), (5, 0, 1, 0.0), (5, 2, 1, 0.4), (10, 3, 3, 1 - 35 / 120)])
def test_pass_at_k(stats, n, c, k, want):
    assert math.isclose(stats.pass_at_k(n, c, k), want, abs_tol=1e-9)


@pytest.mark.parametrize("n,c,k,want", [(5, 5, 5, 1.0), (5, 4, 5, 0.0), (5, 4, 3, 0.4), (10, 8, 2, 28 / 45)])
def test_pass_hat_k(stats, n, c, k, want):
    assert math.isclose(stats.pass_hat_k(n, c, k), want, abs_tol=1e-9)


def test_pass_k_rejects_bad_args(stats):
    for args in [(5, 6, 1), (5, 2, 0), (3, 1, 4)]:
        with pytest.raises(ValueError):
            stats.pass_at_k(*args)


def _report(rows, metrics, items=4, seeds=(1, 2)):
    complete_rows = [{**row, "cost": row.get("cost", 0.0)} for row in rows]
    return {"manifest": {"eval_set_sha": "x", "items": items, "seeds": list(seeds)},
            "rows": complete_rows, "metrics": metrics, "evaluator_failures": []}


ROWS = [{"item_id": f"E-{i:03d}", "seed": s, "pass_rate": True, "slices": ["denial"] if i < 2 else []}
        for i in range(4) for s in (1, 2)]
SPEC = {"eval_set_version": "v2", "metrics": [{"id": "pass_rate", "kind": "capability", "blocking": True,
                                               "threshold": {"min": 0.8}}]}


def test_integrity_flags_nan_and_dropped_rows():
    from lab9 import gate

    base = _report(copy.deepcopy(ROWS), {"pass_rate": 1.0})
    assert gate.integrity_check(base, base, SPEC) == []
    nan = _report(copy.deepcopy(ROWS), {"pass_rate": float("nan")})
    assert gate.integrity_check(nan, base, SPEC)
    dropped = _report(copy.deepcopy(ROWS[:-1]), {"pass_rate": 1.0})
    assert gate.integrity_check(dropped, base, SPEC)


def test_integrity_flags_duplicate_rows_and_evaluator_failures():
    from lab9 import gate

    base = _report(copy.deepcopy(ROWS), {"pass_rate": 1.0})
    duplicated_rows = copy.deepcopy(ROWS)
    duplicated_rows[-1] = copy.deepcopy(duplicated_rows[0])
    duplicated = _report(duplicated_rows, {"pass_rate": 1.0})
    failed_evaluator = _report(copy.deepcopy(ROWS), {"pass_rate": 1.0})
    failed_evaluator["evaluator_failures"] = ["E-001@1:grader raised"]

    assert gate.integrity_check(duplicated, base, SPEC)
    assert gate.integrity_check(failed_evaluator, base, SPEC)


def test_integrity_flags_null_graded_metric_and_relabelled_slice():
    from lab9 import gate

    base = _report(copy.deepcopy(ROWS), {"pass_rate": 1.0})
    null_metric_rows = copy.deepcopy(ROWS)
    null_metric_rows[0]["pass_rate"] = None
    null_metric = _report(null_metric_rows, {"pass_rate": 1.0})
    relabelled_rows = copy.deepcopy(ROWS)
    for row in relabelled_rows:
        if row["item_id"] == "E-000":
            row["slices"] = []
    relabelled = _report(relabelled_rows, {"pass_rate": 1.0})

    assert gate.integrity_check(null_metric, base, SPEC)
    assert gate.integrity_check(relabelled, base, SPEC)


def test_integrity_flags_metric_aggregate_not_matching_rows():
    from lab9 import gate

    base = _report(copy.deepcopy(ROWS), {"pass_rate": 1.0})
    rows = copy.deepcopy(ROWS)
    rows[0]["pass_rate"] = False
    forged = _report(rows, {"pass_rate": 1.0})

    assert gate.integrity_check(forged, base, SPEC)


def test_integrity_flags_loosened_spec():
    from lab9 import gate

    base = _report(copy.deepcopy(ROWS), {"pass_rate": 1.0})
    loose = copy.deepcopy(SPEC)
    loose["metrics"][0]["threshold"]["min"] = 0.5
    assert gate.integrity_check(base, base, loose, SPEC)
    assert gate.integrity_check(base, base, SPEC, SPEC) == []


def test_integrity_flags_removed_metric_or_slice_guard():
    from lab9 import gate

    report = _report(copy.deepcopy(ROWS), {"pass_rate": 1.0})
    removed_metric = dict(SPEC, metrics=[])
    assert gate.integrity_check(report, report, removed_metric, SPEC)

    base_spec = dict(SPEC, slices=[
        {"name": "denial", "metric": "pass_rate", "no_significant_drop": True, "blocking": True}
    ])
    loosened_slice = dict(SPEC, slices=[
        {"name": "denial", "metric": "pass_rate", "blocking": True}
    ])
    assert gate.integrity_check(report, report, loosened_slice, base_spec)


def test_slice_check_blocks_a_slice_below_floor():
    from lab9 import gate

    base = _report(copy.deepcopy(ROWS), {"pass_rate": 1.0})
    rows = copy.deepcopy(ROWS)
    for r in rows:
        if "denial" in r["slices"] and r["seed"] == 1:
            r["pass_rate"] = False
    spec = dict(SPEC, slices=[{"name": "denial", "metric": "pass_rate", "min": 0.9, "blocking": True}])
    blocked, _ = gate.slice_check(_report(rows, {"pass_rate": 0.75}), base, spec)
    assert blocked == ["slice:denial/pass_rate"]


def test_slice_check_does_not_block_when_paired_ci_touches_zero():
    from lab9 import gate

    base = _report(copy.deepcopy(ROWS), {"pass_rate": 1.0})
    rows = copy.deepcopy(ROWS)
    rows[0]["pass_rate"] = False
    spec = dict(SPEC, bootstrap={"n_resamples": 1000, "rng": 2027},
                slices=[{"name": "denial", "metric": "pass_rate",
                         "no_significant_drop": True, "blocking": True}])

    blocked, lines = gate.slice_check(_report(rows, {"pass_rate": 0.875}), base, spec)

    assert blocked == []
    assert "CI [-0.500, +0.000]" in lines[0]
