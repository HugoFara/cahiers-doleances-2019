"""Rattacher les doléances à une grille par mots-clés — sans modèle, et dit tel quel.

La grille « cadrage gouvernemental 2019 » existe sans détections : les
rattacher à un thème demande un modèle, et donc la décision d'hébergement de
la P3. En attendant, ce module fait ce qu'un rattachement *sans* modèle sait
faire : pour chaque question de la grille, un jeu de mots-clés (un fichier
`*.mots_cles.json` à côté de la grille), une requête sur l'index plein texte
de `recherche/` — même configuration sans accent, même syntaxe —, et une
`instance` par doléance qui répond.

Le résultat est un run de genre `analyse` à part, **non actif**, dont
`model` dit « mots-clés » et dont les paramètres portent les requêtes : la
grille reste celle de `analyse/grille.py`, ses thèmes sont copiés dans le
run ; ce sont les détections qui changent de run. C'est ce qui permet à
`taxonomie/` de mesurer de combien ce rattachement est mauvais, et à un
modèle, plus tard, d'être comparé au même étalon bas.

Une doléance est rattachée à une question dès qu'un de ses termes y apparaît.
Le verbatim est la fenêtre autour du premier terme trouvé, le résumé la liste
des termes qui ont mordu. Ni pondération, ni négation, ni contexte : c'est un
détecteur de vocabulaire, pas de propos.

    uv run python -m analyse.mots_cles analyse/grilles/cadrage_gouvernemental_2019.mots_cles.json
"""

import argparse
import json
import re
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from analyse.grille import lire_grille
from analyse.identifiants import DOLEANCE, id_document
from analyse.load_analysis import charger_topics, rattacher_parents
from database.db import check_connection, get_engine
from database.models import Instance, Run
from database.runs import (
    ANALYSE,
    SEGMENTATION,
    activer_run,
    creer_run,
    run_actif,
    run_par_source,
)
from recherche.config import CONFIGURATION
from recherche.extraits import fenetre, plier, termes

DETECTEUR = "mots-clés"
CLES_REQUISES = ("grille", "detecteur", "requetes")

_SQL_DOLEANCES = f"""
    SELECT d.id, d.contribution_id, d.text
    FROM doleance d
    CROSS JOIN websearch_to_tsquery('{CONFIGURATION}', :requete) AS q(query)
    WHERE d.run_id = :run_decoupage
      AND to_tsvector('{CONFIGURATION}', coalesce(d.text, '')) @@ q.query
    ORDER BY d.id
"""


def lire_lexique(fichier: Path) -> dict:
    """Lit et vérifie le lexique : la grille visée, un détecteur, des requêtes.

    Raises:
        ValueError: clé manquante, aucune requête, ou requête vide.
    """
    lexique = json.loads(fichier.read_text(encoding="utf-8"))
    manquantes = [c for c in CLES_REQUISES if c not in lexique]
    if manquantes:
        raise ValueError(f"{fichier.name} : clés manquantes {manquantes}")
    if lexique["detecteur"] != DETECTEUR:
        raise ValueError(
            f"{fichier.name} : détecteur {lexique['detecteur']!r}, attendu {DETECTEUR!r}"
        )
    if not lexique["requetes"]:
        raise ValueError(f"{fichier.name} : aucune requête")
    vides = [t for t, r in lexique["requetes"].items() if not termes(r)]
    if vides:
        raise ValueError(f"{fichier.name} : requête sans terme pour {vides}")
    return lexique


def verifier_cibles(lexique: dict, grille: dict) -> None:
    """Chaque requête vise un thème de la grille — sinon le lexique est faux.

    Raises:
        ValueError: un identifiant de thème inconnu.
    """
    ids = {t["id"] for t in grille["topics"]}
    inconnus = sorted(set(lexique["requetes"]) - ids)
    if inconnus:
        raise ValueError(f"thèmes inconnus dans la grille : {inconnus}")


def termes_trouves(texte: str, requete: str) -> list[str]:
    """Les termes de la requête qui apparaissent dans le texte, à l'accent près.

    Approximation de la correspondance SQL — qui radicalise — par préfixe : un
    terme mord si ses premières lettres ouvrent un mot du texte plié. Sert au
    résumé de l'instance, pas à la détection.
    """
    plie = plier(texte)
    return [t for t in termes(requete) if _mord(plie, t)]


def _mord(plie: str, terme: str) -> bool:
    prefixe = terme[: max(4, len(terme) - 2)]
    return re.search(r"\b" + re.escape(prefixe), plie) is not None


def doleances_repondant(
    session: Session, requete: str, run_decoupage: int
) -> list[tuple]:
    """(id, contribution_id, texte) des doléances du découpage qui répondent.

    PostgreSQL seulement : `websearch_to_tsquery` et l'index de `recherche/`.
    """
    return session.execute(
        text(_SQL_DOLEANCES), {"requete": requete, "run_decoupage": run_decoupage}
    ).all()


def ouvrir_run(
    session: Session,
    fichier: Path,
    grille: dict,
    lexique: dict,
    run_decoupage: Run,
    *,
    auteur: str | None,
) -> Run:
    """Le run de ce lexique : le sien s'il a déjà tourné, un neuf sinon."""
    source = str(fichier)
    existant = run_par_source(session, ANALYSE, source)
    if existant is not None:
        print(f"rattachement repris : run #{existant.id} « {existant.label} »")
        existant.parameters = {
            **(existant.parameters or {}),
            "requetes": lexique["requetes"],
        }
        return existant
    run = creer_run(
        session,
        ANALYSE,
        label=f"{grille['label']} — {DETECTEUR}",
        source=source,
        model=DETECTEUR,
        parameters={
            "detector": DETECTEUR,
            "grille": lexique["grille"],
            "topics": len(grille["topics"]),
            "run_decoupage": run_decoupage.id,
            "requetes": lexique["requetes"],
        },
        corpus=f"doléances du run #{run_decoupage.id} « {run_decoupage.label} »",
        author=auteur,
        notes=lexique.get("note"),
        actif=False,
    )
    print(f"rattachement créé : run #{run.id} « {run.label} »")
    return run


def detecter(
    session: Session,
    run: Run,
    ids_par_theme: dict[str, int],
    requetes: dict[str, str],
    run_decoupage: int,
    chercher=doleances_repondant,
) -> dict[str, int]:
    """Remplace les instances du run par celles que les requêtes trouvent.

    Args:
        session: session ouverte sur la base.
        run: le run de rattachement.
        ids_par_theme: ``{id de thème dans la grille: topic.id}``.
        requetes: ``{id de thème: requête}``.
        run_decoupage: le découpage dont on lit les doléances.
        chercher: la recherche — remplaçable dans les tests, PostgreSQL sinon.

    Returns:
        ``{id de thème: nombre de doléances rattachées}``.
    """
    session.execute(
        text("DELETE FROM instance WHERE run_id = :run_id"), {"run_id": run.id}
    )
    comptes: dict[str, int] = {}
    for theme, requete in requetes.items():
        mots = termes(requete)
        n = 0
        for doleance_id, contribution_id, texte in chercher(
            session, requete, run_decoupage
        ):
            texte = texte or ""
            trouves = termes_trouves(texte, requete) or mots[:1]
            session.add(
                Instance(
                    run_id=run.id,
                    contribution_id=contribution_id,
                    doleance_id=doleance_id,
                    external_doc_id=id_document(DOLEANCE, doleance_id),
                    topic_id=ids_par_theme[theme],
                    # sans les points de suspension de l'extrait : le verbatim
                    # doit se retrouver tel quel dans le texte (taxonomie/)
                    verbatim=fenetre(texte, trouves).strip(" …"),
                    summary=f"{DETECTEUR} : {', '.join(trouves)}",
                )
            )
            n += 1
        comptes[theme] = n
    session.flush()
    return comptes


def charger(
    session: Session,
    fichier: Path,
    *,
    auteur: str | None = None,
    activer: bool = False,
    chercher=doleances_repondant,
) -> tuple[Run, dict[str, int]]:
    """Charge le lexique, copie la grille dans un run à part, détecte.

    Raises:
        ValueError: lexique ou grille invalides, ou aucun découpage actif.
    """
    lexique = lire_lexique(fichier)
    grille = lire_grille(fichier.parent / lexique["grille"])
    verifier_cibles(lexique, grille)
    run_decoupage = run_actif(session, SEGMENTATION)
    if run_decoupage is None:
        raise ValueError(
            "aucun découpage actif : lancer `python -m segmentation` d'abord"
        )
    run = ouvrir_run(session, fichier, grille, lexique, run_decoupage, auteur=auteur)
    ids = charger_topics(session, grille["topics"], run.id)
    rattacher_parents(session, grille["topics"], ids, run.id)
    comptes = detecter(
        session, run, ids, lexique["requetes"], run_decoupage.id, chercher
    )
    if activer:
        activer_run(session, run)
    return run, comptes


def main(fichier: Path, *, auteur: str | None = None, activer: bool = False) -> None:
    engine = get_engine()
    check_connection(engine)
    with Session(engine) as session:
        run, comptes = charger(session, fichier, auteur=auteur, activer=activer)
        run_auteur, run_id = run.author, run.id
        session.commit()
    total = sum(comptes.values())
    for theme, n in comptes.items():
        print(f"  {theme:28s} {n:5d}")
    print(f"{total} rattachement(s) sur {len(comptes)} question(s) · run #{run_id}")
    print(f"run attribué à : {run_auteur}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("fichier", type=Path, help="le lexique *.mots_cles.json")
    parser.add_argument(
        "--auteur", default=None, help="auteur du run (résolu d'office sinon)"
    )
    parser.add_argument(
        "--activer", action="store_true", help="en faire la grille servie par l'app"
    )
    args = parser.parse_args()
    main(args.fichier, auteur=args.auteur, activer=args.activer)
