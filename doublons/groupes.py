"""Des paires similaires aux groupes de doublons.

Deux doléances sont rapprochées si leur similarité de Jaccard dépasse un seuil.
Les groupes sont les **composantes connexes** du graphe ainsi formé : si A
ressemble à B et B à C, les trois sont dans le même groupe même si A et C se
ressemblent moins. C'est le comportement voulu pour des lettres-types qui
dérivent — chacune est proche de la précédente, la première et la dernière
peuvent être assez éloignées.

La contrepartie est connue : un seuil trop bas fait fusionner des groupes qui
n'ont rien à voir, par chaînage. `similarity_min` conserve la plus faible
similarité retenue dans un groupe, ce qui permet de repérer ceux qui ne tiennent
qu'à un fil.

Second garde-fou, moins intuitif : le seuil ne peut pas descendre indéfiniment.
Le filtre LSH qui fournit les paires candidates est réglé pour la similarité
haute ; sous 0,5 il en laisse passer trop peu, si bien qu'un seuil plus bas
rendrait *moins* de doublons. `SEUIL_PLANCHER` le rappelle.
"""

from dataclasses import dataclass

from doublons.empreintes import fragments, jaccard, paires_candidates, signature

# Au-dessus, deux textes sont « le même texte » aux variantes de transcription
# près. En dessous de 0,6 on attrape des doléances qui partagent seulement un
# passage recopié, ce qui est une autre question.
SEUIL = 0.8

# En dessous, le filtre LSH ne propose plus assez de paires pour que le seuil
# veuille dire quelque chose : à 0,3 il n'en propose qu'une sur quatre. Abaisser
# le seuil sous ce plancher donnerait *moins* de doublons, silencieusement. Pour
# chercher plus bas, il faut élargir les bandes, pas baisser le seuil.
SEUIL_PLANCHER = 0.5


@dataclass(frozen=True)
class Groupe:
    """Un ensemble de doléances quasi identiques."""

    membres: tuple[int, ...]
    similarite_min: float

    @property
    def taille(self) -> int:
        return len(self.membres)


class _Composantes:
    """Union-find : regroupe les identifiants reliés deux à deux."""

    def __init__(self) -> None:
        self._parent: dict[int, int] = {}

    def racine(self, x: int) -> int:
        self._parent.setdefault(x, x)
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def unir(self, a: int, b: int) -> None:
        ra, rb = self.racine(a), self.racine(b)
        if ra != rb:
            self._parent[rb] = ra

    def groupes(self) -> dict[int, list[int]]:
        resultat: dict[int, list[int]] = {}
        for x in self._parent:
            resultat.setdefault(self.racine(x), []).append(x)
        return resultat


def paires_similaires(
    textes: dict[int, str], seuil: float = SEUIL
) -> list[tuple[int, int, float]]:
    """Paires dont la similarité dépasse le seuil, vérifiées exactement.

    Le LSH propose, Jaccard dispose : les candidates sont recalculées sur les
    ensembles de fragments réels, pas sur l'estimation.

    Args:
        textes: ``{identifiant: texte}``.
        seuil: similarité minimale pour rapprocher deux textes.

    Returns:
        Les triplets ``(a, b, similarité)``, ``a < b``.
    """
    par_id = {i: fragments(t) for i, t in textes.items()}
    signatures = {i: signature(f) for i, f in par_id.items()}
    retenues = []
    for a, b in sorted(paires_candidates(signatures)):
        score = jaccard(par_id[a], par_id[b])
        if score >= seuil:
            retenues.append((a, b, score))
    return retenues


def grouper(
    textes: dict[int, str], seuil: float = SEUIL
) -> list[Groupe]:
    """Regroupe les doléances quasi identiques.

    Args:
        textes: ``{identifiant: texte}``.
        seuil: similarité minimale.

    Returns:
        Les groupes d'au moins deux membres, du plus grand au plus petit puis
        par identifiant, pour que deux exécutions donnent le même ordre.
    """
    paires = paires_similaires(textes, seuil)
    composantes = _Composantes()
    scores: dict[int, list[float]] = {}
    for a, b, score in paires:
        composantes.unir(a, b)
        scores.setdefault(a, []).append(score)
        scores.setdefault(b, []).append(score)

    groupes = []
    for membres in composantes.groupes().values():
        if len(membres) < 2:
            continue
        dedans = set(membres)
        similarites = [
            score for a, b, score in paires if a in dedans and b in dedans
        ]
        groupes.append(
            Groupe(
                membres=tuple(sorted(membres)),
                similarite_min=min(similarites) if similarites else 0.0,
            )
        )
    return sorted(groupes, key=lambda g: (-g.taille, g.membres))
