# wb-fund-map v1.1

Интерактивная карта для инвестиционного анализа лотов Фонда имущества СПб
с интеграцией зон Wildberries.

Цель: дать инвестиционному менеджеру удобный инструмент, чтобы ежедневно
просматривать торги фонда, видеть пересечение с зонами WB и быстро отбирать
кандидаты по ключевым параметрам (аренда/продажа, площадь, ставка, этаж,
самовольная перепланировка/переустройство).

## Возможности v1.1

- **Зоны Wildberries**
  - Используется официальный стиль WB:
    - `https://wb-maps.wb.ru/api/tiles/style/lightberry-ru.json?key=a6BaPcWAU7k4TRMD6pXz`
  - Зоны приоритета WB берутся напрямую из тайлов:
    - `https://map.wb.ru/tiles/data.priority_zone_united/{z}/{x}/{y}.pbf`
  - Никакого локального кэша зон — карта всегда отображает актуальные полигоны.

- **Лоты Фонда имущества СПб**
  - Официальный API: `https://xn--80adfeoyeh6akig5e.xn--p1ai/v1/items`
  - Скрипт `update_fund_lots.py` формирует `lots.geojson` с активными торгами.
  - Категории:
    - Покупка (typeId = 1)
    - Аренда (typeId = 2)
    - Права на НТО (categoryId = 12)
  - Для аренды дополнительно считаются:
    - `startingPriceMonth` — месячная ставка (из годовой)
    - `pricePerM2Month` — ставка за м² в месяц

- **Подробности по лотам (парсинг карточек)**
  - Скрипт `enrich_fund_lots_details.py` открывает карточки лотов на сайте Фонда
    и вытаскивает:
    - Этаж расположения (`floor`), плюс классификацию `floorClass`:
      - `basement` — подвал
      - `semi` — цоколь
      - `1` — первый этаж
      - `other` — прочие этажи / >1
    - Примечания (полный текст)
    - Признак самовольной перепланировки/переустройства:
      - `has_unauthorized_replan = true`, если в примечаниях встречается
        `самовольная перепланировка` или `самовольное переустройство`.
  - Все детали складываются в `fund_lot_details.json` и подмешиваются в свойства
    объектов карты.

- **Автономное обновление данных**
  - Cron для лотов Фонда и обогащения (под пользователем `lavr`):

    ```cron
    0 4 * * * cd /home/lavr/.openclaw/workspace && \
      /home/lavr/.openclaw/venv/bin/python update_fund_lots.py >> /home/lavr/.openclaw/workspace/fund_lots_cron.log 2>&1 && \
      /home/lavr/.openclaw/venv/bin/python enrich_fund_lots_details.py >> /home/lavr/.openclaw/workspace/fund_lot_details_cron.log 2>&1
    ```

  - Каждую ночь:
    - `update_fund_lots.py` обновляет `lots.geojson`.
    - `enrich_fund_lots_details.py` докачивает этаж/примечания/перепланировки
      для новых лотов.

- **Интерактивная карта (`wb_map.html`)**

  - Источники:
    - `fund-lots` — `lots.geojson` (точки Фонда)
    - `wb-priority-zones` — векторный источник WB зон
    - `ym-zones` — заглушка под будущие полигоны Я.Маркета (`ym_zones.geojson`)

  - Слои Фонда:
    - `Покупка` — `fund-lots-sale`
    - `Аренда` — `fund-lots-rent`
    - `Права на НТО` — `fund-lots-nto`
    - `Совпадения` — `fund-lots-matches` (жёлтые точки внутри WB зон)

  - **Подсветка новых объектов**
    - Лоты, у которых `dateCreate` не старше 7 дней от текущей даты, получают
      `properties.isNew = true`.
    - На карте такие объекты подсвечены более ярким цветом через MapLibre
      style expressions (чуть более насыщенная заливка + светлая обводка).

  - **PIP (Point-in-Polygon) по живым WB зонам**
    - После загрузки карты выполняется клиентский PIP:
      - `map.querySourceFeatures('wb-priority-zones', { sourceLayer: 'data.priority_zone_united' })`
      - `turf.booleanPointInPolygon` для каждого лота.
    - Результат записывается в `properties.inside_wb` и используется для
      окраски точек и слоя совпадений.

  - **Фильтры аренды**
    - При клике по строке "Аренда" в панели слоёв раскрывается блок
      "Фильтры аренды":
      - Самовольная перепланировка:
        - Любая
        - Без перепланировки/переустройства
        - Только с перепланировкой/переустройством
      - Этаж:
        - Любой
        - Подвал
        - Цоколь
        - 1 этаж
        - Выше 1-го
    - Фильтры применяются к слою `fund-lots-rent` через MapLibre
      `setFilter` по `has_unauthorized_replan` и `floorClass`.

  - **Улучшенный UX панели слоёв**
    - Тёмная стеклянная панель со сгруппированными секциями:
      - Зоны маркетплейса
      - Лоты Фонда имущества
      - Совпадения
    - В строке "Аренда" есть стрелка `▾` / `▴`, явно показывающая, что есть
      раскрывающийся фильтр.
    - Кнопка-"ухват" сбоку (вертикальная таблетка `❯` / `❮`) позволяет
      сворачивать панель слоёв вправо и возвращать её обратно, при этом сама
      кнопка всегда остаётся видимой.

  - **Попапы по клику на лот**
    - В едином тёмном стиле, без белых рамок MapLibre.
    - Показывают:
      - Адрес
      - Тип (Продажа / Аренда / НТО) + отметка "внутри зоны WB", если да
      - Площадь
      - Начальная цена
      - Цена в месяц (для аренды)
      - Цена за м²/мес (для аренды)
      - Этаж (сырой текст)
      - Признак самовольной перепланировки/переустройства (Да/Нет,
        с красно-зелёной подсветкой)
      - Ссылку "Открыть карточку лота" с корректным URL:
        - `/realty/spaces/<id>`
        - `/realty/buildings/<id>` (здания с ЗУ)
        - `/realty/nto/<id>` (НТО)

## Как развернуть v1.1 с нуля (для другого бота / оператора)

**Предусловия:**

- Есть Linux-сервер (VPS) с пользователем `lavr`.
- Есть Python 3 и git.
- Есть настроенный venv в `/home/lavr/.openclaw/venv` (или его нужно создать).
- Есть токены/ключи, если они нужны для других частей OpenClaw (не для карты).

### 1. Клонировать репозиторий и перейти в него

```bash
cd /home/lavr/.openclaw
git clone https://github.com/Lavroanca/wb-fund-map.git workspace
cd workspace
```

### 2. Настроить Python venv и зависимости

Если venv ещё нет:

```bash
python3 -m venv /home/lavr/.openclaw/venv
source /home/lavr/.openclaw/venv/bin/activate
pip install --upgrade pip
pip install mapbox-vector-tile shapely requests pyclipper
```

Если venv уже был — просто активировать при необходимости:

```bash
source /home/lavr/.openclaw/venv/bin/activate
```

### 3. Первичное обновление лотов и обогащение

```bash
cd /home/lavr/.openclaw/workspace
/home/lavr/.openclaw/venv/bin/python update_fund_lots.py
/home/lavr/.openclaw/venv/bin/python enrich_fund_lots_details.py
```

После этого должны появиться файлы:

- `lots.geojson` — точки лотов Фонда
- `fund_lot_details.json` — этаж/примечания/перепланировки

### 4. Настроить cron для автономной ежедневной актуализации

От пользователя `lavr`:

```bash
crontab -e
```

Добавить строку:

```cron
0 4 * * * cd /home/lavr/.openclaw/workspace && \
  /home/lavr/.openclaw/venv/bin/python update_fund_lots.py >> /home/lavr/.openclaw/workspace/fund_lots_cron.log 2>&1 && \
  /home/lavr/.openclaw/venv/bin/python enrich_fund_lots_details.py >> /home/lavr/.openclaw/workspace/fund_lot_details_cron.log 2>&1
```

Сохранить и выйти. Проверить:

```bash
crontab -l
```

### 5. Настроить systemd-сервис для статического сервера карты

Создать unit `/etc/systemd/system/wb-map.service` (от root):

```ini
[Unit]
Description=WB Fund Map static server
After=network.target

[Service]
WorkingDirectory=/home/lavr/.openclaw/workspace
ExecStart=/usr/bin/python3 -m http.server 8000
Restart=always
User=lavr
Group=lavr

[Install]
WantedBy=multi-user.target
```

Применить и запустить:

```bash
sudo systemctl daemon-reload
sudo systemctl enable wb-map.service
sudo systemctl restart wb-map.service
sudo systemctl status wb-map.service
```

Карта будет доступна по адресу:

```text
http://<server-ip>:8000/wb_map.html
```

### 6. (Опционально) Настроить YM proxy

Если нужен доступ к рекомендованным объектам Яндекс.Маркета, можно
дополнительно поднять `ym_proxy.py` по аналогии с `ym-proxy.service.sample`.

См. подробности в `INFRA_WB_FUND_MAP.md`.

## Дополнительно

- Подробная инфра-документация: `INFRA_WB_FUND_MAP.md`
- Примечания по Yandex vmap3: `YM_VMAP3_NOTES.md`

Этого README и `INFRA_WB_FUND_MAP.md` достаточно, чтобы "чужой" бот или
оператор мог поднять карту v1.1 на новой машине, имея доступ к репозиторию
и базовым системным инструментам (git, python, systemd, cron).
