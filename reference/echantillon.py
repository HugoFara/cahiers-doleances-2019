"""Tirage d'un échantillon de cahiers à annoter à la main.

Sans étalon, on ne peut pas dire si un découpage vaut mieux qu'un autre : on
peut seulement constater qu'il coupe plus ou moins. Ce module tire l'échantillon
sur lequel l'étalon sera constitué.

**Tirage stratifié, et pourquoi.** Un tirage uniforme donnerait presque
exclusivement des cahiers d'une seule doléance — 89 % des pages n'en portent
qu'une, d'après le découpage actuel — et l'étalon ne dirait rien des cas qui
comptent : ceux où plusieurs contributeurs se succèdent. On stratifie donc sur
le nombre de doléances trouvées, avec un plancher par strate, et on conserve le
**poids** de chaque strate pour que les mesures globales restent celles de la
population et non celles de l'échantillon.

La strate vient du découpage servi : c'est un instrument de tirage, pas une
vérité. L'étalon, lui, est indépendant de tout run — c'est ce à quoi les runs
sont comparés.
"""

import random
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.models import Doleance

# Plancher de cahiers tirés par strate non vide : sans lui, les strates rares
# (trois contributeurs et plus) disparaissent d'un échantillon proportionnel.
MIN_PAR_STRATE = 10


def strate(nb_doleances: int) -> str:
    """Classe un cahier par le nombre de doléances que le découpage y a trouvées."""
    if nb_doleances <= 1:
        return "une"
    if nb_doleances == 2:
        return "deux"
    return "trois-et-plus"


def compter_par_cahier(session: Session, run_id: int) -> dict[str, int]:
    """Nombre de doléances trouvées par cahier, dans ce découpage."""
    lignes = session.execute(
        select(Doleance.pdf_name, func.count(Doleance.id))
        .where(Doleance.run_id == run_id)
        .group_by(Doleance.pdf_name)
    ).all()
    return {pdf_name: n for pdf_name, n in lignes if pdf_name}


def repartir(effectifs: dict[str, int], taille: int) -> dict[str, int]:
    """Combien de cahiers tirer dans chaque strate.

    Proportionnel à la population, avec un plancher par strate, et jamais plus
    que ce que la strate contient.

    Args:
        effectifs: nombre de cahiers par strate dans la population.
        taille: nombre total de cahiers voulu.

    Returns:
        ``{strate: nombre à tirer}``.
    """
    total = sum(effectifs.values())
    if not total:
        return {}
    quotas = {
        nom: min(n, max(MIN_PAR_STRATE, round(taille * n / total)))
        for nom, n in effectifs.items()
    }
    # Le plancher et l'arrondi font déborder : on rogne sur les strates les plus
    # fournies, qui sont aussi celles où l'information marginale est la moindre.
    surplus = sum(quotas.values()) - taille
    for nom in sorted(quotas, key=lambda n: -quotas[n]):
        if surplus <= 0:
            break
        retire = min(surplus, max(0, quotas[nom] - MIN_PAR_STRATE))
        quotas[nom] -= retire
        surplus -= retire
    return quotas


def tirer(
    session: Session, run_id: int, taille: int, graine: int
) -> tuple[list[tuple[str, str]], dict[str, float]]:
    """Tire les cahiers à annoter et calcule le poids de chaque strate.

    Args:
        session: session ouverte sur la base.
        run_id: découpage servant à stratifier.
        taille: nombre de cahiers voulu.
        graine: graine aléatoire — le même appel redonne le même échantillon.

    Returns:
        (liste de (pdf_name, strate) triée, poids par strate).
        Le poids est le nombre de cahiers que chaque cahier tiré représente.
    """
    par_strate: dict[str, list[str]] = defaultdict(list)
    for pdf_name, n in sorted(compter_par_cahier(session, run_id).items()):
        par_strate[strate(n)].append(pdf_name)

    effectifs = {nom: len(cahiers) for nom, cahiers in par_strate.items()}
    quotas = repartir(effectifs, taille)

    alea = random.Random(graine)
    tires: list[tuple[str, str]] = []
    poids: dict[str, float] = {}
    for nom in sorted(par_strate):
        quota = quotas.get(nom, 0)
        if not quota:
            continue
        echantillon = alea.sample(sorted(par_strate[nom]), quota)
        tires.extend((pdf_name, nom) for pdf_name in sorted(echantillon))
        poids[nom] = effectifs[nom] / quota
    return sorted(tires), poids
