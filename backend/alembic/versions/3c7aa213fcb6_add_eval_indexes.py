"""add eval indexes

Revision ID: 3c7aa213fcb6
Revises: cbe658f34eb2
Create Date: 2026-05-29 11:09:41.459878

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '3c7aa213fcb6'
down_revision: str | Sequence[str] | None = 'cbe658f34eb2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # eval_suites: name lookup used by get_suite_by_name
    op.create_index(op.f("ix_eval_suites_name"), "eval_suites", ["name"], unique=False)
    # eval_suites: composite (name, version) for exact lookup
    op.create_index(
        op.f("ix_eval_suites_name_version"),
        "eval_suites",
        ["name", "version"],
        unique=True,
    )
    # eval_runs: status filter used by list_runs
    op.create_index(op.f("ix_eval_runs_status"), "eval_runs", ["status"], unique=False)
    # eval_runs: created_at ordering used by list_runs
    op.create_index(
        op.f("ix_eval_runs_created_at"), "eval_runs", ["created_at"], unique=False
    )
    # eval_results: case_id FK lookup
    op.create_index(
        op.f("ix_eval_results_case_id"), "eval_results", ["case_id"], unique=False
    )
    # eval_comparisons: FK columns
    op.create_index(
        op.f("ix_eval_comparisons_run_a_id"),
        "eval_comparisons",
        ["run_a_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_eval_comparisons_run_b_id"),
        "eval_comparisons",
        ["run_b_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_eval_comparisons_run_b_id"), table_name="eval_comparisons")
    op.drop_index(op.f("ix_eval_comparisons_run_a_id"), table_name="eval_comparisons")
    op.drop_index(op.f("ix_eval_results_case_id"), table_name="eval_results")
    op.drop_index(op.f("ix_eval_runs_created_at"), table_name="eval_runs")
    op.drop_index(op.f("ix_eval_runs_status"), table_name="eval_runs")
    op.drop_index(op.f("ix_eval_suites_name_version"), table_name="eval_suites")
    op.drop_index(op.f("ix_eval_suites_name"), table_name="eval_suites")
