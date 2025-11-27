"""CLI + helpers to push local files (including Drive downloads and employee CSV) into Pinecone."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from dotenv import load_dotenv

from services.rag_service import EmbeddingClient, PineconeVectorStore, build_rag_service_from_env

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent  # Backend/services
REPO_ROOT = BASE_DIR.parents[1]
DEFAULT_EMPLOYEE_CSV = REPO_ROOT / "Backend" / "employee_database.csv"
DEFAULT_DRIVE_DIR = REPO_ROOT / "scripts" / "downloads"
ALLOWED_TEXT_SUFFIXES = {".txt", ".md", ".json", ".log", ".html", ".csv"}

# Load env like the Flask app so local CLI runs the same way.
load_dotenv(REPO_ROOT / ".env", override=False)
load_dotenv(REPO_ROOT / "Backend" / ".env", override=False)


@dataclass
class DocumentChunk:
    """Normalized chunk ready for embedding/upsert."""

    id: str
    text: str
    metadata: Dict[str, Any]


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 120) -> List[str]:
    """Simple word-based chunker to keep prompts small for embeddings."""
    words = text.split()
    if not words:
        return []

    chunks: List[str] = []
    start = 0
    while start < len(words):
        end = min(len(words), start + chunk_size)
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = max(end - overlap, start + 1)
    return chunks


def hash_id(seed: str) -> str:
    return hashlib.md5(seed.encode("utf-8")).hexdigest()


def mask_pii(text: str) -> str:
    """
    Basic redaction for emails, phone-like numbers, and long digit strings.
    Conservative approach: hide most characters, keep minimal suffixes.
    """
    # emails
    text = re.sub(r"([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+)", r"***@\2", text)
    # phone numbers (digits, dashes, spaces, parentheses)
    text = re.sub(r"\+?\d[\d\-\s().]{6,}\d", "***-REDACTED-PHONE***", text)
    # long digit strings (8+ digits) like bank/account numbers
    text = re.sub(r"\b\d{8,}\b", lambda m: "***" + m.group(0)[-4:], text)
    return text


def build_chunks_from_file(path: Path, *, source_type: str) -> List[DocumentChunk]:
    """Convert a single file into chunks with metadata."""
    try:
        rel_path = path.relative_to(REPO_ROOT)
    except ValueError:
        rel_path = path

    suffix = path.suffix.lower()

    # Skip non-text/binary types to avoid leaking raw binary/pdf contents.
    if suffix not in ALLOWED_TEXT_SUFFIXES:
        logger.info("Skipping non-text file for ingestion: %s", rel_path)
        return []

    if suffix == ".csv":
        return list(_build_chunks_from_csv(path, rel_path))

    raw_text = path.read_text(encoding="utf-8", errors="ignore")

    if not raw_text.strip():
        logger.info("Skipping empty file: %s", rel_path)
        return []

    chunks = []
    for idx, chunk in enumerate(chunk_text(raw_text), start=1):
        chunk_id = hash_id(f"{rel_path}:{idx}")
        masked = mask_pii(chunk)
        metadata = {
            "source": str(rel_path),
            "file_name": path.name,
            "chunk": idx,
            "source_type": source_type,
            "text": masked,
        }
        chunks.append(DocumentChunk(id=chunk_id, text=masked, metadata=metadata))
    return chunks


def _build_chunks_from_csv(path: Path, rel_path: Path) -> Iterable[DocumentChunk]:
    """Treat each CSV row as its own document."""
    with path.open(newline="", encoding="utf-8", errors="ignore") as handle:
        reader = csv.DictReader(handle)
        for row_idx, row in enumerate(reader, start=1):
            row_text = " | ".join(f"{k}: {v}" for k, v in row.items() if v)
            if not row_text:
                continue
            row_text = mask_pii(row_text)
            chunk_id = hash_id(f"{rel_path}:row:{row_idx}")
            metadata = {
                "source": str(rel_path),
                "file_name": path.name,
                "row": row_idx,
                "source_type": "employee_record",
                "text": row_text,
            }
            # Lift common HR fields so they can be filtered in Pinecone UI.
            for key in ("first_name", "last_name", "email", "department", "designation", "employee_id"):
                if key in row and row[key]:
                    metadata[key] = mask_pii(str(row[key]))
            yield DocumentChunk(id=chunk_id, text=row_text, metadata=metadata)


def discover_paths(paths: Sequence[str]) -> List[Path]:
    """Expand provided paths into a list of files."""
    found: List[Path] = []
    for raw_path in paths:
        path = Path(raw_path).expanduser()
        if not path.exists():
            logger.warning("Path does not exist, skipping: %s", raw_path)
            continue
        if path.is_dir():
            for file_path in path.rglob("*"):
                if file_path.is_file():
                    found.append(file_path)
        else:
            found.append(path)
    return found


class RAGIngestor:
    """Embeds chunks and writes them into Pinecone."""

    def __init__(self, embedder: EmbeddingClient, vector_store: PineconeVectorStore):
        self.embedder = embedder
        self.vector_store = vector_store

    def ingest(self, chunks: Sequence[DocumentChunk], batch_size: int = 20) -> int:
        total = 0
        batch: List[Dict[str, Any]] = []
        for chunk in chunks:
            vector = self.embedder.embed(chunk.text)
            batch.append({"id": chunk.id, "vector": vector, "metadata": chunk.metadata})
            if len(batch) >= batch_size:
                self.vector_store.upsert(batch)
                total += len(batch)
                batch.clear()

        if batch:
            self.vector_store.upsert(batch)
            total += len(batch)
        return total


def default_search_paths() -> List[Path]:
    """Return existing defaults (employee CSV + Drive downloads if present)."""
    defaults: List[Path] = []
    if DEFAULT_EMPLOYEE_CSV.exists():
        defaults.append(DEFAULT_EMPLOYEE_CSV)
    if DEFAULT_DRIVE_DIR.exists():
        defaults.append(DEFAULT_DRIVE_DIR)
    return defaults


def main():
    parser = argparse.ArgumentParser(description="Ingest local files into Pinecone for RAG.")
    parser.add_argument(
        "--path",
        action="append",
        dest="paths",
        help="File or directory to ingest (repeatable). Defaults to employee_database.csv and scripts/downloads if they exist.",
    )
    parser.add_argument(
        "--namespace",
        help="Override Pinecone namespace (otherwise uses PINECONE_DEFAULT_NAMESPACE or 'main').",
    )
    args = parser.parse_args()

    rag_service = build_rag_service_from_env()
    if args.namespace:
        rag_service.pinecone_config.namespace = args.namespace
        rag_service.vector_store.config.namespace = args.namespace

    candidate_paths = args.paths or [str(p) for p in default_search_paths()]
    if not candidate_paths:
        raise SystemExit("No input paths provided and no defaults found. Use --path to specify files or folders.")

    files = discover_paths(candidate_paths)
    if not files:
        raise SystemExit("No files found to ingest.")

    logger.info("Preparing chunks from %d files", len(files))
    chunks: List[DocumentChunk] = []
    for file_path in files:
        source_type = "drive_file" if DEFAULT_DRIVE_DIR in file_path.parents else "file"
        if file_path == DEFAULT_EMPLOYEE_CSV:
            source_type = "employee_csv"
        chunks.extend(build_chunks_from_file(file_path, source_type=source_type))

    if not chunks:
        raise SystemExit("No text content found in provided paths.")

    logger.info("Embedding and upserting %d chunks into namespace '%s'...", len(chunks), rag_service.pinecone_config.namespace)
    ingestor = RAGIngestor(rag_service.embedder, rag_service.vector_store)
    total = ingestor.ingest(chunks)
    print(json.dumps(
        {
            "status": "ok",
            "namespace": rag_service.pinecone_config.namespace,
            "files_processed": len(files),
            "chunks_written": total,
        },
        indent=2,
    ))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
