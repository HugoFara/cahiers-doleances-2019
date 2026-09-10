"""Constitue et exploite le jeu de référence annoté à la main.

    uv run python -m reference tirer --taille 60 --nom v1
        tire un échantillon stratifié de cahiers et écrit le fichier de travail
        `data/reference/v1.csv` — texte compris, donc **jamais commité**.

    uv run python -m reference figer --nom v1
        transforme le fichier annoté en étalon `reference/etalon/v1.csv`, où le
        texte est remplacé par une empreinte : versionnable sans emporter les
        écrits des contributeurs dans un dépôt public.

    uv run python -m reference evaluer --nom v1
        mesure le découpage servi contre l'étalon, globalement et par strate.
"""

import argparse
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.db import check_connection, get_engine
from database.models import Doleance
from database.runs import SEGMENTATION, run_actif
from reference.echantillon import tirer
from reference.etalon import (
    RACINE_ETALON,
    RACINE_TRAVAIL,
    EtalonDesaligne,
    ecrire_fichier_de_travail,
    ecrire_metadonnees,
    figer,
    lignes_des_cahiers,
    lire_etalon,
    lire_metadonnees,
    verifier_alignement,
)
from reference.evaluation import agreger, evaluer_cahier

GRAINE_PAR_DEFAUT = 20260910


def chemins(nom: str) -> tuple[Path, Path, Path]:
    """(fichier de travail, étalon figé, métadonnées du tirage)."""
    return (
        RACINE_TRAVAIL / f"{nom}.csv",
        RACINE_ETALON / f"{nom}.csv",
        RACINE_ETALON / f"{nom}.json",
    )


def commande_tirer(nom: str, taille: int, graine: int) -> int:
    travail, _, meta = chemins(nom)
    if travail.exists():
        print(f"{travail} existe déjà — le supprimer pour retirer.", file=sys.stderr)
        return 1

    engine = get_engine()
    check_connection(engine)
    with Session(engine) as session:
        run = run_actif(session, SEGMENTATION)
        if run is None:
            print(
                "Aucun découpage servi : la stratification a besoin d'un run "
                "(uv run python -m segmentation).",
                file=sys.stderr,
            )
            return 1
        run_id, run_label = run.id, run.label
        cahiers, poids = tirer(session, run_id, taille, graine)
        if not cahiers:
            print("Aucun cahier à tirer.", file=sys.stderr)
            return 1
        lignes = lignes_des_cahiers(session, [pdf for pdf, _ in cahiers])
        total = ecrire_fichier_de_travail(travail, lignes)

    ecrire_metadonnees(meta, {
        "nom": nom,
        "tire_le": datetime.now(UTC).date().isoformat(),
        "graine": graine,
        "taille_demandee": taille,
        "run_de_stratification": {"id": run_id, "label": run_label},
        "strates": {pdf: strate for pdf, strate in cahiers},
        "poids_par_strate": poids,
    })

    print(f"{len(cahiers)} cahier(s) · {total} ligne(s) -> {travail}")
    for nom_strate, w in sorted(poids.items()):
        tires = sum(1 for _, s in cahiers if s == nom_strate)
        print(f"  strate « {nom_strate} » : {tires} tiré(s), poids {w:.1f}")
    print(
        "\nÀ annoter : mettre 1 dans `debut_doleance` sur la première ligne de "
        "chaque doléance.\nCe fichier contient le texte des cahiers : il ne doit "
        "pas être commité (data/ est ignoré)."
    )
    return 0


def commande_figer(nom: str) -> int:
    travail, etalon, _ = chemins(nom)
    if not travail.exists():
        print(f"{travail} introuvable — tirer l'échantillon d'abord.", file=sys.stderr)
        return 1
    debuts = figer(travail, etalon)
    print(f"{debuts} début(s) de doléance -> {etalon}")
    if debuts == 0:
        print("Aucune annotation : le fichier de travail a-t-il été rempli ?")
    return 0


def frontieres_stockees(
    session: Session, run_id: int, cahiers: list[str]
) -> dict[str, set[int]]:
    """Où le découpage stocké a posé ses frontières, en indices de ligne.

    Reconstruit depuis les doléances enregistrées plutôt qu'en rejouant les
    règles : c'est ce run-là qu'on évalue, avec la configuration qu'il avait, et
    non le code d'aujourd'hui. C'est ce qui rend deux runs comparables.

    L'invariant du découpage — il partitionne les lignes sans en perdre — est ce
    qui permet de retrouver les positions en cumulant les longueurs.
    """
    lignes = session.scalars(
        select(Doleance)
        .where(Doleance.run_id == run_id, Doleance.pdf_name.in_(cahiers))
        .order_by(Doleance.pdf_name, Doleance.position)
    )
    frontieres: dict[str, set[int]] = defaultdict(set)
    position: dict[str, int] = defaultdict(int)
    for doleance in lignes:
        frontieres[doleance.pdf_name].add(position[doleance.pdf_name])
        position[doleance.pdf_name] += len((doleance.text or "").split("\n"))
    return dict(frontieres)


def commande_evaluer(nom: str) -> int:
    _, chemin_etalon, chemin_meta = chemins(nom)
    if not chemin_etalon.exists():
        print(f"{chemin_etalon} introuvable — figer l'étalon d'abord.", file=sys.stderr)
        return 1

    etalon = lire_etalon(chemin_etalon)
    meta = lire_metadonnees(chemin_meta) if chemin_meta.exists() else {}
    strates = meta.get("strates", {})
    poids_strate = meta.get("poids_par_strate", {})
    cahiers = sorted({ligne.pdf_name for ligne in etalon})

    engine = get_engine()
    check_connection(engine)
    with Session(engine) as session:
        run = run_actif(session, SEGMENTATION)
        if run is None:
            print("Aucun découpage servi à évaluer.", file=sys.stderr)
            return 1
        run_id, run_label = run.id, run.label
        lignes_par_cahier = lignes_des_cahiers(session, cahiers)
        try:
            verifier_alignement(etalon, lignes_par_cahier)
        except EtalonDesaligne as erreur:
            print(erreur, file=sys.stderr)
            return 1
        trouvees = frontieres_stockees(session, run_id, cahiers)

    hors_run = [c for c in cahiers if c not in trouvees]
    if hors_run:
        print(
            f"{len(hors_run)} cahier(s) de l'étalon ne sont pas découpés dans le "
            f"run servi et sont écartés — le run couvre-t-il tout le corpus ?",
            file=sys.stderr,
        )
        cahiers = [c for c in cahiers if c in trouvees]
        if not cahiers:
            return 1

    attendues: dict[str, set[int]] = {c: set() for c in cahiers}
    for ligne in etalon:
        if ligne.debut_doleance and ligne.pdf_name in attendues:
            attendues[ligne.pdf_name].add(ligne.ligne)

    resultats = {
        c: evaluer_cahier(attendues[c], trouvees[c], len(lignes_par_cahier[c]))
        for c in cahiers
    }
    poids = {c: poids_strate.get(strates.get(c, ""), 1.0) for c in cahiers}

    print(f"étalon « {nom} » · découpage servi : #{run_id} « {run_label} »")
    print(f"population  : {agreger(resultats, poids).resume()}")
    print(f"échantillon : {agreger(resultats).resume()}")
    for nom_strate in sorted(set(strates.values())):
        dedans = {c: r for c, r in resultats.items() if strates.get(c) == nom_strate}
        if dedans:
            print(f"  « {nom_strate} » : {agreger(dedans).resume()}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--nom", default="v1", help="nom du jeu de référence")
    sous = parser.add_subparsers(dest="commande", required=True)

    p_tirer = sous.add_parser("tirer", help="tirer l'échantillon à annoter")
    p_tirer.add_argument("--taille", type=int, default=60, help="nombre de cahiers")
    p_tirer.add_argument(
        "--graine", type=int, default=GRAINE_PAR_DEFAUT, help="graine du tirage"
    )
    sous.add_parser("figer", help="transformer le fichier annoté en étalon commitable")
    sous.add_parser("evaluer", help="mesurer le découpage servi contre l'étalon")

    args = parser.parse_args()
    if args.commande == "tirer":
        sys.exit(commande_tirer(args.nom, args.taille, args.graine))
    if args.commande == "figer":
        sys.exit(commande_figer(args.nom))
    sys.exit(commande_evaluer(args.nom))
