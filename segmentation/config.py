"""Signaux de rupture entre deux doléances, et seuils du découpage.

Séparé de la logique (`decoupage.py`) pour la même raison que
`extraction/without_ocr/config.py` : ce sont des paramètres métier, qu'on
ajuste en regardant le corpus, sans toucher à l'algorithme.

Ces règles ne lisent que le texte. C'est une contrainte subie, pas un choix :
tant que l'OCR ne rend pas la géométrie des lignes, on n'a ni le blanc vertical
ni le changement d'écriture, qui sont les deux meilleurs séparateurs d'un
registre. Les règles ci-dessous sont donc un plancher, pas une cible.
"""

import re

MOIS = (
    "janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|"
    "septembre|octobre|novembre|décembre|decembre"
)

# « Le 21 février 2019 », « Bourg-en-Bresse, le 3 mars 2019 ». Le lieu éventuel
# est court et sans ponctuation forte : une phrase qui contient une date ne doit
# pas déclencher de coupure, seule une ligne *entièrement* datée compte.
DATE = re.compile(
    rf"^(?:[A-Za-zÀ-ÿ][^,.!?]{{0,40}},\s*)?le\s+\d{{1,2}}(?:er)?\s+(?:{MOIS})\s+\d{{4}}\s*[,.]?\s*$",
    re.IGNORECASE,
)
DATE_NUMERIQUE = re.compile(
    r"^(?:[A-Za-zÀ-ÿ][^,.!?]{0,40},\s*)?(?:le\s+)?\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}\s*[,.]?\s*$",
    re.IGNORECASE,
)

# Apostrophe : « Monsieur le Président de la République, ». Bornée en longueur
# et sans ponctuation de phrase, sinon « Monsieur le Maire a répondu que… »
# ouvrirait une doléance au milieu d'un récit.
APOSTROPHE = re.compile(
    r"^(?:monsieur|madame|mesdames|messieurs|cher|chère|chers|chères)\b[^.!?]{0,60}[,:]?\s*$",
    re.IGNORECASE,
)

# Numérotation explicite d'un registre. On ne reconnaît pas « 1. », « 2° » seuls :
# le corpus est plein de listes de doléances numérotées *à l'intérieur* d'une
# même contribution, elles seraient coupées à chaque puce.
NUMEROTATION = re.compile(
    r"^(?:contribution|doléance|doleance|fiche|témoignage|temoignage)\s*"
    r"(?:n\s*[°ºo]?\s*|num[ée]ro\s*)?\d+",
    re.IGNORECASE,
)

# Filet de séparation tracé à la main ou reproduit par l'extraction.
SEPARATEUR = re.compile(r"^\s*([-_*=~—–])(?:\s*\1){4,}\s*$")

# Formule de politesse finale : la doléance se termine, la signature suit.
CLOTURE = re.compile(
    r"(je vous prie d'agr[ée]|veuillez agr[ée]|veuillez recevoir|veuillez croire|"
    r"dans l'attente|cordialement|salutations|respectueusement|sincèrement)",
    re.IGNORECASE,
)

# Après une formule de clôture, on rattache encore les lignes courtes qui
# suivent (nom, qualité, ville) avant de couper.
LIGNES_SIGNATURE = 4
LONGUEUR_LIGNE_SIGNATURE = 60

# Un signal d'ouverture ne coupe que si la doléance en cours a déjà ce volume.
# Sans ce garde-fou, « Le 21 février 2019 » puis « Monsieur le Préfet, » — l'en-tête
# normal d'une lettre — produirait deux doléances d'une ligne.
MIN_CARACTERES_DOLEANCE = 80
