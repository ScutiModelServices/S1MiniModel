"""Sentence cutting for text that arrives in pieces (streaming) and for long input (chunking).

A piece is a sentence plus the whitespace that followed it, so joining pieces gives back the text.

shortcut: a boundary is `.`, `!` or `?` then whitespace, or a line break; "e.g. x" splits after "e.g." (harmless:
the pieces still join to the same text), upgrade to a real sentence segmenter if clients need exact sentences."""

from __future__ import annotations

import re
from typing import Callable

_END = re.compile(r"(?<=[.!?])\s+|\n+")


def cut(text: str) -> tuple[list[str], str]:
    """The complete pieces of `text` and the unfinished rest."""
    pieces, start = [], 0
    for match in _END.finditer(text):
        pieces.append(text[start:match.end()])
        start = match.end()
    return pieces, text[start:]


class SentenceBuffer:
    """Takes text as it is made; hands out each sentence once its end is seen."""

    def __init__(self) -> None:
        self._rest = ""

    def feed(self, text: str) -> list[str]:
        pieces, self._rest = cut(self._rest + text)
        return pieces

    def flush(self) -> str:
        """The unfinished last sentence (empty if none); call when the text ended."""
        rest, self._rest = self._rest, ""
        return rest


def chunks(text: str, count: Callable[[str], int], limit: int) -> list[str]:
    """`text` split at sentence ends into parts of at most `limit` tokens (`count` measures one). A single sentence
    longer than `limit` stays whole. Parts keep their trailing whitespace, so they join back to `text`."""
    pieces, rest = cut(text)
    if rest:
        pieces.append(rest)
    parts: list[str] = []
    current = ""
    for piece in pieces:
        if current and count(current + piece) > limit:
            parts.append(current)
            current = ""
        current += piece
    if current:
        parts.append(current)
    return parts
