"""
Report Ingestion Pipeline Service for Project Atlas
Coordinates PDF extraction, chunking, metadata enrichment, embedding generation, and vector storage.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
from backend.app.core.config import settings
from backend.app.core.vector_store import VectorStore, vector_store as default_vector_store
from backend.app.ingestion.extractor import PDFExtractor, PDFExtractionError
from backend.app.ingestion.chunker import TextChunker
from backend.app.services.metadata_mapper import MetadataMapper

logger = logging.getLogger(__name__)


class IngestionService:
    """Service orchestrating PDF ingestion and vector persistence."""

    def __init__(
        self,
        reports_dir: Optional[str] = None,
        chunk_size: int = settings.CHUNK_SIZE,
        chunk_overlap: int = settings.CHUNK_OVERLAP,
        vector_store_instance: Optional[VectorStore] = None
    ):
        self.reports_dir = Path(reports_dir or settings.REPORTS_DIR)
        self.chunker = TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.vector_store = vector_store_instance or default_vector_store

    def find_pdf_for_report(self, report_id: str, report_title: str = "") -> Optional[Path]:
        """
        Locate corresponding PDF file in reports_dir.
        Checks for {report_id}.pdf, lowercase, or files containing the report_id in their filename.
        """
        if not self.reports_dir.exists():
            return None

        # 1. Exact match e.g. R-101.pdf or r-101.pdf
        candidates = [
            self.reports_dir / f"{report_id}.pdf",
            self.reports_dir / f"{report_id.lower()}.pdf",
            self.reports_dir / f"{report_id.upper()}.pdf"
        ]
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate

        # 2. Search for report_id substring in filename
        for file in self.reports_dir.glob("*.pdf"):
            if report_id.lower() in file.stem.lower():
                return file

        # 3. Check for matching title keywords if title provided
        if report_title:
            title_slug = "".join(c for c in report_title if c.isalnum()).lower()
            for file in self.reports_dir.glob("*.pdf"):
                file_slug = "".join(c for c in file.stem if c.isalnum()).lower()
                if title_slug and title_slug in file_slug:
                    return file

        return None

    def ingest_single_report(
        self,
        report_id: str,
        pdf_path: Optional[Path] = None,
        metadata: Optional[Dict[str, Any]] = None,
        force_reindex: bool = False
    ) -> Dict[str, Any]:
        """
        Ingest a single report PDF into ChromaDB.

        Args:
            report_id: Report ID (e.g. 'R-101').
            pdf_path: Optional explicit path to PDF.
            metadata: Optional explicit report metadata dict.
            force_reindex: If True, delete existing chunks before upserting.

        Returns:
            Dictionary with processing status, pages count, chunks count, or error.
        """
        # Resolve metadata
        if metadata is None:
            metadata = MetadataMapper.get_report_metadata(report_id) or {
                "id": report_id,
                "title": f"Report {report_id}",
                "publisher": "Unknown",
                "publication_year": 0,
                "sector": "General",
                "access": "paid",
                "region": "Global"
            }

        # Resolve PDF file path
        target_pdf = pdf_path or self.find_pdf_for_report(report_id, metadata.get("title", ""))
        if not target_pdf or not target_pdf.exists():
            msg = f"PDF for report '{report_id}' not found in '{self.reports_dir}'"
            logger.warning("[SKIP] %s", msg)
            return {
                "report_id": report_id,
                "status": "skipped",
                "reason": msg,
                "pages_processed": 0,
                "chunks_stored": 0
            }

        logger.info("Starting ingestion for report '%s' from file '%s'", report_id, target_pdf.name)

        # Step 1: Extract pages
        try:
            pages = PDFExtractor.extract_pages(target_pdf)
        except (FileNotFoundError, PDFExtractionError) as ext_err:
            msg = f"Failed to extract text from '{target_pdf.name}': {ext_err}"
            logger.error(msg)
            return {
                "report_id": report_id,
                "status": "failed",
                "error": msg,
                "pages_processed": 0,
                "chunks_stored": 0
            }

        if not pages:
            msg = f"PDF '{target_pdf.name}' contained no extractable pages."
            logger.warning(msg)
            return {
                "report_id": report_id,
                "status": "empty",
                "reason": msg,
                "pages_processed": 0,
                "chunks_stored": 0
            }

        # Step 2: Chunk pages with metadata
        chunks = self.chunker.chunk_extracted_pages(pages, metadata)

        # Step 3: Manage deduplication & persistence
        if force_reindex:
            self.vector_store.delete_report(report_id)

        stored_count = self.vector_store.upsert_chunks(chunks)

        logger.info(
            "Completed ingestion for '%s': %d page(s), %d chunk(s) stored in ChromaDB.",
            report_id,
            len(pages),
            stored_count
        )

        return {
            "report_id": report_id,
            "status": "success",
            "pdf_file": str(target_pdf.name),
            "pages_processed": len(pages),
            "chunks_stored": stored_count
        }

    def ingest_all(
        self,
        target_report_ids: Optional[List[str]] = None,
        force_reindex: bool = False
    ) -> Dict[str, Any]:
        """
        Run ingestion for all known reports or a specified list of report IDs.
        """
        all_metadata = MetadataMapper.get_all_reports_metadata()
        if target_report_ids:
            reports_to_process = {
                rid: all_metadata.get(rid, {"id": rid, "title": f"Report {rid}"})
                for rid in target_report_ids
            }
        else:
            reports_to_process = all_metadata

        self.reports_dir.mkdir(parents=True, exist_ok=True)

        results: List[Dict[str, Any]] = []
        total_pages = 0
        total_chunks = 0
        success_count = 0
        failed_count = 0
        skipped_count = 0

        logger.info("Scanning for %d report(s) in '%s'...", len(reports_to_process), self.reports_dir)

        for report_id, meta in reports_to_process.items():
            res = self.ingest_single_report(
                report_id=report_id,
                metadata=meta,
                force_reindex=force_reindex
            )
            results.append(res)

            status = res.get("status")
            if status == "success":
                success_count += 1
                total_pages += res.get("pages_processed", 0)
                total_chunks += res.get("chunks_stored", 0)
            elif status == "failed":
                failed_count += 1
            elif status in ("skipped", "empty"):
                skipped_count += 1

        summary = {
            "reports_total": len(reports_to_process),
            "reports_succeeded": success_count,
            "reports_failed": failed_count,
            "reports_skipped": skipped_count,
            "total_pages_processed": total_pages,
            "total_chunks_stored": total_chunks,
            "collection_stats": self.vector_store.get_stats(),
            "details": results
        }

        return summary
