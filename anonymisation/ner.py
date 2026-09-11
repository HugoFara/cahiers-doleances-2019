"""Reconnaissance d'entités nommées : les noms cités sans marqueur.

La passe de formes (`detecteurs.py`) ne voit qu'un nom marqué, par une
civilité ou une signature. « J'ai parlé à Bernard, du service technique »
lui échappe, et c'est le cas le plus fréquent. Ce module y met un modèle de
token classification, **en local et sur CPU** : la décision d'hébergement du
2026-09-11 (journal) vaut pour les données personnelles comme pour les scans.

**Le modèle, et pourquoi lui.** `Jean-Baptiste/camembert-ner`, CamemBERT
affiné sur WikiNER français : quatre étiquettes, personne, lieu,
organisation, divers. Comparé le 2026-09-11 sur 25 doléances tirées au sort
(139 000 caractères) à deux modèles de désidentification multilingues
conseillés pendant le POC (collection OpenMed, entraînés sur des données
synthétiques de formulaires) : le plus gros d'entre eux (434M) mettait 119 s
contre 13 s, et rendait 319 « adresses Litecoin » et 172 « mots de passe »
sur des cahiers de doléances, avec des noms coupés en morceaux de sous-mots ;
l'autre n'était pas téléchargeable. CamemBERT-NER rendait 84 personnes en
spans entiers, là où la passe de formes en marquait 29. Le rappel réel reste
à mesurer sur l'échantillon annoté (`reference/`).

**Le seuil est bas, exprès.** Un faux positif coûte un mot illisible, un nom
manqué est une fuite : les personnes sont gardées dès 0,4 de confiance. Les
lieux et organisations, non caviardés, le sont à 0,6.

Le modèle est chargé à la première demande ; le module s'importe sans torch.
Les dépendances sont l'extra `ner` : `uv sync --extra ner`.
"""

import re
from dataclasses import dataclass, field

from anonymisation.detecteurs import INSTITUTION, LIEU, NOM, Passage

MODELE = "Jean-Baptiste/camembert-ner"
# Étiquettes de WikiNER -> genres de `pii_span`. MISC (œuvres, événements,
# nationalités) n'est ni personnel ni utile ici : ignoré.
GENRES = {"PER": NOM, "LOC": LIEU, "ORG": INSTITUTION}
SEUILS = {NOM: 0.4, LIEU: 0.6, INSTITUTION: 0.6}
# CamemBERT lit 512 sous-mots ; une doléance en fait 750 mots en moyenne. On
# découpe aux paragraphes et aux phrases, sous cette taille en caractères, et
# on ramène les offsets au texte entier.
TAILLE_MORCEAU = 1200

# Une phrase : jusqu'à une ponctuation finale suivie d'un blanc, ou la fin.
_UNITE = re.compile(r".+?(?:[.!?…](?=\s)|$)\s*")


@dataclass
class EntitesNommees:
    """Le détecteur : un modèle chargé une fois, une méthode texte -> passages."""

    modele: str = MODELE
    seuils: dict[str, float] = field(default_factory=lambda: dict(SEUILS))
    taille: int = TAILLE_MORCEAU
    _pipeline: object = field(default=None, repr=False)

    @property
    def detecteur(self) -> str:
        return f"ner:{self.modele}"

    def _charger(self):
        if self._pipeline is None:
            from transformers import pipeline

            self._pipeline = pipeline(
                "token-classification",
                model=self.modele,
                aggregation_strategy="simple",
                device=-1,
            )
        return self._pipeline

    def entites(self, texte: str) -> list[dict]:
        """Les entités brutes du modèle sur un morceau (offsets locaux)."""
        return self._charger()(texte)

    def detecter(self, texte: str) -> list[Passage]:
        """Les personnes, lieux et organisations cités, en offsets du texte."""
        passages: list[Passage] = []
        for debut, morceau in morceaux(texte, self.taille):
            for entite in self.entites(morceau):
                genre = GENRES.get(entite["entity_group"])
                if genre is None or float(entite["score"]) < self.seuils[genre]:
                    continue
                d, f = _rogner(morceau, int(entite["start"]), int(entite["end"]))
                if f > d:
                    passages.append(
                        Passage(debut + d, debut + f, genre, self.detecteur)
                    )
        return passages


def morceaux(texte: str, taille: int = TAILLE_MORCEAU) -> list[tuple[int, str]]:
    """Découpe le texte en morceaux sous `taille`. Rend (offset, morceau),
    chaque morceau étant une tranche exacte du texte.

    Les unités sont les phrases ; les lignes de l'OCR en sont une chacune au
    plus. Elles sont **regroupées** jusqu'à la taille, sauts de ligne compris :
    le texte extrait a un saut de ligne par ligne du scan, et un appel du
    modèle par ligne de soixante caractères était dix fois trop lent, mesuré
    sur le corpus le 2026-09-11. Une phrase plus longue que la taille est
    coupée à la taille. Pas de recouvrement : une entité à cheval sur une
    frontière est rare, et un recouvrement doublerait les passages.
    """
    unites: list[tuple[int, int]] = []  # (début, fin) dans le texte
    for para in re.finditer(r"[^\n]+", texte):
        for m in _UNITE.finditer(para.group()):
            debut, fin = para.start() + m.start(), para.start() + m.end()
            while fin - debut > taille:
                unites.append((debut, debut + taille))
                debut += taille
            unites.append((debut, fin))

    resultat: list[tuple[int, str]] = []
    bloc: tuple[int, int] | None = None
    for debut, fin in unites:
        if bloc is not None and fin - bloc[0] > taille:
            resultat.append((bloc[0], texte[bloc[0] : bloc[1]]))
            bloc = None
        bloc = (debut if bloc is None else bloc[0], fin)
    if bloc is not None:
        resultat.append((bloc[0], texte[bloc[0] : bloc[1]]))
    return [(d, m) for d, m in resultat if m.strip()]


def _rogner(morceau: str, debut: int, fin: int) -> tuple[int, int]:
    """Enlève les blancs et la ponctuation que le tokenizer a accrochés au span."""
    while debut < fin and not morceau[debut].isalnum():
        debut += 1
    while fin > debut and not morceau[fin - 1].isalnum():
        fin -= 1
    return debut, fin
