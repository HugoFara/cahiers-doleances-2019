"""Les signaux de support et d'auteur, repérés dans le texte d'une doléance.

**Où compte la position.** Une formule d'appel ouvre un texte, une formule de
politesse le ferme, une signature de maire est en bas. Cherchées partout, ces
formes se retrouvent au milieu d'une citation ou d'une doléance voisine mal
séparée : « Monsieur le Maire ne répond jamais » n'ouvre pas un courrier. Les
règles qui n'ont de sens qu'à un endroit ne sont donc appliquées qu'à cet
endroit — même raisonnement que `anonymisation.detecteurs.signatures`, qui ne
regarde que les dernières lignes.

**Où compte la casse.** `re.IGNORECASE` s'applique aussi aux classes de
caractères : `association\\s+[A-ZÀ-Ÿ]` cherché sans casse capture « dans une
association ou ». La première version de ces règles annonçait 17 % de coupures de
presse parce que `Le Monde` sans casse trouvait « tout le monde ». Les motifs qui
s'appuient sur une majuscule sont donc écrits sensibles à la casse, et énumèrent
les deux graphies quand il le faut.

Chaque signal est une fonction texte -> booléen : ajouter une reconnaissance
d'entités nommées, ou une règle tirée de la géométrie de l'OCR, se fera en
allongeant la table `SIGNAUX` sans toucher au classement.
"""

import re

# Zones examinées, en caractères. Assez larges pour couvrir un en-tête de
# courrier avec adresse et référence, assez étroites pour ne pas couvrir la
# doléance voisine quand le découpage a manqué une rupture.
OUVERTURE = 500
CLOTURE = 600

# --- courrier ------------------------------------------------------------

_APPEL = re.compile(
    r"\b(?:Monsieur\s+l[ea]\s+(?:Président|Maire|Préfet|Ministre|Députée?)"
    r"|Madame\s+l[ea]\s+(?:Présidente|Maire|Préfète|Ministre|Députée?)"
    r"|Madame,?\s*(?:et\s+)?Monsieur|Monsieur,?\s*(?:et\s+)?Madame"
    r"|Mesdames,?\s*Messieurs)"
)
_OBJET = re.compile(r"(?:^|\n)\s*Objet\s*:", re.IGNORECASE)
_POLITESSE = re.compile(
    r"(?:Veuillez\s+(?:agréer|croire|recevoir)"
    r"|[Jj]e\s+vous\s+prie\s+d[e’']\s?agréer"
    r"|sentiments\s+(?:distingués|respectueux|dévoués|les\s+meilleurs)"
    r"|salutations\s+(?:distinguées|respectueuses)"
    r"|l[’']expression\s+de\s+m[ae]s?\s+(?:haute\s+considération|sentiments))",
    re.IGNORECASE,
)

# --- apparat : ce que la mairie écrit *autour* des contributions ----------

_OBJET_TRANSMISSION = re.compile(
    r"(?:^|\n)\s*Objet\s*:[^\n]{0,80}"
    r"(?:cahier|doléance|doleance|expression|contribution|grand\s+débat)",
    re.IGNORECASE,
)
_FORMULE_TRANSMISSION = re.compile(
    r"\b(?:vous\s+(?:trouverez|prie\s+de\s+trouver)|je\s+vous\s+(?:transmets|adresse|"
    r"fais\s+parvenir)|ci-joint|veuillez\s+trouver)\b[^.\n]{0,120}"
    r"(?:cahier|registre|contributions?|doléances?)",
    re.IGNORECASE,
)

# --- institution / élu ---------------------------------------------------

_SIGNATURE_ELU = re.compile(
    r"(?:^|\n)\s*(?:L[ea]\s+Maire|Le\s+Premier\s+adjoint|L[ea]\s+Maire\s+de"
    r"|Pour\s+le\s+conseil\s+municipal|L[ea]\s+Président[e]?\s+d[eu])\b"
)
_SOUSSIGNE_ELU = re.compile(r"[Jj]e\s+soussign[ée]s?[^.\n]{0,60}\bMaire\b")
_CONSEIL_MUNICIPAL = re.compile(
    r"\b(?:le\s+conseil\s+municipal|délibération\s+du\s+conseil|séance\s+du\s+conseil)",
    re.IGNORECASE,
)
# En-tête de mairie : présent aussi sur les cahiers *fournis* par la commune,
# donc jamais suffisant seul pour conclure à un auteur institutionnel.
_ENTETE_MAIRIE = re.compile(
    r"(?:^|\n)\s*(?:MAIRIE|Mairie\s+de|COMMUNE\s+DE|Commune\s+de|VILLE\s+DE"
    r"|Ville\s+de|Hôtel\s+de\s+[Vv]ille|Cabinet\s+du\s+Maire)\b"
)

# --- collectif -----------------------------------------------------------

_SOUSSIGNES_PLURIEL = re.compile(r"[Nn]ous,?\s+soussign[ée]s")
_NOUS_COLLECTIF = re.compile(
    r"\b[Nn]ous,?\s+(?:les\s+)?(?:habitants|citoyens|usagers|membres|adhérents"
    r"|salariés|retraités|agriculteurs|commerçants|parents)\b"
)
_ORGANISATION = re.compile(
    r"\b(?:l[’']association\s+[A-ZÀ-Ÿ]|le\s+syndicat\s+[A-ZÀ-Ÿ]"
    r"|la\s+section\s+(?:syndicale|locale)|le\s+collectif\s+[A-ZÀ-Ÿ]"
    r"|notre\s+(?:association|syndicat|collectif|fédération)"
    r"|la\s+fédération\s+[A-ZÀ-Ÿ]|le\s+comité\s+[A-ZÀ-Ÿ])"
)
_PETITION = re.compile(r"\b[Pp]étition\b")

# --- formulaire ----------------------------------------------------------

_FORMULAIRE = re.compile(
    r"(?:^|\n)\s*(?:Nom\s+et\s+prénom|Nom\s*:|Prénom\s*:)\s*(?:\n|$)"
    r"|[Ff]ormulaire\s+à\s+remplir|[Rr]ayez\s+la\s+mention"
)

# --- individu ------------------------------------------------------------

# Les formes élidées comptent autant que les autres : sans « j'ai », « j'habite »,
# la première personne était sous-comptée de six points.
_PREMIERE_PERSONNE = re.compile(
    r"\b[Jj]e\s+(?:suis|pense|demande|propose|souhaite|trouve|vis|vais|veux"
    r"|travaille|paie|paye|gagne|constate|estime|voudrais|aimerais|crois"
    r"|considère|réclame|dénonce|refuse|dois|peux|sais|comprends|subis)\b"
    r"|\b[Jj][’']\s?(?:ai|aimerais|estime|espère|habite|attends|exerce"
    r"|observe|entends|écris|ajoute|insiste|approuve)\b"
    r"|\b(?:à\s+titre\s+personnel|en\s+tant\s+que\s+(?:citoyen|citoyenne"
    r"|retraité|retraitée|salarié|salariée|artisan|agriculteur|mère|père))\b"
)
_SITUATION_PERSONNELLE = re.compile(
    r"\b(?:ma\s+retraite|mon\s+salaire|mes\s+enfants|ma\s+femme|mon\s+mari"
    r"|mon\s+épouse|mon\s+métier|mon\s+entreprise|ma\s+pension|mon\s+loyer"
    r"|mes\s+impôts|mon\s+âge|ma\s+santé)\b"
)

# --- bruit d'extraction --------------------------------------------------

_MOT_PLAUSIBLE = re.compile(r"\b[a-zà-öø-ÿ]{3,}\b", re.IGNORECASE)
# En dessous de cette part de mots vraisemblables, le texte est du bruit
# d'extraction et non de la prose : aucune règle de forme ne veut rien dire
# dessus. Le seuil est bas à dessein — une liste de doléances télégraphique
# reste très au-dessus.
PART_MOTS_PLAUSIBLES = 0.5
# En deçà, la part est trop bruyante pour être lue : trois mots dont un mal
# reconnu font déjà 67 %.
MOTS_MINIMUM = 12

# --- longueur ------------------------------------------------------------

# Un mot de transmission tient en une page. Au-delà, une formule de transmission
# ne signale plus un courrier d'accompagnement mais une couverture recollée à la
# contribution qui la suit, faute d'une rupture vue par le découpage. Le seuil
# est pris dans un trou du corpus : sur les 33 doléances portant une formule de
# transmission, 24 font moins de 140 mots et les 9 autres plus de 330.
MOTS_TEXTE_BREF = 250

APPEL = "appel"
OBJET = "objet"
POLITESSE = "politesse"
TRANSMISSION = "transmission"
SIGNATURE_ELU = "signature_elu"
CONSEIL_MUNICIPAL = "conseil_municipal"
ENTETE_MAIRIE = "entete_mairie"
SOUSSIGNES_PLURIEL = "soussignes_pluriel"
NOUS_COLLECTIF = "nous_collectif"
ORGANISATION = "organisation"
PETITION = "petition"
FORMULAIRE = "formulaire"
PREMIERE_PERSONNE = "premiere_personne"
SITUATION_PERSONNELLE = "situation_personnelle"
TEXTE_ILLISIBLE = "texte_illisible"
TEXTE_BREF = "texte_bref"


def _ouverture(texte: str) -> str:
    return texte[:OUVERTURE]


def _cloture(texte: str) -> str:
    return texte[-CLOTURE:]


def texte_illisible(texte: str) -> bool:
    """Le texte est-il dominé par du bruit d'extraction ?

    Les pages `needs_ocr` sont écartées du découpage, mais le score de qualité
    laisse passer des couvertures manuscrites et des tampons : on retrouve des
    « doléances » entièrement composées de fragments de caractères. Aucune règle
    de forme ne veut rien dire dessus, et les compter comme des contributions
    fausserait tous les taux.

    Args:
        texte: le texte de la doléance.

    Returns:
        Vrai si moins de `PART_MOTS_PLAUSIBLES` des jetons sont des mots
        vraisemblables. Un texte trop court pour être jugé renvoie faux.
    """
    jetons = (texte or "").split()
    if len(jetons) < MOTS_MINIMUM:
        return False
    return len(_MOT_PLAUSIBLE.findall(texte)) / len(jetons) < PART_MOTS_PLAUSIBLES


def signaux(texte: str) -> set[str]:
    """Tous les signaux repérés dans une doléance.

    Args:
        texte: le texte de la doléance, tel qu'il est en base.

    Returns:
        L'ensemble des noms de signaux présents. Vide est un résultat, pas une
        erreur : beaucoup de doléances sont des listes de revendications sans
        sujet grammatical, et rien dans leur forme ne dit qui les écrit.
    """
    texte = texte or ""
    if not texte.strip():
        return set()

    ouverture, cloture = _ouverture(texte), _cloture(texte)
    trouves: set[str] = set()

    if texte_illisible(texte):
        trouves.add(TEXTE_ILLISIBLE)
    if len(texte.split()) <= MOTS_TEXTE_BREF:
        trouves.add(TEXTE_BREF)
    if _APPEL.search(ouverture):
        trouves.add(APPEL)
    if _OBJET.search(ouverture):
        trouves.add(OBJET)
    if _POLITESSE.search(cloture):
        trouves.add(POLITESSE)
    if _OBJET_TRANSMISSION.search(ouverture) or _FORMULE_TRANSMISSION.search(texte):
        trouves.add(TRANSMISSION)
    if _SIGNATURE_ELU.search(cloture) or _SOUSSIGNE_ELU.search(texte):
        trouves.add(SIGNATURE_ELU)
    if _CONSEIL_MUNICIPAL.search(texte):
        trouves.add(CONSEIL_MUNICIPAL)
    if _ENTETE_MAIRIE.search(ouverture):
        trouves.add(ENTETE_MAIRIE)
    for nom, motif in (
        (SOUSSIGNES_PLURIEL, _SOUSSIGNES_PLURIEL),
        (NOUS_COLLECTIF, _NOUS_COLLECTIF),
        (ORGANISATION, _ORGANISATION),
        (PETITION, _PETITION),
        (FORMULAIRE, _FORMULAIRE),
        (PREMIERE_PERSONNE, _PREMIERE_PERSONNE),
        (SITUATION_PERSONNELLE, _SITUATION_PERSONNELLE),
    ):
        if motif.search(texte):
            trouves.add(nom)
    return trouves
