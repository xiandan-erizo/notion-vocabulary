"""Command line interface for the Notion Vocabulary pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from .config import DatabaseConfig
from .pipeline import VocabularyPipeline


def _load_texts(source: Path) -> Iterable[str]:
    if source.is_dir():
        for path in sorted(source.rglob("*.txt")):
            yield path.read_text(encoding="utf-8")
    else:
        yield source.read_text(encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Text file or directory to process")
    parser.add_argument("--host", required=True, help="MySQL host")
    parser.add_argument("--port", type=int, default=3306, help="MySQL port")
    parser.add_argument("--user", required=True, help="Database user")
    parser.add_argument("--password", required=True, help="Database password")
    parser.add_argument("--database", required=True, help="Schema name")
    parser.add_argument(
        "--language-model",
        default="en_core_web_sm",
        help="spaCy language model (default: en_core_web_sm)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path where the JSON summary will be written",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    texts = list(_load_texts(args.source))
    config = DatabaseConfig(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database,
    )
    pipeline = VocabularyPipeline(config, language_model=args.language_model)
    results = pipeline.process_many(texts)

    summary = [result.__dict__ for result in results]
    if args.output:
        args.output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    else:
        print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
