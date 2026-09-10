"""Regroupement des graphies d'une même commune.

La commune est parsée de l'en-tête des PDF, et la même commune n'y est pas
toujours écrite pareil : « AHUILLE » et « AHUILLÉ », « FONTENAY SUR CONIE » et
« FONTENAY-SUR-CONIE ». Sans regroupement, la liste déroulante de l'app propose
deux entrées pour une seule commune, chacune ne montrant qu'une partie des
contributions.

Les fonctions ici sont volontairement sans base de données : elles travaillent
sur la liste des graphies, ce qui les rend testables sans PostgreSQL.
"""

import unicodedata

# Séparateurs interchangeables d'une graphie à l'autre (« SUR CONIE » /
# « SUR-CONIE », « L HUISSERIE » / « L'HUISSERIE »).
SEPARATEURS = "-'’"


def cle_commune(nom: str) -> str:
    """Clé de regroupement d'une graphie : sans accent ni séparateur, en majuscules.

    Args:
        nom: une graphie telle qu'extraite du PDF.

    Returns:
        La clé sous laquelle toutes les graphies d'une même commune se rejoignent.
    """
    decompose = unicodedata.normalize("NFKD", nom)
    sans_accent = "".join(c for c in decompose if not unicodedata.combining(c))
    for sep in SEPARATEURS:
        sans_accent = sans_accent.replace(sep, " ")
    return " ".join(sans_accent.upper().split())


def _richesse(nom: str) -> int:
    """Nombre de caractères porteurs d'information typographique.

    Sert à départager les graphies d'un même groupe : on préfère afficher
    « TORCÉ-VIVIERS-EN-CHARNIE » à « TORCE VIVIERS EN CHARNIE ».
    """
    return sum(1 for c in nom if not (c.isascii() and (c.isalnum() or c == " ")))


def regrouper(graphies: list[str]) -> dict[str, list[str]]:
    """Regroupe les graphies par commune.

    Args:
        graphies: toutes les valeurs de ``contribution.city`` rencontrées.

    Returns:
        ``{graphie affichée: toutes les graphies de cette commune}``, trié par
        graphie affichée. La graphie affichée est la plus riche du groupe
        (accents et traits d'union conservés), à égalité la première dans
        l'ordre alphabétique.
    """
    groupes: dict[str, list[str]] = {}
    for graphie in graphies:
        propre = graphie.strip()
        if propre:
            groupes.setdefault(cle_commune(propre), []).append(propre)

    affichage = {}
    for variantes in groupes.values():
        uniques = sorted(set(variantes))
        representant = max(uniques, key=lambda n: (_richesse(n), -uniques.index(n)))
        affichage[representant] = uniques
    return dict(sorted(affichage.items()))


def libelle_commune(officiel: str | None, graphie: str | None, code: str) -> str:
    """Le nom sous lequel une commune s'affiche, du plus fiable au moins.

    Le nom officiel du Code officiel géographique d'abord, la graphie de
    l'en-tête du cahier ensuite, le code seul en dernier — jamais rien. Cent
    cinquante-trois communes du corpus n'ont aucune graphie : sans ce dernier
    repli, elles n'auraient pas d'entrée dans le sélecteur, et leurs
    contributions ne seraient atteignables par aucun chemin.

    Le code reste affiché entre parenthèses dans tous les cas : c'est lui
    l'identifiant, et deux communes peuvent porter le même nom.

    Args:
        officiel: le libellé du Code officiel géographique, s'il est chargé.
        graphie: la graphie retenue dans le corpus, si l'en-tête était lisible.
        code: le code INSEE, toujours présent.

    Returns:
        Le libellé à afficher.
    """
    return f"{officiel or graphie or code} ({code})"
