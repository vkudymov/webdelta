# ВебДельта (WebDelta)

Инструмент для отслеживания изменений на веб-страницах.

A tool for tracking changes on web pages.

## Функциональность / Features

- **Скачать страницу / Download page**: Сохраняет текст страницы и вложения
- **Показать дельту / Show Delta**: Сравнивает две выбранные версии из списка и показывает различия с подсветкой
- В шапке выбирается способ сверки файлов: **Хеш** (как раньше, по байтам и номеру строки) или **Модель**. Модель ищет соответствующий фрагмент даже если выше вставили текст, и отдельно решает, изменился ли смысл. Для теста нужен LM Studio (`FILEDIFF_BASE_URL`, по умолчанию `http://127.0.0.1:1234/v1`). Учёт токенов пишется в `FILEDIFF_USAGE_PATH`.

## Хранение / Storage

- Снимки страниц **всегда** пишутся в папку `results/<сайт>/<дата>/<время>/` (`page.json`, вложения, `error.json`). Каталог `results/` **не хранится в Git** (`.gitignore`); это только локальные данные.
- Текст страницы лежит в `page.json` (`content`). В `files/` сохраняются только документы по ссылкам: PDF, Word, Excel, PowerPoint, ODF, CSV, RTF, TXT и архивы. Картинки и пиксели счётчиков не скачиваются.
- **Supabase** опционален: если в `.env` заданы `SUPABASE_URL` и `SUPABASE_SERVICE_ROLE_KEY`, те же данные дополнительно пишутся в облачную БД.
- Без ключей Supabase приложение работает только с файлами.
- В шапке рядом с языком выбирается, **откуда читать** данные: **Файлы** или **Supabase**.

## Технический стек / Tech Stack

- **Frontend**: Next.js + Tailwind CSS
- **Backend**: Python + FastAPI
- **Web reading**: Playwright (rendered DOM)
- **Storage**: local `results/` + optional Supabase (Postgres)
- **AI**: OpenAI SDK — короткое объяснение дельты (опционально)

## Запуск разработки / Dev

В корне есть скрипт, который делает первый запуск (установка зависимостей) и запускает backend+frontend в отдельных окнах Terminal:

```bash
./dev.sh
```

- Frontend: http://localhost:3000
- Backend: http://127.0.0.1:8000

Либо из VS Code / Cursor: запустите `run.py`.

## Переменные окружения / Environment

Скопируйте пример и заполните нужные значения:

```bash
cp .env.example .env
```

Локальные снимки сохраняются в `RESULTS_DIR` (по умолчанию `results/`). Ключи Supabase нужны только если хотите читать и писать в облако.

## Supabase schema

SQL схема лежит в `backend/supabase/schema.sql`. Её можно выполнить в Supabase SQL Editor (service role).

## API Endpoints

- `GET /api/storage` — доступные источники (`results`, опционально `supabase`)
- `GET /api/pages/check?url=<url>&source=` — проверить наличие сохранённой страницы
- `POST /api/pages/download` — скачать и сохранить страницу
- `POST /api/pages/compare` — сравнить текущую версию с сохранённой (в ответе может быть `explanation`)
- `GET /api/pages/list?source=` — список сайтов
- `DELETE /api/pages/{id}?source=` — удалить сайт

Параметр `source` — `results` или `supabase`.

## Структура проекта / Project Structure

```
webdelta/
├── backend/
│   ├── app/                  # FastAPI + Playwright + storage layer + agent
│   ├── requirements.txt
│   └── supabase/
│       └── schema.sql
├── frontend/
│   ├── src/                  # Next.js App Router UI
│   └── package.json
├── results/                  # локальные снимки страниц
└── README.md
```

## Локализация / Localization

Интерфейс поддерживает два языка:
- Русский (по умолчанию)
- English

Переключение языка доступно в шапке приложения.
