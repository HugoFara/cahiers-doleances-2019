"""Mesurer un découpage contre l'étalon.

Deux mesures, parce qu'elles ne disent pas la même chose.

**Précision / rappel / F1 sur les frontières** : exact. Une frontière posée une
ligne trop loin compte comme un faux positif *et* un faux négatif. C'est sévère,
mais c'est la mesure qui parle quand on veut savoir si les règles repèrent les
bons signaux.

**WindowDiff** : tolérant. Il fait glisser une fenêtre sur le texte et compte
les endroits où le nombre de frontières diffère ; une frontière décalée d'une
ligne n'est presque pas pénalisée. C'est la mesure qui parle quand on veut
savoir si le corpus est découpé au bon endroit *à peu près*, ce qui suffit pour
la plupart des usages en aval. **Plus bas est meilleur**, 0 = découpage parfait.

La première ligne d'un cahier ouvre forcément une doléance : elle est exclue du
calcul, la prédire est gratuit et gonflerait tous les scores.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Score:
    """Ce que vaut un découpage sur un ensemble de cahiers."""

    precision: float
    rappel: float
    f1: float
    window_diff: float
    frontieres_attendues: int
    frontieres_trouvees: int
    cahiers: int

    def resume(self) -> str:
        # 0 attendue et 0 trouvée, c'est un accord parfait sur un cas trivial :
        # afficher « P 0 % · R 0 % » le ferait lire comme un échec.
        if not self.frontieres_attendues and not self.frontieres_trouvees:
            return (
                f"aucune frontière attendue ni trouvée sur {self.cahiers} cahier(s) "
                "— rien à mesurer"
            )
        return (
            f"P {self.precision:.0%} · R {self.rappel:.0%} · F1 {self.f1:.0%} "
            f"· WindowDiff {self.window_diff:.3f} "
            f"({self.frontieres_trouvees}/{self.frontieres_attendues} frontières "
            f"sur {self.cahiers} cahier(s))"
        )


def f_mesure(precision: float, rappel: float) -> float:
    """Moyenne harmonique, 0.0 si l'une des deux est nulle."""
    if precision + rappel == 0:
        return 0.0
    return 2 * precision * rappel / (precision + rappel)


def taille_fenetre(frontieres: set[int], lignes: int) -> int:
    """Demi-longueur moyenne des segments, la fenêtre usuelle de WindowDiff."""
    segments = len(frontieres) + 1
    return max(1, round(lignes / (2 * segments)))


def window_diff(
    attendues: set[int], trouvees: set[int], lignes: int, k: int | None = None
) -> float:
    """Écart de découpage tolérant aux frontières légèrement décalées.

    Args:
        attendues: indices de ligne ouvrant une doléance selon l'étalon.
        trouvees: indices proposés par le découpage évalué.
        lignes: nombre de lignes du cahier.
        k: largeur de fenêtre ; déduite de l'étalon si absente.

    Returns:
        Une valeur entre 0 (identiques) et 1 (tout faux).
    """
    if lignes < 2:
        return 0.0
    k = k or taille_fenetre(attendues, lignes)
    k = min(k, lignes - 1)
    fenetres = lignes - k
    desaccords = sum(
        len({i for i in attendues if debut < i <= debut + k})
        != len({i for i in trouvees if debut < i <= debut + k})
        for debut in range(fenetres)
    )
    return desaccords / fenetres


def evaluer_cahier(
    attendues: set[int], trouvees: set[int], lignes: int
) -> tuple[int, int, int, float]:
    """(vrais positifs, prédites, attendues, WindowDiff) pour un cahier.

    Les frontières sont comptées hors ligne 0.
    """
    attendues = {i for i in attendues if i > 0}
    trouvees = {i for i in trouvees if i > 0}
    return (
        len(attendues & trouvees),
        len(trouvees),
        len(attendues),
        window_diff(attendues, trouvees, lignes),
    )


def agreger(
    par_cahier: dict[str, tuple[int, int, int, float]],
    poids: dict[str, float] | None = None,
) -> Score:
    """Agrège les cahiers en un score, pondéré par strate si on le lui donne.

    Sans pondération, le score est celui de l'échantillon. Avec, c'est
    l'estimation pour la population : l'échantillon sur-représente exprès les
    cahiers à plusieurs contributeurs, les compter à parts égales donnerait un
    corpus bien plus fragmenté qu'il ne l'est.

    Args:
        par_cahier: sortie de `evaluer_cahier` pour chaque cahier.
        poids: poids de chaque cahier ; 1.0 partout si absent.

    Returns:
        Le score agrégé.
    """
    poids = poids or {}
    vp = predites = attendues = 0.0
    wd_pondere = total_poids = 0.0
    cahiers = 0
    for nom, (v, p, a, wd) in par_cahier.items():
        w = poids.get(nom, 1.0)
        vp += v * w
        predites += p * w
        attendues += a * w
        wd_pondere += wd * w
        total_poids += w
        cahiers += 1

    precision = vp / predites if predites else 0.0
    rappel = vp / attendues if attendues else 0.0
    return Score(
        precision=precision,
        rappel=rappel,
        f1=f_mesure(precision, rappel),
        window_diff=wd_pondere / total_poids if total_poids else 0.0,
        frontieres_attendues=round(attendues),
        frontieres_trouvees=round(predites),
        cahiers=cahiers,
    )
