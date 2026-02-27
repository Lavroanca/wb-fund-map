#!/usr/bin/env python3
"""Отметить лоты фонда, которые попадают в зоны WB.

Берёт:
  - lots.geojson (Point, lon/lat)
  - тайлы WB data.priority_zone_united вокруг СПб

Добавляет/обновляет свойство inside_wb: true/false.

Требует: shapely, requests, mapbox_vector_tile
"""

import json
from pathlib import Path

import requests
from shapely.geometry import Point, shape
import mapbox_vector_tile

# Те же тайлы, что мы используем для SPb
TILES = [
    (12, 2393, 1190),
    (12, 2393, 1191),
    (12, 2392, 1190),
    (12, 2392, 1191),
    (13, 4786, 2381),
    (13, 4786, 2382),
]

LOTS_PATH = Path('lots.geojson')


def fetch_tile(z: int, x: int, y: int):
    url = f'https://map.wb.ru/tiles/data.priority_zone_united/{z}/{x}/{y}.pbf'
    print(f"[INFO] fetch tile {z}/{x}/{y}: {url}")
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.content


def build_zones() -> list:
    polys = []
    for z, x, y in TILES:
        data = fetch_tile(z, x, y)
        decoded = mapbox_vector_tile.decode(data)
        layer = decoded.get('data.priority_zone_united') or {}
        for feat in layer.get('features', []):
            geom = feat.get('geometry')
            if not geom:
                continue
            if geom['type'] not in ('Polygon', 'MultiPolygon'):
                continue
            # mapbox_vector_tile даёт уже в тайловых координатах, но shapely shape() умеет работать
            # с dict-геометрией, нам нужно только координаты привести к lon/lat.
            # Однако здесь проще воспользоваться тем, что MapboxVectorTile уже декодирует в
            # WGS84, если была включена опция. В нашем случае decode() вернул пиксели,
            # поэтому для качественного анализа лучше использовать наш ранее подготовленный
            # wb_zones_merged.geojson. Чтобы не усложнять, здесь воспользуемся им.
            pass
    return polys


def main() -> None:
    # Используем wb_zones_merged.geojson, уже пересчитанный в lon/lat
    zones_path = Path('wb_zones_merged.geojson')
    if not zones_path.is_file():
        print(f"[ERROR] wb_zones_merged.geojson not found in {zones_path.resolve()}")
        return

    print(f"[INFO] loading zones from {zones_path}")
    with zones_path.open('r', encoding='utf-8') as f:
        zones_fc = json.load(f)

    zone_geoms = [shape(feat['geometry']) for feat in zones_fc.get('features', []) if feat.get('geometry')]
    print(f"[INFO] zones loaded: {len(zone_geoms)}")

    if not LOTS_PATH.is_file():
        print(f"[ERROR] lots.geojson not found in {LOTS_PATH.resolve()}")
        return

    print(f"[INFO] loading lots from {LOTS_PATH}")
    with LOTS_PATH.open('r', encoding='utf-8') as f:
        lots_fc = json.load(f)

    count_inside = 0
    for feat in lots_fc.get('features', []):
        geom = feat.get('geometry')
        if not geom or geom.get('type') != 'Point':
            continue
        coords = geom.get('coordinates')
        if not coords:
            continue
        lon, lat = coords
        p = Point(lon, lat)
        inside = any(p.within(z) for z in zone_geoms)
        props = feat.setdefault('properties', {})
        props['inside_wb'] = inside
        if inside:
            count_inside += 1

    print(f"[INFO] lots total: {len(lots_fc.get('features', []))}, inside WB: {count_inside}")

    with LOTS_PATH.open('w', encoding='utf-8') as f:
        json.dump(lots_fc, f, ensure_ascii=False)
    print("[DONE] lots.geojson updated with inside_wb")


if __name__ == '__main__':
    main()
