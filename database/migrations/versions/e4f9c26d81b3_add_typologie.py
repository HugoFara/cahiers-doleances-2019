"""add table typologie

Revision ID: e4f9c26d81b3
Revises: d3e8b12c57a9
Create Date: 2026-09-10 23:59:00.000000

Additive : une table neuve, rien d'existant n'est touché.

Deux axes en lignes (`axis` = `support` ou `auteur`) plutôt qu'en colonnes. Un
axe de plus — type de revendication, ton — n'exigera alors pas de migration de
colonne, et une lecture qui n'en veut qu'un ne lit qu'un axe. L'unicité porte sur
le triplet (run, doléance, axe) : dans un même run, un axe se tranche une fois.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4f9c26d81b3"
down_revision: str | Sequence[str] | None = "d3e8b12c57a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_DOLEANCE = "ix_typologie_doleance_id"


def upgrade() -> None:
    """Pose la table des deux axes."""
    op.create_table(
        "typologie",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=True),
        sa.Column("doleance_id", sa.Integer(), nullable=True),
        sa.Column("axis", sa.String(), nullable=True),
        sa.Column("value", sa.String(), nullable=True),
        sa.Column("detector", sa.String(), nullable=True),
        sa.Column("confirmed", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["doleance_id"], ["doleance.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["run.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id", "doleance_id", "axis", name="uq_typologie_run_doleance_axe"
        ),
    )
    op.create_index(INDEX_DOLEANCE, "typologie", ["doleance_id"])


def downgrade() -> None:
    """Retire la table. Les relectures humaines partent avec elle."""
    op.drop_index(INDEX_DOLEANCE, table_name="typologie")
    op.drop_table("typologie")
