"""PDF discovery helpers for the data directory.

``PATH_TO_DATA`` is walked recursively: a flat folder of cahiers works, and so
does the tree of the BnF deposit (``BnF_GDN_<dept>_PDF/CC/<cahier>.pdf``, one
folder per département — mind ``Bnf_GDN_65_PDF``, whose case differs). A
cahier is identified by its file name alone, wherever it sits in the tree.
"""

import re
from pathlib import Path

from extraction.without_ocr.settings import settings

# Folders of the BnF deposit that hold something other than cahiers: ``A_lire``
# carries one inventory PDF per département, not contributions.
DOSSIERS_HORS_CORPUS = frozenset({"A_lire"})


def _natural_sort_key(path: Path) -> list[str | int]:
    """Return a sort key that mixes alphabetical and numeric ordering.

    Splits the path into alternating text and integer chunks so that
    ``page_2.pdf`` sorts before ``page_10.pdf``.
    """
    parts = re.split(r"(\d+)", str(path))
    return [int(part) if part.isdigit() else part for part in parts]


def list_pdfs(path: str | Path) -> list[Path]:
    """List PDF files under a directory, recursively, sorted in natural order.

    Args:
        path: Directory containing the PDFs, flat or as the BnF tree.

    Returns:
        A list of ``Path`` objects pointing to ``*.pdf`` files, ordered by
        their path relative to ``path``.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        NotADirectoryError: If ``path`` is not a directory.
        ValueError: If no PDF is found.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"PATH_TO_DATA directory not found: {p}")
    if not p.is_dir():
        raise NotADirectoryError(f"PATH_TO_DATA is not a directory: {p}")

    pdfs = sorted(
        (
            f
            for f in p.rglob("*.pdf")
            if f.is_file()
            and DOSSIERS_HORS_CORPUS.isdisjoint(f.relative_to(p).parts[:-1])
        ),
        key=lambda f: _natural_sort_key(f.relative_to(p)),
    )
    if not pdfs:
        raise ValueError(f"No PDF found in {p}")

    return pdfs


def index_pdfs(path: str | Path) -> dict[str, Path]:
    """Map each cahier's file name to its path under ``path``.

    The database only stores file names; the tree is the deposit's business.
    Two files with the same name in different folders would make the name
    ambiguous, so this refuses rather than picking one silently.

    Raises:
        ValueError: If a file name appears more than once, or no PDF is found.
    """
    index: dict[str, Path] = {}
    for pdf in list_pdfs(path):
        if pdf.name in index:
            raise ValueError(
                f"{pdf.name} appears twice under {path}: {index[pdf.name]} and {pdf}"
            )
        index[pdf.name] = pdf
    return index


def first_pdf(path: str | Path) -> Path:
    """Return the first PDF from the data directory.

    Thin wrapper around :func:`list_pdfs` for the common single-file case.

    Args:
        path: Directory containing the PDFs.

    Returns:
        The first PDF path (sorted in natural order).
    """
    return list_pdfs(path)[0]


def require_path_to_data() -> Path:
    """Read ``path_to_data`` from settings and ensure it is configured.

    Returns:
        The configured data directory as a ``Path``.

    Raises:
        ValueError: If ``PATH_TO_DATA`` is empty or not configured.
    """
    raw = settings.path_to_data
    if not raw:
        raise ValueError(
            "PATH_TO_DATA is not set. Add it to your .env file "
            "(`PATH_TO_DATA=/path/to/pdfs`)."
        )
    return Path(raw)
