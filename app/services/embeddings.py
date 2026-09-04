import hashlib
import math
import re
from functools import lru_cache

from app.core.config import get_settings

DIMENSIONS = 1024


def _hash_embedding(text: str) -> list[float]:
    vector = [0.0] * DIMENSIONS
    normalized = text.lower()
    tokens = re.findall(r"[a-z0-9_]+", normalized)
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", normalized))
    tokens.extend(chinese)
    tokens.extend(chinese[index : index + 2] for index in range(max(0, len(chinese) - 1)))
    for token in tokens:
        digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % DIMENSIONS
        vector[index] += 1.0 if digest[4] % 2 else -1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


@lru_cache
def _load_model():
    try:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(get_settings().embedding_model)
    except ImportError:
        return None


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = _load_model()
    if model is None:
        return [_hash_embedding(text) for text in texts]
    vectors = model.encode(texts, normalize_embeddings=True)
    return [vector.tolist() for vector in vectors]
