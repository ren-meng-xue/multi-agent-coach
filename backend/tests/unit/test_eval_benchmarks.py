"""扫描 benchmark suite，验证基础 schema 完整性。"""
from pathlib import Path

import pytest

from app.eval.datasets import load_suite
from app.eval.dimensions import TargetType

BENCHMARKS_DIR = Path(__file__).parent.parent.parent / "data" / "benchmarks"


@pytest.mark.parametrize("benchmark_file", list(BENCHMARKS_DIR.glob("*.json")))
def test_benchmark_schema_valid(benchmark_file):
    suite = load_suite(str(benchmark_file))
    assert "name" in suite
    assert "judge_mode" in suite
    assert "cases" in suite
    assert isinstance(suite["cases"], list)
    assert len(suite["cases"]) >= 5, f"{benchmark_file.name} 至少 5 个 case"

    seen_target_types = set()
    for case in suite["cases"]:
        assert "id" in case
        assert "target_type" in case
        assert case["target_type"] in {t.value for t in TargetType}
        assert "input_json" in case
        seen_target_types.add(case["target_type"])

    assert len(seen_target_types) >= 1


def test_all_target_types_have_at_least_one_case():
    """整套 benchmark 必须覆盖全部 target_type。"""
    all_target_types = set()
    for f in BENCHMARKS_DIR.glob("*.json"):
        suite = load_suite(str(f))
        for case in suite["cases"]:
            all_target_types.add(case["target_type"])
    expected = {t.value for t in TargetType}
    missing = expected - all_target_types
    assert not missing, f"以下 target_type 没有 benchmark case: {missing}"
