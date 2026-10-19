"""
Text Chunking Module for Project Atlas
Splits page text into overlapping semantic chunks with preserved metadata and deterministic IDs.
"""

from typing import List, Dict, Any, Optional
import re
import logging

logger = logging.getLogger(__name__)


class TextChunker:
    """Chunks page text into overlapping windows and attaches report metadata."""

    def __init__(self, chunk_size: int = 600, chunk_overlap: int = 100):
        if chunk_overlap >= chunk_size:
            raise ValueError(f"chunk_overlap ({chunk_overlap}) must be smaller than chunk_size ({chunk_size})")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    @staticmethod
    def generate_chunk_id(report_id: str, page_number: int, chunk_index: int) -> str:
        """
        Generate a deterministic, stable chunk identifier.
        Format: {report_id}_p{page_number}_c{chunk_index}
        Example: R-101_p1_c0
        """
        clean_report_id = str(report_id).strip().replace(" ", "_")
        return f"{clean_report_id}_p{page_number}_c{chunk_index}"

    def split_text(self, text: str) -> List[str]:
        """
        Split a given text into overlapping text windows.
        Tries to break cleanly on paragraph breaks, sentences, or word boundaries.
        """
        text = text.strip()
        if not text:
            return []

        # If text is already smaller than chunk_size, return as single chunk
        if len(text) <= self.chunk_size:
            return [text]

        chunks: List[str] = []
        step = self.chunk_size - self.chunk_overlap
        start = 0
        total_len = len(text)

        while start < total_len:
            end = min(start + self.chunk_size, total_len)
            chunk_slice = text[start:end]

            # Try to snap to the nearest sentence or word boundary if not at the very end
            if end < total_len:
                # Look for sentence boundary (.!?) in the last 20% of the slice
                boundary_window = chunk_slice[int(len(chunk_slice) * 0.75):]
                match = re.search(r'([.!?\n])\s+', boundary_window)
                if match:
                    split_offset = int(len(chunk_slice) * 0.75) + match.end()
                    chunk_slice = chunk_slice[:split_offset]
                else:
                    # Look for whitespace boundary
                    space_idx = chunk_slice.rfind(" ")
                    if space_idx > int(len(chunk_slice) * 0.6):
                        chunk_slice = chunk_slice[:space_idx]

            cleaned_chunk = chunk_slice.strip()
            if cleaned_chunk:
                chunks.append(cleaned_chunk)

            # Advance forward by length of chunk minus overlap
            advance = max(len(chunk_slice) - self.chunk_overlap, 1)
            start += advance

        return chunks

    def chunk_page(
        self,
        page_text: str,
        page_number: int,
        report_metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Chunk text from a single page and bind all report-level metadata.

        Args:
            page_text: Extracted page text.
            page_number: 1-indexed page number.
            report_metadata: Dictionary of report metadata (id, title, sector, etc.).

        Returns:
            List of chunk records with text, deterministic chunk_id, and metadata.
        """
        text_pieces = self.split_text(page_text)
        report_id = str(report_metadata.get("id", "UNKNOWN"))
        title = str(report_metadata.get("title", ""))
        publisher = str(report_metadata.get("publisher", ""))
        sector = str(report_metadata.get("sector", ""))
        region = str(report_metadata.get("region", "Global"))
        publication_year = int(report_metadata.get("publication_year", 0))
        access = str(report_metadata.get("access", "public"))

        chunk_records: List[Dict[str, Any]] = []

        for chunk_idx, chunk_content in enumerate(text_pieces):
            chunk_id = self.generate_chunk_id(report_id, page_number, chunk_idx)
            chunk_metadata = {
                "report_id": report_id,
                "title": title,
                "publisher": publisher,
                "sector": sector,
                "region": region,
                "publication_year": publication_year,
                "page_number": page_number,
                "chunk_index": chunk_idx,
                "access": access
            }

            chunk_records.append({
                "chunk_id": chunk_id,
                "text": chunk_content,
                "metadata": chunk_metadata
            })

        return chunk_records

    def chunk_extracted_pages(
        self,
        extracted_pages: List[Dict[str, Any]],
        report_metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Chunk all pages from a report.
        """
        all_chunks: List[Dict[str, Any]] = []
        for page_data in extracted_pages:
            page_num = page_data.get("page_number", 1)
            page_text = page_data.get("text", "")
            if not page_text:
                continue

            chunks = self.chunk_page(
                page_text=page_text,
                page_number=page_num,
                report_metadata=report_metadata
            )
            all_chunks.extend(chunks)

        return all_chunks
