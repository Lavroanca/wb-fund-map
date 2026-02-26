#!/usr/bin/env python3
"""Собрать lots.geojson из JSON ответов Фонда имущества СПб.

Ищет файлы file_17*.json, file_18*.json, file_19*.json в
/home/lavr/.openclaw/media/inbound/ и конкатенирует их items.

Фильтрует только объекты с ненулевыми latitude/longitude.
"""

import json
import os
from pathlib import Path

INBOUND_DIR = Path('/home/lavr/.openclaw/media/inbound')
OUTPUT_PATH = Path('lots.geojson')  # в текущем каталоге (workspace)

INPUT_FILES = [
    'file_17---a5306d14-9923-488f-8746-53af5585302f.json',
    'file_18---27a0c0c1-25a1-4550-ad73-7fa6932454bb.json',
    'file_19---c3915f8c-dcf0-40c0-87b9-05496ca2a0fe.json',
]

FIELDS = [
    'id', 'code', 'categoryId', 'objectTypeId', 'typeId',
    'address', 'district', 'totalArea', 'startingPrice',
    'condition', 'possibleUse', 'dateCreate', 'dateBid',
]


def load_items(path: Path):
    with path.open('r', encoding='utf-8') as f:
        data = json.load(f)
    items = data.get('items') or data.get('data') or []
    return items


def main() -> None:
    all_features = []

    for name in INPUT_FILES:
        p = INBOUND_DIR / name
        if not p.is_file():
            print(f"[WARN] file not found: {p}")
            continue
        print(f"[INFO] loading {p}")
        items = load_items(p)
        print(f"[INFO]  items: {len(items)}")

        for it in items:
            lat = it.get('latitude')
            lon = it.get('longitude')
            if lat is None or lon is None:
                continue
            try:
                lat_f = float(lat)
                lon_f = float(lon)
            except Exception:
                continue

            props = {k: it.get(k) for k in FIELDS}
            feature = {
                'type': 'Feature',
                'geometry': {
                    'type': 'Point',
                    'coordinates': [lon_f, lat_f],
                },
                'properties': props,
            }
            all_features.append(feature)

    fc = {'type': 'FeatureCollection', 'features': all_features}
    print(f"[INFO] writing {len(all_features)} features to {OUTPUT_PATH}")
    with OUTPUT_PATH.open('w', encoding='utf-8') as f:
        json.dump(fc, f, ensure_ascii=False)


if __name__ == '__main__':
    main()
