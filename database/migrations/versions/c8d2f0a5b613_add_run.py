"""add run table + run_id sur doleance, topic, instance

Revision ID: c8d2f0a5b613
Revises: b7c1e9d2f4a3
Create Date: 2026-09-10 15:00:00.000000

Expand + backfill dans une seule migration : rien de ce qui portait des données
n'est supprimé. Le seul retrait est la contrainte d'unicité globale
`uq_topic_external_id`, remplacée par `uq_topic_run_external_id`, plus stricte
dans un run et plus permissive entre runs — c'est justement ce qui autorise deux
grilles concurrentes. Les lignes déjà en base sont rattachées à deux runs
« hérités » pour qu'aucune ne devienne orpheline.

Faire un dump avant de l'appliquer : la contrainte retirée ne se rétablirait pas
si deux grilles avaient été chargées entre-temps (le downgrade le signale).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8d2f0a5b613"
down_revision: str | Sequence[str] | None = "b7c1e9d2f4a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UQ_TOPIC_EXTERNAL = "uq_topic_external_id"
UQ_TOPIC_RUN_EXTERNAL = "uq_topic_run_external_id"
IX_RUN_ACTIF = "uq_run_actif_par_genre"


def upgrade() -> None:
    """Crée `run`, rattache les couches existantes, ouvre l'unicité par run."""
    op.create_table(
        "run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=True),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("prompt_version", sa.String(), nullable=True),
        sa.Column("parameters", sa.JSON(), nullable=True),
        sa.Column("corpus", sa.String(), nullable=True),
        sa.Column("author", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column("active", sa.Boolean(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_run"),
    )
    # Un seul run actif par genre, garanti par la base et pas seulement par le code.
    op.create_index(
        IX_RUN_ACTIF, "run", ["kind"], unique=True, postgresql_where=sa.text("active")
    )

    for table in ("doleance", "topic", "instance"):
        op.add_column(table, sa.Column("run_id", sa.Integer(), nullable=True))
        op.create_foreign_key(f"fk_{table}_run", table, "run", ["run_id"], ["id"])

    _backfill()

    # L'unicité de l'UUID de livraison devient relative au run.
    op.drop_constraint(UQ_TOPIC_EXTERNAL, "topic", type_="unique")
    op.create_unique_constraint(
        UQ_TOPIC_RUN_EXTERNAL, "topic", ["run_id", "external_id"]
    )


def _backfill() -> None:
    """Rattache les lignes déjà en base à un run hérité, par genre.

    Sans cela elles resteraient hors de toute couche : invisibles dès que les
    lectures filtrent sur le run actif.
    """
    connexion = op.get_bind()
    heritage = {
        "segmentation": ("doleance",),
        "analyse": ("topic", "instance"),
    }
    for genre, tables in heritage.items():
        peuplees = [
            table
            for table in tables
            if connexion.execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first()
        ]
        if not peuplees:
            continue
        run_id = connexion.execute(
            sa.text(
                "INSERT INTO run (kind, label, source, author, active, notes) "
                "VALUES (:kind, :label, :source, :author, TRUE, :notes) RETURNING id"
            ),
            {
                "kind": genre,
                "label": f"{genre} hérité",
                "source": "avant la table run",
                "author": "inconnu",
                "notes": (
                    "Rattachement rétroactif : ces lignes existaient avant que les "
                    "couches soient versionnées. Modèle, prompt et paramètres sont "
                    "perdus."
                ),
            },
        ).scalar_one()
        for table in peuplees:
            connexion.execute(
                sa.text(f"UPDATE {table} SET run_id = :run_id WHERE run_id IS NULL"),
                {"run_id": run_id},
            )


def downgrade() -> None:
    """Retire run_id et la table ; les runs hérités disparaissent avec.

    Échoue si deux grilles coexistent : l'unicité globale de `topic.external_id`
    ne peut pas être rétablie sans choisir laquelle supprimer, et ce choix
    n'appartient pas à une migration.
    """
    op.drop_constraint(UQ_TOPIC_RUN_EXTERNAL, "topic", type_="unique")
    op.create_unique_constraint(UQ_TOPIC_EXTERNAL, "topic", ["external_id"])

    for table in ("doleance", "topic", "instance"):
        op.drop_constraint(f"fk_{table}_run", table, type_="foreignkey")
        op.drop_column(table, "run_id")

    op.drop_index(IX_RUN_ACTIF, table_name="run")
    op.drop_table("run")
