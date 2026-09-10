"""Des signaux aux deux axes : quel support, quel auteur.

Deux axes séparés parce que les deux questions le sont : une pétition peut être
portée par une association ou par des habitants sans organisation, un courrier
peut venir d'un particulier comme d'un maire. Les croiser dans une seule
étiquette obligerait à inventer des cases que le corpus ne porte pas.

**`INDETERMINE` est une valeur, pas une absence.** Elle est écrite en base comme
les autres. « On a regardé et rien ne tranche » et « on n'a pas regardé » sont
deux états différents, et le premier est un résultat : sur ce corpus, c'est même
le plus fréquent des deux axes réunis.

**L'ordre des règles fait partie de la décision.** Il va du plus contraint au
plus général, et chaque valeur est produite par une seule branche, pour qu'un
comptage soit une partition et non une somme de recouvrements.
"""

from typologie import regles

SUPPORT = "support"
AUTEUR = "auteur"
AXES = (SUPPORT, AUTEUR)

# --- valeurs de l'axe support --------------------------------------------
ILLISIBLE = "illisible"
APPARAT = "apparat"
LETTRE_TYPE = "lettre_type"
FORMULAIRE = "formulaire"
PETITION = "petition"
DELIBERATION = "deliberation"
COURRIER = "courrier"
REGISTRE = "registre"
SUPPORTS = (
    ILLISIBLE,
    APPARAT,
    LETTRE_TYPE,
    FORMULAIRE,
    PETITION,
    DELIBERATION,
    COURRIER,
    REGISTRE,
)

# --- valeurs de l'axe auteur ---------------------------------------------
INSTITUTION = "institution"
COLLECTIF = "collectif"
INDIVIDU = "individu"
INDETERMINE = "indetermine"
AUTEURS = (INSTITUTION, COLLECTIF, INDIVIDU, INDETERMINE)


def support(signaux: set[str], recopie: bool = False) -> tuple[str, str]:
    """Quel genre de document est cette doléance.

    Args:
        signaux: ce que `typologie.regles.signaux` a repéré.
        recopie: la doléance appartient-elle à un groupe de doublons couvrant
            plusieurs communes ? Ce signal ne vient pas du texte mais de la
            couche `doublons/`, d'où son passage séparé.

    Returns:
        Le couple (valeur, signaux ayant tranché), les seconds joints par ``+``
        pour que la décision reste lisible ligne à ligne en base.
    """
    if regles.TEXTE_ILLISIBLE in signaux:
        return ILLISIBLE, regles.TEXTE_ILLISIBLE
    # L'apparat passe avant le courrier : c'est un courrier, mais son objet est
    # de transmettre le cahier, pas de contribuer. Le confondre avec une
    # contribution ajoute au corpus des textes que personne n'a écrits pour lui.
    #
    # La brièveté est exigée, et c'est elle qui fait le plus de travail : neuf
    # doléances portent une formule de transmission au milieu de plusieurs
    # milliers de mots de contributions, parce que le découpage n'a pas vu la
    # rupture entre la couverture et ce qui la suit. Les classer « apparat »
    # jetterait le contenu avec l'emballage.
    if (
        regles.TRANSMISSION in signaux
        and regles.TEXTE_BREF in signaux
        and {regles.SIGNATURE_ELU, regles.ENTETE_MAIRIE} & signaux
    ):
        return APPARAT, _joint(signaux, regles.TRANSMISSION, regles.TEXTE_BREF,
                               regles.SIGNATURE_ELU, regles.ENTETE_MAIRIE)
    if recopie:
        return LETTRE_TYPE, "doublon_multi_communes"
    if regles.FORMULAIRE in signaux:
        return FORMULAIRE, regles.FORMULAIRE
    if {regles.PETITION, regles.SOUSSIGNES_PLURIEL} & signaux:
        return PETITION, _joint(signaux, regles.PETITION, regles.SOUSSIGNES_PLURIEL)
    if regles.CONSEIL_MUNICIPAL in signaux and regles.SIGNATURE_ELU in signaux:
        return DELIBERATION, _joint(signaux, regles.CONSEIL_MUNICIPAL,
                                    regles.SIGNATURE_ELU)
    if {regles.APPEL, regles.POLITESSE, regles.OBJET} & signaux:
        return COURRIER, _joint(signaux, regles.APPEL, regles.POLITESSE, regles.OBJET)
    return REGISTRE, "defaut"


def auteur(signaux: set[str]) -> tuple[str, str]:
    """Qui écrit — un individu, un collectif, une institution, ou nul ne sait.

    L'en-tête de mairie ne conclut à rien seul : les communes ont fourni les
    cahiers, leur papier à en-tête se retrouve en tête de contributions
    d'habitants. Il faut une signature d'élu ou une mention du conseil.

    Args:
        signaux: ce que `typologie.regles.signaux` a repéré.

    Returns:
        Le couple (valeur, signaux ayant tranché).
    """
    if regles.TEXTE_ILLISIBLE in signaux:
        return INDETERMINE, regles.TEXTE_ILLISIBLE
    if {regles.SIGNATURE_ELU, regles.CONSEIL_MUNICIPAL} & signaux:
        return INSTITUTION, _joint(signaux, regles.SIGNATURE_ELU,
                                   regles.CONSEIL_MUNICIPAL)
    collectifs = {
        regles.SOUSSIGNES_PLURIEL,
        regles.NOUS_COLLECTIF,
        regles.ORGANISATION,
        regles.PETITION,
    }
    if collectifs & signaux:
        return COLLECTIF, _joint(signaux, *sorted(collectifs))
    personnels = {regles.PREMIERE_PERSONNE, regles.SITUATION_PERSONNELLE}
    if personnels & signaux:
        return INDIVIDU, _joint(signaux, *sorted(personnels))
    return INDETERMINE, "aucun_signal"


def _joint(signaux: set[str], *candidats: str) -> str:
    """Les signaux réellement présents parmi les candidats, joints par ``+``."""
    return "+".join(nom for nom in candidats if nom in signaux)


def classer(texte: str, recopie: bool = False) -> dict[str, tuple[str, str]]:
    """Les deux axes d'une doléance, en une passe.

    Args:
        texte: le texte de la doléance.
        recopie: appartient-elle à un groupe de doublons multi-communes.

    Returns:
        ``{axe: (valeur, détecteur)}`` pour les deux axes, toujours renseignés.
    """
    trouves = regles.signaux(texte)
    return {SUPPORT: support(trouves, recopie), AUTEUR: auteur(trouves)}
