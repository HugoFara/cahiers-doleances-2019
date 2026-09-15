"""page_extraction.categorie : la catégorie du versement, lue dans le nom

Revision ID: a3c7e1d9b2f4
Revises: f8c4d2e1a057
Create Date: 2026-09-15 15:00:00.000000

Le versement BnF classe les contributions en quatre catégories — CC cahiers
citoyens, CO courriers, CR et IL comptes rendus — portées par le préfixe du
nom de fichier. Ce sont des genres de documents différents ; tout ce qui lit
le corpus filtre sur la catégorie pour ne pas les mélanger. La colonne est
remplie depuis le nom pour les lignes existantes (toutes des cahiers à ce
jour) et reste NULL hors de la convention de nommage.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3c7e1d9b2f4"
down_revision: str | Sequence[str] | None = "f8c4d2e1a057"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX = "ix_page_extraction_categorie"


def upgrade() -> None:
    """Pose la colonne et la remplit depuis le préfixe du nom."""
    op.add_column("page_extraction", sa.Column("categorie", sa.String(2), nullable=True))
    op.execute(
        "UPDATE page_extraction SET categorie = upper(substr(pdf_name, 1, 2)) "
        "WHERE upper(substr(pdf_name, 1, 3)) IN ('CC_', 'CO_', 'CR_', 'IL_')"
    )
    op.create_index(INDEX, "page_extraction", ["categorie"])


def downgrade() -> None:
    """Retire la colonne ; la catégorie reste lisible dans le nom."""
    op.drop_index(INDEX, table_name="page_extraction")
    op.drop_column("page_extraction", "categorie")
