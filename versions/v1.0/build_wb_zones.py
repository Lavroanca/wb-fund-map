#!/usr/bin/env python3
"""Download and decode WB priority zone tiles into one GeoJSON.

Usage:
    python build_wb_zones.py output.geojson

Tiles are hardcoded for now from data.priority_zone_united around SPb
(zoom 12 + a couple of 13 zoom tiles).

Requires: mapbox_vector_tile (already in venv).
"""

import json
import math
import os
import sys
from urllib.request import urlopen

import mapbox_vector_tile


# Hardcoded tiles from HAR (priority zones around СПб)
TILES = [
    (12, 2393, 1190),
    (12, 2393, 1191),
    (12, 2392, 1190),
    (12, 2392, 1191),
    (13, 4786, 2381),
    (13, 4786, 2382),
]

BASE_URL = "https://map.wb.ru/tiles/data.priority_zone_united/{z}/{x}/{y}.pbf"


def tile_to_lonlat(z: int, x: int, y: int, px: float, py: float, extent: int) -> tuple[float, float]:
    """Convert tile-local (px,py) in [0,extent] to WGS84 lon/lat.

    Используем стандартную формулу WebMercator через дробные координаты тайла.
    """
    # Доля тайла по X/Y
    xt = x + px / extent
    yt = y + py / extent

    # В долях всего мира
    n_tiles = 2 ** z

    lon = xt / n_tiles * 360.0 - 180.0

    # Стандартная формула из XYZ → lat
    n = math.pi - 2.0 * math.pi * yt / n_tiles
    lat = math.degrees(math.atan(math.sinh(n)))
    return lon, lat


def decode_tile(z: int, x: int, y: int) -> list[dict]:
    url = BASE_URL.format(z=z, x=x, y=y)
    print(f"[INFO] Fetching tile {z}/{x}/{y}: {url}")
    with urlopen(url) as resp:
        data = resp.read()

    decoded = mapbox_vector_tile.decode(data)
    features: list[dict] = []

    for layer_name, layer in decoded.items():
        # Берём extent слоя, по умолчанию 4096
        extent = int(layer.get("extent", 4096))

        for feat in layer.get("features", []):
            geom = feat.get("geometry")
            if not geom:
                continue
            if geom["type"] not in ("Polygon", "MultiPolygon"):
                # Для зон интересуют только полигоны
                continue

            def convert_coords(coords):
                if geom["type"] == "Polygon":
                    return [
                        [
                            list(tile_to_lonlat(z, x, y, px, py, extent))
                            for (px, py) in ring
                        ]
                        for ring in coords
                    ]
                else:  # MultiPolygon
                    return [
                        [
                            [
                                list(tile_to_lonlat(z, x, y, px, py, extent))
                                for (px, py) in ring
                            ]
                            for ring in poly
                        ]
                        for poly in coords
                    ]

            new_geom = {
                "type": geom["type"],
                "coordinates": convert_coords(geom["coordinates"]),
            }

            props = feat.get("properties", {}).copy()
            props["_layer"] = layer_name
            props["_z"] = z
            props["_x"] = x
            props["_y"] = y

            features.append({
                "type": "Feature",
                "geometry": new_geom,
                "properties": props,
            })

    print(f"[INFO] Decoded {len(features)} polygon features from {z}/{x}/{y}")
    return features


def main(argv: list[str]) -> None:
    if len(argv) < 2:
        print("Usage: python build_wb_zones.py output.geojson")
        sys.exit(1)

    out_path = argv[1]

    all_features: list[dict] = []
    for z, x, y in TILES:
        try:
            feats = decode_tile(z, x, y)
            all_features.extend(feats)
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] Failed to decode tile {z}/{x}/{y}: {e}")

    fc = {"type": "FeatureCollection", "features": all_features}

    print(f"[INFO] Writing merged zones to {out_path} ({len(all_features)} features)")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False)

    print("[DONE]")


if __name__ == "__main__":
    main(sys.argv)
