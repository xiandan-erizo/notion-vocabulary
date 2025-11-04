"""Domain models used by the Notion Vocabulary project."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class WordStatus(str, Enum):
    """Enumeration of the learning status for a vocabulary entry."""

    UNMASTERED = "unmastered"
    LEARNING = "learning"
    MASTERED = "mastered"


@dataclass(slots=True)
class Word:
    """Represents a single word stored in the database."""

    id: int
    word: str
    frequency: int
    status: WordStatus
    first_seen: datetime
    last_seen: datetime


@dataclass(slots=True)
class Context:
    """Represents an example sentence associated with a word."""

    id: int
    word_id: int
    sentence: str


@dataclass(slots=True)
class WordWithContexts:
    """Aggregate that bundles a word with its example sentences."""

    word: Word
    contexts: list[Context]

    def add_context(self, context: Context) -> None:
        """Add a context to the aggregate if it is not already present."""

        if not any(existing.id == context.id for existing in self.contexts):
            self.contexts.append(context)


@dataclass(slots=True)
class WordUpsertResult:
    """Return value from the repository when upserting a word."""

    word: Word
    created: bool
    context_inserted: bool
    frequency_updated: bool

    @property
    def message(self) -> str:
        """Summarise the outcome in a human readable string."""

        parts: list[str] = []
        if self.created:
            parts.append("created word")
        if self.frequency_updated:
            parts.append("frequency updated")
        if self.context_inserted:
            parts.append("context inserted")
        if not parts:
            return "no changes"
        return ", ".join(parts)


def parse_status(value: Optional[str]) -> WordStatus:
    """Parse the textual status stored in the database."""

    if value is None:
        return WordStatus.UNMASTERED
    try:
        return WordStatus(value)
    except ValueError as exc:  # pragma: no cover - defensive programming
        raise ValueError(f"Unknown status value: {value!r}") from exc
