"""Le dépôt d'un run en fichiers texte : chemins, incrément, manifeste."""

import csv
import json
from datetime import datetime, timezone
from types import SimpleNamespace

from extraction.with_ocr.export import chemin_page, deposer, nom_dossier


def _run(**extra):
    base = dict(
        id=18, kind="transcription", label="OCR ornith-1.5:9b — manuscrit",
        model="ornith-1.5:9b", source="extraction.with_ocr", prompt_version=None,
        parameters={"format": "jpeg"}, corpus="manuscrit", author="x",
        created_at=datetime(2026, 9, 11, 9, 14, tzinfo=timezone.utc), active=True, notes=None,
    )
    return SimpleNamespace(**{**base, **extra})


def _page(id, pdf, num, texte, score=0.9):
    return SimpleNamespace(
        id=id, page_extraction_id=100 + id, pdf_name=pdf, page_number=num,
        text=texte, quality_score=score, run_id=18,
    )


class _Session:
    def __init__(self, pages):
        self.pages = pages

    def scalars(self, _stmt):
        return iter(self.pages)


class TestChemins:
    def test_le_dossier_porte_l_id_et_un_modele_sans_caractere_interdit(self):
        assert nom_dossier(_run()) == "run_18_ornith-1.5-9b"
        assert nom_dossier(_run(model=None)) == "run_18_sans-modele"

    def test_la_page_va_sous_son_cahier_numerotee_sur_quatre_chiffres(self, tmp_path):
        p = chemin_page(tmp_path, _page(1, "CC_01004_Ambérieu_MD_x.pdf", 7, ""))
        assert p == tmp_path / "CC_01004_Ambérieu_MD_x" / "p0007.txt"


class TestDeposer:
    def test_ecrit_les_pages_le_run_et_le_manifeste(self, tmp_path):
        pages = [_page(1, "A.pdf", 1, "un"), _page(2, "A.pdf", 2, "deux"), _page(3, "B.pdf", 1, "")]
        dossier, ecrites, inchangees = deposer(_Session(pages), _run(), tmp_path)
        assert (ecrites, inchangees) == (3, 0)
        assert (dossier / "A" / "p0001.txt").read_text(encoding="utf-8") == "un"
        assert (dossier / "B" / "p0001.txt").read_text(encoding="utf-8") == ""
        run = json.loads((dossier / "run.json").read_text(encoding="utf-8"))
        assert run["model"] == "ornith-1.5:9b" and run["created_at"].startswith("2026-09-11")
        with (dossier / "manifeste.csv").open(encoding="utf-8") as f:
            lignes = list(csv.DictReader(f))
        assert len(lignes) == 3
        assert lignes[1]["fichier"] == "A/p0002.txt" and lignes[1]["caracteres"] == "4"

    def test_relancer_n_ecrit_que_ce_qui_a_change(self, tmp_path):
        pages = [_page(1, "A.pdf", 1, "un"), _page(2, "A.pdf", 2, "deux")]
        deposer(_Session(pages), _run(), tmp_path)
        pages[1].text = "deux, relu"
        pages.append(_page(3, "A.pdf", 3, "trois"))
        _, ecrites, inchangees = deposer(_Session(pages), _run(), tmp_path)
        assert (ecrites, inchangees) == (2, 1)
