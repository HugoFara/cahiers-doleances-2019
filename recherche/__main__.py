"""Cherche dans le texte des doléances.

    uv run python -m recherche éoliennes
    uv run python -m recherche "pouvoir d'achat" --limite 5
    uv run python -m recherche 'impôt -taxe'

Syntaxe : les mots s'ajoutent, les guillemets font une expression exacte, `or`
alterne, un tiret exclut. Aucune requête ne lève d'erreur de syntaxe.

Les extraits sont **caviardés** : les passages personnels repérés par
`python -m anonymisation` y sont occultés, et un passage non relu l'est aussi.
`--brut` les montre en clair, pour un usage interne seulement.
"""

import argparse
import sys

from sqlalchemy.orm import Session

from database.db import check_connection, get_engine
from recherche.config import LIMITE_DEFAUT
from recherche.requetes import RequeteVide, chercher, compter


def main(requete: str, limite: int, brut: bool) -> int:
    engine = get_engine()
    check_connection(engine)
    with Session(engine) as session:
        try:
            total = compter(session, requete)
            resultats = chercher(session, requete, limite, caviardage=not brut)
        except RequeteVide as erreur:
            print(erreur, file=sys.stderr)
            return 1

    if not total:
        print(f"Aucune doléance ne répond à « {requete} ».")
        print(
            "\n  La recherche ne porte que sur le découpage actif, et le corpus\n"
            "  découpé n'est que sa moitié dactylographiée."
        )
        return 0

    montres = len(resultats)
    print(f"{total} doléance(s) · {montres} montrée(s)\n")
    for resultat in resultats:
        print(f"  {resultat.resume()}")
        print(f"    {resultat.extrait}\n")

    if not brut:
        print(
            "  Extraits caviardés : les passages personnels repérés sont occultés,\n"
            "  et un passage non relu l'est aussi. Ce n'est pas une anonymisation\n"
            "  (voir anonymisation/README.md)."
        )
    else:
        print("  ⚠ Extraits NON caviardés — usage interne.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("requete", nargs="+", help="les termes cherchés")
    parser.add_argument("--limite", type=int, default=LIMITE_DEFAUT)
    parser.add_argument(
        "--brut", action="store_true", help="ne pas caviarder (usage interne)"
    )
    args = parser.parse_args()
    sys.exit(main(" ".join(args.requete), args.limite, args.brut))
