"""Rendu caviardé d'une doléance, à partir de ses offsets.

Le caviardage est **produit à la lecture**, jamais stocké. Le texte d'origine
reste intact et fait foi : c'est ce qui permet de corriger une détection, d'en
ajouter une, ou de changer la politique de caviardage sans avoir abîmé la source.

Deux règles de politique, toutes deux discutables et donc explicites :

- un passage marqué **faux positif** à la relecture n'est pas caviardé ;
- un passage marqué **rôle public** ou **institution** ne l'est pas non plus — un
  ministre cité dans sa fonction, l'adresse d'une mairie ou celle du dispositif
  lui-même sont publiques par destination, et les occulter viderait les textes de
  leur objet. Le maire nommément **accusé**, lui, relève de la relecture humaine :
  la règle ne sait pas faire la différence.
"""

from dataclasses import dataclass

from anonymisation.detecteurs import NON_PERSONNELS

REMPLACEMENTS = {
    "email": "[courriel]",
    "telephone": "[téléphone]",
    "iban": "[IBAN]",
    "url": "[lien]",
    "adresse": "[adresse]",
    "nom": "[nom]",
}
DEFAUT = "[occulté]"


@dataclass(frozen=True)
class PassageRendu:
    """Ce qu'il faut savoir d'un passage pour décider de le caviarder."""

    debut: int
    fin: int
    genre: str
    confirme: bool | None = None  # None = non relu


def a_caviarder(passage: PassageRendu) -> bool:
    """Vrai si ce passage doit disparaître du rendu public.

    Un passage non relu est caviardé : tant qu'un humain n'a pas tranché, le
    doute profite à la personne. C'est le même sens de l'erreur que partout
    ailleurs ici — un faux positif coûte un mot illisible, un nom manqué est une
    fuite.
    """
    if passage.confirme is False:
        return False
    return passage.genre not in NON_PERSONNELS


def caviarder(texte: str, passages: list[PassageRendu]) -> str:
    """Rend le texte avec ses passages personnels remplacés par un marqueur.

    Args:
        texte: le texte d'origine, inchangé en base.
        passages: les passages repérés, avec leur état de relecture.

    Returns:
        Le texte caviardé.
    """
    morceaux = []
    curseur = 0
    for debut, fin, genre in _intervalles(passages):
        morceaux.append(texte[curseur:debut])
        morceaux.append(REMPLACEMENTS.get(genre, DEFAUT))
        curseur = fin
    morceaux.append(texte[curseur:])
    return "".join(morceaux)


def _intervalles(passages: list[PassageRendu]) -> list[tuple[int, int, str]]:
    """Fusionne les passages à caviarder en intervalles disjoints.

    `detecter` fusionne déjà ce qu'il produit, mais les passages peuvent avoir
    été corrigés à la main : deux qui se recouvrent ne doivent pas donner deux
    marqueurs collés. Le genre retenu est celui du premier de l'intervalle.
    """
    retenus = sorted(
        (p for p in passages if a_caviarder(p)), key=lambda p: (p.debut, p.fin)
    )
    intervalles: list[tuple[int, int, str]] = []
    for passage in retenus:
        if intervalles and passage.debut <= intervalles[-1][1]:
            debut, fin, genre = intervalles[-1]
            intervalles[-1] = (debut, max(fin, passage.fin), genre)
        else:
            intervalles.append((passage.debut, passage.fin, passage.genre))
    return intervalles
