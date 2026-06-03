"""Unit tests for interview three-gaps fixes."""
from __future__ import annotations

from app.agents.interviewer.chief import _answer_is_sufficient
from app.agents.interviewer.nodes import _EvaluatorScoring


class TestEvaluatorScoringNewFields:
    def test_default_followup_would_help_is_true(self):
        s = _EvaluatorScoring()
        assert s.followup_would_help is True

    def test_default_is_repeated_answer_is_false(self):
        s = _EvaluatorScoring()
        assert s.is_repeated_answer is False

    def test_followup_would_help_can_be_set_false(self):
        s = _EvaluatorScoring(followup_would_help=False)
        assert s.followup_would_help is False

    def test_is_repeated_answer_can_be_set_true(self):
        s = _EvaluatorScoring(is_repeated_answer=True)
        assert s.is_repeated_answer is True


class TestAnswerIsSufficient:
    def _make_report(self, score=5.0, missing=None, repeated=False, followup_help=True):
        scoring = {
            "summary_score": score,
            "missing_dimensions": missing or [],
            "is_repeated_answer": repeated,
            "followup_would_help": followup_help,
        }
        return {"scoring": scoring}

    def test_high_score_no_missing_is_sufficient(self):
        assert _answer_is_sufficient(self._make_report(score=7.5)) is True

    def test_high_score_with_missing_not_sufficient(self):
        assert _answer_is_sufficient(self._make_report(score=7.5, missing=["量化指标"])) is False

    def test_low_score_not_sufficient_by_default(self):
        assert _answer_is_sufficient(self._make_report(score=5.5)) is False

    def test_repeated_answer_is_sufficient_regardless_of_score(self):
        assert _answer_is_sufficient(self._make_report(score=4.0, repeated=True)) is True

    def test_followup_would_not_help_is_sufficient(self):
        assert _answer_is_sufficient(self._make_report(score=5.0, followup_help=False)) is True

    def test_followup_would_help_true_and_low_score_not_sufficient(self):
        assert _answer_is_sufficient(self._make_report(score=5.0, followup_help=True)) is False
