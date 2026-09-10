"""Passage des détecteurs sur les doléances, et écriture des offsets."""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from anonymisation.detecteurs import detecter
from database.models import Doleance, PiiSpan


def lire_doleances(session: Session, run_segmentation: int) -> dict[int, str]:
    """``{doleance_id: texte}`` pour un découpage donné."""
    lignes = session.execute(
        select(Doleance.id, Doleance.text).where(
            Doleance.run_id == run_segmentation, Doleance.text.is_not(None)
        )
    ).all()
    return {identifiant: texte for identifiant, texte in lignes if texte}


def oublier_run(session: Session, run_id: int) -> None:
    """Efface les passages d'un run, pour le rejouer.

    Attention : les relectures humaines de ce run partent avec. C'est pour cela
    qu'un nouveau réglage crée un run de plus plutôt que d'écraser celui-ci.
    """
    session.execute(delete(PiiSpan).where(PiiSpan.run_id == run_id))
    session.flush()


def detecter_tout(
    session: Session, run_id: int, textes: dict[int, str]
) -> dict[str, int]:
    """Passe les détecteurs sur chaque doléance et écrit les offsets.

    Args:
        session: session ouverte (le commit reste à l'appelant).
        run_id: run d'anonymisation auquel rattacher les passages.
        textes: ``{doleance_id: texte}``.

    Returns:
        ``{genre: nombre de passages}``.
    """
    comptes: dict[str, int] = {}
    for doleance_id, texte in textes.items():
        for passage in detecter(texte):
            session.add(
                PiiSpan(
                    run_id=run_id,
                    doleance_id=doleance_id,
                    start=passage.debut,
                    end=passage.fin,
                    kind=passage.genre,
                    detector=passage.detecteur,
                )
            )
            comptes[passage.genre] = comptes.get(passage.genre, 0) + 1
    return comptes
