"""add pii_span

Revision ID: f6a2d8b4e137
Revises: e5f9c3a7d418
Create Date: 2026-09-10 23:00:00.000000

Additive. La table ne contient que des **offsets** : le texte d'origine n'est ni
copié ni modifié, le caviardage est un rendu produit à la lecture.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6a2d8b4e137"
down_revision: str | Sequence[str] | None = "e5f9c3a7d418"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Crée la table des passages à caviarder."""
    op.create_table(
        "pii_span",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=True),
        sa.Column("doleance_id", sa.Integer(), nullable=True),
        sa.Column("start", sa.Integer(), nullable=True),
        sa.Column("end", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(), nullable=True),
        sa.Column("detector", sa.String(), nullable=True),
        sa.Column("confirmed", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["run.id"], name="fk_pii_span_run"),
        sa.ForeignKeyConstraint(
            ["doleance_id"], ["doleance.id"], name="fk_pii_span_doleance"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pii_span"),
    )
    # Toute lecture caviardée part d'une doléance et demande ses passages.
    op.create_index("ix_pii_span_doleance_id", "pii_span", ["doleance_id"])


def downgrade() -> None:
    """Supprime la table ; les relectures humaines sont perdues avec elle."""
    op.drop_index("ix_pii_span_doleance_id", table_name="pii_span")
    op.drop_table("pii_span")
