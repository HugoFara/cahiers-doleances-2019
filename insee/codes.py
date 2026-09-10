"""Lecture du code INSEE d'un cahier, depuis ses deux sources.

La commune est aujourd'hui une chaîne parsée de l'en-tête du PDF, et la même
commune n'y est pas toujours écrite pareil — d'où le regroupement de graphies de
`gradio_app/communes.py`, qui rattrape après coup ce qui aurait dû être une clé.
Le code INSEE est cette clé : stable, officiel, et il porte le département.

Il est présent **deux fois** dans les données, ce qui est une chance :

- dans le **nom du fichier**, `CC_<code postal>_<AAMMJJ>_<INSEE>_MD_<id>.pdf` ;
- dans l'**en-tête du PDF**, `BOURG-EN-BRESSE - 01053`, où le parsing actuel le
  voit déjà et le jette (`ExtractionConfig.CITY_PATTERN` capture le nom et
  ignore le groupe de cinq chiffres qui suit).

Deux sources indépendantes permettent de se contrôler l'une l'autre : un code
confirmé par les deux vaut mieux qu'un code lu une fois, et les désaccords
signalent les cahiers à regarder à la main.
"""

import re

# `CC_01000_190304_01053_MD_15462.pdf` : code postal, date, INSEE, service, id.
NOM_DE_FICHIER = re.compile(
    r"^CC_(?P<code_postal>\d{5})_(?P<date>\d{6})_(?P<insee>\d[0-9AB]\d{3})_"
    r"(?P<service>[A-Z]{2})_(?P<identifiant>\d+)\.pdf$",
    re.IGNORECASE,
)

# `BOURG-EN-BRESSE - 01053`, `GUEREINS-01183`, `MONTCEAUX- 01258` : l'espacement
# autour du tiret varie d'un cahier à l'autre.
ENTETE = re.compile(
    r"Cahier\s+citoyen\s*\n\s*[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-'’\s]*?\s*-\s*(\d[0-9AB]\d{3})\b",
    re.IGNORECASE,
)

# Code de remplissage employé à la source quand la commune n'est pas renseignée :
# cahier remis sans commune, ou en-tête laissé vide. Ce n'est pas un code.
CODE_ABSENT = "00000"


def normaliser(code: str | None) -> str | None:
    """Met un code en forme, ou renvoie ``None`` s'il n'en est pas un.

    Args:
        code: le code brut, tel que lu.

    Returns:
        Le code en majuscules (2A/2B pour la Corse), ou ``None``.
    """
    if not code:
        return None
    propre = code.strip().upper()
    if len(propre) != 5 or propre == CODE_ABSENT:
        return None
    return propre


def code_du_nom_de_fichier(nom: str) -> str | None:
    """Code INSEE porté par le nom du fichier, s'il y en a un."""
    trouve = NOM_DE_FICHIER.match(nom or "")
    return normaliser(trouve.group("insee")) if trouve else None


def code_de_l_entete(texte: str) -> str | None:
    """Code INSEE porté par l'en-tête du cahier, s'il y en a un."""
    trouve = ENTETE.search(texte or "")
    return normaliser(trouve.group(1)) if trouve else None


def departement(code: str) -> str | None:
    """Département d'un code INSEE.

    Corse (2A/2B) et outre-mer (971 à 976) ont des préfixes à part : les traiter
    comme les autres rangerait Saint-Denis de La Réunion dans l'Aisne.

    Args:
        code: un code INSEE à cinq caractères.

    Returns:
        Le code du département, ou ``None`` si le code est invalide.
    """
    code = normaliser(code)
    if code is None:
        return None
    if code.startswith(("2A", "2B")):
        return code[:2]
    if code.startswith("97") or code.startswith("98"):
        return code[:3]
    return code[:2]


def rapprocher(du_fichier: str | None, de_l_entete: str | None) -> tuple[str | None, str]:
    """Croise les deux sources et dit ce qu'on en retient.

    Le nom de fichier l'emporte en cas de désaccord : il vient du système qui a
    déposé le cahier, alors que l'en-tête est un champ rempli à la main puis
    passé dans une extraction de texte. Mais le désaccord est signalé — il
    désigne exactement les cahiers à vérifier.

    Args:
        du_fichier: code lu dans le nom du fichier.
        de_l_entete: code lu dans l'en-tête.

    Returns:
        (code retenu ou ``None``, origine parmi « accord », « fichier »,
        « entete », « desaccord », « aucun »).
    """
    if du_fichier and de_l_entete:
        return (du_fichier, "accord" if du_fichier == de_l_entete else "desaccord")
    if du_fichier:
        return du_fichier, "fichier"
    if de_l_entete:
        return de_l_entete, "entete"
    return None, "aucun"
