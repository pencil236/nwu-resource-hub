from app.services.documents import chunk_text
from app.services.embeddings import embed_texts


def test_chunk_text_keeps_overlap_and_content():
    text = "第一章 极限\n" + "重要内容。" * 1000
    chunks = chunk_text(text, size=200, overlap=20)
    assert len(chunks) > 2
    assert all(chunks)
    assert all(len(chunk) <= 200 for chunk in chunks)


def test_fallback_embedding_is_normalized_and_deterministic():
    first, second = embed_texts(["高等数学积分", "高等数学积分"])
    assert first == second
    assert len(first) == 1024
    assert abs(sum(value * value for value in first) - 1.0) < 1e-6
