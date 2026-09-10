"""expand city : colonnes du Code officiel géographique

Revision ID: a9b3c7e21d54
Revises: d4e8a1c6b092
Create Date: 2026-09-10 21:30:00.000000

Additive : quatre colonnes nullables sur `city`, aucune donnée existante touchée.

**Pas de backfill ici.** Les valeurs viennent d'extraits de référentiels
versionnés dans `insee/referentiel/`, chargés par `python -m insee cog`, qui est
idempotent et rejouable quand le millésime ou la source changent. Une migration
fige le schéma, pas un référentiel : coller ici 1 646 communes rendrait la
migration illisible et la reconstruction impossible sans un downgrade.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a9b3c7e21d54"
down_revision: str | Sequence[str] | None = "d4e8a1c6b092"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLONNES = (
    # Le libellé officiel au millésime pivot, à côté — et non à la place — de la
    # graphie rencontrée dans le corpus, qui est un fait de provenance.
    ("official_name", sa.String()),
    # COM / COMD / COMA au 1er janvier 2019.
    ("cog_type", sa.String(length=4)),
    ("parent_code", sa.String(length=5)),
    # Le code au millésime courant est une annotation : `code` reste celui de
    # 2019, sans quoi les rattachements existants désigneraient autre chose.
    ("current_code", sa.String(length=5)),
)


def upgrade() -> None:
    """Ajoute les colonnes du COG à `city`."""
    for nom, type_ in COLONNES:
        op.add_column("city", sa.Column(nom, type_, nullable=True))


def downgrade() -> None:
    """Retire les colonnes ; le référentiel se recharge avec `python -m insee cog`.

    Rien d'irremplaçable ne disparaît : les extraits restent dans le dépôt.
    """
    for nom, _ in reversed(COLONNES):
        op.drop_column("city", nom)
