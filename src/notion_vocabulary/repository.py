"""Database repository that encapsulates MySQL interactions."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime
from typing import TYPE_CHECKING, Iterable, Iterator, Optional

from .config import DatabaseConfig
from .models import Context, Word, WordStatus, WordUpsertResult, parse_status

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    from mysql.connector.connection import MySQLConnection
    from mysql.connector.cursor import MySQLCursorDict
else:
    MySQLConnection = object  # type: ignore[misc,assignment]
    MySQLCursorDict = object  # type: ignore[misc,assignment]


class VocabularyRepository:
    """High level wrapper around the ``words`` and ``contexts`` tables."""

    def __init__(self, config: DatabaseConfig):
        self._config = config

    @contextmanager
    def _cursor(self) -> Iterator[MySQLCursorDict]:
        import mysql.connector  # Imported lazily to avoid mandatory dependency at import time

        connection: MySQLConnection = mysql.connector.connect(
            **self._config.as_connector_kwargs()
        )
        cursor: MySQLCursorDict = connection.cursor(dictionary=True)
        try:
            yield cursor
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def get_word(self, word: str) -> Optional[Word]:
        """Fetch a word by its lemma from the database."""

        query = (
            "SELECT id, word, frequency, status, first_seen, last_seen "
            "FROM words WHERE word = %s"
        )
        with self._cursor() as cursor:
            cursor.execute(query, (word,))
            row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_word(row)

    def upsert_word_with_context(self, word: str, sentence: str) -> WordUpsertResult:
        """Insert or update a word and attach the provided context."""

        with self._cursor() as cursor:
            return self._upsert_word_with_context(cursor, word, sentence)

    def upsert_many_words_with_context(
        self, items: Iterable[tuple[str, str]]
    ) -> list[WordUpsertResult]:
        """Persist multiple words and contexts using a single database connection."""

        results: list[WordUpsertResult] = []
        with self._cursor() as cursor:
            for word, sentence in items:
                results.append(self._upsert_word_with_context(cursor, word, sentence))
        return results

    def _upsert_word_with_context(
        self, cursor: MySQLCursorDict, word: str, sentence: str
    ) -> WordUpsertResult:
        cursor.execute("SELECT id, frequency FROM words WHERE word = %s", (word,))
        row = cursor.fetchone()
        if row is None:
            word_id = self._insert_word(cursor, word)
            created = True
            frequency_updated = False
        else:
            word_id = int(row["id"])
            created = False
            frequency_updated = self._increment_frequency(cursor, word_id)

        context_inserted = self._insert_context(cursor, word_id, sentence)
        cursor.execute(
            "SELECT id, word, frequency, status, first_seen, last_seen "
            "FROM words WHERE id = %s",
            (word_id,),
        )
        word_row = cursor.fetchone()
        if word_row is None:  # pragma: no cover - highly unlikely
            raise RuntimeError("Failed to fetch word after upsert operation")
        return WordUpsertResult(
            word=self._row_to_word(word_row),
            created=created,
            context_inserted=context_inserted,
            frequency_updated=frequency_updated,
        )

    def _insert_word(self, cursor: MySQLCursorDict, word: str) -> int:
        query = (
            "INSERT INTO words (word, frequency, status, first_seen, last_seen) "
            "VALUES (%s, %s, %s, %s, %s)"
        )
        now = datetime.utcnow()
        cursor.execute(
            query,
            (
                word,
                1,
                WordStatus.UNMASTERED.value,
                now,
                now,
            ),
        )
        return int(cursor.lastrowid)

    def _increment_frequency(self, cursor: MySQLCursorDict, word_id: int) -> bool:
        query = (
            "UPDATE words SET frequency = frequency + 1, "
            "last_seen = CURRENT_TIMESTAMP WHERE id = %s"
        )
        cursor.execute(query, (word_id,))
        return cursor.rowcount > 0

    def _insert_context(self, cursor: MySQLCursorDict, word_id: int, sentence: str) -> bool:
        query = (
            "INSERT IGNORE INTO contexts (word_id, sentence) VALUES (%s, %s)"
        )
        cursor.execute(query, (word_id, sentence))
        return cursor.rowcount > 0

    def _row_to_word(self, row: dict[str, object]) -> Word:
        return Word(
            id=int(row["id"]),
            word=str(row["word"]),
            frequency=int(row["frequency"]),
            status=parse_status(row.get("status")),
            first_seen=row["first_seen"],
            last_seen=row["last_seen"],
        )

    def fetch_word_with_contexts(self, word: str) -> Optional[dict[str, object]]:
        """Return a serialisable representation of a word and its contexts."""

        with self._cursor() as cursor:
            cursor.execute(
                "SELECT id, word, frequency, status, first_seen, last_seen "
                "FROM words WHERE word = %s",
                (word,),
            )
            word_row = cursor.fetchone()
            if word_row is None:
                return None
            cursor.execute(
                "SELECT id, word_id, sentence FROM contexts WHERE word_id = %s",
                (word_row["id"],),
            )
            contexts = cursor.fetchall()
        word_obj = self._row_to_word(word_row)
        context_objs = [
            Context(
                id=int(context_row["id"]),
                word_id=int(context_row["word_id"]),
                sentence=str(context_row["sentence"]),
            )
            for context_row in contexts
        ]
        result = asdict(word_obj)
        result["status"] = word_obj.status.value
        result["contexts"] = [asdict(context) for context in context_objs]
        return result
