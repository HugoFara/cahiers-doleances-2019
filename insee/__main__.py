"""Rattache les contributions au code INSEE de leur commune.

    uv run python -m insee rattacher
        remplit `city` et `contribution.city_code` depuis les noms de fichiers.
        Idempotent.

    uv run python -m insee auditer
        rouvre les PDF de PATH_TO_DATA et croise les deux sources du code — le
        nom du fichier et l'en-tête — pour dire ce que vaut le rattachement.

    uv run python -m insee cog
        renseigne nom officiel, population et coordonnées depuis les extraits
        versionnés de `insee/referentiel/`, et pèse le corpus en habitants.
        Idempotent, sans réseau.

    uv run python -m insee referentiel --departements 01 28 39 53
        reconstruit ces extraits depuis l'INSEE. **Sort sur le réseau** et
        réécrit des fichiers versionnés : à ne lancer que délibérément.
"""

import argparse
import sys
from pathlib import Path

import fitz
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.db import check_connection, get_engine
from database.models import City
from extraction.without_ocr.config import ExtractionConfig
from extraction.without_ocr.discovery import list_pdfs
from extraction.without_ocr.settings import settings
from insee.codes import code_de_l_entete, code_du_nom_de_fichier, rapprocher
from insee.cog import (
    REFERENTIEL,
    communes_par_departement,
    enrichir,
    lire,
    population_par_departement,
    population_totale,
)
from insee.rattachement import couverture_par_departement, rattacher

CAHIERS_MONTRES = 5
DEPARTEMENTS_DU_CORPUS = ("01", "28", "39", "53")


def commande_rattacher() -> int:
    engine = get_engine()
    check_connection(engine)
    with Session(engine) as session:
        rapport = rattacher(session)
        session.commit()
        couverture = couverture_par_departement(session)

    if not rapport.contributions:
        print(
            "Aucune contribution en base. Lancer l'extraction "
            "(uv run python -m extraction.without_ocr) ?",
            file=sys.stderr,
        )
        return 1

    for ligne in rapport.resume():
        print(f"  {ligne}")
    if rapport.cahiers_sans_code:
        print("\n  Cahiers sans code INSEE (commune non renseignée à la source) :")
        for nom in rapport.cahiers_sans_code[:CAHIERS_MONTRES]:
            print(f"    {nom}")
        reste = len(rapport.cahiers_sans_code) - CAHIERS_MONTRES
        if reste > 0:
            print(f"    … et {reste} autres")

    print("\n  Par département :")
    for dep, (communes, contributions) in couverture.items():
        print(f"    {dep} : {communes:4d} commune(s) · {contributions:5d} contribution(s)")

    print(
        "\n  `city.name` est la graphie la plus riche rencontrée, pas le nom "
        "officiel.\n  `python -m insee cog` ajoute le nom officiel, la "
        "population et les coordonnées."
    )
    return 0


def entete(chemin: Path) -> str:
    """Texte des pages de metadata d'un cahier, celles que l'extraction saute."""
    doc = fitz.open(chemin)
    pages = min(ExtractionConfig.SKIP_FIRST_N_PAGES.value, doc.page_count)
    texte = "\n".join(doc[i].get_text() for i in range(pages))
    doc.close()
    return texte


def commande_auditer(dossier: Path | None) -> int:
    dossier = dossier or Path(settings.path_to_data)
    if not dossier.is_dir():
        print(f"{dossier} n'est pas un dossier — renseigner PATH_TO_DATA.", file=sys.stderr)
        return 1

    origines: dict[str, int] = {}
    desaccords: list[tuple[str, str, str]] = []
    codes: set[str] = set()
    for chemin in list_pdfs(dossier):
        du_fichier = code_du_nom_de_fichier(chemin.name)
        de_l_entete = code_de_l_entete(entete(chemin))
        code, origine = rapprocher(du_fichier, de_l_entete)
        origines[origine] = origines.get(origine, 0) + 1
        if origine == "desaccord":
            desaccords.append((chemin.name, du_fichier, de_l_entete))
        if code:
            codes.add(code)

    total = sum(origines.values())
    if not total:
        print(f"Aucun PDF dans {dossier}.", file=sys.stderr)
        return 1

    print(f"{total} cahier(s) · {len(codes)} commune(s) distincte(s)\n")
    libelles = {
        "accord": "code confirmé par le nom de fichier ET l'en-tête",
        "fichier": "code lu dans le nom de fichier seul (en-tête illisible)",
        "entete": "code lu dans l'en-tête seul",
        "desaccord": "les deux sources se contredisent",
        "aucun": "aucun code (commune non renseignée à la source)",
    }
    for origine in ("accord", "fichier", "entete", "desaccord", "aucun"):
        n = origines.get(origine, 0)
        if n:
            print(f"  {n:4d} ({n / total:3.0%}) — {libelles[origine]}")

    if desaccords:
        print("\n  À vérifier à la main :")
        for nom, a, b in desaccords[:CAHIERS_MONTRES]:
            print(f"    {nom} : fichier={a} en-tête={b}")
    return 0


def commande_cog() -> int:
    referentiel = lire()
    engine = get_engine()
    check_connection(engine)
    with Session(engine) as session:
        rapport = enrichir(session, referentiel)
        codes = {code for (code,) in session.execute(select(City.code))}
        session.commit()

    if not rapport.communes:
        print(
            "Aucune commune en base. Lancer `python -m insee rattacher` ?",
            file=sys.stderr,
        )
        return 1

    for ligne in rapport.resume():
        print(f"  {ligne}")

    if rapport.deleguees:
        print(
            "\n  Codes qui ne désignaient déjà plus une commune de plein exercice"
            "\n  au 1er janvier 2019 — le cahier a été déposé sous un code périmé :"
        )
        for code in rapport.deleguees:
            commune = referentiel[code]
            print(
                f"    {code} {commune.nom} → {commune.code_courant} "
                f"{commune.nom_courant}"
            )
    if rapport.disparues:
        print("\n  Communes du corpus disparues depuis 2019 :")
        for code in rapport.disparues:
            commune = referentiel[code]
            print(
                f"    {code} {commune.nom} → {commune.code_courant} "
                f"{commune.nom_courant}"
            )
    if rapport.renommees:
        print("\n  Communes renommées depuis 2019 (le code n'a pas bougé) :")
        for code in rapport.renommees:
            commune = referentiel[code]
            print(f"    {code} {commune.nom} → {commune.nom_courant}")
    if rapport.doubles:
        print(
            "\n  Doubles comptes de population — une commune déléguée et sa"
            "\n  parente sont toutes deux dans le corpus, leurs habitants se"
            "\n  recouvrent. Ils ne sont comptés qu'une fois :"
        )
        for delegue, parent in rapport.doubles:
            print(
                f"    {delegue} {referentiel[delegue].nom} ⊂ "
                f"{parent} {referentiel[parent].nom}"
            )

    print("\n  Couverture par département, en communes et en habitants :")
    communes_totales = communes_par_departement(referentiel)
    populations_totales = population_par_departement(referentiel)
    for departement in sorted(communes_totales):
        du_corpus = {
            code
            for code in codes
            if (commune := referentiel.get(code))
            and commune.departement == departement
        }
        total_communes = communes_totales[departement]
        total_population = populations_totales[departement]
        habitants = population_totale(du_corpus, referentiel)
        print(
            f"    {departement} : {len(du_corpus):4d}/{total_communes:4d} communes "
            f"({len(du_corpus) / total_communes:3.0%})"
            f" · {habitants:7d}/{total_population:7d} habitants "
            f"({habitants / total_population:3.0%})"
        )

    print(
        "\n  La part en habitants est ce qui manquait : 459 communes sur 1 494 ne"
        "\n  dit rien tant qu'une commune de 90 habitants y pèse autant qu'une de"
        "\n  16 000. Elle ne dit toujours pas que le corpus est représentatif —"
        "\n  seulement quelle part de la population a un cahier quelque part."
    )
    return 0


def commande_referentiel(departements: list[str], cache: Path) -> int:
    from insee.telecharger import construire

    print(
        f"  Téléchargement depuis l'INSEE — départements "
        f"{' '.join(departements)}.\n  Les fichiers de insee/referentiel/ vont "
        f"être réécrits.\n"
    )
    rapport = construire(REFERENTIEL, departements, cache)
    for ligne in rapport.resume():
        print(f"  {ligne}")
    if rapport.sans_population:
        print(f"\n  Sans population légale : {' '.join(rapport.sans_population)}")
    print(
        "\n  Penser à mettre à jour la date d'extraction dans"
        "\n  insee/referentiel/SOURCES.md."
    )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sous = parser.add_subparsers(dest="commande", required=True)
    sous.add_parser("rattacher", help="remplir city et contribution.city_code")
    sous.add_parser("cog", help="renseigner city depuis le référentiel INSEE")
    p_ref = sous.add_parser("referentiel", help="reconstruire les extraits (réseau)")
    p_ref.add_argument(
        "--departements",
        nargs="+",
        default=list(DEPARTEMENTS_DU_CORPUS),
        help="départements à retenir (défaut : ceux du corpus)",
    )
    p_ref.add_argument(
        "--cache",
        type=Path,
        default=Path("data/cache_insee"),
        help="où garder les fichiers bruts téléchargés",
    )
    p_audit = sous.add_parser("auditer", help="croiser les deux sources du code")
    p_audit.add_argument("--dossier", type=Path, help="dossier des PDF (défaut : PATH_TO_DATA)")

    args = parser.parse_args()
    if args.commande == "rattacher":
        sys.exit(commande_rattacher())
    if args.commande == "cog":
        sys.exit(commande_cog())
    if args.commande == "referentiel":
        sys.exit(commande_referentiel(args.departements, args.cache))
    sys.exit(commande_auditer(args.dossier))
