"""Lecture du corpus, application des règles, écriture des deux axes."""

from collections import Counter

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from database.models import Doleance, DuplicateGroup, DuplicateMember
from database.models import Typologie as LigneTypologie
from typologie.classement import AXES, classer

# Un texte présent dans plusieurs communes est une lettre-type ou un tract ; le
# même texte recopié deux fois dans une seule commune est plus souvent un cahier
# scanné en double, ce qui ne dit rien du support.
COMMUNES_MINIMUM = 2


def lire_doleances(session: Session, run_segmentation: int) -> dict[int, str]:
    """``{doleance_id: texte}`` pour un découpage donné."""
    lignes = session.execute(
        select(Doleance.id, Doleance.text).where(
            Doleance.run_id == run_segmentation, Doleance.text.is_not(None)
        )
    ).all()
    return {identifiant: texte for identifiant, texte in lignes if texte}


def lire_recopies(session: Session, run_doublons: int | None) -> set[int]:
    """Doléances appartenant à un groupe de doublons couvrant plusieurs communes.

    C'est le seul signal de cette passe qui ne vienne pas du texte : il vient de
    la couche `doublons/`. Il est **facultatif** — sans run de déduplication
    servi, la passe tourne et le support `lettre_type` n'est simplement jamais
    conclu. Le run employé est consigné dans les paramètres, pour qu'on sache
    lequel des deux cas on lit.

    Args:
        session: session ouverte sur la base.
        run_doublons: run de déduplication à lire, ``None`` pour aucun.

    Returns:
        Les identifiants de doléances concernés, vide si aucun run.
    """
    if run_doublons is None:
        return set()
    return {
        identifiant
        for (identifiant,) in session.execute(
            select(DuplicateMember.doleance_id)
            .join(DuplicateGroup, DuplicateGroup.id == DuplicateMember.group_id)
            .where(
                DuplicateGroup.run_id == run_doublons,
                DuplicateGroup.cities >= COMMUNES_MINIMUM,
            )
        ).all()
    }


def oublier_run(session: Session, run_id: int) -> None:
    """Efface la typologie d'un run, pour le rejouer.

    Les relectures humaines de ce run partent avec : c'est pour cela qu'un
    nouveau réglage crée un run de plus plutôt que d'écraser celui-ci.
    """
    session.execute(delete(LigneTypologie).where(LigneTypologie.run_id == run_id))
    session.flush()


def classer_tout(
    session: Session,
    run_id: int,
    textes: dict[int, str],
    recopies: set[int] | None = None,
) -> dict[str, Counter]:
    """Classe chaque doléance sur les deux axes et écrit les lignes.

    Args:
        session: session ouverte (le commit reste à l'appelant).
        run_id: run de typologie auquel rattacher les lignes.
        textes: ``{doleance_id: texte}``.
        recopies: doléances membres d'un groupe de doublons multi-communes.

    Returns:
        ``{axe: Counter({valeur: nombre})}``, les deux axes toujours présents.
    """
    recopies = recopies or set()
    comptes: dict[str, Counter] = {axe: Counter() for axe in AXES}
    for doleance_id, texte in textes.items():
        for axe, (valeur, detecteur) in classer(texte, doleance_id in recopies).items():
            session.add(
                LigneTypologie(
                    run_id=run_id,
                    doleance_id=doleance_id,
                    axis=axe,
                    value=valeur,
                    detector=detecteur,
                )
            )
            comptes[axe][valeur] += 1
    return comptes
