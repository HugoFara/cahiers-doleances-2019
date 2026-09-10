"""Charge le référentiel INSEE dans `city`, et pèse le corpus en habitants.

Lit les extraits versionnés de `insee/referentiel/` — **jamais le réseau**, qui
est l'affaire de `insee.telecharger`. Un chargement doit être rejouable hors
ligne et donner le même résultat d'une année sur l'autre : c'est la condition
pour qu'un chiffre publié reste vérifiable.

Ce que ça débloque : la **pondération par population**. Sans elle, « 459 communes
sur 1 494 » compte une commune de 90 habitants comme une de 16 000, et ne dit
rien de représentativité. Avec elle on sait quelle part des habitants des quatre
départements a un cahier dans le corpus, et surtout quelle part n'en a aucune
page lisible.

Deux pièges, tous deux rencontrés sur le corpus réel :

- **Le double compte.** Une commune déléguée a sa propre population, mais celle-ci
  est déjà comprise dans celle de sa commune parente. Le corpus contient les
  deux cas de figure. `population_totale` refuse de les additionner ; `doubles`
  les nomme.
- **Le millésime.** Deux codes du corpus ne désignaient déjà plus une commune de
  plein exercice en février 2019, et un troisième a disparu depuis. Le code reste
  celui du dépôt ; `current_code` dit ce qu'il est devenu.
"""

import csv
from dataclasses import dataclass, field, replace
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import City

REFERENTIEL = Path(__file__).parent / "referentiel"

COMMUNE = "COM"


@dataclass(frozen=True)
class Commune:
    """Une commune du référentiel, au millésime pivot."""

    code: str
    type: str
    commune_parente: str | None
    nom: str
    departement: str
    population: int | None
    latitude: float | None = None
    longitude: float | None = None
    code_courant: str | None = None
    nom_courant: str | None = None

    @property
    def deleguee(self) -> bool:
        """Vrai si le code ne désignait déjà plus une commune de plein exercice."""
        return self.type != COMMUNE


@dataclass
class Rapport:
    """Ce qu'a donné un chargement du référentiel."""

    communes: int = 0
    rapprochees: int = 0
    inconnues: list[str] = field(default_factory=list)
    deleguees: list[str] = field(default_factory=list)
    disparues: list[str] = field(default_factory=list)
    renommees: list[str] = field(default_factory=list)
    sans_coordonnees: int = 0
    doubles: list[tuple[str, str]] = field(default_factory=list)

    def resume(self) -> list[str]:
        return [
            f"communes du corpus renseignées : {self.rapprochees}/{self.communes}",
            f"codes absents du référentiel : {len(self.inconnues)}",
            f"codes déjà absorbés au millésime pivot : {len(self.deleguees)}",
            f"communes disparues depuis 2019 : {len(self.disparues)}",
            f"communes renommées depuis 2019 : {len(self.renommees)}",
            f"sans coordonnées : {self.sans_coordonnees}",
        ]


def _entier(valeur: str) -> int | None:
    return int(valeur) if valeur else None


def _flottant(valeur: str) -> float | None:
    return float(valeur) if valeur else None


def lire(dossier: Path = REFERENTIEL) -> dict[str, Commune]:
    """Assemble les trois extraits en un référentiel indexé par code.

    Args:
        dossier: le dossier des extraits (`insee/referentiel/` par défaut).

    Returns:
        ``{code INSEE 2019: Commune}``.
    """
    communes: dict[str, Commune] = {}
    with (dossier / "communes_2019.csv").open(encoding="utf-8") as f:
        for ligne in csv.DictReader(f):
            communes[ligne["code"]] = Commune(
                code=ligne["code"],
                type=ligne["type"],
                commune_parente=ligne["commune_parente"] or None,
                nom=ligne["nom"],
                departement=ligne["departement"],
                population=_entier(ligne["population"]),
            )

    geometrie = dossier / "geometrie.csv"
    if geometrie.exists():
        with geometrie.open(encoding="utf-8") as f:
            for ligne in csv.DictReader(f):
                commune = communes.get(ligne["code"])
                if commune is None:
                    continue
                communes[ligne["code"]] = replace(
                    commune,
                    latitude=_flottant(ligne["latitude"]),
                    longitude=_flottant(ligne["longitude"]),
                )

    passage = dossier / "passage.csv"
    if passage.exists():
        with passage.open(encoding="utf-8") as f:
            for ligne in csv.DictReader(f):
                commune = communes.get(ligne["code_2019"])
                if commune is None:
                    continue
                communes[ligne["code_2019"]] = replace(
                    commune,
                    code_courant=ligne["code_courant"] or None,
                    nom_courant=ligne["nom_courant"] or None,
                )

    # Une commune absente de `passage.csv` n'a pas bougé : son code et son nom
    # courants sont ceux du pivot. Le dire ici évite que chaque lecture en aval
    # ait à retenir que NULL veut dire « inchangée ».
    return {
        code: (
            commune
            if commune.code_courant or commune.deleguee
            else replace(commune, code_courant=code, nom_courant=commune.nom)
        )
        for code, commune in communes.items()
    }


def doubles_comptes(codes: set[str], referentiel: dict[str, Commune]) -> list[tuple[str, str]]:
    """Les couples (déléguée, parente) tous deux présents dans un ensemble de codes.

    Leurs populations se recouvrent : la déléguée est comptée dans la parente.
    Additionner les deux surestime, et rien dans les données ne le signale — d'où
    cette vérification explicite plutôt qu'une note dans un coin.

    Args:
        codes: les codes dont on veut sommer la population.
        referentiel: le référentiel chargé par `lire`.

    Returns:
        Les couples ``(code délégué, code parent)`` en conflit.
    """
    conflits = []
    for code in sorted(codes):
        commune = referentiel.get(code)
        if commune and commune.deleguee and commune.commune_parente in codes:
            conflits.append((code, commune.commune_parente))
    return conflits


def populations_sans_double_compte(
    codes: set[str], referentiel: dict[str, Commune]
) -> dict[str, int]:
    """Population de chaque code, les recouvrements mis à zéro.

    Une commune déléguée dont la parente est aussi dans l'ensemble se voit
    attribuer 0 : ses habitants sont déjà comptés dans la parente. Rendre un
    dictionnaire plutôt qu'un total permet aux mesures en aval — la couverture,
    par exemple — de pondérer commune par commune sans avoir à connaître la
    règle.

    Args:
        codes: les codes concernés.
        referentiel: le référentiel chargé par `lire`.

    Returns:
        ``{code: population municipale}``, 0 pour les recouvrements.
    """
    doubles = {delegue for delegue, _ in doubles_comptes(codes, referentiel)}
    return {
        code: 0 if code in doubles else (commune.population or 0)
        for code in codes
        if (commune := referentiel.get(code))
    }


def population_totale(codes: set[str], referentiel: dict[str, Commune]) -> int:
    """Population municipale d'un ensemble de communes, sans double compte.

    Args:
        codes: les codes à sommer.
        referentiel: le référentiel chargé par `lire`.

    Returns:
        La somme des populations municipales.
    """
    return sum(populations_sans_double_compte(codes, referentiel).values())


def population_par_departement(referentiel: dict[str, Commune]) -> dict[str, int]:
    """Population de chaque département entier, dénominateur de la couverture.

    Seules les communes de plein exercice sont sommées : les déléguées sont déjà
    comptées dans leur parente.
    """
    totaux: dict[str, int] = {}
    for commune in referentiel.values():
        if commune.deleguee:
            continue
        totaux[commune.departement] = totaux.get(commune.departement, 0) + (
            commune.population or 0
        )
    return totaux


def communes_par_departement(referentiel: dict[str, Commune]) -> dict[str, int]:
    """Nombre de communes de plein exercice par département."""
    totaux: dict[str, int] = {}
    for commune in referentiel.values():
        if commune.deleguee:
            continue
        totaux[commune.departement] = totaux.get(commune.departement, 0) + 1
    return totaux


def enrichir(session: Session, referentiel: dict[str, Commune] | None = None) -> Rapport:
    """Remplit les colonnes du COG sur les communes déjà en base.

    N'en crée aucune : `city` est peuplée par `python -m insee rattacher`, à
    partir des cahiers. Le référentiel renseigne ce qui existe, il ne décide pas
    du périmètre du corpus.

    `name` — la graphie rencontrée dans le corpus — n'est jamais écrasé.

    Args:
        session: session ouverte (le commit reste à l'appelant).
        referentiel: référentiel déjà chargé, sinon lu depuis `insee/referentiel/`.

    Returns:
        Le rapport du chargement.
    """
    referentiel = referentiel if referentiel is not None else lire()
    villes = list(session.scalars(select(City)))
    rapport = Rapport(communes=len(villes))

    for ville in villes:
        commune = referentiel.get(ville.code)
        if commune is None:
            rapport.inconnues.append(ville.code)
            continue
        ville.official_name = commune.nom
        ville.cog_type = commune.type
        ville.parent_code = commune.commune_parente
        ville.current_code = commune.code_courant
        ville.population = commune.population
        ville.latitude = commune.latitude
        ville.longitude = commune.longitude
        rapport.rapprochees += 1
        if commune.latitude is None:
            rapport.sans_coordonnees += 1
        if commune.deleguee:
            rapport.deleguees.append(commune.code)
        elif commune.code_courant and commune.code_courant != commune.code:
            rapport.disparues.append(commune.code)
        if (
            commune.code_courant == commune.code
            and commune.nom_courant
            and commune.nom_courant != commune.nom
        ):
            rapport.renommees.append(commune.code)

    rapport.doubles = doubles_comptes({v.code for v in villes}, referentiel)
    return rapport
