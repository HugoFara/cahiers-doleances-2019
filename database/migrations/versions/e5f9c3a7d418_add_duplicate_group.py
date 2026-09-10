"""add duplicate_group + duplicate_member

Revision ID: e5f9c3a7d418
Revises: a9b3c7e21d54
Create Date: 2026-09-10 21:00:00.000000

Additive : deux tables nouvelles, rien de touché ailleurs. Le regroupement est
produit par `python -m doublons`, pas par cette migration — il dépend d'un seuil
de similarité, qui est un réglage et non un schéma.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f9c3a7d418"
down_revision: str | Sequence[str] | None = "a9b3c7e21d54"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Crée les tables de groupes de doublons et leur liaison aux doléances."""
    op.create_table(
        "duplicate_group",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=True),
        sa.Column("size", sa.Integer(), nullable=True),
        sa.Column("cities", sa.Integer(), nullable=True),
        sa.Column("similarity_min", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["run.id"], name="fk_duplicate_group_run"),
        sa.PrimaryKeyConstraint("id", name="pk_duplicate_group"),
    )
    op.create_table(
        "duplicate_member",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=True),
        sa.Column("doleance_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["group_id"], ["duplicate_group.id"], name="fk_duplicate_member_group"
        ),
        sa.ForeignKeyConstraint(
            ["doleance_id"], ["doleance.id"], name="fk_duplicate_member_doleance"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_duplicate_member"),
    )
    # « À quel groupe appartient cette doléance » est la question posée par
    # toute lecture qui veut pondérer un comptage.
    op.create_index("ix_duplicate_member_doleance_id", "duplicate_member", ["doleance_id"])


def downgrade() -> None:
    """Supprime les deux tables ; le regroupement se refait avec `python -m doublons`."""
    op.drop_index("ix_duplicate_member_doleance_id", table_name="duplicate_member")
    op.drop_table("duplicate_member")
    op.drop_table("duplicate_group")
