from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

import httpx
from loguru import logger
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from milk_bot.bot.config import get_settings
from milk_bot.bot.db.models import Category, Product
from milk_bot.bot.services.n_i_catalog import (
    SEED_PAGES,
    category_from_url,
    discover_category_pages,
    discover_more_pages,
    fetch,
    parse_products_from_page,
)

def dedupe_products(items: list[dict]) -> list[dict]:
    by_url: dict[str, dict] = {}
    for raw in items:
        src = raw.get("source_url")
        if not src:
            continue
        if src not in by_url:
            by_url[src] = raw
            continue
        prev = by_url[src]
        if not prev.get("photo_url") and raw.get("photo_url"):
            prev["photo_url"] = raw["photo_url"]
        if not prev.get("description") and raw.get("description"):
            prev["description"] = raw["description"]
    return list(by_url.values())


def sync_url() -> str:
    settings = get_settings()
    u = settings.database_url
    if u.startswith("sqlite+aiosqlite"):
        return u.replace("sqlite+aiosqlite", "sqlite", 1)
    return u


def _apply_photo_from_site(product: Product, photo_url: str | None) -> None:
    """Обновить фото с сайта, не затирая уже закешированный Telegram file_id."""
    if not photo_url:
        return
    current = (product.photo_file_id or "").strip()
    if not current:
        product.photo_file_id = photo_url
        return
    if current.startswith(("http://", "https://")):
        if current != photo_url:
            product.photo_file_id = photo_url
        return


def upsert_category(session: Session, name: str) -> Category:
    row = session.scalars(select(Category).where(Category.name == name)).first()
    if row:
        return row
    c = Category(name=name, sort_order=0)
    session.add(c)
    session.flush()
    return c


def import_products(
    session: Session, items: Iterable[dict]
) -> tuple[int, int, int, set[str]]:
    inserted = updated = skipped = 0
    seen_urls: set[str] = set()
    for raw in items:
        try:
            cat = upsert_category(session, raw["category_hint"])
            src = raw.get("source_url")
            if src:
                seen_urls.add(src)
                existing = session.scalars(
                    select(Product).where(Product.source_url == src)
                ).first()
                photo = raw.get("photo_url")
                if existing:
                    existing.name = raw["name"]
                    existing.description = raw.get("description")
                    _apply_photo_from_site(existing, photo)
                    existing.category_id = cat.id
                    existing.is_active = True
                    updated += 1
                else:
                    session.add(
                        Product(
                            category_id=cat.id,
                            name=raw["name"],
                            description=raw.get("description"),
                            price=Decimal("0.00"),
                            photo_file_id=photo,
                            is_active=True,
                            source_url=src,
                        )
                    )
                    inserted += 1
            else:
                skipped += 1
        except Exception as exc:  # noqa: BLE001
            logger.exception("Skip product due to error: {} | {}", raw.get("name"), exc)
            skipped += 1
    return inserted, updated, skipped, seen_urls


def deactivate_missing(session: Session, seen_urls: set[str]) -> int:
    hidden = 0
    for product in session.scalars(select(Product).where(Product.source_url.isnot(None))):
        if product.source_url and product.source_url not in seen_urls:
            if product.is_active:
                product.is_active = False
                hidden += 1
    return hidden


@dataclass(frozen=True)
class ImportResult:
    inserted: int
    updated: int
    skipped: int
    deactivated: int
    pages: int
    products: int


def _category_count(session: Session) -> int:
    return int(session.scalar(select(func.count()).select_from(Category)) or 0)


async def run_catalog_import(*, if_empty: bool = False) -> ImportResult | None:
    os.environ.setdefault("BOT_TOKEN", os.environ.get("BOT_TOKEN", "0:import"))
    engine = create_engine(sync_url(), future=True)
    SessionLocal = sessionmaker(engine, expire_on_commit=False, class_=Session)

    if if_empty:
        with SessionLocal() as session:
            n = _category_count(session)
            if n > 0:
                logger.info("Catalog already has {} categories — skip import", n)
                return None

    collected: list[dict] = []
    seen_pages: set[str] = set()

    MAX_PAGES = 120
    queued_urls: set[str] = set()
    async with httpx.AsyncClient(headers={"User-Agent": "milk-bot-import/1.0"}) as client:
        queue = list(SEED_PAGES)
        for seed_url, _seed_cat in SEED_PAGES:
            try:
                seed_html = await fetch(client, seed_url)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Seed page fetch failed {}: {}", seed_url, exc)
                continue
            for url, cat in discover_category_pages(seed_html):
                if url not in queued_urls:
                    queue.append((url, cat))
                    queued_urls.add(url)
        for url, _ in queue:
            queued_urls.add(url)
        while queue and len(seen_pages) < MAX_PAGES:
            url, cat = queue.pop(0)
            if url in seen_pages:
                continue
            seen_pages.add(url)
            try:
                html = await fetch(client, url)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to fetch {}: {}", url, exc)
                continue
            page_cat = category_from_url(url, cat)
            items = parse_products_from_page(html, page_cat)
            for p in items:
                p["category_hint"] = category_from_url(p.get("source_url", ""), page_cat)
                collected.append(p)
            for extra in discover_more_pages(html):
                if extra in seen_pages or extra in queued_urls:
                    continue
                queued_urls.add(extra)
                guessed = category_from_url(extra, page_cat)
                queue.append((extra, guessed))

    collected = dedupe_products(collected)
    with_photo = sum(1 for p in collected if p.get("photo_url"))
    logger.info(
        "Parsed {} products ({} with image URL), from {} pages",
        len(collected),
        with_photo,
        len(seen_pages),
    )

    with SessionLocal() as session:
        ins, upd, sk, seen_urls = import_products(session, collected)
        deactivated = deactivate_missing(session, seen_urls)
        session.commit()
        result = ImportResult(
            inserted=ins,
            updated=upd,
            skipped=sk,
            deactivated=deactivated,
            pages=len(seen_pages),
            products=len(collected),
        )
        logger.info(
            "Import done: inserted={}, updated={}, skipped={}, deactivated={}",
            ins,
            upd,
            sk,
            deactivated,
        )
        return result
