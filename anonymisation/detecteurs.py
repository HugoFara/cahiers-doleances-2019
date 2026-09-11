"""Règles de repérage des données personnelles dans le texte d'une doléance.

**Ce que cette passe couvre et ce qu'elle ne couvre pas.** Elle repère des
formes : adresses électroniques, numéros de téléphone, IBAN, adresses postales,
et les noms **marqués** par une civilité ou posés en signature. Elle ne repère
pas un nom cité au fil du texte sans marqueur — « j'ai parlé à Bernard, du
service technique ». C'est pourtant le cas le plus fréquent, et il demande une
reconnaissance d'entités nommées, donc un modèle qui n'est pas ici.

**Le rappel de cette passe est inconnu.** Il ne se mesure que sur un échantillon
annoté à la main, et cet échantillon n'existe pas. Rien de ce module ne permet
donc de dire qu'une doléance est anonymisée — seulement qu'on y a trouvé telle
et telle forme.

Chaque détecteur est une fonction texte -> passages, ce qui rend l'ajout d'une
reconnaissance d'entités nommées mécanique le jour où le modèle sera choisi.
"""

import re
from dataclasses import dataclass

EMAIL = "email"
TELEPHONE = "telephone"
IBAN = "iban"
URL = "url"
ADRESSE = "adresse"
NOM = "nom"
ROLE_PUBLIC = "role_public"
INSTITUTION = "institution"
# Produit par la reconnaissance d'entités nommées (`ner.py`) : un lieu cité.
LIEU = "lieu"

# Genres qui ne sont pas des données personnelles : une adresse de mairie, une
# fonction publique ou un lieu cité n'ont pas à être occultés, et les occulter
# viderait les textes de leur objet. Ils l'emportent sur les autres genres lors
# de la fusion. Le lieu qui identifie à lui seul (« la seule infirmière du
# village ») est la réidentification contextuelle du plan, hors de portée ici.
NON_PERSONNELS = frozenset({ROLE_PUBLIC, INSTITUTION, LIEU})


@dataclass(frozen=True)
class Passage:
    """Un passage repéré, par ses offsets dans le texte d'origine."""

    debut: int
    fin: int
    genre: str
    detecteur: str


_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]{2,}\b")

# Adresses institutionnelles : celles des mairies, préfectures et du dispositif
# lui-même. Elles sont publiques par destination. Le courriel d'un particulier,
# lui, ne se distingue par aucune forme — d'où la file de relecture.
_EMAIL_INSTITUTION = re.compile(
    r"\b[\w.+-]*(?:mairie|commune|prefecture|préfecture|granddebat|"
    r"grand-debat|cabinet|secretariat|secrétariat|accueil|contact)[\w.+-]*"
    r"@[\w-]+\.[\w.-]{2,}\b"
    r"|\b[\w.+-]+@[\w.-]*(?:mairie|ville|commune|granddebat|grand-debat)[\w.-]*"
    r"\.[\w.-]{2,}\b"
    r"|\b[\w.+-]+@[\w.-]+\.gouv\.fr\b",
    re.IGNORECASE,
)

# Numéros français, avec les séparateurs qu'on trouve dans les cahiers :
# 06 12 34 56 78, 06.12.34.56.78, 0612345678, +33 6 12 34 56 78.
_TELEPHONE = re.compile(r"(?<!\d)(?:\+33[\s.-]?|0)\d(?:[\s.-]?\d{2}){4}(?!\d)")

_IBAN = re.compile(r"\bFR\d{2}(?:[\s]?[A-Z0-9]{4}){5}[\s]?[A-Z0-9]{3}\b")

_URL = re.compile(r"\bhttps?://\S+|\bwww\.[\w-]+\.[\w.-]+\b")

# « 12 rue des Lilas », « 3 bis avenue de la Gare ». Le numéro est ce qui
# distingue une adresse d'une simple mention de rue.
_VOIES = (
    "rue|avenue|av|boulevard|bd|impasse|allee|allée|chemin|route|place|quai|"
    "lotissement|hameau|residence|résidence|cours|square|voie|sentier"
)
# Mots qui ouvrent une nouvelle proposition : sans eux, « 12 rue des Lilas où
# habite M. Dupont » serait capturé en entier comme une adresse, et le nom
# disparaîtrait dans le passage voisin au lieu d'être compté comme un nom.
# Les articles en sont volontairement absents : « avenue de la Gare », « rue du
# Général Leclerc » les contiennent, les couper amputerait l'adresse.
_ARRET = (
    "ou|où|que|qui|quand|dans|chez|et|avec|pour|par|sous|depuis|car|mais|"
    "je|j|tu|il|elle|on|nous|vous|ils|elles|est|sont|etait|était"
)
_ADRESSE = re.compile(
    rf"\b\d{{1,4}}\s*(?:bis|ter|quater)?\s+(?:{_VOIES})\b"
    rf"(?:\s+(?!(?:{_ARRET})\b)[\w'’-]+){{0,4}}",
    re.IGNORECASE,
)

# « M. Dupont », « Madame Marie-Claire Bernard ». La civilité est le marqueur ;
# sans elle, distinguer un patronyme d'un nom de commune demande un modèle.
_CIVILITE = re.compile(
    r"\b(?:M\.|MM\.|Mme|Mmes|Mlle|Monsieur|Madame|Mademoiselle|Messieurs|Mesdames)"
    r"(?:\s+[A-ZÀ-Ÿ][\w'’-]+){1,3}"
)

# Fonctions publiques : citées dans leur rôle, elles n'ont pas à être occultées.
# Ce sont des **rôles**, pas des noms : la liste ne vieillit pas avec les
# personnes, et c'est à la relecture de trancher les cas limites.
_ROLE_PUBLIC = re.compile(
    r"\b(?:le\s+)?(?:Président\s+de\s+la\s+République|Premier\s+ministre|"
    r"ministre\s+(?:de|des|du)\s+[\w'’\s-]{3,30}|Préfet|Préfète|Maire|"
    r"député|députée|sénateur|sénatrice|Assemblée\s+nationale|Sénat)\b",
    re.IGNORECASE,
)

_REGLES: list[tuple[str, str, re.Pattern[str]]] = [
    (INSTITUTION, "email_institution", _EMAIL_INSTITUTION),
    (EMAIL, "regex_email", _EMAIL),
    (TELEPHONE, "regex_telephone", _TELEPHONE),
    (IBAN, "regex_iban", _IBAN),
    (URL, "regex_url", _URL),
    (ADRESSE, "regex_adresse", _ADRESSE),
    (NOM, "civilite", _CIVILITE),
    (ROLE_PUBLIC, "role_public", _ROLE_PUBLIC),
]

# Un nom en signature tient sur une ligne courte ; au-delà, c'est une phrase.
LONGUEUR_SIGNATURE = 40
# On ne regarde que la fin de la doléance : c'est là que se trouve la signature.
LIGNES_FIN_EXAMINEES = 4


def formes(texte: str) -> list[Passage]:
    """Passages repérés par les règles de forme."""
    trouves = []
    for genre, detecteur, motif in _REGLES:
        for occurrence in motif.finditer(texte or ""):
            trouves.append(
                Passage(occurrence.start(), occurrence.end(), genre, detecteur)
            )
    return trouves


def signatures(texte: str) -> list[Passage]:
    """Lignes de fin qui ont la forme d'une signature.

    Dans un registre, le nom de l'auteur est presque toujours seul sur une ligne
    courte à la fin de sa contribution. La règle est grossière et produit des
    faux positifs — un slogan court en fin de texte y passera — ce qui est le
    bon sens de l'erreur : un faux positif se lève à la relecture, un nom manqué
    est une fuite.
    """
    if not texte:
        return []
    lignes = texte.split("\n")
    # La première ligne d'une doléance l'ouvre — en-tête, date, apostrophe — elle
    # ne la signe pas. Sans cette exclusion, toute doléance de deux lignes verrait
    # son ouverture prise pour une signature.
    candidates = lignes[max(1, len(lignes) - LIGNES_FIN_EXAMINEES) :]
    trouves = []
    position = len(texte)
    for ligne in reversed(candidates):
        debut = position - len(ligne)
        propre = ligne.strip()
        if propre and len(propre) <= LONGUEUR_SIGNATURE and _ressemble_a_un_nom(propre):
            decalage = len(ligne) - len(ligne.lstrip())
            trouves.append(
                Passage(
                    debut + decalage, debut + decalage + len(propre), NOM, "signature"
                )
            )
        position = debut - 1  # le saut de ligne
    return sorted(trouves, key=lambda p: p.debut)


def _ressemble_a_un_nom(ligne: str) -> bool:
    """Une ligne courte, sans ponctuation de phrase, dont un mot est capitalisé."""
    if any(c in ligne for c in ".!?;:"):
        return False
    mots = ligne.split()
    if not 1 <= len(mots) <= 4:
        return False
    return any(mot[:1].isupper() for mot in mots)


def fusionner(passages: list[Passage]) -> list[Passage]:
    """Fusionne les passages qui se chevauchent, le genre le plus fort l'emportant.

    Un même texte peut être vu par deux règles — « Monsieur le Maire » est à la
    fois une civilité et un rôle public, `mairie@x.fr` est à la fois un courriel
    et une adresse institutionnelle. Les genres non personnels l'emportent : une
    fonction publique ou une adresse de mairie n'a pas à être occultée, et
    l'occulter viderait les textes de leur objet.
    """
    if not passages:
        return []
    ordonnes = sorted(passages, key=lambda p: (p.debut, -p.fin))
    fusionnes = [ordonnes[0]]
    for passage in ordonnes[1:]:
        dernier = fusionnes[-1]
        if passage.debut < dernier.fin:
            gagnant = next(
                (p for p in (dernier, passage) if p.genre in NON_PERSONNELS), dernier
            )
            fusionnes[-1] = Passage(
                dernier.debut,
                max(dernier.fin, passage.fin),
                gagnant.genre,
                gagnant.detecteur,
            )
        else:
            fusionnes.append(passage)
    return fusionnes


def detecter(texte: str) -> list[Passage]:
    """Tous les passages repérés dans une doléance, chevauchements fusionnés."""
    return fusionner(formes(texte) + signatures(texte))
