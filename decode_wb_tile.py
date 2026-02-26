#!/usr/bin/env python3
"""Decode a Wildberries .pbf/.mvt vector tile into GeoJSON polygons.

Usage:
    python3 decode_wb_tile.py input.pbf output.geojson

If output is omitted, will use input name + '.geojson'.

Requires:
    pip install --user mapbox-vector-tile
"""

import json
import os
import sys

try:
    import mapbox_vector_tile
except ImportError as e:
    print("[ERROR] Python package 'mapbox-vector-tile' is not installed.")
    print("Install it with:\n    python3 -m pip install --user mapbox-vector-tile")
    sys.exit(1)


def usage() -> None:
    print("Usage: python3 decode_wb_tile.py input.pbf [output.geojson]")


def tile_to_geojson(data: bytes) -> dict:
    """Decode Mapbox vector tile bytes to a GeoJSON FeatureCollection.

    We don't know точное имя слоя WB, поэтому берём все слои подряд
    и превращаем их в GeoJSON. Потом можно отфильтровать нужный.
    """
    decoded = mapbox_vector_tile.decode(data)

    features = []
    for layer_name, layer in decoded.items():
        for feat in layer.get("features", []):
            geom = feat.get("geometry")
            if not geom:
                continue
            properties = feat.get("properties", {}).copy()
            properties["_layer"] = layer_name
            features.append({
                "type": "Feature",
                "geometry": geom,
                "properties": properties,
            })

    return {"type": "FeatureCollection", "features": features}


def main(argv: list[str]) -> None:
    if len(argv) < 2:
        usage()
        sys.exit(1)

    input_path = argv[1]
    if len(argv) >= 3:
        output_path = argv[2]
    else:
        output_path = input_path + ".geojson"

    if not os.path.isfile(input_path):
        print(f"[ERROR] Input file not found: {input_path}")
        sys.exit(1)

    print(f"[INFO] Reading tile: {input_path}")
    with open(input_path, "rb") as f:
        data = f.read()

    print("[INFO] Decoding vector tile...")
    fc = tile_to_geojson(data)

    print(f"[INFO] Writing GeoJSON to: {output_path}")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False)

    print("[DONE] Features:", len(fc.get("features", [])))


if __name__ == "__main__":
    main(sys.argv)
