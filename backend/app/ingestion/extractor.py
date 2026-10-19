"""
PDF Extraction Module for Project Atlas
Extracts text page-by-page from PDF documents using PyMuPDF.
"""

from pathlib import Path
from typing import List, Dict, Any
import logging
import pymupdf

logger = logging.getLogger(__name__)


class PDFExtractionError(Exception):
    """Custom exception raised when PDF extraction fails."""
    pass


class PDFExtractor:
    """Extracts text page-by-page from PDF files."""

    @staticmethod
    def extract_pages(pdf_path: str | Path) -> List[Dict[str, Any]]:
        """
        Extract text from a PDF file page by page.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            List of dicts containing page_number (1-indexed) and extracted text.

        Raises:
            FileNotFoundError: If the PDF does not exist.
            PDFExtractionError: If the PDF cannot be parsed or read.
        """
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found at: {path}")

        if not path.is_file():
            raise PDFExtractionError(f"Path is not a file: {path}")

        pages: List[Dict[str, Any]] = []

        try:
            doc = pymupdf.open(str(path))
        except Exception as e:
            raise PDFExtractionError(f"Failed to open PDF '{path.name}': {str(e)}") from e

        try:
            total_pages = len(doc)
            logger.info("Extracting %d pages from '%s'", total_pages, path.name)

            for page_index in range(total_pages):
                page_number = page_index + 1
                try:
                    page = doc.load_page(page_index)
                    text = page.get_text("text").strip()
                    pages.append({
                        "page_number": page_number,
                        "text": text,
                        "char_count": len(text)
                    })
                except Exception as page_err:
                    logger.warning("Error reading page %d of '%s': %s", page_number, path.name, page_err)
                    pages.append({
                        "page_number": page_number,
                        "text": "",
                        "char_count": 0,
                        "error": str(page_err)
                    })

        finally:
            doc.close()

        return pages
