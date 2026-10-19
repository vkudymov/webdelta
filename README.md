# ВебДельта (WebDelta)

Инструмент для отслеживания изменений на веб-страницах.

A tool for tracking changes on web pages.

## Функциональность / Features

- **Скачать оригинал / Download Original**: Сохраняет текст страницы и все вложения в базу данных
- **Сравнить с оригиналом / Compare with Original**: Сравнивает текущую версию страницы с сохранённой
- **Показать дельту / Show Delta**: Отображает найденные различия с подсветкой

## Технический стек / Tech Stack

- **Frontend**: Next.js + Tailwind CSS
- **Backend**: Python + FastAPI
- **Web reading**: Playwright (rendered DOM)
- **Database**: Supabase (Postgres) (в dev без ключей автоматически используется локальный SQLite fallback)
- **AI**: OpenAI SDK — короткое объяснение дельты (опционально)

## Запуск разработки / Dev

В корне есть скрипт, который делает первый запуск (установка зависимостей) и запускает backend+frontend в отдельных окнах Terminal:

```bash
./dev.sh
```

- Frontend: http://localhost:3000
- Backend: http://127.0.0.1:8000

## Переменные окружения / Environment

Скопируйте пример и заполните нужные значения:

```bash
cp .env.example .env
```

Если `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` не заданы, backend автоматически использует локальный `SQLite` файл `backend/webdelta.dev.db`.

## Supabase schema

SQL схема лежит в `backend/supabase/schema.sql`. Её можно выполнить в Supabase SQL Editor (service role).

## API Endpoints

- `GET /api/pages/check?url=<url>` — проверить наличие сохранённой страницы
- `POST /api/pages/download` — скачать и сохранить страницу
- `POST /api/pages/compare` — сравнить текущую версию с сохранённой (в ответе может быть `explanation`)
- `GET /api/pages/list` — список всех сохранённых страниц
- `DELETE /api/pages/{id}` — удалить сохранённую страницу

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
└── README.md
```

## Локализация / Localization

Интерфейс поддерживает два языка:
- 🇷🇺 Русский (по умолчанию)
- 🇬🇧 English

Переключение языка доступно в шапке приложения.
