"""add table page_transcription

Revision ID: f8c4d2e1a057
Revises: c2d7a91b46f8
Create Date: 2026-09-11 00:30:00.000000

Additive : une table neuve, rien d'existant n'est touché — le squelette
(`page_extraction.text`) reste la couche texte produite sans OCR, il n'est
pas écrasé.

La transcription OCR dépend d'un modèle, d'un rendu et d'une consigne : c'est
une lecture de l'image, versionnée par un run comme les autres couches.
L'unicité porte sur le couple (run, page) : dans une passe, une page est
transcrite une fois — c'est aussi ce qui rend la passe reprenable après
interruption. `layout` conserve la géométrie ligne à ligne quand le backend
la donne : la concaténer reste toujours possible, la retrouver jamais.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f8c4d2e1a057"
down_revision: str | Sequence[str] | None = "c2d7a91b46f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_PAGE = "ix_page_transcription_page_extraction_id"
INDEX_PDF = "ix_page_transcription_pdf_name"


def upgrade() -> None:
    """Pose la table des transcriptions."""
    op.create_table(
        "page_transcription",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=True),
        sa.Column("page_extraction_id", sa.Integer(), nullable=True),
        sa.Column("pdf_name", sa.String(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("layout", sa.JSON(), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["page_extraction_id"], ["page_extraction.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["run.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id", "page_extraction_id", name="uq_page_transcription_run_page"
        ),
    )
    op.create_index(INDEX_PAGE, "page_transcription", ["page_extraction_id"])
    op.create_index(INDEX_PDF, "page_transcription", ["pdf_name"])


def downgrade() -> None:
    """Retire la table. Les passes OCR partent avec elle, le squelette reste."""
    op.drop_index(INDEX_PDF, table_name="page_transcription")
    op.drop_index(INDEX_PAGE, table_name="page_transcription")
    op.drop_table("page_transcription")
