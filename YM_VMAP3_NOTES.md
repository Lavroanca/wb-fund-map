# Yandex Market vmap3 tiles - notes

We discovered YM polygon tiles are served as Yandex vmap3 protobuf tiles (not standard Mapbox MVT).

Example URLs from hubs.market.yandex.ru HAR (brand map):

```text
https://core-renderer-tiles.maps.yandex.net/vmap3/tiles?lang=ru_RU&x=38285&y=19116&z=16&zmin=16&zmax=16&v=26.02.26-0~b:260210161500~ib:26.02.27-0&apikey=68913428-2934-48be-9ee5-edf66b2a29c8
https://core-renderer-tiles.maps.yandex.net/vmap3/tiles?lang=ru_RU&x=38286&y=19116&z=16&zmin=16&zmax=16&v=26.02.26-0~b:260210161500~ib:26.02.27-0&apikey=68913428-2934-48be-9ee5-edf66b2a29c8
```

General template (zmin/zmax locked to z):

```text
https://core-renderer-tiles.maps.yandex.net/vmap3/tiles?
  lang=ru_RU&
  x={x}&
  y={y}&
  z={z}&
  zmin={z}&
  zmax={z}&
  v=26.02.26-0~b:260210161500~ib:26.02.27-0&
  apikey=68913428-2934-48be-9ee5-edf66b2a29c8
```

Attempts to parse the response with `mapbox_vector_tile.decode` fail with a protobuf DecodeError, confirming this is not Mapbox MVT but Yandex's own vmap3 protobuf schema.

Next steps (blocked until we have a vmap3 decoder):

- Identify or implement a decoder for Yandex vmap3 tiles (protobuf schema + geometry extraction).
- Wrap it into a small Python service that:
  - accepts z/x/y,
  - fetches the vmap3 tile from core-renderer-tiles.maps.yandex.net,
  - converts selected layers (YM support zones) into GeoJSON,
  - returns as `application/json`.
- On the front-end (wb_map.html), add a MapLibre GeoJSON source pointing at that service, style zones, and reuse Turf.js for point-in-polygon against fund lots.

For now we only store the endpoints and acknowledge that polygon extraction cannot be implemented correctly without a vmap3-aware decoder.
