#!/usr/bin/env python3
import sys, json, requests, re, time
floor_regex = re.compile(r"Этаж[^<]*?</span></b>\s*<b[^>]*><span>([^<]+)", re.IGNORECASE)
session = requests.Session()
data = {}
for lot_id in sys.argv[1:]:
    url = f"https://xn--80adfeoyeh6akig5e.xn--p1ai/realty/spaces/{lot_id}"
    try:
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
        html = resp.text
        m = floor_regex.search(html)
        value = m.group(1).strip() if m else "не указано"
    except Exception:
        value = "не указано"
    data[lot_id] = value
    time.sleep(0.3)
with open(f"data/floor_batch_{sys.argv[1]}.json", "w") as f:
    json.dump(data, f, ensure_ascii=False)
