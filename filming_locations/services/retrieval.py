"""외부 API 없이 문자 n-gram TF-IDF로 관련 청크를 고른다.

로컬 어휘 검색이며, 과제의 의미 임베딩 검색은 후속 구현 대상이다.
"""
import math
import re
from collections import Counter

from settings import limits


def features(text):
    tokens = []
    for word in re.findall(r"[가-힣a-z0-9]+", text.casefold()):
        tokens.append(word)
        tokens.extend(word[i:i + 2] for i in range(len(word) - 1))
    return Counter(tokens)


def retrieve(question, sources, history):
    config = limits()
    chunks, seen = [], set()
    for source in sources:
        text = source["text"]
        for start in range(0, len(text), config["chunk_size"] - config["chunk_overlap"]):
            snippet = text[start:start + config["chunk_size"]].strip()
            if snippet and snippet not in seen:
                chunks.append(dict(source, text=snippet, chunk_start=start))
                seen.add(snippet)
    if not chunks:
        return []
    previous = next((m["content"][-200:] for m in reversed(history) if m["role"] == "user"), "")
    query = features(question + " " + previous)
    vectors = [features(c["title"] + " " + c["text"]) for c in chunks]
    frequencies = Counter(token for vector in vectors for token in vector)
    idf = {token: math.log(1 + len(vectors) / (1 + freq)) for token, freq in frequencies.items()}

    def score(vector):
        norm = math.sqrt(sum((count * idf[token]) ** 2 for token, count in vector.items())) or 1
        return sum(query[token] * count * idf[token] ** 2 for token, count in vector.items()) / norm

    ranked = sorted(range(len(chunks)), key=lambda i: score(vectors[i]), reverse=True)
    selected, budget = [], config["context_chars"]
    for index in ranked:
        if score(vectors[index]) <= 0 or len(selected) >= config["top_k"] or budget <= 0:
            break
        chunk = dict(chunks[index], text=chunks[index]["text"][:budget])
        selected.append(chunk)
        budget -= len(chunk["text"])
    return selected
