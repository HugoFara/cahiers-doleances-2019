"""Empreintes de similarité : MinHash et LSH, sans dépendance.

Comparer chaque doléance à toutes les autres est quadratique — 3 000 doléances
font 4,5 millions de comparaisons, chacune sur des ensembles de plusieurs
centaines de fragments. MinHash ramène chaque texte à une signature de taille
fixe dont la proportion de valeurs communes **estime** la similarité de Jaccard,
et le LSH ne présente à la comparaison que les paires qui ont une chance d'être
proches.

Rien de tout cela n'est approximatif au moment de conclure : les paires
candidates sont ensuite vérifiées sur les ensembles réels. Le MinHash sert à ne
pas regarder les 4,5 millions d'autres.

Aucune dépendance nouvelle : `datasketch` ferait la même chose, mais ajouter une
dépendance à un projet qui en a déjà beaucoup pour 60 lignes de code se paierait
à chaque montée de version.
"""

import hashlib
import random
import re
import unicodedata

# Nombre de mots par fragment. Trop court, deux textes qui partagent du
# vocabulaire courant se ressemblent ; trop long, une faute d'OCR suffit à
# désaligner un texte de son quasi-jumeau. 5 est l'usage.
TAILLE_FRAGMENT = 5

# Taille de la signature. Plus elle est grande, plus l'estimation est fine et
# plus le calcul coûte. 128 donne une erreur type d'environ 9 points.
TAILLE_SIGNATURE = 128

# Découpage de la signature pour le LSH. Deux textes sont candidats dès qu'ils
# partagent une bande entière. Avec 32 bandes de 4 valeurs, la probabilité
# qu'une paire de similarité s soit proposée vaut 1-(1-s⁴)³² :
#
#   s = 0,3 -> 23 %    s = 0,5 -> 87 %    s = 0,7 -> 100 %
#   s = 0,4 -> 56 %    s = 0,6 -> 99 %
#
# Au-dessus de 0,6 le filtre ne manque pratiquement rien ; en dessous de 0,5 il
# devient une passoire. C'est ce qui fixe SEUIL_PLANCHER dans `groupes.py` : un
# seuil plus bas ne cherche pas plus de doublons, il en trouve moins et sans le
# dire. Le sens de l'erreur retenu est le bon — un candidat de trop coûte une
# vérification, un candidat manqué est un doublon jamais vu.
BANDES = 32

MAX_HASH = (1 << 32) - 1
_MOTS = re.compile(r"[a-z0-9]+")


def normaliser(texte: str) -> str:
    """Réduit un texte à ce qui doit rester comparable.

    Casse, accents et ponctuation sautent : ils varient d'une transcription à
    l'autre sans que le texte soit un autre texte. Les chiffres restent — dans
    ces cahiers ils portent du sens (montants, articles de loi, effectifs).
    """
    decompose = unicodedata.normalize("NFKD", texte or "")
    sans_accent = "".join(c for c in decompose if not unicodedata.combining(c))
    return " ".join(_MOTS.findall(sans_accent.lower()))


def fragments(texte: str, taille: int = TAILLE_FRAGMENT) -> set[str]:
    """Les suites de `taille` mots consécutifs d'un texte.

    Un texte plus court qu'un fragment en donne un seul, tronqué : sans cela les
    doléances de trois mots n'auraient aucune empreinte et ne pourraient jamais
    être rapprochées.
    """
    mots = normaliser(texte).split()
    if not mots:
        return set()
    if len(mots) <= taille:
        return {" ".join(mots)}
    return {" ".join(mots[i : i + taille]) for i in range(len(mots) - taille + 1)}


# Nombre premier de Mersenne : module des permutations affines.
PREMIER = (1 << 61) - 1


def _hachage(fragment: str) -> int:
    """Hachage stable d'un fragment.

    `hash()` de Python est randomisé d'un processus à l'autre : deux exécutions
    ne donneraient pas les mêmes groupes. Blake2b est rapide et déterministe.
    """
    return int.from_bytes(
        hashlib.blake2b(fragment.encode("utf-8"), digest_size=8).digest(), "little"
    )


def _permutations(taille: int) -> list[tuple[int, int]]:
    """Coefficients (a, b) des permutations `a·h + b mod p`.

    Hacher chaque fragment une fois puis le permuter coûte un hachage par
    fragment au lieu de `taille`. Sur ce corpus, c'est la différence entre
    96 millions de hachages et 750 000. Les coefficients sont tirés d'une graine
    fixe : deux exécutions doivent donner les mêmes signatures.
    """
    alea = random.Random(20260910)
    return [
        (alea.randrange(1, PREMIER), alea.randrange(0, PREMIER)) for _ in range(taille)
    ]


_PERMUTATIONS: dict[int, list[tuple[int, int]]] = {}


def signature(fragments_du_texte: set[str], taille: int = TAILLE_SIGNATURE) -> tuple[int, ...]:
    """Signature MinHash : le plus petit hachage permuté de chaque position.

    Args:
        fragments_du_texte: les fragments du texte (`fragments`).
        taille: nombre de valeurs de la signature.

    Returns:
        La signature ; une signature de `MAX_HASH` partout pour un texte vide.
    """
    if not fragments_du_texte:
        return tuple([MAX_HASH] * taille)
    if taille not in _PERMUTATIONS:
        _PERMUTATIONS[taille] = _permutations(taille)
    haches = [_hachage(fragment) for fragment in fragments_du_texte]
    return tuple(
        min((a * h + b) % PREMIER for h in haches) & MAX_HASH
        for a, b in _PERMUTATIONS[taille]
    )


def jaccard(a: set[str], b: set[str]) -> float:
    """Similarité de Jaccard exacte entre deux ensembles de fragments."""
    if not a and not b:
        return 1.0
    union = len(a | b)
    return len(a & b) / union if union else 0.0


def paires_candidates(
    signatures: dict[int, tuple[int, ...]], bandes: int = BANDES
) -> set[tuple[int, int]]:
    """Paires qui partagent au moins une bande de signature.

    C'est le filtre LSH : il remplace la comparaison de tout avec tout par un
    regroupement par seau. Les paires renvoyées sont des *candidates*, à
    vérifier sur les ensembles réels.

    Args:
        signatures: ``{identifiant: signature}``.
        bandes: nombre de tranches de la signature.

    Returns:
        Les paires ``(a, b)`` avec ``a < b``.
    """
    if not signatures:
        return set()
    taille = len(next(iter(signatures.values())))
    largeur = max(1, taille // bandes)

    candidates: set[tuple[int, int]] = set()
    for bande in range(bandes):
        debut = bande * largeur
        if debut >= taille:
            break
        seaux: dict[tuple[int, ...], list[int]] = {}
        for identifiant, sign in signatures.items():
            seaux.setdefault(sign[debut : debut + largeur], []).append(identifiant)
        for groupe in seaux.values():
            if len(groupe) < 2:
                continue
            groupe.sort()
            for i, a in enumerate(groupe):
                for b in groupe[i + 1 :]:
                    candidates.add((a, b))
    return candidates
