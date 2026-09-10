"""add extension vector + table embedding

Revision ID: c2d7a91b46f8
Revises: b1c5f8e34a72
Create Date: 2026-09-10 23:15:00.000000

Additive : l'extension et une table neuve, rien d'existant n'est touché.

**L'extension n'est pas dans l'image `postgres:16`.** `compose.yaml` pointe
désormais sur `pgvector/pgvector:pg16`, qui est la même image avec l'extension
compilée dedans — même version majeure, même format de répertoire de données,
le volume passe de l'une à l'autre sans rien perdre.

**La colonne `vector` n'a pas de dimension déclarée.** Elle dépend du modèle
d'embedding, qui n'est pas choisi — et ce choix n'est pas seulement technique :
ces textes sont des opinions politiques nominatives, la passe doit tourner en UE.
pgvector accepte un vecteur non contraint mais refuse de l'indexer : la recherche
vectorielle fera donc un parcours complet, sans conséquence sur mille doléances.
Le jour où le modèle est choisi, une migration fixe la dimension et pose l'index.

DDL écrit à la main plutôt qu'avec le type SQLAlchemy de `pgvector` : une
migration est une archive, et elle ne doit pas dépendre de l'API d'une
bibliothèque tierce pour rester rejouable dans deux ans.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2d7a91b46f8"
down_revision: str | Sequence[str] | None = "b1c5f8e34a72"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_DOLEANCE = "ix_embedding_doleance_id"


def upgrade() -> None:
    """Pose l'extension et la table des vecteurs."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE TABLE embedding (
            id serial PRIMARY KEY,
            run_id integer REFERENCES run(id),
            doleance_id integer REFERENCES doleance(id),
            vector vector,
            CONSTRAINT uq_embedding_run_doleance UNIQUE (run_id, doleance_id)
        )
        """
    )
    op.create_index(INDEX_DOLEANCE, "embedding", ["doleance_id"])


def downgrade() -> None:
    """Retire la table ; l'extension reste.

    Même raisonnement que pour `unaccent` : l'extension peut servir ailleurs, et
    la retirer sous les pieds d'un autre objet casserait ce dernier. La reposer
    coûte une commande.
    """
    op.drop_index(INDEX_DOLEANCE, table_name="embedding")
    op.drop_table("embedding")
