"""Unit tests for PDF discovery helpers."""

from pathlib import Path

import pytest

from extraction.without_ocr.discovery import (
    _natural_sort_key,
    categorie,
    first_pdf,
    index_pdfs,
    list_pdfs,
    require_path_to_data,
)


def test_natural_sort_key_handles_numbers():
    p1 = Path("page_2.pdf")
    p2 = Path("page_10.pdf")
    assert _natural_sort_key(p1) < _natural_sort_key(p2)


def test_list_pdfs_returns_only_pdf_files(tmp_path: Path):
    (tmp_path / "a.pdf").touch()
    (tmp_path / "b.txt").touch()
    (tmp_path / "c.pdf").touch()

    result = list_pdfs(tmp_path)
    assert [p.name for p in result] == ["a.pdf", "c.pdf"]


def test_list_pdfs_sorts_naturally(tmp_path: Path):
    (tmp_path / "page_10.pdf").touch()
    (tmp_path / "page_2.pdf").touch()
    (tmp_path / "page_1.pdf").touch()

    result = list_pdfs(tmp_path)
    assert [p.name for p in result] == ["page_1.pdf", "page_2.pdf", "page_10.pdf"]


def test_list_pdfs_raises_when_directory_does_not_exist():
    with pytest.raises(FileNotFoundError):
        list_pdfs("/does/not/exist")


def test_list_pdfs_raises_when_not_a_directory(tmp_path: Path):
    file = tmp_path / "not_a_dir.pdf"
    file.touch()
    with pytest.raises(NotADirectoryError):
        list_pdfs(file)


def test_list_pdfs_raises_when_no_pdf_found(tmp_path: Path):
    with pytest.raises(ValueError):
        list_pdfs(tmp_path)


def test_first_pdf_returns_first_sorted_pdf(tmp_path: Path):
    (tmp_path / "z.pdf").touch()
    (tmp_path / "a.pdf").touch()

    assert first_pdf(tmp_path).name == "a.pdf"


def test_first_pdf_raises_when_no_pdf_found(tmp_path: Path):
    with pytest.raises(ValueError):
        first_pdf(tmp_path)


def test_require_path_to_data_uses_setting(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "extraction.without_ocr.discovery.settings.path_to_data",
        str(tmp_path),
    )
    assert require_path_to_data() == tmp_path


def test_require_path_to_data_raises_when_empty(monkeypatch):
    monkeypatch.setattr(
        "extraction.without_ocr.discovery.settings.path_to_data",
        "",
    )
    with pytest.raises(ValueError):
        require_path_to_data()


def test_list_pdfs_walks_the_bnf_tree(tmp_path: Path):
    """Un dossier par département, les cahiers sous CC/, l'inventaire à part."""
    for dept, nom in (
        ("01", "CC_01000_190304_01053_MD_15462.pdf"),
        ("65", "CC_65000_190301_65440_MD_20001.pdf"),
    ):
        dossier = tmp_path / f"BnF_GDN_{dept}_PDF" / "CC"
        dossier.mkdir(parents=True)
        (dossier / nom).touch()
    (tmp_path / "Bnf_GDN_02_PDF" / "CC").mkdir(parents=True)
    (tmp_path / "Bnf_GDN_02_PDF" / "CC" / "CC_02000_190304_02168_MD_15900.pdf").touch()
    (tmp_path / "A_lire").mkdir()
    (tmp_path / "A_lire" / "BNF_GDN_01_Ain_inventaire_contributions.pdf").touch()
    (tmp_path / "BnF_GDN_01_PDF" / "CC" / "Thumbs.db").touch()

    result = [str(p.relative_to(tmp_path)) for p in list_pdfs(tmp_path)]
    assert result == [
        "BnF_GDN_01_PDF/CC/CC_01000_190304_01053_MD_15462.pdf",
        "BnF_GDN_65_PDF/CC/CC_65000_190301_65440_MD_20001.pdf",
        "Bnf_GDN_02_PDF/CC/CC_02000_190304_02168_MD_15900.pdf",
    ]


def test_list_pdfs_raises_when_only_inventories(tmp_path: Path):
    (tmp_path / "A_lire").mkdir()
    (tmp_path / "A_lire" / "inventaire.pdf").touch()
    with pytest.raises(ValueError):
        list_pdfs(tmp_path)


def test_index_pdfs_maps_names_to_paths(tmp_path: Path):
    (tmp_path / "d1").mkdir()
    (tmp_path / "d1" / "a.pdf").touch()
    (tmp_path / "b.pdf").touch()

    index = index_pdfs(tmp_path)
    assert index == {"a.pdf": tmp_path / "d1" / "a.pdf", "b.pdf": tmp_path / "b.pdf"}


def test_index_pdfs_refuses_a_duplicated_name(tmp_path: Path):
    for d in ("d1", "d2"):
        (tmp_path / d).mkdir()
        (tmp_path / d / "a.pdf").touch()
    with pytest.raises(ValueError, match="appears twice"):
        index_pdfs(tmp_path)


@pytest.mark.parametrize(
    ("nom", "attendu"),
    [
        ("CC_01000_190304_01053_MD_15462.pdf", "CC"),
        ("CO_01000_190215_D_02389.pdf", "CO"),
        ("CR_01150_190304_MD_02737.pdf", "CR"),
        ("IL_28220_190322_M_01189.pdf", "IL"),
        ("cc_01000_190304_01053_MD_15462.pdf", "CC"),
        ("Cahier_citoyen_test.pdf", None),
        ("CCX_1.pdf", None),
        ("a.pdf", None),
    ],
)
def test_categorie_lue_dans_le_prefixe(nom, attendu):
    assert categorie(nom) == attendu


def test_list_pdfs_filtre_par_categorie(tmp_path: Path):
    """Les quatre catégories du versement ne se chargent pas ensemble."""
    for d, n in (
        ("CC", "CC_01000_190304_01053_MD_15462.pdf"),
        ("CO", "CO_01000_190215_D_02389.pdf"),
        ("CR", "CR_01150_190304_MD_02737.pdf"),
    ):
        (tmp_path / d).mkdir()
        (tmp_path / d / n).touch()
    (tmp_path / "hors_convention.pdf").touch()

    assert [p.name[:2] for p in list_pdfs(tmp_path, ["CC"])] == ["CC"]
    assert [p.name[:2] for p in list_pdfs(tmp_path, ["co", "CR"])] == ["CO", "CR"]
    assert len(list_pdfs(tmp_path)) == 4
    with pytest.raises(ValueError):
        list_pdfs(tmp_path, ["IL"])
