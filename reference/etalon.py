"""L'étalon : où commence chaque doléance, dit par un humain.

Deux fichiers, et la raison de leur séparation est la protection des données.

- **Le fichier de travail** (`data/reference/`, ignoré par git) porte le texte
  des cahiers, ligne à ligne : c'est ce que l'annotateur ouvre dans un tableur
  et complète. Il ne doit jamais être commité — ce sont des écrits nominatifs de
  personnes privées, dans un dépôt public.
- **L'étalon figé** (`reference/etalon/`, commité) ne garde que les
  coordonnées et une **empreinte** de chaque ligne. Il est donc versionnable, et
  reste vérifiable : si l'extraction change, les empreintes ne correspondent
  plus et le désalignement est détecté au lieu d'être silencieux.

L'étalon ne dépend d'aucun run. C'est ce à quoi les runs sont comparés.
"""

import csv
import hashlib
import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from segmentation.decoupage import Ligne
from segmentation.persistance import grouper_par_cahier, lire_pages

RACINE_TRAVAIL = Path("data/reference")
RACINE_ETALON = Path(__file__).resolve().parent / "etalon"

COLONNES_TRAVAIL = ["pdf_name", "page", "ligne", "texte", "debut_doleance"]
# Un corpus décalé produit un écart par ligne : on en montre assez pour
# comprendre, pas de quoi noyer le message.
MAX_ECARTS_MONTRES = 5
COLONNES_ETALON = ["pdf_name", "page", "ligne", "empreinte", "debut_doleance"]


class EtalonDesaligne(Exception):
    """Le corpus a bougé sous l'étalon : les empreintes ne correspondent plus."""


@dataclass(frozen=True)
class LigneEtalon:
    """Une ligne annotée : où elle est, ce qu'elle valait, ce qu'on en a dit."""

    pdf_name: str
    page: int
    ligne: int
    empreinte: str
    debut_doleance: bool


def empreinte(texte: str) -> str:
    """Empreinte courte et stable d'une ligne, insensible à l'espacement.

    Normalisation Unicode et espaces écrasés : l'extraction peut changer sa
    façon de recoller les mots sans que la ligne soit une autre ligne. Elle ne
    permet pas de retrouver le texte, seulement de vérifier qu'il n'a pas changé.
    """
    normalise = " ".join(unicodedata.normalize("NFC", texte).split())
    return hashlib.sha256(normalise.encode("utf-8")).hexdigest()[:16]


def lignes_des_cahiers(
    session: Session, cahiers: list[str], garder_pages_ocr: bool = False
) -> dict[str, list[Ligne]]:
    """Les lignes de ces cahiers, dans l'ordre, telles que le découpage les voit.

    Passe par les mêmes fonctions que `segmentation/` : un étalon construit sur
    d'autres lignes que celles évaluées ne mesurerait rien.
    """
    voulus = set(cahiers)
    groupes = grouper_par_cahier(lire_pages(session, garder_pages_ocr))
    return {
        pdf_name: [
            Ligne(texte=t, page=p.page_number)
            for p in pages
            for t in (p.text or "").split("\n")
            if t.strip()
        ]
        for pdf_name, pages in groupes.items()
        if pdf_name in voulus
    }


def ecrire_fichier_de_travail(
    chemin: Path, lignes_par_cahier: dict[str, list[Ligne]]
) -> int:
    """Écrit le CSV que l'annotateur complète. Renvoie le nombre de lignes.

    `debut_doleance` est pré-rempli à 1 sur la première ligne de chaque cahier
    — elle en ouvre forcément une — et vide ailleurs : à l'annotateur de poser
    les autres. Pré-remplir avec la prédiction du découpage biaiserait l'étalon
    vers ce qu'on cherche justement à évaluer.
    """
    chemin.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with chemin.open("w", encoding="utf-8", newline="") as f:
        writeur = csv.DictWriter(f, fieldnames=COLONNES_TRAVAIL)
        writeur.writeheader()
        for pdf_name in sorted(lignes_par_cahier):
            for i, ligne in enumerate(lignes_par_cahier[pdf_name]):
                writeur.writerow({
                    "pdf_name": pdf_name,
                    "page": ligne.page,
                    "ligne": i,
                    "texte": ligne.texte,
                    "debut_doleance": 1 if i == 0 else "",
                })
                total += 1
    return total


def figer(chemin_travail: Path, chemin_etalon: Path) -> int:
    """Transforme le fichier de travail annoté en étalon commitable.

    Le texte est remplacé par son empreinte : l'étalon devient versionnable
    sans emporter les écrits des contributeurs dans un dépôt public.

    Returns:
        Le nombre de débuts de doléance retenus.
    """
    with chemin_travail.open(encoding="utf-8", newline="") as f:
        lignes = list(csv.DictReader(f))

    manquantes = set(COLONNES_TRAVAIL) - set(lignes[0] if lignes else [])
    if manquantes:
        raise ValueError(f"colonnes absentes du fichier de travail : {sorted(manquantes)}")

    chemin_etalon.parent.mkdir(parents=True, exist_ok=True)
    debuts = 0
    with chemin_etalon.open("w", encoding="utf-8", newline="") as f:
        writeur = csv.DictWriter(f, fieldnames=COLONNES_ETALON)
        writeur.writeheader()
        for ligne in lignes:
            marque = _vrai(ligne["debut_doleance"])
            debuts += marque
            writeur.writerow({
                "pdf_name": ligne["pdf_name"],
                "page": ligne["page"],
                "ligne": ligne["ligne"],
                "empreinte": empreinte(ligne["texte"]),
                "debut_doleance": 1 if marque else 0,
            })
    return debuts


def _vrai(valeur: str) -> bool:
    """Ce qu'un annotateur écrit pour dire oui, dans un tableur."""
    return str(valeur).strip().lower() in {"1", "x", "oui", "true", "vrai"}


def lire_etalon(chemin: Path) -> list[LigneEtalon]:
    """Relit un étalon figé."""
    with chemin.open(encoding="utf-8", newline="") as f:
        return [
            LigneEtalon(
                pdf_name=r["pdf_name"],
                page=int(r["page"]),
                ligne=int(r["ligne"]),
                empreinte=r["empreinte"],
                debut_doleance=r["debut_doleance"] == "1",
            )
            for r in csv.DictReader(f)
        ]


def verifier_alignement(
    etalon: list[LigneEtalon], lignes_par_cahier: dict[str, list[Ligne]]
) -> None:
    """Vérifie que l'étalon décrit bien le corpus actuel.

    Un étalon désaligné donnerait des scores parfaitement crédibles et
    parfaitement faux : mieux vaut refuser d'évaluer.

    Raises:
        EtalonDesaligne: si un cahier manque ou si une empreinte ne correspond pas.
    """
    ecarts = []
    for ligne in etalon:
        if len(ecarts) >= MAX_ECARTS_MONTRES:
            break
        lignes = lignes_par_cahier.get(ligne.pdf_name)
        if lignes is None:
            ecarts.append(f"{ligne.pdf_name} : absent du corpus")
        elif ligne.ligne >= len(lignes):
            ecarts.append(f"{ligne.pdf_name} ligne {ligne.ligne} : au-delà du cahier")
        elif empreinte(lignes[ligne.ligne].texte) != ligne.empreinte:
            ecarts.append(f"{ligne.pdf_name} ligne {ligne.ligne} : texte différent")
    if ecarts:
        raise EtalonDesaligne(
            "L'étalon ne décrit plus ce corpus (l'extraction a-t-elle changé ?) :\n  "
            + "\n  ".join(ecarts)
        )


def ecrire_metadonnees(chemin: Path, donnees: dict) -> None:
    """Sidecar JSON : ce qui rend le tirage rejouable et les mesures pondérables."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(donnees, ensure_ascii=False, indent=2) + "\n")


def lire_metadonnees(chemin: Path) -> dict:
    return json.loads(chemin.read_text())
