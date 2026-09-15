"""Extract all PDFs from PATH_TO_DATA and persist them page by page.

Cahiers already in ``page_extraction`` are skipped up front, so the command
can be interrupted and relaunched on a large deposit and only does what is
left. Displays a concise recap of each created Contribution and the total
extraction time.
"""

import sys

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tqdm import tqdm

from database.db import check_connection, get_engine
from database.models import Base, Contribution, PageExtraction
from extraction.without_ocr.discovery import list_pdfs, require_path_to_data
from extraction.without_ocr.extract_text import extract_pdf_pages
from extraction.without_ocr.settings import logger
from extraction.without_ocr.timing import timed


@timed
def main() -> int:
    """Extract and persist all PDFs found in PATH_TO_DATA.

    Returns:
        0 if all PDFs were processed successfully, 1 otherwise.
    """
    data_dir = require_path_to_data()
    pdf_paths = list_pdfs(data_dir)

    logger.info(f"Found {len(pdf_paths)} PDF(s) in {data_dir.resolve()}")

    engine = get_engine()
    check_connection(engine)
    Base.metadata.create_all(engine)
    failed: list[str] = []
    succeeded: list[int] = []

    with Session(engine) as session:
        already = set(
            session.execute(select(PageExtraction.pdf_name).distinct()).scalars()
        )
        todo = [p for p in pdf_paths if p.name not in already]
        skipped = len(pdf_paths) - len(todo)
        if skipped:
            logger.info(f"  already extracted: {skipped} PDF(s), skipped")

        for pdf_path in tqdm(todo, desc="Extracting PDFs"):
            logger.debug(f"\nSelected PDF: {pdf_path.name}")
            logger.debug(f"Full path: {pdf_path.resolve()}")

            try:
                contribution_ids = extract_pdf_pages(pdf_path, engine=engine)
            except Exception as exc:  # noqa: BLE001 - catch any per-PDF failure to keep the batch running
                logger.warning(f"Failed to extract {pdf_path.name}: {exc}")
                failed.append(pdf_path.name)
                continue

            if not contribution_ids:
                logger.warning(f"No contributions created for {pdf_path.name}")
                failed.append(pdf_path.name)
                continue

            contributions = (
                session.execute(
                    select(Contribution).where(Contribution.id.in_(contribution_ids))
                )
                .scalars()
                .all()
            )

            page_count = (
                session.execute(
                    select(func.count(PageExtraction.id)).where(
                        PageExtraction.contribution_id.in_(contribution_ids)
                    )
                ).scalar()
                or 0
            )

            handwritten_count = sum(1 for c in contributions if c.is_handwritten)
            clean_count = len(contributions) - handwritten_count

            logger.debug(f"--- {pdf_path.name} ---")
            logger.debug(f"  contributions: {len(contributions)}")
            logger.debug(
                f"  city: {contributions[0].city if contributions else '(not set)'}"
            )
            logger.debug(
                f"  pages: {contributions[0].start_page if contributions else '?'}-{contributions[-1].end_page if contributions else '?'}"
            )
            logger.debug(f"  page_extraction_rows: {page_count}")
            logger.debug(f"  clean (needs_ocr=False): {clean_count}")
            logger.debug(f"  handwritten (needs_ocr=True): {handwritten_count}")

            succeeded.extend(contribution_ids)

    logger.info("\n=== Summary ===")
    logger.info(f"  processed: {len(succeeded)}")
    logger.info(f"  skipped (already extracted): {skipped}")
    logger.info(f"  failed: {len(failed)}")
    if failed:
        logger.info(f"  failed files: {', '.join(failed)}")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
