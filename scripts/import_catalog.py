"""CLI: импорт каталога с n-i.ru (логика в milk_bot.bot.services.catalog_import)."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from milk_bot.bot.services.catalog_import import run_catalog_import  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Import product catalog from n-i.ru")
    parser.add_argument(
        "--if-empty",
        action="store_true",
        help="Skip import when categories already exist in the database",
    )
    args = parser.parse_args()
    result = asyncio.run(run_catalog_import(if_empty=args.if_empty))
    if result is None:
        print("Skipped (catalog not empty).")
    else:
        print(
            f"Done: +{result.inserted} new, ~{result.updated} updated, "
            f"{result.deactivated} hidden, {result.products} from site"
        )


if __name__ == "__main__":
    main()
