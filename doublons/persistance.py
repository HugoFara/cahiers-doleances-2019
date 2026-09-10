"""Lecture des doléances, écriture des groupes de doublons."""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from database.models import Contribution, Doleance, DuplicateGroup, DuplicateMember
from doublons.groupes import Groupe


def lire_doleances(session: Session, run_segmentation: int) -> dict[int, str]:
    """``{doleance_id: texte}`` pour un découpage donné."""
    lignes = session.execute(
        select(Doleance.id, Doleance.text).where(
            Doleance.run_id == run_segmentation, Doleance.text.is_not(None)
        )
    ).all()
    return {identifiant: texte for identifiant, texte in lignes if texte.strip()}


def communes_des_doleances(session: Session, run_segmentation: int) -> dict[int, str]:
    """``{doleance_id: code INSEE}``, les non rattachées en moins.

    Le code plutôt que la graphie : c'est lui qui dit si un texte a circulé
    entre communes distinctes ou s'il a été recopié dans le même registre.
    """
    lignes = session.execute(
        select(Doleance.id, Contribution.city_code)
        .join(Contribution, Doleance.contribution_id == Contribution.id)
        .where(Doleance.run_id == run_segmentation, Contribution.city_code.is_not(None))
    ).all()
    return dict(lignes)


def oublier_run(session: Session, run_id: int) -> None:
    """Efface les groupes d'un run de déduplication, pour le rejouer."""
    groupes = select(DuplicateGroup.id).where(DuplicateGroup.run_id == run_id)
    session.execute(
        delete(DuplicateMember).where(DuplicateMember.group_id.in_(groupes))
    )
    session.execute(delete(DuplicateGroup).where(DuplicateGroup.run_id == run_id))
    session.flush()


def enregistrer(
    session: Session,
    run_id: int,
    groupes: list[Groupe],
    communes: dict[int, str],
) -> int:
    """Écrit les groupes et leurs membres. Renvoie le nombre de doléances groupées.

    Le groupe est créé et flushé avant ses membres : la clé étrangère l'exige,
    et l'autoflush écrirait sinon les membres en premier.
    """
    total = 0
    for groupe in groupes:
        ligne = DuplicateGroup(
            run_id=run_id,
            size=groupe.taille,
            cities=len({communes[m] for m in groupe.membres if m in communes}),
            similarity_min=groupe.similarite_min,
        )
        session.add(ligne)
        session.flush()
        for membre in groupe.membres:
            session.add(DuplicateMember(group_id=ligne.id, doleance_id=membre))
        total += groupe.taille
    return total
