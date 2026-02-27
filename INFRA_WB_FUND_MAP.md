# wb-fund-map infrastructure guide

Purpose: this file describes how to run and maintain the latest version of the WB + ФИСПб + Yandex Market map on this VPS.
It is written so that **another assistant** can follow it step by step without asking extra questions.

## 1. Paths and environment

- Workspace (git repo root):
  - `/home/lavr/.openclaw/workspace`
- Python venv:
  - `/home/lavr/.openclaw/venv`
- Static map files (served via http.server):
  - `wb_map.html`
  - `lots.geojson`
- System user:
  - `lavr`

Assume all commands are run as user `lavr` (not root) unless explicitly stated.

## 2. Python environment

The venv already exists and has required packages:

- `mapbox-vector-tile`
- `shapely`
- `requests`
- `pyclipper`

To activate venv in a shell (if needed):

```bash
source /home/lavr/.openclaw/venv/bin/activate
```

## 3. Updating fund lots from official API

Script:

- `/home/lavr/.openclaw/workspace/update_fund_lots.py`

What it does:

- Calls the official Фонд имущества СПб API at
  `https://xn--80adfeoyeh6akig5e.xn--p1ai/v1/items`
- Iterates pages until no more items
- Filters items with non-null latitude/longitude
- Writes a GeoJSON FeatureCollection to:
  - `/home/lavr/.openclaw/workspace/lots.geojson`

Manual run (one-shot update):

```bash
/home/lavr/.openclaw/venv/bin/python \
  /home/lavr/.openclaw/workspace/update_fund_lots.py
```

Cron (already configured under user `lavr`):

```cron
0 4 * * * /home/lavr/.openclaw/venv/bin/python /home/lavr/.openclaw/workspace/update_fund_lots.py >> /home/lavr/.openclaw/workspace/fund_lots_cron.log 2>&1
```

Checks:

- Verify `lots.geojson` mtime around 04:00:
  ```bash
  ls -l /home/lavr/.openclaw/workspace/lots.geojson
  ```
- Tail the cron log:
  ```bash
  tail -n 50 /home/lavr/.openclaw/workspace/fund_lots_cron.log
  ```

## 4. Static HTTP server for the map (wb-map.service)

Systemd unit (user-level) should be named `wb-map.service` and run:

```ini
[Service]
WorkingDirectory=/home/lavr/.openclaw/workspace
ExecStart=/usr/bin/python3 -m http.server 8000
Restart=always
User=lavr
Group=lavr

[Install]
WantedBy=multi-user.target
```

(Exact unit file may already exist under `/etc/systemd/system/wb-map.service` – do not overwrite without checking.)

Key commands (run as root or with sudo for system-wide unit):

```bash
sudo systemctl daemon-reload
sudo systemctl enable wb-map.service
sudo systemctl restart wb-map.service
sudo systemctl status wb-map.service
```

To confirm the map is served:

- Open in browser (from your machine):
  - `http://<server-ip>:8000/wb_map.html`

## 5. Yandex Market proxy service (ym-proxy)

Script:

- `/home/lavr/.openclaw/workspace/ym_proxy.py`

What it does:

- Runs a simple HTTP server (Python) on a given port (e.g. 8001)
- Forwards requests to YM endpoint:
  - `https://hubs.market.yandex.ru/api/partner-gateway/outlet-map/recommended-buildings`
- Copies query params: `zoom`, `minLat`, `maxLat`, `minLon`, `maxLon`
- Returns YM JSON with permissive CORS headers

Sample systemd unit (already present as template):

- `/home/lavr/.openclaw/workspace/ym-proxy.service.sample`

Contents (for reference):

```ini
[Service]
WorkingDirectory=/home/lavr/.openclaw/workspace
ExecStart=/home/lavr/.openclaw/venv/bin/python /home/lavr/.openclaw/workspace/ym_proxy.py 8001
Restart=always
User=lavr
Group=lavr

[Install]
WantedBy=multi-user.target
```

To enable this service (example, if not yet installed):

```bash
sudo cp /home/lavr/.openclaw/workspace/ym-proxy.service.sample /etc/systemd/system/ym-proxy.service
sudo systemctl daemon-reload
sudo systemctl enable ym-proxy.service
sudo systemctl restart ym-proxy.service
sudo systemctl status ym-proxy.service
```

The front-end (`wb_map.html`) expects the proxy at:

- `http://<server-ip>:8001/ym_recommended_buildings`

## 6. Front-end map (`wb_map.html`)

File:

- `/home/lavr/.openclaw/workspace/wb_map.html`

Responsibilities:

- Load MapLibre GL JS from CDN
- Use WB official style:
  - `https://wb-maps.wb.ru/api/tiles/style/lightberry-ru.json?key=a6BaPcWAU7k4TRMD6pXz`
- Add sources:
  - `fund-lots` – `lots.geojson` (ФИСПб lots as points)
  - `wb-priority-zones` – vector source from Wildberries:
    - `https://map.wb.ru/tiles/data.priority_zone_united/{z}/{x}/{y}.pbf`
  - `ym-lightning` – GeoJSON from local YM proxy
- Layers:
  - `fund-lots-layer` – circles, color depends on `inside_wb` property
  - `wb-priority-zones-fill` / `wb-priority-zones-outline` – WB support zone polygons
  - `ym-lightning-layer` – Yandex Market LIGHTNING points
- Client-side point-in-polygon (WB):
  - Uses `turf.booleanPointInPolygon` on `map.querySourceFeatures('wb-priority-zones', { sourceLayer: 'data.priority_zone_united' })`
  - Sets `inside_wb` flag on lot features

To "deploy" a new front-end version:

1. Ensure latest code is pulled/built in `/home/lavr/.openclaw/workspace`.
2. Confirm `wb_map.html` and `lots.geojson` exist and are up-to-date.
3. Restart `wb-map.service` (see section 4).

## 7. Git workflow

Repo root: `/home/lavr/.openclaw/workspace`.

To see status:

```bash
cd /home/lavr/.openclaw/workspace
git status -sb
```

To pull latest changes from GitHub:

```bash
cd /home/lavr/.openclaw/workspace
git pull
```

To commit local changes (minimal example):

```bash
cd /home/lavr/.openclaw/workspace
git add wb_map.html lots.geojson update_fund_lots.py ym_proxy.py
git commit -m "feat: update map and YM proxy"
git push
```

## 8. How to fully restart the pipeline (operator checklist)

1. **Update lots from API**
   - Run:
     ```bash
     /home/lavr/.openclaw/venv/bin/python /home/lavr/.openclaw/workspace/update_fund_lots.py
     ```
   - Confirm `lots.geojson` updated.

2. **Ensure YM proxy is running**
   - Check:
     ```bash
     sudo systemctl status ym-proxy.service
     ```
   - If not active, see section 5 to enable/restart.

3. **Ensure static map server is running**
   - Check:
     ```bash
     sudo systemctl status wb-map.service
     ```
   - If needed:
     ```bash
     sudo systemctl restart wb-map.service
     ```

4. **Open the map**
   - In a browser, go to:
     ```
     http://<server-ip>:8000/wb_map.html
     ```
   - Verify layers:
     - WB zones appear as magenta polygons.
     - Fund lots appear as points (yellow if inside WB, blue otherwise).
     - YM "LIGHTNING" points appear as yellow markers.

If all four steps succeed, the current infrastructure is **up** and serving the latest version of the map.
