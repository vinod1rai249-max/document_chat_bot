from backend.app.utils.text import chunk_text, clean_text


def test_clean_text_collapses_whitespace():
    assert clean_text("Hello   \n world\t!") == "Hello world !"


def test_chunk_text_creates_multiple_chunks():
    text = "abcdefghij" * 50
    chunks = chunk_text(text, chunk_size=100, overlap=10)
    assert len(chunks) > 1
    assert all(chunks)
