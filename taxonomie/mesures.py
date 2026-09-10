"""Mesures d'une grille de thèmes.

Le reproche fait à la grille actuelle — 6 788 thèmes pour 1 380 documents, dont
4 543 au niveau 0 — n'est pas qu'elle soit grosse : c'est qu'on ne sait pas si
elle est bonne. Les 32 passes successives de `factorize`/`structure` du
`RECIPE.md` de topic-builder traitent un symptôme à la main, sans instrument
pour dire si la passe suivante améliore quoi que ce soit.

Ce module fournit les instruments. Aucun ne dit « la grille est bonne » : ils
disent ce qu'elle fait, ce qui permet de comparer deux grilles et de voir dans
quel sens on va.

Les fonctions ne prennent que des lignes déjà lues : elles se testent sans
PostgreSQL et ne manipulent pas le texte des cahiers, seulement des compteurs et
des identifiants.
"""

import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Reutilisation:
    """Combien de documents chaque thème sert, et combien de thèmes chaque document porte.

    C'est la mesure centrale. Un thème attesté par un seul document n'est pas un
    thème : c'est la paraphrase de ce document. Une grille dont la plupart des
    thèmes sont des singletons ne généralise rien, elle réécrit le corpus.
    """

    documents_par_theme: Counter
    themes_par_document: Counter
    themes_sans_document: int

    @property
    def themes(self) -> int:
        return len(self.documents_par_theme) + self.themes_sans_document

    @property
    def documents(self) -> int:
        return len(self.themes_par_document)

    @property
    def singletons(self) -> int:
        """Thèmes attestés par exactement un document."""
        return sum(1 for n in self.documents_par_theme.values() if n == 1)

    @property
    def part_singletons(self) -> float:
        """Part des thèmes attestés une seule fois, parmi ceux qui le sont."""
        attestes = len(self.documents_par_theme)
        return self.singletons / attestes if attestes else 0.0

    def resume(self) -> list[str]:
        moyenne = (
            sum(self.themes_par_document.values()) / self.documents
            if self.documents
            else 0.0
        )
        return [
            f"thèmes : {self.themes} ({self.themes_sans_document} sans aucune détection)",
            f"documents : {self.documents} · {moyenne:.1f} thème(s) par document",
            f"thèmes attestés une seule fois : {self.singletons} "
            f"({self.part_singletons:.0%} des thèmes attestés)",
        ]


@dataclass
class Hierarchie:
    """L'état de l'arbre des thèmes.

    Une hiérarchie ne sert que si elle permet de remonter : parcourir « fiscalité »
    doit donner tout ce qui en relève. Racines trop nombreuses, cycles et thèmes
    isolés sont autant d'endroits où la remontée ne marche pas.
    """

    racines: int
    isoles: int  # ni parent, ni enfant : hors de l'arbre
    cycliques: int
    profondeur_max: int
    enfants_max: int
    noms_dupliques: int

    def resume(self) -> list[str]:
        return [
            f"racines : {self.racines} · thèmes isolés : {self.isoles}",
            f"thèmes dans un cycle : {self.cycliques}",
            f"profondeur maximale : {self.profondeur_max} · "
            f"enfants d'un même parent, au plus : {self.enfants_max}",
            f"noms portés par plusieurs thèmes : {self.noms_dupliques}",
        ]


@dataclass
class Couverture:
    """Ce que les détections couvrent du texte, et ce qu'elles laissent dehors.

    « Hors grille » est le chiffre qui manque à tout comptage de thèmes : sans
    lui, on ne sait pas si « 34 % des contributions parlent de fiscalité » porte
    sur un corpus lu en entier ou sur les quelques passages que la grille a su
    reconnaître.
    """

    documents: int = 0
    documents_sans_theme: int = 0
    caracteres: int = 0
    caracteres_couverts: int = 0
    verbatims: int = 0
    verbatims_introuvables: int = 0
    details: list = field(default_factory=list)

    @property
    def part_couverte(self) -> float:
        return self.caracteres_couverts / self.caracteres if self.caracteres else 0.0

    @property
    def part_hors_grille(self) -> float:
        return 1.0 - self.part_couverte

    def resume(self) -> list[str]:
        introuvables = (
            self.verbatims_introuvables / self.verbatims if self.verbatims else 0.0
        )
        return [
            f"documents mesurés : {self.documents} "
            f"({self.documents_sans_theme} sans aucun thème)",
            f"texte couvert par une détection : {self.part_couverte:.0%}",
            f"**hors grille : {self.part_hors_grille:.0%}**",
            f"verbatims introuvables dans leur document : "
            f"{self.verbatims_introuvables}/{self.verbatims} ({introuvables:.0%})",
        ]


def reutilisation(detections: list[tuple[str, str]], themes: list[str]) -> Reutilisation:
    """Croise thèmes et documents.

    Args:
        detections: couples (identifiant de thème, identifiant de document).
        themes: tous les identifiants de thèmes de la grille, détectés ou non.

    Returns:
        Les distributions et le compte de thèmes jamais détectés.
    """
    par_theme: dict[str, set[str]] = defaultdict(set)
    par_document: dict[str, set[str]] = defaultdict(set)
    for theme, document in detections:
        par_theme[theme].add(document)
        par_document[document].add(theme)

    return Reutilisation(
        documents_par_theme=Counter({t: len(d) for t, d in par_theme.items()}),
        themes_par_document=Counter({d: len(t) for d, t in par_document.items()}),
        themes_sans_document=sum(1 for t in themes if t not in par_theme),
    )


def _normaliser(valeur: str) -> str:
    """Minuscules, sans accent, espaces écrasés, tirets et apostrophes unifiés.

    Comme `load_analysis._normaliser`, mais **plus permissif** : les accents
    sautent aussi. Les deux fonctions ne servent pas à la même chose. Là-bas, il
    s'agit de décider si toute une livraison parle bien de notre corpus, et la
    sévérité protège. Ici, il s'agit de savoir si un verbatim cite ou reformule :
    un extrait qui ne diffère que par un accent est une citation, le compter
    introuvable gonflerait artificiellement le taux de paraphrase.
    """
    remplace = (valeur or "").replace("−", "-").replace("’", "'")
    decompose = unicodedata.normalize("NFKD", remplace)
    sans_accent = "".join(c for c in decompose if not unicodedata.combining(c))
    return " ".join(sans_accent.split()).lower()


def _fusionner(segments: list[tuple[int, int]]) -> int:
    """Longueur totale couverte par des segments éventuellement chevauchants.

    Deux détections peuvent citer le même passage : compter deux fois donnerait
    une couverture supérieure à 100 %.
    """
    total = 0
    fin_courante = -1
    for debut, fin in sorted(segments):
        if fin <= fin_courante:
            continue
        total += fin - max(debut, fin_courante)
        fin_courante = fin
    return total


def couverture(documents: dict[str, str], verbatims: dict[str, list[str]]) -> Couverture:
    """Mesure la part du texte que les détections citent réellement.

    Un verbatim introuvable dans son document n'est pas compté comme couvrant :
    c'est une reformulation du modèle, pas une citation. Leur proportion est un
    indicateur en soi — elle dit à quel point la grille cite ou paraphrase.

    Args:
        documents: ``{identifiant: texte}``.
        verbatims: ``{identifiant de document: extraits cités}``.

    Returns:
        La couverture agrégée, avec le détail par document.
    """
    resultat = Couverture(documents=len(documents))
    for identifiant, texte in documents.items():
        normalise = _normaliser(texte)
        extraits = verbatims.get(identifiant, [])
        if not extraits:
            resultat.documents_sans_theme += 1

        segments = []
        for extrait in extraits:
            resultat.verbatims += 1
            aiguille = _normaliser(extrait)
            position = normalise.find(aiguille) if aiguille else -1
            if position < 0:
                resultat.verbatims_introuvables += 1
                continue
            segments.append((position, position + len(aiguille)))

        couvert = _fusionner(segments)
        resultat.caracteres += len(normalise)
        resultat.caracteres_couverts += couvert
        resultat.details.append((identifiant, len(normalise), couvert))
    return resultat


def hierarchie(themes: list[tuple[str, str | None, str]]) -> Hierarchie:
    """Analyse l'arbre des thèmes.

    Args:
        themes: triplets (identifiant, identifiant du parent ou ``None``, nom).

    Returns:
        L'état de l'arbre : racines, isolés, cycles, profondeur, largeur.
    """
    parent = {identifiant: pere for identifiant, pere, _ in themes}
    noms = [nom for _, _, nom in themes if nom]
    enfants: Counter = Counter(p for p in parent.values() if p in parent)

    cycliques = set()
    profondeurs: dict[str, int] = {}

    def profondeur(identifiant: str) -> int:
        """Profondeur d'un thème ; 0 pour un thème dans un cycle."""
        chemin = []
        courant = identifiant
        while courant in parent and parent[courant] in parent:
            if courant in profondeurs:
                break
            if courant in chemin:
                cycliques.update(chemin)
                for noeud in chemin:
                    profondeurs[noeud] = 0
                return 0
            chemin.append(courant)
            courant = parent[courant]
        base = profondeurs.get(courant, 0)
        for rang, noeud in enumerate(reversed(chemin), start=1):
            profondeurs[noeud] = base + rang
        return profondeurs.get(identifiant, 0)

    for identifiant, _, _ in themes:
        profondeur(identifiant)

    racines = sum(1 for identifiant, pere, _ in themes if pere is None or pere not in parent)
    isoles = sum(
        1
        for identifiant, pere, _ in themes
        if (pere is None or pere not in parent) and enfants[identifiant] == 0
    )
    doublons = sum(n - 1 for n in Counter(noms).values() if n > 1)

    return Hierarchie(
        racines=racines,
        isoles=isoles,
        cycliques=len(cycliques),
        profondeur_max=max(profondeurs.values(), default=0),
        enfants_max=max(enfants.values(), default=0),
        noms_dupliques=doublons,
    )
