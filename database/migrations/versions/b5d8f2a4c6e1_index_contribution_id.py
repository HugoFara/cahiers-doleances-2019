"""index sur les clés étrangères vers contribution

Revision ID: b5d8f2a4c6e1
Revises: a3c7e1d9b2f4
Create Date: 2026-09-15 19:30:00.000000

Cinq tables pointent sur `contribution` sans index sur la colonne :
`page_extraction` (430 000 lignes), `extraction` (263 000), `instance`,
`doleance`, `feeling`. Supprimer une contribution oblige alors PostgreSQL à
balayer chacune pour vérifier la clé — mesuré le 2026-09-15 : la purge de
20 000 contributions n'avait pas fini après 1 h 30. Les mêmes index servent
toutes les lectures par contribution (`lire_pages(contributions=…)`, l'app).
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b5d8f2a4c6e1"
down_revision: str | Sequence[str] | None = "a3c7e1d9b2f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("page_extraction", "extraction", "instance", "doleance", "feeling")


def upgrade() -> None:
    """Pose un index sur `contribution_id` là où il manque."""
    for table in TABLES:
        op.create_index(f"ix_{table}_contribution_id", table, ["contribution_id"])


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_index(f"ix_{table}_contribution_id", table_name=table)
