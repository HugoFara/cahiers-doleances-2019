"""run.author NOT NULL

Revision ID: d3e8b12c57a9
Revises: f6a2d8b4e137
Create Date: 2026-09-10 23:55:00.000000

L'auteur d'un run était réclamé — un `--auteur` facultatif et un message
imprimé en fin de commande — jamais imposé. Un avertissement qu'on lit une fois
puis plus jamais ne tient pas lieu de contrainte.

Les runs déjà anonymes ne sont pas inventés a posteriori : ils reçoivent
`inconnu`, qui dit exactement ce qu'on sait d'eux. C'est la même valeur que
porte déjà le run d'analyse hérité, créé avant l'existence de la table.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d3e8b12c57a9"
down_revision: str | Sequence[str] | None = "f6a2d8b4e137"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INCONNU = "inconnu"


def upgrade() -> None:
    """Comble les auteurs manquants, puis ferme la colonne."""
    op.execute(sa.text(f"UPDATE run SET author = '{INCONNU}' WHERE author IS NULL"))
    op.alter_column("run", "author", existing_type=sa.String(), nullable=False)


def downgrade() -> None:
    """Rouvre la colonne ; les `inconnu` posés ci-dessus restent.

    Les repasser à NULL supposerait qu'aucun run légitime ne porte cette
    valeur, ce qui est faux : le run d'analyse hérité la portait avant cette
    migration. On préfère garder une mention exacte qu'un NULL reconstruit.
    """
    op.alter_column("run", "author", existing_type=sa.String(), nullable=True)
