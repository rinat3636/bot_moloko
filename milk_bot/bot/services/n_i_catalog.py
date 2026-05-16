"""Парсинг каталога n-i.ru без зависимости от БД (импорт, PDF-инструкция)."""

from __future__ import annotations

from urllib.parse import urljoin, urlparse

import httpx
from selectolax.parser import HTMLParser, Node

BASE = "https://n-i.ru"

CATEGORY_PAGES: dict[str, str] = {
    "moloko": "Молоко",
    "kefir": "Кефир",
    "kefir-2": "Тан",
    "tvorog": "Творог",
    "smetana": "Сметана",
    "jogurt": "Йогурт",
    "maslo-slivochnoe": "Масло сливочное",
    "maslo-toplenoe": "Масло топлёное",
    "syrki": "Сырки",
    "smetanno-tvorozhnye": "Сметанно-творожные",
    "tvorozhki": "Творожки",
    "slivki": "Сливки",
    "ryazhenka": "Ряженка",
    "ryazhenka-i-prostokvasha": "Ряженка",
    "prostokvasha": "Простокваша",
    "31-prostokvasha-2": "Кисели",
    "35-airan": "Айран",
    "produkty-dlya-vashego-biznesa": "Продукты для бизнеса",
}

_SKIP_URL_PARTS = (
    "kontakty",
    "dostavka",
    "vakansii",
    "o-nas",
    "poslednie-novosti",
    "shablon",
    "template",
    "internet-magazin",
)


def _clean_category_label(raw: str) -> str:
    label = " ".join(raw.split()).strip(" .")
    if not label or label.lower().startswith("подробнее"):
        return ""
    if len(label) > 80:
        return ""
    return label


def _is_category_index_link(url: str) -> bool:
    path = urlparse(url).path.lower()
    if not path.endswith(".html"):
        return False
    if any(part in path for part in _SKIP_URL_PARTS):
        return False
    parts = [p for p in path.strip("/").split("/") if p]
    if not parts:
        return False
    last = parts[-1].removesuffix(".html")
    if len(parts) == 1:
        return parts[0] not in ("index.html", "katalog-produktsii.html")
    if "katalog-produktsii" in path:
        return "poslednie-novosti" not in path
    if len(parts) >= 2 and last and last[0].isdigit():
        return False
    return False


def _is_crawlable_catalog_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    if not path.endswith(".html"):
        return False
    if any(part in path for part in _SKIP_URL_PARTS):
        return False
    if _is_category_index_link(url):
        return True
    parts = [p for p in path.strip("/").split("/") if p]
    if len(parts) >= 2 and parts[-1] and parts[-1][0].isdigit():
        return True
    return any(f"/{slug}" in path or path.endswith(f"{slug}.html") for slug in CATEGORY_PAGES)


def discover_category_pages(html: str) -> list[tuple[str, str]]:
    tree = HTMLParser(html)
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for a in tree.css(".item-title a, h2.item-title a"):
        href = a.attributes.get("href", "")
        if not href:
            continue
        full = _abs_url(href)
        if not _is_category_index_link(full):
            continue
        path = urlparse(full).path.lower()
        slug = path.rsplit("/", 1)[-1].removesuffix(".html")
        label = _clean_category_label(_text(a)) or CATEGORY_PAGES.get(slug, "")
        if not label:
            continue
        if full not in seen:
            seen.add(full)
            found.append((full, label))
    return found


def build_seed_pages() -> list[tuple[str, str]]:
    return [
        (f"{BASE}/katalog-produktsii/sobstvennaya-produktsiya.html", "Каталог"),
        (f"{BASE}/katalog-produktsii/chuzhaya.html", "Доп. ассортимент"),
    ]


SEED_PAGES: list[tuple[str, str]] = build_seed_pages()


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


def category_from_url(url: str, fallback: str) -> str:
    path = urlparse(url).path.lower().strip("/")
    if path.endswith(".html"):
        slug = path.rsplit("/", 1)[-1].removesuffix(".html")
        if slug in CATEGORY_PAGES:
            return CATEGORY_PAGES[slug]
    for slug, name in CATEGORY_PAGES.items():
        if f"/{slug}/" in path or path.startswith(f"{slug}/"):
            return name
    low = url.lower()
    if "chuzhaya" in low:
        return "Доп. ассортимент"
    if "katalog-produktsii" in low:
        return fallback or "Каталог"
    return fallback or "Прочее"


def discover_more_pages(html: str, limit: int = 120) -> list[str]:
    tree = HTMLParser(html)
    urls: list[str] = []
    for a in tree.css("a"):
        href = a.attributes.get("href", "")
        if not href or href.startswith("#"):
            continue
        full = _abs_url(href)
        if urlparse(full).netloc and "n-i.ru" not in urlparse(full).netloc:
            continue
        if not _is_crawlable_catalog_url(full):
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


async def fetch_site_category_names() -> list[str]:
    names: dict[str, str] = {}
    async with httpx.AsyncClient(headers={"User-Agent": "milk-bot-import/1.0"}) as client:
        for url, _ in SEED_PAGES:
            try:
                html = await fetch(client, url)
            except Exception:  # noqa: BLE001
                continue
            for _, label in discover_category_pages(html):
                names[label.casefold()] = label
    return sorted(names.values(), key=str.casefold)
