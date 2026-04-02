"""Palavras aleatórias em português (maiúsculas, sem acentos) para códigos de verificação."""

from __future__ import annotations

import random
import unicodedata
from functools import lru_cache


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize('NFD', text)
    return ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')


@lru_cache(maxsize=1)
def _word_pool() -> tuple[str, ...]:
    from wordfreq import top_n_list

    raw = top_n_list('pt', n=200_000)
    seen: set[str] = set()
    out: list[str] = []
    for w in raw:
        w = w.strip()
        if not w or not w.isalpha():
            continue
        plain = _strip_accents(w).upper()
        if not plain.isascii() or not plain.isalpha():
            continue
        if not (4 <= len(plain) <= 16):
            continue
        if plain in seen:
            continue
        seen.add(plain)
        out.append(plain)
    return tuple(out)


def random_verification_word() -> str:
    pool = _word_pool()
    return random.choice(pool)
