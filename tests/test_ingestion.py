"""
Unit Tests for Report Ingestion and Vector Storage Pipeline
Tests text extraction, chunking, metadata preservation, and duplicate prevention.
"""

import sys
import tempfile
from pathlib import Path
import pytest
import pymupdf

# Ensure project root in sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.app.ingestion.extractor import PDFExtractor
from backend.app.ingestion.chunker import TextChunker
from backend.app.core.vector_store import VectorStore
from backend.app.services.ingestion import IngestionService


@pytest.fixture
def sample_pdf():
    """Generates a temporary multi-page PDF for test verification."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    doc = pymupdf.open()
    # Page 1
    page1 = doc.new_page()
    page1.insert_text(
        (50, 72),
        "Page 1: Global Smart Water Meter Market Analysis.\n"
        "The smart water meter market is expanding rapidly worldwide.\n"
        "Key drivers include automated meter reading and regulatory mandates."
    )
    # Page 2
    page2 = doc.new_page()
    page2.insert_text(
        (50, 72),
        "Page 2: Regional Market Forecast.\n"
        "The global market reached USD 4.21 billion in 2024.\n"
        "Forecasted CAGR is 11.2% between 2025 and 2030."
    )
    doc.save(str(tmp_path))
    doc.close()

    yield tmp_path

    if tmp_path.exists():
        tmp_path.unlink()


def test_pdf_extraction(sample_pdf):
    """Verify page-by-page text extraction preserves page numbers and text."""
    pages = PDFExtractor.extract_pages(sample_pdf)
    assert len(pages) == 2
    assert pages[0]["page_number"] == 1
    assert "Global Smart Water Meter Market" in pages[0]["text"]
    assert pages[1]["page_number"] == 2
    assert "USD 4.21 billion" in pages[1]["text"]


def test_missing_pdf_handling():
    """Verify missing PDF raises FileNotFoundError without crashing."""
    with pytest.raises(FileNotFoundError):
        PDFExtractor.extract_pages("non_existent_report_123.pdf")


def test_chunking_and_metadata_preservation():
    """Verify text chunker preserves report ID, page number, and custom metadata."""
    chunker = TextChunker(chunk_size=150, chunk_overlap=30)
    meta = {
        "id": "R-101",
        "title": "Global Smart Water Meter Market 2025",
        "publisher": "CMR",
        "sector": "Utilities",
        "region": "Global, APAC",
        "publication_year": 2025,
        "access": "paid"
    }

    sample_text = (
        "The global smart water meter market was valued at USD 4.21 billion in 2024 "
        "and is expected to grow at a CAGR of 11.2% from 2025 to 2030. "
        "Asia-Pacific accounted for 38% of 2024 revenue. The region exhibits high adoption "
        "due to government infrastructure renewal and leak detection programs."
    )

    chunks = chunker.chunk_page(page_text=sample_text, page_number=8, report_metadata=meta)

    assert len(chunks) >= 1
    for chunk in chunks:
        # Check chunk ID structure
        assert chunk["chunk_id"].startswith("R-101_p8_c")
        # Check metadata fields
        m = chunk["metadata"]
        assert m["report_id"] == "R-101"
        assert m["page_number"] == 8
        assert m["title"] == "Global Smart Water Meter Market 2025"
        assert m["sector"] == "Utilities"
        assert m["region"] == "Global, APAC"
        assert m["publication_year"] == 2025
        assert m["access"] == "paid"
        assert len(chunk["text"]) > 0


def test_deduplication_in_vector_store():
    """Verify stable chunk IDs prevent duplicate records upon repeated ingestion."""
    # Use ignore_cleanup_errors=True to prevent Windows file lock conflicts with sqlite3
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        store = VectorStore(persist_dir=tmp_dir, collection_name="test_dedup")

        chunks = [
            {
                "chunk_id": "R-101_p1_c0",
                "text": "The global smart water meter market was valued at USD 4.21 billion in 2024.",
                "metadata": {"report_id": "R-101", "page_number": 1, "sector": "Utilities"}
            },
            {
                "chunk_id": "R-101_p1_c1",
                "text": "Forecasted CAGR is 11.2% from 2025 to 2030 with strong APAC adoption.",
                "metadata": {"report_id": "R-101", "page_number": 1, "sector": "Utilities"}
            }
        ]

        # First ingestion
        count_first = store.upsert_chunks(chunks)
        assert count_first == 2
        assert store.collection.count() == 2

        # Second ingestion with identical chunk IDs (simulating repeated ingestion)
        count_second = store.upsert_chunks(chunks)
        assert count_second == 2
        # Count MUST remain 2 (no duplicate chunks created)
        assert store.collection.count() == 2

        # Verify search returns unique chunk
        results = store.query_similar("smart water meter market", n_results=5)
        assert len(results) == 2


def test_ingestion_service_skips_missing_safely():
    """Verify IngestionService handles missing PDFs gracefully without throwing errors."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_reports_dir, \
         tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_chroma:
        store = VectorStore(persist_dir=tmp_chroma, collection_name="test_skip")
        service = IngestionService(reports_dir=tmp_reports_dir, vector_store_instance=store)

        result = service.ingest_single_report("R-MISSING-999")
        assert result["status"] == "skipped"
        assert "not found" in result["reason"]
        assert result["chunks_stored"] == 0
