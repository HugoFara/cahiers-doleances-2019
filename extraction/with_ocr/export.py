"""Déposer un run de transcription en fichiers texte, sous `data/`.

La base est la référence, mais elle vit dans un volume podman : quinze heures
de GPU y tiennent sans autre copie. Ce module écrit chaque page transcrite en
un fichier `.txt` lisible sans outil, avec un manifeste, dans un dossier par
run :

    data/transcriptions/run_18_ornith-1.5-9b/
        run.json                  le run tel qu'en base (label, modèle, paramètres, notes)
        manifeste.csv             une ligne par page : ids, cahier, page, score, longueur
        <cahier>/p<page>.txt      le texte de la page, tel qu'en base

`data/` est hors dépôt (NDA) : ces fichiers ne sont jamais commités. Le dépôt
est **incrémental** : relancé sur un run qui avance, il n'écrit que les pages
nouvelles ou changées, et le manifeste est réécrit en entier.

    uv run python -m extraction.with_ocr.export --run-id 18
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.db import check_connection, get_engine
from database.models import PageTranscription, Run
from database.runs import TRANSCRIPTION

DOSSIER_DEFAUT = Path("data/transcriptions")
COLONNES = ("id", "page_extraction_id", "pdf_name", "page_number", "quality_score", "caracteres", "fichier")


def nom_dossier(run: Run) -> str:
    """`run_<id>_<modèle>`, le modèle réduit à ce qu'un chemin accepte."""
    modele = re.sub(r"[^A-Za-z0-9.-]+", "-", run.model or "sans-modele").strip("-")
    return f"run_{run.id}_{modele}"


def chemin_page(dossier: Path, page: PageTranscription) -> Path:
    cahier = Path(page.pdf_name or "sans-cahier").stem
    return dossier / cahier / f"p{page.page_number:04d}.txt"


def deposer(session: Session, run: Run, racine: Path) -> tuple[Path, int, int]:
    """Écrit le run sous `racine`. Retourne (dossier, pages écrites, pages inchangées)."""
    dossier = racine / nom_dossier(run)
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / "run.json").write_text(
        json.dumps(
            {
                "id": run.id, "kind": run.kind, "label": run.label, "model": run.model,
                "source": run.source, "prompt_version": run.prompt_version,
                "parameters": run.parameters, "corpus": run.corpus, "author": run.author,
                "created_at": run.created_at.isoformat() if run.created_at else None,
                "active": run.active, "notes": run.notes,
            },
            ensure_ascii=False, indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    pages = session.scalars(
        select(PageTranscription)
        .where(PageTranscription.run_id == run.id)
        .order_by(PageTranscription.pdf_name, PageTranscription.page_number)
    )
    ecrites = inchangees = 0
    lignes = []
    for page in pages:
        fichier = chemin_page(dossier, page)
        texte = page.text or ""
        if fichier.exists() and fichier.read_text(encoding="utf-8") == texte:
            inchangees += 1
        else:
            fichier.parent.mkdir(parents=True, exist_ok=True)
            fichier.write_text(texte, encoding="utf-8")
            ecrites += 1
        lignes.append((
            page.id, page.page_extraction_id, page.pdf_name, page.page_number,
            page.quality_score, len(texte), str(fichier.relative_to(dossier)),
        ))
    with (dossier / "manifeste.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLONNES)
        w.writerows(lignes)
    return dossier, ecrites, inchangees


def main(run_id: int, racine: Path) -> int:
    engine = get_engine()
    check_connection(engine)
    with Session(engine) as session:
        run = session.get(Run, run_id)
        if run is None or run.kind != TRANSCRIPTION:
            print(f"run {run_id} : introuvable ou pas un run de transcription", file=sys.stderr)
            return 1
        dossier, ecrites, inchangees = deposer(session, run, racine)
    print(f"{dossier} : {ecrites} page(s) écrite(s), {inchangees} inchangée(s), manifeste réécrit")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--run-id", type=int, required=True, help="le run de transcription à déposer")
    parser.add_argument("--dossier", type=Path, default=DOSSIER_DEFAUT, help=f"racine du dépôt (défaut : {DOSSIER_DEFAUT})")
    args = parser.parse_args()
    sys.exit(main(args.run_id, args.dossier))
