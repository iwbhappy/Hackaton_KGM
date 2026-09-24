# Certificate Radar — полное ТЗ для разработки (Hackathon MVP)

> Документ предназначен для исполнителя-кодера (Codex). Выполняй шаги из раздела 10 **строго по порядку**.
> После каждого шага: прогон тестов → `git commit -m "step N: <кратко>"`. Не переходи к следующему шагу, пока не выполнены критерии приёмки текущего.
> Дедлайн сдачи: **13:00**. Feature freeze: **11:00**. После 11:00 — только исправление багов.

---

## 0. Инструкции для Codex (обязательно к соблюдению)

1. Язык интерфейса, сообщений об ошибках, рекомендаций и отчётов — **русский**. Идентификаторы в коде, имена файлов, API — **английские**.
2. Никаких экзотических библиотек. Разрешённый стек — раздел 3. Если нужна библиотека не из списка — не добавляй, реши стандартными средствами.
3. Всё должно работать **офлайн** (на площадке может не быть интернета): никаких CDN. JS-библиотеки кладутся в `app/static/vendor/`.
4. Кроссплатформенно: Windows 10/11 и Linux. Пути — через `pathlib`. Скрипты запуска: `run.bat` и `run.sh`.
5. Решение **только читает**: единственное сетевое действие по целям — TLS-handshake. Никаких логинов на целевые серверы, никаких изменений на них.
6. Секреты (токен Telegram, SMTP-пароль, Teams webhook) — только в `.env`. В UI и логах — только маскированно (`12345****`). В БД секреты не хранить.
7. Каждый модуль покрывается минимальными pytest-тестами (раздел 11). `pytest` должен проходить после каждого шага.
8. Не делай «заглушек, которые выглядят как работающие». Если что-то не реализовано — явно пиши в UI «не настроено».
9. Код простой и читаемый: функции до ~60 строк, type hints, docstring у публичных функций.

---

## 1. Цель продукта

Certificate Radar — веб-приложение, которое по списку DNS-имён / IP / URL / сетевых диапазонов подключается к TLS-сервисам, получает сертификаты, анализирует их и показывает на Dashboard состояние сертификатной инфраструктуры: сроки, статусы, проблемы, оценку риска с причинами и рекомендациями. Уведомляет о приближении окончания срока. Экспортирует отчёт.

Ключевой принцип: **«Обнаружить проблему до того, как она станет инцидентом».**

Целевой пользователь: системный администратор и специалист ИБ. Интерфейс должен быть понятен без обучения.

---

## 2. Объём MVP (что оценивает жюри) и сверх него

### 2.1. Обязательно (из ТЗ хакатона, п. 3.11)
| # | Требование | Где реализуется |
|---|---|---|
| 1 | Загрузка списка DNS/IP (+URL, CIDR, host:port, CSV) | Шаг 2, 5 |
| 2 | Автоматическое подключение к TLS-сервисам (обязательно порт 443) | Шаг 3 |
| 3 | Получение сертификата и основных атрибутов | Шаг 3 |
| 4 | Дата окончания и Days Left | Шаг 4 |
| 5 | Проверка соответствия DNS-имени (CN/SAN) | Шаг 4 |
| 6 | Базовая проверка цепочки доверия | Шаг 3–4 |
| 7 | Статусы OK / Information / Warning / Critical / Expired | Шаг 4 |
| 8 | Dashboard с фильтрами и сортировкой по сервису, владельцу, Issuer, сроку, статусу | Шаг 6 |
| 9 | Экспорт отчёта | Шаг 8 |
| 10 | Уведомление о сертификатах с малым остаточным сроком | Шаг 9 |
| — | Настраиваемые пороги, журналирование действий, read-only, без хранения паролей | Шаг 10 |

### 2.2. Сверх MVP (конкурентные преимущества, делаем в рамках плана)
- **Risk Score 0–100** с объяснимыми причинами и рекомендациями (п. 3.9 ТЗ хакатона).
- **Владелец и критичность сервиса** (назначение в UI и через CSV).
- **Слабая криптография**: RSA < 2048, SHA-1/MD5 подпись, TLS 1.0/1.1.
- Детальная классификация ошибок цепочки (self-signed / неполная цепочка / недоверенный корень).
- Загрузка корпоративных корневых CA как доверенных.
- История сканирований.
- Печатный HTML-отчёт (PDF через «Печать → Сохранить как PDF»).

### 2.3. Вне объёма (не делать)
Авторизация пользователей, автоматическое исправление/перевыпуск сертификатов, порты кроме заданных пользователем, интеграция с продуктивной инфраструктурой, AD-модуль.

---

## 3. Стек

| Слой | Технология |
|---|---|
| Язык | Python 3.11+ |
| Backend | FastAPI + Uvicorn |
| Шаблоны | Jinja2 (одна базовая страница + vanilla JS, обращающийся к JSON API) |
| БД | SQLite через SQLAlchemy 2.x (файл `data/radar.db`) |
| TLS | стандартный `ssl` + `socket` |
| Разбор сертификатов | `cryptography` (≥ 42) |
| Экспорт XLSX | `openpyxl` |
| Уведомления | `httpx` (Telegram, Teams webhook), `smtplib` (Email) |
| Конфиг | `pydantic-settings` + `.env` |
| Графики | Chart.js (файл `chart.umd.min.js` положить в `app/static/vendor/`) |
| Планировщик (опционально) | `APScheduler` |
| Тесты | `pytest` |

`requirements.txt`: `fastapi uvicorn[standard] jinja2 sqlalchemy cryptography openpyxl httpx pydantic-settings python-multipart apscheduler pytest`.

---

## 4. Архитектура (модульная — требование ТЗ п. 4.1)

```
Input (текст/CSV)
   │  parser.py → список Target(host, port, sni, owner, criticality, service_name)
   ▼
Collector (collectors/tls_collector.py)   ← интерфейс BaseCollector, в будущем DNS/AD/...
   │  → RawObservation (сырые данные: DER-сертификат, TLS-версия, ошибка верификации, IP)
   ▼
Analyzer (analysis/)
   ├─ cert_parser.py   → атрибуты (CN, SAN, Issuer, Thumbprint, даты, ключ, подпись)
   ├─ checks/*.py      → список Issue (реестр проверок, каждая проверка = отдельная функция)
   ├─ status.py        → OK/INFO/WARNING/CRITICAL/EXPIRED
   └─ risk.py          → Risk Score + причины + рекомендации
   ▼
Storage (db.py, models.py)  → SQLite
   ▼
Outputs
   ├─ api/*            → JSON API
   ├─ web (templates)  → Dashboard
   ├─ exporters/*      → CSV, XLSX, HTML-отчёт
   ├─ notifiers/*      → Telegram, Email, Teams (BaseNotifier)
   └─ audit.py         → журнал действий (БД + файл logs/audit.log)
```

### 4.1. Структура проекта
```
certificate-radar/
├─ app/
│  ├─ main.py                 # FastAPI app, роуты страниц, подключение роутеров
│  ├─ config.py               # Settings (pydantic-settings), чтение .env
│  ├─ db.py                   # engine, SessionLocal, init_db()
│  ├─ models.py               # SQLAlchemy модели
│  ├─ schemas.py              # Pydantic-схемы API
│  ├─ parser.py               # разбор входного списка
│  ├─ scanner.py              # оркестрация скана (параллельность, запись в БД)
│  ├─ collectors/
│  │  ├─ base.py              # BaseCollector (abstract)
│  │  └─ tls_collector.py
│  ├─ analysis/
│  │  ├─ cert_parser.py
│  │  ├─ hostname.py          # сопоставление имени с CN/SAN
│  │  ├─ checks.py            # реестр проверок + Issue
│  │  ├─ status.py
│  │  └─ risk.py
│  ├─ notifiers/
│  │  ├─ base.py
│  │  ├─ telegram.py
│  │  ├─ email.py
│  │  ├─ teams.py
│  │  └─ dispatcher.py        # решает, что и кому отправлять, дедупликация
│  ├─ exporters/
│  │  ├─ csv_export.py
│  │  ├─ xlsx_export.py
│  │  └─ html_report.py
│  ├─ audit.py
│  ├─ api/
│  │  ├─ scans.py
│  │  ├─ results.py
│  │  ├─ endpoints.py
│  │  ├─ settings.py
│  │  ├─ export.py
│  │  └─ notifications.py
│  ├─ templates/  (base.html, dashboard.html, scan.html, details.html, settings.html, audit.html, report.html)
│  └─ static/     (app.css, app.js, vendor/chart.umd.min.js)
├─ lab/
│  ├─ generate_certs.py       # генерация тестовых CA и сертификатов
│  ├─ lab_server.py           # тестовый HTTPS-сервер с SNI
│  ├─ hosts.txt               # строки для файла hosts
│  ├─ targets.txt             # готовый список для демо
│  ├─ targets.csv             # тот же список с owner/criticality
│  └─ iis_setup.ps1           # (опционально) развернуть те же сертификаты в IIS
├─ data/                      # radar.db, trusted_ca/*.pem  (в .gitignore, кроме .gitkeep)
├─ logs/                      # audit.log, app.log
├─ tests/
├─ .env.example
├─ requirements.txt
├─ run.bat / run.sh
└─ README.md
```

---

## 5. Модель данных (SQLite)

### `endpoints` — что сканируем (уникально по host+port)
| поле | тип | примечание |
|---|---|---|
| id | int PK | |
| host | str | DNS-имя или IP (без схемы и порта) |
| port | int | по умолчанию 443 |
| service_name | str? | человекочитаемое имя, по умолчанию = host |
| owner | str? | ответственный (ФИО/email/группа) |
| criticality | str | `low` / `normal` / `high` / `critical`, по умолчанию `normal` |
| created_at, updated_at | datetime | |

### `scans` — запуски сканирования
| поле | тип |
|---|---|
| id | int PK |
| started_at, finished_at | datetime |
| status | `running` / `done` / `failed` |
| targets_total, targets_ok, targets_failed | int |
| initiated_by | str (IP клиента или `scheduler`) |

### `results` — результат по endpoint в рамках скана
| поле | тип | примечание |
|---|---|---|
| id | int PK | |
| scan_id | FK scans | |
| endpoint_id | FK endpoints | |
| resolved_ip | str? | |
| reachable | bool | |
| error | str? | текст ошибки подключения (таймаут, отказ, не TLS) |
| tls_version | str? | `TLSv1.3` и т.п. |
| subject_cn | str? | |
| san_dns | JSON list | |
| san_ip | JSON list | |
| issuer_cn | str? | |
| issuer_o | str? | организация издателя (для колонки «Issuer»/«Certificate») |
| serial | str? | hex |
| thumbprint_sha1 | str? | UPPERCASE hex без разделителей (как в Windows) |
| fingerprint_sha256 | str? | |
| not_before, not_after | datetime (UTC) | |
| days_left | int? | |
| key_type | str? | RSA / EC / Ed25519 |
| key_size | int? | |
| signature_algorithm | str? | напр. `sha256WithRSAEncryption` |
| chain_status | str | см. 6.3 |
| chain_message | str? | текст от OpenSSL |
| hostname_match | str | `match` / `mismatch` / `not_checked` |
| self_signed | bool | |
| status | str | `OK`/`INFO`/`WARNING`/`CRITICAL`/`EXPIRED`/`ERROR` |
| risk_score | int? | 0–100 |
| risk_level | str? | `Low`/`Medium`/`High`/`Critical` |
| issues | JSON list | `[{code, severity, title, detail, recommendation, points}]` |
| scanned_at | datetime | |

Dashboard всегда показывает **последний результат по каждому endpoint** (подзапрос по max(scan_id)).

### `settings` — key/value (JSON)
Пороги статусов, пороги уведомлений, веса риска, параллельность, таймаут. Значения по умолчанию — раздел 6.

### `notifications_sent` — дедупликация
`id, endpoint_id, thumbprint_sha1, threshold_days, channel, sent_at, success, error`. Уникальность: (thumbprint_sha1, threshold_days, channel).

### `audit_log`
`id, ts, actor (IP клиента / system), action, details (JSON)`. Действия: `scan_started`, `scan_finished`, `targets_uploaded`, `endpoint_updated`, `settings_changed`, `export_downloaded`, `notification_sent`, `notification_failed`, `trusted_ca_uploaded`, `app_started`. Дублировать в `logs/audit.log` (одна строка JSON на событие).

---

## 6. Функциональные требования (детально)

### 6.1. Входные данные (`parser.py`)
Принимаются: textarea (одна цель на строку) и загрузка файла `.txt` / `.csv`.

Поддерживаемые форматы строки:
| Ввод | Результат |
|---|---|
| `portal.company.kz` | host=portal.company.kz, port=443, sni=host |
| `portal.company.kz:8443` | port=8443 |
| `https://portal.company.kz/path` | host из URL, port из URL или 443 |
| `10.0.0.5` | host=IP, sni=None |
| `10.0.0.5:8443` | |
| `[2001:db8::1]:443` | IPv6 |
| `10.0.0.0/28` | развернуть в хосты (без network/broadcast для IPv4 при префиксе < 31), порт 443 |
| пустые строки, `# комментарии` | игнорировать |

Правила:
- CIDR больше `/22` (1024 адреса) — отклонить с понятной ошибкой (лимит настраивается `max_cidr_hosts`).
- Дубликаты (host+port) — схлопывать.
- Невалидные строки — не падать, вернуть список ошибок с номером строки; UI показывает их пользователю.
- CSV: заголовок обязателен, колонки `target` (обязательная), `service_name`, `owner`, `criticality` (опциональные). Разделитель `,` или `;` (автоопределение). Кодировка UTF-8 и UTF-8-BOM (Excel).
- При загрузке endpoint создаётся или обновляется (owner/criticality/service_name перезаписываются, только если в CSV непустые).

### 6.2. TLS-сбор (`collectors/tls_collector.py`)
Для каждой цели — **два подключения**:

**Подключение A (получить сертификат при любом его состоянии):**
- `ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)`, `check_hostname=False`, `verify_mode=CERT_NONE`.
- `ctx.minimum_version = ssl.TLSVersion.TLSv1` (чтобы увидеть и старые сервисы); `ctx.set_ciphers("DEFAULT:@SECLEVEL=0")` — чтобы получить даже слабые сертификаты (RSA 1024/SHA-1). Обернуть в try: если OpenSSL не позволяет — использовать дефолт.
- `server_hostname = sni` (для DNS-имени — имя; для IP — не передавать SNI).
- Получить: `getpeercert(binary_form=True)` → DER, `version()` → TLS-версия, `getpeername()[0]` → IP.

**Подключение B (проверка цепочки доверия):**
- `ssl.create_default_context()` (загружает системное хранилище; на Windows — хранилище Windows ROOT) + `load_verify_locations()` для каждого файла из `data/trusted_ca/*.pem|*.crt|*.cer`.
- `check_hostname=False` (имя проверяем сами, см. 6.4), `verify_mode=CERT_REQUIRED`.
- Успех → `chain_status = "valid"`. Исключение `ssl.SSLCertVerificationError` → классифицировать по `verify_code` (6.3).

Общие правила:
- Таймаут подключения — `connect_timeout` (по умолчанию 4 с).
- Параллельность — `ThreadPoolExecutor(max_workers=concurrency)`, по умолчанию 32.
- Ошибки сети (DNS не резолвится, refused, timeout, не TLS) → `reachable=False`, `status=ERROR`, понятный текст на русском («DNS-имя не разрешается», «Порт закрыт», «Таймаут подключения», «Сервис не поддерживает TLS»).
- Для IP-адресов без SNI сервер отдаёт сертификат «по умолчанию» — в UI показывать подсказку «сканирование по IP: проверка имени выполнена по IP-адресу».

### 6.3. Классификация цепочки (`chain_status`)
| verify_code OpenSSL | chain_status | Отображение |
|---|---|---|
| успех | `valid` | ✅ Цепочка доверена |
| 18 (self-signed leaf) | `self_signed` | Самоподписанный сертификат |
| 19 (self-signed in chain) | `untrusted_root` | Недоверенный корневой CA |
| 20 (unable to get local issuer) | `incomplete_or_untrusted` | Неполная цепочка или недоверенный CA |
| 21 (unable to verify leaf signature) | `incomplete_or_untrusted` | то же |
| 10 (certificate has expired) | `valid_but_expired` | Цепочка построена, сертификат истёк (ошибкой цепочки **не** считается — отдельная проблема EXPIRED) |
| 9 (not yet valid) | `not_yet_valid` | Сертификат ещё не действителен |
| прочее | `error` | текст `verify_message` |

Уточнение для `incomplete_or_untrusted`: если у сертификата есть расширение AIA (caIssuers) и issuer ≠ subject — в детали добавить подсказку «вероятно, сервер не отдаёт промежуточный сертификат».

`self_signed = True`, если subject == issuer **и** подпись проверяется собственным открытым ключом (`cert.verify_directly_issued_by(cert)` в try/except).

### 6.4. Проверка имени (`analysis/hostname.py`)
Реализовать собственную функцию `match_hostname(target_host, san_dns, san_ip, subject_cn) -> bool` по RFC 6125:
- сравнение без учёта регистра, отбросить завершающую точку;
- если есть SAN DNS — CN **игнорируется**; если SAN нет — сравнивать с CN;
- wildcard `*` допустим только как весь левый лейбл и покрывает ровно один лейбл (`*.company.kz` ⊃ `a.company.kz`, но ⊅ `company.kz` и ⊅ `a.b.company.kz`);
- IP-цель сравнивается только с SAN IP (и с CN, если SAN нет);
- результат: `match` / `mismatch`; если сертификат не получен — `not_checked`.

### 6.5. Атрибуты сертификата (`analysis/cert_parser.py`)
Из DER через `cryptography.x509`: CN, SAN (DNS + IP), Issuer CN и O, serial, SHA-1 thumbprint (UPPERCASE), SHA-256 fingerprint, not_before/not_after (`not_valid_after_utc`), тип и размер ключа, алгоритм подписи (`signature_hash_algorithm.name` + тип ключа), наличие AIA.

`days_left = floor((not_after - now_utc).total_seconds() / 86400)`.

### 6.6. Статусы (`analysis/status.py`) — пороги настраиваемые
| Условие (по умолчанию) | Статус | Цвет |
|---|---|---|
| days_left > 60 | `OK` | зелёный |
| 31–60 | `INFO` (Information) | синий |
| 15–30 | `WARNING` | жёлтый |
| 0–14 | `CRITICAL` | оранжево-красный |
| < 0 | `EXPIRED` | тёмно-красный |
| сертификат не получен | `ERROR` | серый |

Настройки: `threshold_info=60`, `threshold_warning=30`, `threshold_critical=14`. Валидация: info > warning > critical ≥ 0.

Статус — только про срок. Прочие проблемы отражаются в Issues и Risk Score.

### 6.7. Проверки — Issues (`analysis/checks.py`)
Реестр: список функций `check(result, endpoint, settings) -> Issue | None`. Добавление новой проверки = новая функция + регистрация (показать это на защите как «модульность»).

| code | Условие | severity | Заголовок (RU) | Рекомендация (RU) |
|---|---|---|---|---|
| `EXPIRED` | days_left < 0 | critical | Сертификат истёк | Немедленно перевыпустить и установить новый сертификат; проверить доступность сервиса |
| `EXPIRING` | 0 ≤ days_left ≤ threshold_info | по статусу | Сертификат скоро истекает (N дн.) | Запланировать перевыпуск; уведомить владельца |
| `SELF_SIGNED` | self_signed | high | Самоподписанный сертификат | Заменить на сертификат, выпущенный корпоративным или публичным CA |
| `CHAIN_UNTRUSTED` | chain_status ∈ {untrusted_root, incomplete_or_untrusted, error} и не self_signed | high | Ошибка цепочки доверия | Установить на сервере полную цепочку (включая промежуточные сертификаты) или добавить корневой CA в доверенные |
| `HOSTNAME_MISMATCH` | hostname_match = mismatch | high | Имя сервиса не совпадает с CN/SAN | Перевыпустить сертификат с корректным SAN, включающим имя сервиса |
| `WEAK_KEY` | RSA < 2048 или EC < 256 | medium | Слабый ключ (RSA 1024) | Перевыпустить с ключом RSA ≥ 2048 или ECDSA P-256 |
| `WEAK_SIGNATURE` | SHA-1 / MD5 | medium | Устаревший алгоритм подписи | Перевыпустить с подписью SHA-256 или выше |
| `OLD_TLS` | TLS 1.0 / 1.1 согласован | medium | Устаревшая версия TLS | Отключить TLS 1.0/1.1 на сервере, включить TLS 1.2/1.3 |
| `NOT_YET_VALID` | not_before > now | medium | Сертификат ещё не действителен | Проверить время на сервере и дату выпуска |
| `NO_OWNER` | owner пустой | low | Не назначен владелец | Назначить ответственного за сервис |
| `UNREACHABLE` | reachable = False | info | Сервис недоступен | Проверить доступность сервиса и корректность адреса |

### 6.8. Risk Score (`analysis/risk.py`) — объяснимый
```
base = 
  EXPIRED               → 80
  days_left 0..7        → 70
  days_left 8..14       → 55
  days_left 15..30      → 35
  days_left 31..60      → 15
  иначе                 → 0
+ SELF_SIGNED           → +20
+ CHAIN_UNTRUSTED       → +25   (не суммируется с SELF_SIGNED — берётся одно, большее)
+ HOSTNAME_MISMATCH     → +25
+ WEAK_KEY / WEAK_SIGNATURE / OLD_TLS → +15 (один раз за всю группу)
+ NO_OWNER              → +10
multiplier by criticality: low 0.85, normal 1.0, high 1.15, critical 1.3
score = min(100, round(sum * multiplier))
level: 0–19 Low, 20–49 Medium, 50–79 High, 80–100 Critical
```
- Для `ERROR` (недоступен) score = null, уровень «—».
- Каждое слагаемое попадает в `reasons` с текстом: «Сертификат истекает через 5 дней (+70)», «Сервис критичный (×1.3)».
- Все веса хранятся в settings (редактирование весов в UI — опционально, пороги — обязательно).
- **Контрольный пример из ТЗ хакатона:** `vpn.lab.local`, 5 дней, criticality=critical, owner задан, цепочка ок → 70 × 1.3 = 91 → **Critical**. Покрыть тестом.

### 6.9. Dashboard (главная страница `/`)
Верх — KPI-карточки (кликабельны, применяют фильтр):
- Всего сертификатов (уникальных по thumbprint) / всего сервисов;
- OK / Information / Warning / Critical / Expired / Недоступно;
- Проблемы цепочки; Несоответствие имени; Без владельца;
- **Infrastructure Certificate Health**: 100 − средний risk_score по доступным сервисам (большая цифра + цвет).

Графики (Chart.js):
- Doughnut: распределение по статусам;
- Bar: «Истекают в ближайшие 90 дней» по неделям (или по бакетам 0–7, 8–14, 15–30, 31–60, 61–90);

Блок «Требуют внимания»: топ-10 по risk_score с причинами одной строкой.

Основная таблица (последний результат по каждому endpoint):
| Service | Owner | Criticality | Certificate (Issuer) | CN | Expiration | Days Left | Status | Chain | Name | Risk | Issues |

- Сортировка по клику на любой колонке (по умолчанию — Risk desc, затем Days Left asc).
- Фильтры: поиск по сервису/CN/SAN, owner (select), issuer (select), status (мультиселект-чекбоксы), диапазон days left (от/до), «только с проблемами».
- Фильтрация/сортировка на клиенте (данных мало) — `app.js`.
- Строка кликабельна → страница деталей.
- Цветовые бейджи статусов (6.6), бейдж риска.
- Кнопки: «Новое сканирование», «Пересканировать всё», «Экспорт ▾ (CSV / Excel / Отчёт)», «Отправить уведомления».
- Пустое состояние: «Сертификатов пока нет — загрузите список целей» + кнопка.

### 6.10. Страница сканирования (`/scan`)
- Textarea + загрузка файла + кнопка «Вставить демо-список» (подставляет `lab/targets.txt`).
- Предпросмотр распознанных целей и ошибок парсинга до запуска.
- Кнопка «Сканировать» → `POST /api/scans` → прогресс-бар (polling `GET /api/scans/{id}` раз в 1 с: сколько обработано из скольких) → по завершении редирект на Dashboard.
- Скан выполняется в фоне (`BackgroundTasks` или поток), UI не блокируется.

### 6.11. Страница деталей (`/endpoint/{id}`)
- Все атрибуты из 3.4 ТЗ хакатона: сервис, порт, IP, CN, SAN (списком), Issuer, Thumbprint (кнопка «копировать»), SHA-256, Not Before, Not After, Days Left, TLS-версия, ключ, подпись, состояние цепочки + текст OpenSSL, результат проверки имени.
- Risk Score крупно + список причин + таблица Issues с рекомендациями.
- Редактируемые поля: service_name, owner, criticality → `PATCH /api/endpoints/{id}` → пересчёт risk без повторного скана.
- История: таблица прошлых результатов этого endpoint (дата скана, thumbprint, days left, status) — видно, когда сертификат заменили.

### 6.12. Настройки (`/settings`)
- Пороги статусов (info/warning/critical).
- Пороги уведомлений (по умолчанию `60,30,14,7,1`).
- Параллельность, таймаут.
- Каналы уведомлений: статус «настроен / не настроен» по данным `.env` (значения маскированы), кнопка «Тест» для каждого канала.
- Доверенные корневые CA: загрузка `.pem/.crt/.cer` (DER конвертировать в PEM), список загруженных с CN и сроком, удаление.
- Автоскан по расписанию (опционально): вкл/выкл + интервал в минутах.

### 6.13. Уведомления (`notifiers/`)
- `BaseNotifier.send(subject: str, text: str) -> None`; реализации: Telegram (`sendMessage`, parse_mode HTML), Email (SMTP, STARTTLS), Teams (Incoming Webhook, простой MessageCard/текст).
- Канал активен, если в `.env` заданы параметры: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`; `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_TO`; `TEAMS_WEBHOOK_URL`.
- **Логика (`dispatcher.py`):** после каждого скана для каждого результата с сертификатом найти наименьший порог T из `[60,30,14,7,1]`, такой что `days_left ≤ T` (для истёкших — порог `0` «истёк»). Если для пары (thumbprint, T, channel) уведомление ещё не отправлялось — отправить и записать в `notifications_sent`. Новый сертификат (новый thumbprint) → счётчики начинаются заново.
- Группировать: одно сообщение на скан со списком, отсортированным по days_left:
  ```
  🔴 Certificate Radar: 3 сертификата требуют внимания
  • vpn.lab.local — истекает через 5 дн. (15.10.2026), риск 91/100 Critical, владелец: Иванов И.
  • expired.lab.local — ИСТЁК 5 дн. назад, риск 80/100
  • warn.lab.local — 25 дн., риск 35/100
  Открыть: http://<host>:8000/
  ```
- Кнопка «Отправить уведомления сейчас» — отправляет сводку по текущему состоянию **без** учёта дедупликации (для демо).
- Ошибки отправки не роняют скан: пишутся в audit_log и показываются в UI.

### 6.14. Экспорт (`exporters/`)
- `GET /api/export/csv` — UTF-8-BOM (чтобы Excel открыл кириллицу), разделитель `;`.
- `GET /api/export/xlsx` — лист «Сертификаты» (все колонки таблицы + SAN, Thumbprint, Issues через `; `), заливка ячейки статуса цветом, автофильтр, закреплённая шапка, ширина колонок; лист «Сводка» (KPI); лист «Проблемы» (одна строка на Issue с рекомендацией).
- `GET /report` — HTML-отчёт для печати: шапка (дата, кол-во целей), KPI, топ рисков, полная таблица, раздел «Рекомендации»; `@media print` стили; кнопка «Печать / PDF».
- Экспорт учитывает текущие фильтры (параметры query string) — желательно, не обязательно.
- Каждая выгрузка — запись в audit_log.

### 6.15. Журнал (`/audit`)
Таблица последних 500 событий audit_log (время, actor, действие, детали) с фильтром по действию.

---

## 7. API (JSON)

| Метод | Путь | Назначение |
|---|---|---|
| POST | `/api/targets/parse` | body `{text}` или multipart file → `{targets:[...], errors:[...]}` (предпросмотр) |
| POST | `/api/scans` | body `{text}` / file / `{rescan_all:true}` → `{scan_id}` |
| GET | `/api/scans` | список сканов |
| GET | `/api/scans/{id}` | статус + прогресс `{done, total, status}` |
| GET | `/api/results` | последние результаты по всем endpoint (для Dashboard) |
| GET | `/api/summary` | KPI + данные для графиков + топ-10 |
| GET | `/api/endpoints/{id}` | детали + история |
| PATCH | `/api/endpoints/{id}` | `{service_name?, owner?, criticality?}` |
| DELETE | `/api/endpoints/{id}` | удалить цель |
| GET/PUT | `/api/settings` | чтение/изменение настроек (с валидацией) |
| POST | `/api/trusted-ca` | загрузка корневого CA |
| GET | `/api/trusted-ca` | список |
| DELETE | `/api/trusted-ca/{name}` | удалить |
| POST | `/api/notifications/test/{channel}` | тест канала |
| POST | `/api/notifications/send-now` | отправить сводку |
| GET | `/api/export/csv`, `/api/export/xlsx` | экспорт |
| GET | `/api/audit` | журнал |
| GET | `/health` | `{"status":"ok"}` |

Страницы: `/`, `/scan`, `/endpoint/{id}`, `/settings`, `/audit`, `/report`.

---

## 8. Требования безопасности и нефункциональные
- Read-only: только TLS-handshake к целям.
- Нет хранения паролей: секреты только в `.env`, маскирование в UI/логах, `.env` в `.gitignore`.
- Журналирование всех действий (6.15).
- Приложение по умолчанию слушает `127.0.0.1:8000`; для показа с другого устройства — `HOST=0.0.0.0` в `.env`.
- Ограничение размера загружаемого файла (1 МБ) и числа целей за скан (`max_targets=2048`).
- Экранирование всего пользовательского ввода в HTML (Jinja autoescape, в JS — `textContent`, не `innerHTML` для данных).
- Производительность: 50 целей сканируются < 15 с.
- Запуск одной командой: `run.bat` / `run.sh` (создать venv при отсутствии, установить зависимости, `init_db`, запустить uvicorn).

---

## 9. Тестовый стенд (демо)

### 9.1. Генерация сертификатов — `lab/generate_certs.py`
Использует `cryptography`, даты относительно текущего момента. Создаёт в `lab/certs/`:
- `lab-root-ca` (Lab Root CA, 10 лет) → **копируется в `data/trusted_ca/`** (эмуляция корпоративного CA);
- `lab-intermediate-ca` (подписан root);
- `rogue-ca` (НЕ доверенный);
- для каждого сервиса: `<name>.key`, `<name>.crt` (leaf), `<name>.fullchain.pem` (leaf + intermediate), `<name>.pfx` (пароль `lab`, для IIS).

| Хост (SNI) | Сертификат | Ожидаемый результат |
|---|---|---|
| `valid.lab.local` | intermediate, 365 дн., SAN=имя, fullchain | OK, риск Low |
| `info.lab.local` | 45 дн. | INFO |
| `warn.lab.local` | 25 дн. | WARNING |
| `soon.lab.local` | 10 дн. | CRITICAL |
| `vpn.lab.local` | 5 дн., в CSV criticality=critical, owner задан | CRITICAL, **риск 91** (пример из ТЗ) |
| `expired.lab.local` | not_before −400 дн., not_after −5 дн. | EXPIRED |
| `selfsigned.lab.local` | self-signed | SELF_SIGNED |
| `untrusted.lab.local` | подписан rogue-ca | CHAIN_UNTRUSTED |
| `nochain.lab.local` | подписан intermediate, сервер отдаёт **только leaf** | CHAIN_UNTRUSTED (неполная цепочка) |
| `mismatch.lab.local` | SAN=`www.other.local` | HOSTNAME_MISMATCH |
| `weak.lab.local` | RSA 1024 + SHA-1, 200 дн. | WEAK_KEY + WEAK_SIGNATURE |
| `wildcard.lab.local` | SAN=`*.lab.local`, 300 дн. | OK (проверка wildcard) |
| `dead.lab.local` | нет сервера (в hosts указан, порт закрыт) | ERROR / UNREACHABLE |

### 9.2. Тестовый сервер — `lab/lab_server.py`
- Один процесс, слушает `0.0.0.0:443` (если нет прав — `8443`, порт параметром `--port`).
- `ssl.SSLContext.sni_callback` выбирает контекст по SNI; без SNI — сертификат `valid`.
- Для `weak` — контекст с `set_ciphers("DEFAULT:@SECLEVEL=0")`, в try (если OpenSSL не даёт — вывести предупреждение и пропустить).
- На любой GET отвечает простой HTML «Lab service: <name>».
- `dead.lab.local` в hosts указывать на `127.0.0.2` (там ничего не слушает).

### 9.3. Файлы
- `lab/hosts.txt` — строки `127.0.0.1 valid.lab.local` … для копирования в `C:\Windows\System32\drivers\etc\hosts` / `/etc/hosts`.
- `lab/targets.txt` — все хосты (+ одна строка CIDR `127.0.0.0/30` и одна URL-строка для демонстрации парсера).
- `lab/targets.csv` — с колонками `target;service_name;owner;criticality`, у 2–3 целей owner пустой.
- `lab/iis_setup.ps1` (опционально, если останется время): импорт PFX в `Cert:\LocalMachine\My`, создание сайтов IIS с SNI-привязками на 443. Для показа «как в ТЗ» на Windows Server VM.

### 9.4. Резервный стенд (если локальный не поднялся)
`expired.badssl.com`, `self-signed.badssl.com`, `wrong.host.badssl.com`, `untrusted-root.badssl.com`, `incomplete-chain.badssl.com`, `sha1-intermediate.badssl.com`, `rsa2048.badssl.com` — в `lab/targets_public.txt`. Требует интернет.

---

## 10. План разработки по шагам

Время указано ориентировочно (старт 03:45). Каждый шаг = отдельный коммит.

### Шаг 0. Каркас (03:45–04:15)
- Структура из 4.1, `requirements.txt`, `.env.example`, `.gitignore`, `run.bat`, `run.sh`, `config.py`, `db.py`, `models.py`, `init_db()`, `main.py` с `/health` и пустой `base.html` (шапка с навигацией: Dashboard · Сканирование · Настройки · Журнал · Отчёт).
- Скачать `chart.umd.min.js` в `app/static/vendor/`.
- **Приёмка:** `run.bat` поднимает сервер, `/health` → ok, `data/radar.db` создана, таблицы есть.

### Шаг 1. Тестовый стенд (04:15–05:00)
- `lab/generate_certs.py`, `lab/lab_server.py`, `hosts.txt`, `targets.txt`, `targets.csv`, `targets_public.txt`.
- **Приёмка:** после добавления hosts `curl -vk https://soon.lab.local` (или браузер) показывает нужный сертификат; `openssl s_client -connect 127.0.0.1:443 -servername nochain.lab.local` показывает цепочку из одного сертификата.

### Шаг 2. Парсер целей (05:00–05:25)
- `parser.py` по 6.1 + тесты `tests/test_parser.py`.
- **Приёмка:** все примеры из таблицы 6.1 разбираются верно; CIDR `/30` → 2 хоста; `/16` → ошибка; CSV с `;` и BOM читается.

### Шаг 3. TLS-коллектор + разбор сертификата (05:25–06:30)
- `collectors/base.py`, `collectors/tls_collector.py` (6.2, 6.3), `analysis/cert_parser.py` (6.5), `analysis/hostname.py` (6.4).
- Тесты: `test_hostname.py` (точное, wildcard, CN-fallback, IP, регистр); `test_collector_lab.py` — интеграционный, помечен `@pytest.mark.lab`, запускается при поднятом стенде.
- **Приёмка:** CLI-проверка `python -m app.collectors.tls_collector soon.lab.local` печатает JSON со всеми атрибутами; для каждого хоста из 9.1 chain_status соответствует таблице.

### Шаг 4. Анализ: статусы, проверки, риск (06:30–07:10)
- `analysis/status.py`, `analysis/checks.py`, `analysis/risk.py` по 6.6–6.8.
- Тесты `test_status.py` (границы 60/31/30/15/14/0/−1), `test_risk.py` (**vpn: 91 Critical**; expired; self-signed не суммируется с chain; ERROR → null).
- **Приёмка:** тесты зелёные.

### Шаг 5. Скан-оркестратор + API сканирования (07:10–07:45)
- `scanner.py` (параллельный скан, прогресс в памяти + запись в БД, создание/обновление endpoints), `api/scans.py`, `api/results.py`, `api/endpoints.py`, `audit.py` (запись событий).
- **Приёмка:** `POST /api/scans` с `lab/targets.txt` → через < 15 с `GET /api/results` возвращает все цели с корректными статусами, issues и risk; в audit_log есть `scan_started/finished`.

### Шаг 6. Dashboard + страница сканирования (07:45–09:00) — **самый важный для жюри**
- `/scan` (6.10), `/` (6.9): KPI, 2 графика, топ-10, таблица с фильтрами и сортировкой, бейджи, пустое состояние.
- Аккуратный CSS: светлая тема, карточки, читаемая таблица, sticky-шапка таблицы, адаптивность до 1280px.
- **Приёмка:** сценарий «вставить демо-список → сканировать → увидеть Dashboard» выполняется без ошибок в консоли браузера; все фильтры и сортировки работают.

### Шаг 7. Детали, владельцы, история (09:00–09:40)
- `/endpoint/{id}` (6.11), PATCH с пересчётом риска, загрузка CSV с владельцами.
- **Приёмка:** назначение owner у цели без владельца убирает NO_OWNER и снижает риск на 10×multiplier; смена criticality меняет риск сразу.

### Шаг 8. Экспорт (09:40–10:10)
- CSV, XLSX (3 листа), HTML-отчёт `/report` (6.14).
- **Приёмка:** XLSX открывается в Excel без предупреждений, кириллица корректна, статусы раскрашены.

### Шаг 9. Уведомления (10:10–10:45)
- `notifiers/*`, `dispatcher.py`, вызов после скана, кнопки «Тест» и «Отправить сейчас».
- **Приёмка:** при заданном Telegram-токене после скана стенда приходит одно сводное сообщение; повторный скан **не** шлёт дубли; «Отправить сейчас» шлёт.

### Шаг 10. Настройки, доверенные CA, журнал (10:45–11:00)
- `/settings` (6.12), `/audit` (6.15). Изменение порогов пересчитывает статусы последних результатов без пересканирования.
- **Приёмка:** смена `threshold_info` 60→40 сразу переводит `info.lab.local` (45 дн.) из INFO в OK, а смена `threshold_warning` 30→50 — в WARNING; загрузка/удаление CA работает; все действия видны в журнале.

### 🔒 11:00 — FEATURE FREEZE

### Шаг 11. Стабилизация (11:00–11:45)
- Полный прогон демо-сценария (раздел 12) 2 раза с нуля (удалить `data/radar.db`).
- `README.md`: назначение, архитектура (схема из раздела 4), запуск, стенд, соответствие требованиям ТЗ (таблица 2.1 с галочками), безопасность, развитие (Infrastructure Risk Radar: Identity/DNS/Service/Patch/Backup Radar).
- **Приёмка:** `pytest` зелёный, свежий клон + `run.bat` работает.

### 11:45–13:00 — репетиция демо, презентация, буфер (без кода).

### Опционально (только если опережаете график)
1. Автоскан по расписанию (APScheduler).
2. `iis_setup.ps1` и показ на Windows Server VM.
3. Экспорт с учётом фильтров.
4. Редактирование весов риска в UI.
5. Эндпоинт `/metrics` в формате Prometheus (`cert_days_left{host=...}`) — «интеграция с корпоративным мониторингом».

---

## 11. Тесты (минимальный набор)
| Файл | Что проверяет |
|---|---|
| `test_parser.py` | все форматы 6.1, CIDR-лимит, CSV `;`/`,`/BOM, дубликаты, ошибки строк |
| `test_hostname.py` | точное совпадение, wildcard (1 лейбл), CN-fallback, игнор CN при наличии SAN, IP, регистр, завершающая точка |
| `test_status.py` | границы порогов, кастомные пороги |
| `test_risk.py` | пример vpn = 91 Critical; expired; не-суммирование self-signed+chain; NO_OWNER; ERROR → null; cap 100 |
| `test_checks.py` | каждая проверка срабатывает/не срабатывает |
| `test_dispatcher.py` | выбор порога, дедупликация, новый thumbprint сбрасывает (notifier замокан) |
| `test_collector_lab.py` (`-m lab`) | все хосты стенда дают ожидаемые статусы из 9.1 |

---

## 12. Демо-сценарий (5–7 минут)
1. **Проблема (30 с):** «Истёкший сертификат = простой сервиса. Сейчас проверки ручные».
2. **Стенд:** показать список целей (DNS, IP, URL, CIDR) и CSV с владельцами/критичностью.
3. **Скан:** «Вставить демо-список» → «Сканировать» → прогресс → Dashboard.
4. **Dashboard:** KPI, график сроков, «Требуют внимания» — `vpn.lab.local` **91/100 Critical: истекает через 5 дней, сервис критичный** (дословно пример из ТЗ).
5. **Фильтры/сортировка:** по статусу Critical, по Issuer, по владельцу.
6. **Детали:** `nochain.lab.local` — ошибка цепочки с подсказкой про промежуточный сертификат; `mismatch.lab.local` — CN/SAN vs имя; `weak.lab.local` — слабая криптография. Рекомендации по устранению.
7. **Владелец:** назначить owner → риск снижается на глазах.
8. **Уведомление:** в Telegram на телефоне уже пришла сводка (показать экран).
9. **Экспорт:** скачать Excel и открыть отчёт для печати.
10. **Безопасность:** read-only, без паролей, журнал действий (открыть `/audit`), настраиваемые пороги (поменять и показать пересчёт).
11. **Развитие:** модульная архитектура (новая проверка = одна функция), путь к Infrastructure Risk Radar.

---

## 13. Чек-лист соответствия ТЗ хакатона (заполнить в README перед сдачей)
- [ ] 3.3 Список серверов/IP/DNS/URL/диапазонов, порт 443
- [ ] 3.4 Все 8 атрибутов отображаются
- [ ] 3.5 Пять статусов, пороги настраиваемые
- [ ] 3.6 Истёкший / скоро истекает / self-signed / цепочка / несоответствие имени
- [ ] 3.7 Dashboard: количество, состояние, ближайшие сроки, фильтры и сортировка по сервису, владельцу, Issuer, сроку, статусу
- [ ] 3.8 Уведомления на порогах 60/30/14/7/1 (Telegram/Email/Teams)
- [ ] 3.9 Risk Score с причинами
- [ ] 3.11 Экспорт отчёта
- [ ] 4.1 Модульная архитектура
- [ ] 4.2 Read-only, без хранения паролей, журналирование
- [ ] 4.3 Понятный интерфейс, настраиваемые пороги, экспорт
