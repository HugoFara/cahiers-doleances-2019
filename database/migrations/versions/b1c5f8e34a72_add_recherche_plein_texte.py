"""recherche plein texte : configuration française sans accent + index GIN

Revision ID: b1c5f8e34a72
Revises: e4f9c26d81b3
Create Date: 2026-09-10 22:30:00.000000

Trois objets, tous PostgreSQL : l'extension `unaccent`, une configuration de
recherche `francais_sans_accent`, et un index GIN d'expression sur
`doleance.text`.

**Un index d'expression, pas une colonne générée.** Une colonne `tsvector` sur
le modèle casserait les tests, qui montent le schéma sur SQLite — lequel ne
connaît ni `tsvector` ni `to_tsvector`. L'index d'expression donne la même
performance sans rien ajouter au modèle : c'est un objet de base, pas une
donnée.

**Pourquoi une configuration sans accent.** `french` distingue « école » de
« ecole ». Deux raisons de ne pas le vouloir ici : l'OCR abîme les accents — le
corpus contient `qüe`, `qùè`, `qüé` pour « que » — et surtout personne ne tape
les accents dans un champ de recherche. Mesuré sur les 1 002 doléances, la
configuration sans accent trouve entre 2 % et 10 % de doléances de plus selon le
terme.

Elle a un effet de bord assumé : elle confond « retraite » et « retraité », deux
mots distincts. Le radicaliseur français les confondait déjà (même racine), la
configuration ne fait qu'ajouter les variantes abîmées.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1c5f8e34a72"
down_revision: str | Sequence[str] | None = "e4f9c26d81b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONFIGURATION = "francais_sans_accent"
INDEX = "ix_doleance_recherche"


def upgrade() -> None:
    """Crée la configuration de recherche et l'index qui l'utilise."""
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    # `COPY = french` reprend le radicaliseur et la liste de mots vides ; seule
    # la correspondance des mots change, pour passer par unaccent d'abord.
    op.execute(f"CREATE TEXT SEARCH CONFIGURATION {CONFIGURATION} (COPY = french)")
    op.execute(
        f"ALTER TEXT SEARCH CONFIGURATION {CONFIGURATION} "
        "ALTER MAPPING FOR hword, hword_part, word WITH unaccent, french_stem"
    )
    # Nom qualifié : l'index fige la configuration par son OID, mais le SQL des
    # requêtes, lui, dépend du search_path s'il n'est pas qualifié.
    op.execute(
        f"CREATE INDEX {INDEX} ON doleance USING gin "
        f"(to_tsvector('public.{CONFIGURATION}', coalesce(text, '')))"
    )


def downgrade() -> None:
    """Retire l'index puis la configuration ; l'extension reste.

    `unaccent` peut servir ailleurs et sa suppression n'appartient pas à cette
    migration — la reposer coûte une commande, la retirer sous les pieds d'un
    autre objet casserait ce dernier.
    """
    op.execute(f"DROP INDEX IF EXISTS {INDEX}")
    op.execute(f"DROP TEXT SEARCH CONFIGURATION IF EXISTS {CONFIGURATION}")
