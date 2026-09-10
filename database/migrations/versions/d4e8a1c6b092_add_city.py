"""add city table + contribution.city_code

Revision ID: d4e8a1c6b092
Revises: c8d2f0a5b613
Create Date: 2026-09-10 18:00:00.000000

Additive : `city` est nouvelle et `contribution.city_code` est nullable.

**Pas de backfill ici.** Le code INSEE se lit dans le nom du fichier, ce qui
demande une expression régulière et une politique de rapprochement — deux choses
qui évoluent. Une migration est une archive : elle fige le schéma, pas une règle
métier. Le remplissage est fait par `python -m insee rattacher`, qui est
idempotent et rejouable quand la règle change.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e8a1c6b092"
down_revision: str | Sequence[str] | None = "c8d2f0a5b613"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FK_CONTRIBUTION_CITY = "fk_contribution_city_code"


def upgrade() -> None:
    """Crée la table city et la clé étrangère depuis contribution."""
    op.create_table(
        "city",
        sa.Column("code", sa.String(length=5), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("department", sa.String(), nullable=True),
        sa.Column("population", sa.Integer(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("code", name="pk_city"),
    )
    # La couverture se lit par département : c'est l'échelle des Archives.
    op.create_index("ix_city_department", "city", ["department"])

    op.add_column("contribution", sa.Column("city_code", sa.String(length=5), nullable=True))
    op.create_foreign_key(
        FK_CONTRIBUTION_CITY, "contribution", "city", ["city_code"], ["code"]
    )


def downgrade() -> None:
    """Retire la clé étrangère puis la table ; les rattachements sont perdus.

    Ils se refont avec `python -m insee rattacher`, qui ne dépend que des noms
    de fichiers : rien d'irremplaçable ne disparaît ici.
    """
    op.drop_constraint(FK_CONTRIBUTION_CITY, "contribution", type_="foreignkey")
    op.drop_column("contribution", "city_code")
    op.drop_index("ix_city_department", table_name="city")
    op.drop_table("city")
