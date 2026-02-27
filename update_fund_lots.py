#!/usr/bin/env python3
"""Забирает лоты из API Фонда имущества СПб и собирает lots.geojson.

Endpoint (из DevTools):
  https://xn--80adfeoyeh6akig5e.xn--p1ai/v1/items

Используем параметры:
  areaMax=6200070
  per-page=100
  sort=-dateBid
  statusId=2   # активные торги
  typeId=0     # все типы (продажа + аренда)

Делаем постраничный обход по page=1..N, пока:
  - не придёт пустой items
  - или не достигнем разумного предела страниц.

Фильтрация:
  - latitude/longitude not null
  - остальные свойства берём как в старом build_lots_geojson.py.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

import requests

API_URL = "https://xn--80adfeoyeh6akig5e.xn--p1ai/v1/items"
OUTPUT_PATH = Path("lots.geojson")

FIELDS = [
    "id",
    "code",
    "categoryId",
    "objectTypeId",
    "typeId",
    "address",
    "district",
    "totalArea",
    "startingPrice",
    "condition",
    "possibleUse",
    "dateCreate",
    "dateBid",
]


def fetch_page(page: int, per_page: int = 100) -> Dict[str, Any]:
    params = {
        "areaMax": 6200070,
        "page": page,
        "per-page": per_page,
        "sort": "-dateBid",
        "statusId": 2,
        "typeId": 0,
    }
    print(f"[INFO] fetching page {page}...")
    r = requests.get(API_URL, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def main() -> None:
    all_features: List[Dict[str, Any]] = []
    page = 1
    per_page = 100
    max_pages = 50  # защитный лимит

    while page <= max_pages:
        data = fetch_page(page, per_page=per_page)
        items = data.get("items") or []
        print(f"[INFO]  items on page {page}: {len(items)}")

        if not items:
            break

        for it in items:
            lat = it.get("latitude")
            lon = it.get("longitude")
            if lat is None or lon is None:
                continue
            try:
                lat_f = float(lat)
                lon_f = float(lon)
            except Exception:
                continue

            props = {k: it.get(k) for k in FIELDS}
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [lon_f, lat_f],
                },
                "properties": props,
            }
            all_features.append(feature)

        # если пришло меньше per_page — считаем, что это последняя страница
        if len(items) < per_page:
            break

        page += 1

    fc = {"type": "FeatureCollection", "features": all_features}
    print(f"[INFO] writing {len(all_features)} features to {OUTPUT_PATH}")
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False)

    print("[DONE]")


if __name__ == "__main__":
    main()
