"""
Project Atlas — Report Ingestion CLI Script
Location: backend/scripts/ingest_reports.py

Usage:
  python backend/scripts/ingest_reports.py
  python backend/scripts/ingest_reports.py --reports-dir data/reports
  python backend/scripts/ingest_reports.py --report-id R-101
  python backend/scripts/ingest_reports.py --force-reindex
"""

import sys
import argparse
from pathlib import Path

# Ensure project root is in sys.path
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.app.core.config import settings
from backend.app.services.ingestion import IngestionService
from backend.app.core.vector_store import vector_store


def main():
    parser = argparse.ArgumentParser(
        description="Project Atlas: Ingest PDF reports into persistent ChromaDB vector storage."
    )
    parser.add_argument(
        "--reports-dir",
        type=str,
        default=settings.REPORTS_DIR,
        help=f"Directory containing PDF reports (default: {settings.REPORTS_DIR})"
    )
    parser.add_argument(
        "--report-id",
        type=str,
        default=None,
        help="Specific report ID to ingest (e.g. R-101). If omitted, all reports in MySQL/catalog are processed."
    )
    parser.add_argument(
        "--force-reindex",
        action="store_true",
        help="Purge existing vectors for target reports before re-indexing."
    )

    args = parser.parse_args()

    print("=" * 65)
    print(" PROJECT ATLAS — REPORT INGESTION PIPELINE")
    print("=" * 65)
    print(f"Reports Directory    : {args.reports_dir}")
    print(f"ChromaDB Storage Dir : {settings.CHROMA_PERSIST_DIR}")
    print(f"ChromaDB Collection  : {settings.CHROMA_COLLECTION_NAME}")
    print(f"Ollama Base URL      : {settings.OLLAMA_BASE_URL}")
    print(f"Ollama Embed Model   : {settings.OLLAMA_EMBED_MODEL}")
    print(f"Chunk Size / Overlap : {settings.CHUNK_SIZE} / {settings.CHUNK_OVERLAP}")
    print(f"Force Reindex        : {args.force_reindex}")
    if args.report_id:
        print(f"Target Report ID     : {args.report_id}")
    print("-" * 65)

    service = IngestionService(
        reports_dir=args.reports_dir,
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        vector_store_instance=vector_store
    )

    targets = [args.report_id] if args.report_id else None
    summary = service.ingest_all(target_report_ids=targets, force_reindex=args.force_reindex)

    print("\n" + "=" * 65)
    print(" INGESTION PIPELINE EXECUTION SUMMARY")
    print("=" * 65)
    print(f"Total Reports Scanned  : {summary['reports_total']}")
    print(f"Reports Succeeded      : {summary['reports_succeeded']}")
    print(f"Reports Failed         : {summary['reports_failed']}")
    print(f"Reports Skipped/Empty  : {summary['reports_skipped']}")
    print(f"Total Pages Processed  : {summary['total_pages_processed']}")
    print(f"Total Chunks Stored    : {summary['total_chunks_stored']}")
    print("-" * 65)

    for item in summary["details"]:
        rid = item.get("report_id")
        status = item.get("status")
        if status == "success":
            print(f"  [SUCCESS] {rid} -> {item.get('pdf_file')} ({item.get('pages_processed')} pages, {item.get('chunks_stored')} chunks)")
        elif status == "failed":
            print(f"  [FAILED]  {rid} -> Error: {item.get('error')}")
        elif status == "skipped":
            print(f"  [SKIPPED] {rid} -> Reason: {item.get('reason')}")

    print("-" * 65)
    c_stats = summary.get("collection_stats", {})
    print(f"ChromaDB Total Chunks Now : {c_stats.get('total_chunks', 0)}")
    print(f"Indexed Report IDs        : {', '.join(c_stats.get('indexed_reports', [])) or 'None'}")
    print("=" * 65)

    if summary["reports_failed"] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
