"""Normalisation des sorties de backends — markdown et chaîne de pensée.

Mistral OCR rend du markdown (titres ``#``, liens d'images) ; les modèles
« pensants » servis par Ollama laissent parfois fuir leur raisonnement avant
la transcription (mesuré sur ornith-1.5, 2026-09-10). On ne retire ici que la
*syntaxe* : jamais l'orthographe — la transcription est la version
diplomatique, et la graphie d'origine est un marqueur social que des
chercheurs voudront étudier (couche 3 du plan). La normalisation pour la
recherche se produit à la lecture, pas ici.
"""

import re

_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_TITRE = re.compile(r"^#{1,6}\s*")
_EMPHASE = re.compile(r"\*\*|__|`")
_MARQUEUR_PENSEE = "</think>"


def couper_chaine_de_pensee(texte: str) -> str:
    """Ne garde que ce qui suit le dernier marqueur `</think>`.

    La consigne « ne produis que la transcription » ne suffit pas : le
    raisonnement précède la transcription dans la même réponse. Un modèle qui
    n'emploie pas le marqueur passe inchangé.
    """
    if _MARQUEUR_PENSEE in texte:
        return texte.split(_MARQUEUR_PENSEE)[-1].strip()
    return texte


def normaliser_markdown(texte: str) -> str:
    """Retire la syntaxe markdown sans toucher aux mots.

    Titres, liens d'images (le scan n'a pas d'images à transcrire), emphases
    et code inline. Les mots, la ponctuation et les sauts de ligne restent.
    """
    lignes = []
    for ligne in texte.split("\n"):
        ligne = _IMAGE.sub("", ligne)
        ligne = _TITRE.sub("", ligne)
        ligne = _EMPHASE.sub("", ligne)
        lignes.append(ligne)
    return "\n".join(lignes).strip()


def normaliser(texte: str) -> str:
    """Chaîne complète : chaîne de pensée d'abord, syntaxe ensuite."""
    return normaliser_markdown(couper_chaine_de_pensee(texte))
