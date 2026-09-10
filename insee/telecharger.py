"""Construit les extraits du référentiel INSEE versionnés dans `insee/referentiel/`.

**Seul module du dépôt qui sorte sur le réseau.** Il est séparé de `insee.cog`
délibérément : le chargement en base ne doit jamais dépendre de la disponibilité
du site de l'INSEE, et les tests n'ont pas à simuler des téléchargements.

Le pivot est le **millésime 2019** : les codes que portent les noms de fichiers
des cahiers ont été attribués par le système qui les a déposés en février-avril
2019, et un code est une clé datée. Prendre le millésime courant paraît naturel
et c'est le piège — une commune absorbée depuis dans une commune nouvelle n'y a
plus de ligne, sa population deviendrait NULL sans bruit, ou pire, celle de la
commune fusionnée, et la pondération par population serait fausse sans qu'aucun
test ne le voie.

Trois sources, une par fichier produit, pour que la provenance se lise dans la
disposition du dossier :

- `communes_2019.csv` — Code officiel géographique au 1ᵉʳ janvier 2019, plus les
  **populations légales millésimées 2017**. Ce millésime-là et pas un autre :
  l'INSEE le publie « dans les limites territoriales des communes au 1ᵉʳ janvier
  2019 », c'est-à-dire exactement la géographie de nos codes. Le millésime 2016,
  celui qui était *en vigueur* quand les cahiers ont été écrits, porte les
  limites de 2018 et ne recouvre donc pas nos codes ; le recensement de 2017 est
  au passage plus proche de février 2019 que celui de 2016.
- `geometrie.csv` — coordonnées du centre, API Découpage administratif. Millésime
  **courant**, et c'est assumé : une commune inchangée depuis 2019 a le même
  centre, la géométrie ne dépend pas du millésime là où la population en dépend.
  Les communes disparues depuis n'y sont pas et restent sans coordonnées.
- `passage.csv` — table de passage 2019 → millésime courant, construite depuis le
  fichier des mouvements de communes, qui recense les événements depuis 1943.

Usage :

    uv run python -m insee referentiel --departements 01 28 39 53
"""

import csv
import io
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import requests

from insee.codes import departement

MILLESIME_PIVOT = "2019"
MILLESIME_COURANT = "2026"

COG_PIVOT = (
    "https://www.insee.fr/fr/statistiques/fichier/3720946/communes-01012019-csv.zip"
)
COG_MOUVEMENTS = (
    "https://www.insee.fr/fr/statistiques/fichier/8740222/v_mvt_commune_2026.csv"
)
COG_COURANT = "https://www.insee.fr/fr/statistiques/fichier/8740222/v_commune_2026.csv"
POPULATIONS = "https://www.insee.fr/fr/statistiques/fichier/4265429/ensemble.zip"
GEOMETRIE = "https://geo.api.gouv.fr/departements/{departement}/communes?fields=code,centre"

# Types d'entité du COG. COM est une commune de plein exercice ; COMD et COMA
# sont des communes déléguées et associées, c'est-à-dire des communes absorbées
# qui gardent un code et une identité résiduelle. Le corpus en contient : deux
# cahiers ont été déposés sous le code d'une commune qui avait déjà fusionné.
COMMUNE = "COM"
DELEGUEE = "COMD"
ASSOCIEE = "COMA"

CHANGEMENT_DE_NOM = "10"

# `mvt_commune`, colonne MOD — libellés de l'INSEE, repris tels quels pour que
# le fichier produit reste lisible sans sa documentation.
EVENEMENTS = {
    "10": "changement de nom",
    "20": "création",
    "21": "rétablissement",
    "30": "suppression",
    "31": "fusion simple",
    "32": "création de commune nouvelle",
    "33": "fusion association",
    "34": "transformation de fusion association en fusion simple",
    "35": "suppression de commune déléguée",
    "41": "changement de code dû à un changement de département",
    "50": "changement de code dû à un transfert de chef-lieu",
    "70": "transformation de commune associée en commune déléguée",
    "71": "rétablissement de commune déléguée",
    "72": "création de commune déléguée",
}

PIVOT_EFFET = f"{MILLESIME_PIVOT}-01-01"
# Un mouvement peut mener à un code lui-même disparu : on suit la chaîne. La
# borne évite une boucle infinie si les données en contenaient une.
CHAINE_MAX = 10


@dataclass
class Rapport:
    """Ce qu'a produit une construction du référentiel."""

    communes: int = 0
    par_type: dict[str, int] = field(default_factory=dict)
    sans_population: list[str] = field(default_factory=list)
    avec_coordonnees: int = 0
    passages: int = 0

    def resume(self) -> list[str]:
        types = " · ".join(f"{t} {n}" for t, n in sorted(self.par_type.items()))
        return [
            f"communes du millésime {MILLESIME_PIVOT} : {self.communes} ({types})",
            f"sans population légale : {len(self.sans_population)}",
            f"avec coordonnées : {self.avec_coordonnees}",
            f"lignes de table de passage vers {MILLESIME_COURANT} : {self.passages}",
        ]


def _telecharger(url: str, cache: Path) -> bytes:
    """Récupère une URL, en gardant une copie locale pour ne pas la refrapper."""
    cache.parent.mkdir(parents=True, exist_ok=True)
    if cache.exists():
        return cache.read_bytes()
    reponse = requests.get(url, timeout=180)
    reponse.raise_for_status()
    cache.write_bytes(reponse.content)
    return reponse.content


def _membre_zip(contenu: bytes, nom: str) -> str:
    with zipfile.ZipFile(io.BytesIO(contenu)) as archive:
        return archive.read(nom).decode("utf-8")


def _lignes(texte: str, delimiteur: str = ",") -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(texte.lstrip("﻿")), delimiter=delimiteur))


def _populations(contenu: bytes) -> dict[str, int]:
    """Population municipale par code, communes déléguées et associées comprises.

    `PMUN` et non `PTOT` : la population municipale est celle qui sert aux
    comparaisons entre communes, la population totale y ajoute les personnes
    comptées à part, qui sont déjà comptées ailleurs.
    """
    populations: dict[str, int] = {}
    for fichier in ("Communes.csv", "Communes_associees_ou_deleguees.csv"):
        for ligne in _lignes(_membre_zip(contenu, fichier), ";"):
            code = ligne["DEPCOM"].strip()
            # Une commune déléguée porte souvent le code de sa commune nouvelle :
            # la ligne de plein exercice, lue en premier, doit rester la bonne.
            populations.setdefault(code, int(ligne["PMUN"]))
    return populations


def _suivre(
    code: str, apres: dict[str, list[dict]], courantes: set[str]
) -> tuple[str | None, list[dict]]:
    """Suit les mouvements d'un code jusqu'à une commune du millésime courant.

    Args:
        code: le code de départ, au millésime pivot.
        apres: mouvements postérieurs au pivot, indexés par code d'origine.
        courantes: codes de plein exercice au millésime courant.

    Returns:
        (code courant ou ``None`` si la chaîne se perd, mouvements suivis).
    """
    chaine: list[dict] = []
    vu = {code}
    for _ in range(CHAINE_MAX):
        if code in courantes:
            return code, chaine
        suite = [
            m
            for m in apres.get(code, [])
            if m["TYPECOM_AP"] == COMMUNE and m["COM_AP"] not in vu
        ]
        if not suite:
            return None, chaine
        mouvement = min(suite, key=lambda m: m["DATE_EFF"])
        chaine.append(mouvement)
        code = mouvement["COM_AP"]
        vu.add(code)
    return None, chaine


def _absorption(code: str, tous: dict[str, list[dict]]) -> dict | None:
    """Le mouvement qui a fait d'une commune une entité déléguée ou associée.

    Il est **antérieur au millésime pivot** — c'est tout l'intérêt de le
    retrouver : il date le moment où le code a cessé de désigner une commune de
    plein exercice, et deux cahiers du corpus ont été déposés après ce moment-là
    sous ce code-là.
    """
    absorptions = [
        m for m in tous.get(code, []) if m["TYPECOM_AP"] in (DELEGUEE, ASSOCIEE)
    ]
    return max(absorptions, key=lambda m: m["DATE_EFF"]) if absorptions else None


def _renommage(code: str, apres: dict[str, list[dict]]) -> dict | None:
    """Le dernier changement de nom d'un code qui, lui, n'a pas bougé."""
    noms = [m for m in apres.get(code, []) if m["MOD"] == CHANGEMENT_DE_NOM]
    return max(noms, key=lambda m: m["DATE_EFF"]) if noms else None


def construire(
    dossier: Path, departements: Iterable[str], cache: Path
) -> Rapport:
    """Reconstruit les trois extraits du référentiel pour ces départements.

    Args:
        dossier: où écrire les CSV (`insee/referentiel/`).
        departements: codes de département à retenir.
        cache: dossier où garder les fichiers bruts téléchargés.

    Returns:
        Le rapport de construction.
    """
    departements = sorted(set(departements))
    dossier.mkdir(parents=True, exist_ok=True)

    pivot = _lignes(
        _membre_zip(_telecharger(COG_PIVOT, cache / "communes-01012019-csv.zip"),
                    "communes-01012019.csv")
    )
    populations = _populations(_telecharger(POPULATIONS, cache / "populations-2017.zip"))
    courant = _lignes(_telecharger(COG_COURANT, cache / "v_commune_courant.csv").decode("utf-8"))
    mouvements = _lignes(
        _telecharger(COG_MOUVEMENTS, cache / "v_mvt_commune_courant.csv").decode("utf-8")
    )

    # Une commune de plein exercice l'emporte sur l'entité déléguée qui partage
    # son code : c'est elle que désigne le code d'un cahier.
    retenues: dict[str, dict[str, str]] = {}
    for ligne in pivot:
        code = ligne["com"]
        if departement(code) not in departements:
            continue
        if code in retenues and retenues[code]["typecom"] == COMMUNE:
            continue
        retenues[code] = ligne

    rapport = Rapport(communes=len(retenues))
    for ligne in retenues.values():
        rapport.par_type[ligne["typecom"]] = rapport.par_type.get(ligne["typecom"], 0) + 1

    with (dossier / "communes_2019.csv").open("w", encoding="utf-8", newline="") as f:
        plume = csv.writer(f)
        plume.writerow(["code", "type", "commune_parente", "nom", "departement", "population"])
        for code in sorted(retenues):
            ligne = retenues[code]
            population = populations.get(code)
            if population is None:
                rapport.sans_population.append(code)
            plume.writerow([
                code,
                ligne["typecom"],
                ligne["comparent"],
                ligne["libelle"],
                departement(code),
                "" if population is None else population,
            ])

    coordonnees: dict[str, tuple[float, float]] = {}
    for dep in departements:
        reponse = requests.get(GEOMETRIE.format(departement=dep), timeout=120)
        reponse.raise_for_status()
        for commune in reponse.json():
            centre = commune.get("centre") or {}
            if centre.get("coordinates"):
                longitude, latitude = centre["coordinates"]
                coordonnees[commune["code"]] = (latitude, longitude)

    with (dossier / "geometrie.csv").open("w", encoding="utf-8", newline="") as f:
        plume = csv.writer(f)
        plume.writerow(["code", "latitude", "longitude"])
        for code in sorted(c for c in coordonnees if c in retenues):
            latitude, longitude = coordonnees[code]
            plume.writerow([code, latitude, longitude])
            rapport.avec_coordonnees += 1

    courantes = {ligne["COM"]: ligne for ligne in courant if ligne["TYPECOM"] == COMMUNE}
    tous: dict[str, list[dict]] = {}
    apres: dict[str, list[dict]] = {}
    for mouvement in mouvements:
        tous.setdefault(mouvement["COM_AV"], []).append(mouvement)
        if mouvement["DATE_EFF"] > PIVOT_EFFET:
            apres.setdefault(mouvement["COM_AV"], []).append(mouvement)

    with (dossier / "passage.csv").open("w", encoding="utf-8", newline="") as f:
        plume = csv.writer(f)
        plume.writerow(["code_2019", "code_courant", "nom_courant", "date_effet", "evenement"])
        for code in sorted(retenues):
            ligne = retenues[code]
            deleguee = ligne["typecom"] != COMMUNE
            # Une entité déjà déléguée au pivot n'a plus d'existence propre :
            # c'est sa commune parente qu'il faut suivre.
            depart = ligne["comparent"] if deleguee else code
            arrivee, chaine = _suivre(depart, apres, set(courantes))
            nom_courant = courantes[arrivee]["LIBELLE"] if arrivee in courantes else ""
            if arrivee == code and nom_courant == ligne["libelle"]:
                continue  # ni le code ni le nom n'ont bougé : pas de ligne
            # Ce qui explique la ligne, dans cet ordre : l'absorption antérieure
            # au pivot, le premier mouvement de la chaîne, le simple renommage.
            mouvement = (
                _absorption(code, tous)
                if deleguee
                else (chaine[0] if chaine else _renommage(code, apres))
            ) or {}
            plume.writerow([
                code,
                arrivee or "",
                nom_courant,
                mouvement.get("DATE_EFF", ""),
                EVENEMENTS.get(mouvement.get("MOD", ""), ""),
            ])
            rapport.passages += 1

    return rapport
