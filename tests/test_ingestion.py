import pytest
from src.chunking.chunker import chunk_text

def test_chunking_basic():
    text = "This is a simple text that needs to be chunked. " * 50
    chunks = chunk_text(text, chunk_size=100, overlap=10)
    assert len(chunks) > 0, "Chunker should produce at least one chunk for large text."
    assert all(isinstance(c, str) for c in chunks), "All chunks must be strings."
