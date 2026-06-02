from app.eval.dimensions import DIMENSIONS, TargetType


def test_dimensions_completeness():
    # 验证 DIMENSIONS 覆盖全部 TargetType
    assert len(DIMENSIONS) == len(TargetType)
    for t in TargetType:
        assert t in DIMENSIONS


def test_dimensions_content():
    for _target_type, dims in DIMENSIONS.items():
        # 每种 TargetType 至少有 3-4 个维度
        assert len(dims) >= 3
        
        for dim in dims:
            # 每维度有 name, description, rubric_text, pass_threshold 字段
            assert "name" in dim
            assert "description" in dim
            assert "rubric_text" in dim
            assert "pass_threshold" in dim
            assert isinstance(dim["pass_threshold"], float)
