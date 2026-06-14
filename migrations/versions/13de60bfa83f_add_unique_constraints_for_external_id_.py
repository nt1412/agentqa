"""add unique constraints for external_id and build name

Revision ID: 13de60bfa83f
Revises: e56577598840
Create Date: 2026-06-14 11:22:59.617818

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '13de60bfa83f'
down_revision: Union[str, Sequence[str], None] = 'e56577598840'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_test_cases_project_external", "test_cases", ["project_id", "external_id"]
    )
    op.create_unique_constraint("uq_builds_plan_name", "builds", ["plan_id", "name"])


def downgrade() -> None:
    op.drop_constraint("uq_builds_plan_name", "builds", type_="unique")
    op.drop_constraint(
        "uq_test_cases_project_external", "test_cases", type_="unique"
    )
