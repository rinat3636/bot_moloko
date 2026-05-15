from __future__ import annotations

import asyncio
import sys
from decimal import Decimal
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse

import httpx
from loguru import logger
from selectolax.parser import HTMLParser, Node
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from milk_bot.bot.config import get_settings  # noqa: E402
from milk_bot.bot.db.models import Category, Product  # noqa: E402

BASE = "https://n-i.ru"
SEED_PAGES: list[tuple[str, str]] = [
    (f"{BASE}/moloko.html", "Молоко"),
    (f"{BASE}/katalog-produktsii/sobstvennaya-produktsiya.html", "Собственная продукция"),
    (f"{BASE}/katalog-produktsii/chuzhaya.html", "Доп. ассортимент"),
]


def _abs_url(href: str) -> str:
    return urljoin(BASE + "/", href)


def _text(node: Node | None) -> str:
    if node is None:
        return ""
    return " ".join(node.text().split()).strip()


def _first_img_src(block: Node) -> str | None:
    img = block.css_first("img")
    if img is None:
        return None
    src = img.attributes.get("src")
    if not src:
        return None
    return _abs_url(src)


def parse_products_from_page(html: str, default_category: str) -> list[dict]:
    tree = HTMLParser(html)
    out: list[dict] = []
    for item in tree.css("div.blog div.item"):
        title_a = item.css_first("h2.item-title a") or item.css_first(".item-title a")
        if title_a is None:
            continue
        name = _text(title_a)
        if not name:
            continue
        href = title_a.attributes.get("href", "")
        source_url = _abs_url(href) if href else None
        desc_parts: list[str] = []
        for p in item.css(".content-wrapper p"):
            t = _text(p)
            if t and not t.lower().startswith("подробнее"):
                desc_parts.append(t)
        description = "\n".join(desc_parts) if desc_parts else None
        photo = _first_img_src(item)
        out.append(
            {
                "name": name,
                "description": description,
                "photo_url": photo,
                "source_url": source_url,
                "category_hint": default_category,
            }
        )
    return out


def discover_more_pages(html: str, limit: int = 40) -> list[str]:
    tree = HTMLParser(html)
    urls: list[str] = []
    for a in tree.css("a"):
        href = a.attributes.get("href", "")
        if not href or href.startswith("#"):
            continue
        full = _abs_url(href)
        if urlparse(full).netloc and "n-i.ru" not in urlparse(full).netloc:
            continue
        path = urlparse(full).path.lower()
        if not full.endswith(".html"):
            continue
        if not (
            "/moloko/" in path
            or path.endswith("/moloko.html")
            or "/katalog-produktsii/" in path
        ):
            continue
        if full not in urls:
            urls.append(full)
        if len(urls) >= limit:
            break
    return urls


async def fetch(client: httpx.AsyncClient, url: str) -> str:
    r = await client.get(url, timeout=30.0)
    r.raise_for_status()
    return r.text


def sync_url() -> str:
    settings = get_settings()
    u = settings.database_url
    if u.startswith("sqlite+aiosqlite"):
        return u.replace("sqlite+aiosqlite", "sqlite", 1)
    return u


def upsert_category(session: Session, name: str) -> Category:
    row = session.scalars(select(Category).where(Category.name == name)).first()
    if row:
        return row
    c = Category(name=name, sort_order=0)
    session.add(c)
    session.flush()
    return c


def import_products(session: Session, items: Iterable[dict]) -> tuple[int, int, int]:
    inserted = updated = skipped = 0
    for raw in items:
        try:
            cat = upsert_category(session, raw["category_hint"])
            src = raw.get("source_url")
            if src:
                existing = session.scalars(
                    select(Product).where(Product.source_url == src)
                ).first()
                price = Decimal("0.00")
                photo = raw.get("photo_url")
                if existing:
                    existing.name = raw["name"]
                    existing.description = raw.get("description")
                    existing.photo_file_id = photo
                    existing.category_id = cat.id
                    existing.is_active = True
                    updated += 1
                else:
                    session.add(
                        Product(
                            category_id=cat.id,
                            name=raw["name"],
                            description=raw.get("description"),
                            price=price,
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
    return inserted, updated, skipped


async def run_import() -> None:
    import os

    os.environ.setdefault("BOT_TOKEN", "0:import")
    settings = get_settings()
    logger.remove()
    logger.add(sys.stderr, level=settings.log_level)
    engine = create_engine(sync_url(), future=True)
    SessionLocal = sessionmaker(engine, expire_on_commit=False, class_=Session)

    collected: list[dict] = []
    seen_pages: set[str] = set()

    MAX_PAGES = 60
    async with httpx.AsyncClient(headers={"User-Agent": "milk-bot-import/1.0"}) as client:
        queue = list(SEED_PAGES)
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
            items = parse_products_from_page(html, cat)
            for p in items:
                collected.append(p)
            for extra in discover_more_pages(html):
                if extra not in seen_pages and extra not in [u for u, _ in queue]:
                    guessed = cat
                    low = extra.lower()
                    if "chuzhaya" in low:
                        guessed = "Доп. ассортимент"
                    elif "sobstvennaya" in low or "moloko" in low:
                        guessed = "Молоко" if "moloko" in low else "Собственная продукция"
                    queue.append((extra, guessed))

    with SessionLocal() as session:
        ins, upd, sk = import_products(session, collected)
        session.commit()
        logger.info("Import done: inserted={}, updated={}, skipped={}", ins, upd, sk)


def main() -> None:
    asyncio.run(run_import())


if __name__ == "__main__":
    main()
