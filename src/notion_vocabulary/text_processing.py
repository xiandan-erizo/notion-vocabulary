"""Utilities for transforming raw text into clean vocabulary tokens."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable, Iterator

if TYPE_CHECKING:  # pragma: no cover
    from spacy.language import Language
    from spacy.tokens import Doc, Token
else:  # pragma: no cover - used to keep type checkers happy without runtime dependency
    Language = object  # type: ignore[misc,assignment]
    Doc = object  # type: ignore[misc,assignment]
    Token = object  # type: ignore[misc,assignment]


@dataclass(frozen=True)
class ProcessedToken:
    """A token that is ready to be stored in the vocabulary."""

    lemma: str
    sentence: str


class TokenProcessor:
    """Encapsulates the spaCy pipeline for token processing."""

    def __init__(self, language_model: str = "en_core_web_sm") -> None:
        import spacy

        self._model_name = language_model
        self._nlp: Language = spacy.load(language_model)

    @property
    def model_name(self) -> str:
        return self._model_name

    def iter_processed_tokens(self, text: str) -> Iterator[ProcessedToken]:
        """Yield lemma/context pairs from ``text``."""

        doc: Doc = self._nlp(text)
        for token in doc:  # type: ignore[assignment]
            if self._should_skip(token):
                continue
            sentence = token.sent.text.strip()  # type: ignore[union-attr]
            lemma = token.lemma_.lower()  # type: ignore[union-attr]
            if not lemma:
                continue
            yield ProcessedToken(lemma=lemma, sentence=sentence)

    def _should_skip(self, token: Token) -> bool:  # type: ignore[override]
        return bool(
            getattr(token, "is_stop", False)
            or getattr(token, "is_punct", False)
            or not getattr(token, "is_alpha", True)
        )


def collect_tokens(processor: TokenProcessor, texts: Iterable[str]) -> list[ProcessedToken]:
    """Process many pieces of text and return a list of processed tokens."""

    tokens: list[ProcessedToken] = []
    for text in texts:
        tokens.extend(processor.iter_processed_tokens(text))
    return tokens
