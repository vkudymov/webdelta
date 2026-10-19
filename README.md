# ВебДельта (WebDelta)

Инструмент для отслеживания изменений на веб-страницах.

A tool for tracking changes on web pages.

## Функциональность / Features

- **Скачать оригинал / Download Original**: Сохраняет текст страницы и все вложения в базу данных
- **Сравнить с оригиналом / Compare with Original**: Сравнивает текущую версию страницы с сохранённой
- **Показать дельту / Show Delta**: Отображает найденные различия с подсветкой

## Технический стек / Tech Stack

- **Frontend**: React + Vite + Tailwind CSS
- **Backend**: Node.js + Express
- **Database**: SQLite
- **Diff**: jsdiff library

## Установка / Installation

### Backend (сервер)

```bash
cd server
npm install
npm start
```

Сервер запустится на http://localhost:3001

### Frontend (клиент)

```bash
cd client
npm install
npm run dev
```

Клиент запустится на http://localhost:5173

## API Endpoints

- `GET /api/pages/check?url=<url>` - Проверить наличие сохранённой страницы
- `POST /api/pages/download` - Скачать и сохранить страницу
- `POST /api/pages/compare` - Сравнить текущую версию с сохранённой
- `GET /api/pages/list` - Список всех сохранённых страниц
- `DELETE /api/pages/:id` - Удалить сохранённую страницу

## Структура проекта / Project Structure

```
webdelta/
├── server/
│   ├── src/
│   │   ├── index.js          # Точка входа сервера
│   │   ├── db.js             # SQLite инициализация
│   │   ├── routes/
│   │   │   └── pages.js      # API маршруты
│   │   └── services/
│   │       ├── fetcher.js    # Загрузка страниц
│   │       └── differ.js     # Сравнение текстов
│   └── package.json
├── client/
│   ├── src/
│   │   ├── App.jsx           # Главный компонент
│   │   ├── components/       # UI компоненты
│   │   ├── hooks/            # React хуки
│   │   └── i18n/             # Локализация (RU/EN)
│   └── package.json
└── README.md
```

## Локализация / Localization

Интерфейс поддерживает два языка:
- 🇷🇺 Русский (по умолчанию)
- 🇬🇧 English

Переключение языка доступно в шапке приложения.
