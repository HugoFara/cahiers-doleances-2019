"""add doleance table + instance.doleance_id

Revision ID: b7c1e9d2f4a3
Revises: 770ed9d30389
Create Date: 2026-09-10 10:00:00.000000

Purement additive : la table `doleance` est nouvelle et `instance.doleance_id`
est nullable, les livraisons déjà chargées restent lisibles telles quelles.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c1e9d2f4a3"
down_revision: str | Sequence[str] | None = "770ed9d30389"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Crée la table doleance et la clé étrangère instance -> doleance."""
    op.create_table(
        "doleance",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("contribution_id", sa.Integer(), nullable=True),
        sa.Column("pdf_name", sa.String(), nullable=True),
        sa.Column("city", sa.String(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("start_page", sa.Integer(), nullable=True),
        sa.Column("end_page", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("signal", sa.String(), nullable=True),
        sa.Column("num_words", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["contribution_id"], ["contribution.id"], name="fk_doleance_contribution"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_doleance"),
    )
    # Le découpage se relit et se rejoue cahier par cahier.
    op.create_index("ix_doleance_pdf_name", "doleance", ["pdf_name"])

    op.add_column("instance", sa.Column("doleance_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_instance_doleance", "instance", "doleance", ["doleance_id"], ["id"]
    )


def downgrade() -> None:
    """Retire la clé étrangère puis la table."""
    op.drop_constraint("fk_instance_doleance", "instance", type_="foreignkey")
    op.drop_column("instance", "doleance_id")
    op.drop_index("ix_doleance_pdf_name", table_name="doleance")
    op.drop_table("doleance")
