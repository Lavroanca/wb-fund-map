#!/usr/bin/env python3
"""Обогащает lots.geojson деталями со страниц лотов Фонда имущества.

Берём текущий lots.geojson, для каждого лота:
- строим URL карточки (spaces / buildings / nto) по categoryId/objectTypeId
- скачиваем HTML
- выдёргиваем:
  - этаж расположения
  - наличие самовольной перепланировки (по тексту в примечаниях)
  - RAW-текст примечаний (на будущее для более тонкого анализа)

Результат: создаётся файл fund_lot_details.json вида:
{
  "5115": {
    "floor": "1",
    "has_unauthorized_replan": true,
    "notes": "..."
  },
  ...
}

Запускать по необходимости вручную (это живой парсинг сайта, не cron по умолчанию).
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict

import requests

WORKDIR = Path(__file__).resolve().parent
LOTS_PATH = WORKDIR / "lots.geojson"
OUTPUT_PATH = WORKDIR / "fund_lot_details.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def build_lot_url(props: Dict[str, Any]) -> str:
    """Формирует URL карточки по правилам, как в wb_map.html."""
    lot_id = props.get("id")
    if not lot_id:
        raise ValueError("no id in properties")

    category_id = props.get("categoryId")
    object_type_id = props.get("objectTypeId")

    base = "https://xn--80adfeoyeh6akig5e.xn--p1ai/realty"

    # НТО
    if category_id == 12 or object_type_id == 12:
        return f"{base}/nto/{lot_id}"

    # Здания с земельным участком
    if category_id == 3 or object_type_id == 3:
        return f"{base}/buildings/{lot_id}"

    # Остальные торги по недвижимости / ЗУ
    return f"{base}/spaces/{lot_id}"


def fetch_html(url: str) -> str:
    resp = SESSION.get(url, timeout=15)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


def extract_floor(html: str) -> str | None:
    """Выдёргивает значение поля "Этаж расположения" (сырая строка)."""

    pattern = re.compile(
        r"<b[^>]*class=\"dotted-line-left\"[^>]*>\s*<span>\s*Этаж расположения\s*</span>\s*</b>\s*"  # noqa: E501
        r"<b[^>]*class=\"dotted-line-right\"[^>]*>\s*<span>([^<]+)</span>",
        re.IGNORECASE | re.DOTALL,
    )
    m = pattern.search(html)
    if not m:
        return None
    return m.group(1).strip()


def classify_floor(raw: str | None) -> str | None:
    """Классифицирует этаж: подвал / цоколь / 1 / выше / другое.

    Возвращает один из: "basement", "semi", "1", "other", или None.
    """
    if not raw:
        return None
    s = raw.strip().lower()
    if "подвал" in s:
        return "basement"
    if "цокол" in s:
        return "semi"
    # чисто числовое значение
    try:
        n = int(s)
    except Exception:
        return "other"
    if n == 1:
        return "1"
    return "other"


def extract_notes_block(html: str) -> str | None:
    """Достаёт текст примечаний целиком (без HTML-тегов).

    Ищем блок:
        <span class="title-info">Примечания</span>
        <div class="roll-txt">
            <p> ... </p>
    """

    # сначала локализуем небольшой фрагмент вокруг "Примечания"
    anchor = re.search(r"<span[^>]*class=\"title-info\"[^>]*>\s*Примечания\s*</span>", html)
    if not anchor:
        return None

    start = anchor.end()
    snippet = html[start : start + 4000]  # ограничимся разумным куском

    p_match = re.search(r"<p[^>]*>(.*?)</p>", snippet, re.DOTALL | re.IGNORECASE)
    if not p_match:
        return None

    raw = p_match.group(1)
    # убираем HTML-теги и приводим пробелы
    text = re.sub(r"<br\s*/?>", "\n", raw, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_has_unauthorized_replan(notes: str | None) -> bool | None:
    """Определяет признак самовольной перепланировки по тексту примечаний."""
    if not notes:
        return None
    lowered = notes.lower()
    # базовая эвристика, можно расширять по мере накопления примеров
    if "самовольная переплан" in lowered:
        return True
    if "самовольное переустрой" in lowered:
        return True
    return False


def process_lot(props: Dict[str, Any]) -> Dict[str, Any]:
    url = build_lot_url(props)
    html = fetch_html(url)

    floor = extract_floor(html)
    floor_class = classify_floor(floor)
    notes = extract_notes_block(html)
    has_replan = extract_has_unauthorized_replan(notes)

    return {
        "url": url,
        "floor": floor,
        "floorClass": floor_class,
        "has_unauthorized_replan": has_replan,
        "notes": notes,
    }


def main() -> None:
    if not LOTS_PATH.exists():
        print(f"[ERR] {LOTS_PATH} not found", file=sys.stderr)
        sys.exit(1)

    data = json.loads(LOTS_PATH.read_text(encoding="utf-8"))
    features = data.get("features") or []

    # если есть старый файл — подгружаем и дообновляем, чтобы не ходить по старым лотам
    existing: Dict[str, Any] = {}
    if OUTPUT_PATH.exists():
        try:
            existing = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        except Exception:
            existing = {}

    out: Dict[str, Any] = dict(existing)

    print(f"[INFO] total lots: {len(features)}")

    for idx, feat in enumerate(features, start=1):
        props = feat.get("properties") or {}
        lot_id = props.get("id")
        if lot_id is None:
            continue
        key = str(lot_id)

        if key in out:
            # уже обогащали этот лот
            continue

        try:
            print(f"[INFO] ({idx}/{len(features)}) lot {lot_id}: fetching details...")
            out[key] = process_lot(props)
            # сразу пишем на диск, чтобы можно было остановить в любой момент
            OUTPUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[WARN] failed to enrich lot {lot_id}: {e}", file=sys.stderr)
        finally:
            time.sleep(0.7)  # минимальный таймаут, чтобы не долбить сайт

    print(f"[DONE] enriched details for {len(out)} lots -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
