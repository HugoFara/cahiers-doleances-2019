"""Rattache les contributions au code INSEE de leur commune.

    uv run python -m insee rattacher
        remplit `city` et `contribution.city_code` depuis les noms de fichiers.
        Idempotent.

    uv run python -m insee auditer
        rouvre les PDF de PATH_TO_DATA et croise les deux sources du code — le
        nom du fichier et l'en-tête — pour dire ce que vaut le rattachement.
"""

import argparse
import sys
from pathlib import Path

import fitz
from sqlalchemy.orm import Session

from database.db import check_connection, get_engine
from extraction.without_ocr.config import ExtractionConfig
from extraction.without_ocr.settings import settings
from insee.codes import code_de_l_entete, code_du_nom_de_fichier, rapprocher
from insee.rattachement import couverture_par_departement, rattacher

CAHIERS_MONTRES = 5


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
        "officiel.\n  Population et coordonnées restent NULL : elles demandent "
        "le Code officiel\n  géographique, sans lequel il n'y a ni pondération "
        "par population ni carte."
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
    for chemin in sorted(dossier.glob("*.pdf")):
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sous = parser.add_subparsers(dest="commande", required=True)
    sous.add_parser("rattacher", help="remplir city et contribution.city_code")
    p_audit = sous.add_parser("auditer", help="croiser les deux sources du code")
    p_audit.add_argument("--dossier", type=Path, help="dossier des PDF (défaut : PATH_TO_DATA)")

    args = parser.parse_args()
    if args.commande == "rattacher":
        sys.exit(commande_rattacher())
    sys.exit(commande_auditer(args.dossier))
