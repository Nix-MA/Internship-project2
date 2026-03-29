"""
ingestion package — document loading, text extraction, chunking.
"""
from src.ingestion.extractor import extract_document, detect_file_type
from src.chunking.chunker import chunk_text, deduplicate_chunks
