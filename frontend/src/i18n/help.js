export const helpContent = {
  ru: {
    title: "Справка",
    leadTitle: "Зачем нужна ВебДельта",
    lead: [
      "ВебДельта создана, чтобы вы могли сохранить «как страница выглядела в этот день» и позже сравнить её с другой датой — без ручного просмотра всего текста и вложений.",
      "Типичная задача: регламенты, договоры, формы заявок и списки документов на сайте меняются незаметно. Вы скачиваете страницу сейчас, через неделю скачиваете снова и видите, что именно изменилось в тексте и в файлах.",
    ],
    sections: [
      {
        id: "can",
        title: "Что умеет приложение",
        blocks: [
          {
            type: "ul",
            items: [
              "Открыть страницу в браузере (как видит пользователь) и сохранить её текст.",
              "Скачать связанные документы: PDF, Word, Excel, PowerPoint, ODF, CSV, RTF, TXT и архивы. Картинки и счётчики не качаются.",
              "Хранить несколько версий одной проверки по дате и времени.",
              "Сверить любые две сохранённые версии: текст страницы и каждый файл.",
              "Сверять файлы по хешу (байты и строки) или по смыслу через локальную модель.",
              "Работать с локальной папкой «Файлы» и, если настроено, с облачной базой Supabase.",
              "Показать короткое объяснение дельты, если подключена модель-анализатор.",
              "Переключить язык интерфейса: RU / EN.",
            ],
          },
        ],
      },
      {
        id: "screen",
        title: "Как устроен экран",
        blocks: [
          {
            type: "ul",
            items: [
              "Слева — список сайтов и их версий.",
              "Справа сверху — название проверки, URL и кнопки «Скачать страницу» и «Показать дельту».",
              "В шапке — источник данных (Файлы / Supabase), способ сверки (Хеш / Модель), язык и эта справка.",
            ],
          },
        ],
      },
      {
        id: "download",
        title: "Как прочитать страницу в первый раз",
        blocks: [
          {
            type: "steps",
            items: [
              "В поле «Название проверки» задайте понятное имя (оно станет названием в списке слева). Если оставить пустым, возьмётся заголовок страницы.",
              "Вставьте полный URL страницы, включая https://.",
              "Нажмите «Скачать страницу».",
              "Дождитесь уведомления «Страница сохранена» и числа найденных вложений.",
              "Слева появится сайт со снимком: дата, время и сколько файлов скачано.",
            ],
          },
          {
            type: "note",
            text: "Приложение открывает страницу так, как её рисует браузер. Если сайт требует входа или закрыт сетью, чтение не получится — статус слева станет «Ошибка», подробности откроются по красной метке.",
          },
        ],
      },
      {
        id: "new-version",
        title: "Как прочитать новую версию той же страницы",
        blocks: [
          {
            type: "p",
            text: "Каждое скачивание — отдельный снимок. Старые версии не затираются: они остаются в списке по дате и времени.",
          },
          {
            type: "steps",
            items: [
              "Выберите сайт слева (подставятся URL и название) или введите тот же URL.",
              "Нажмите «Скачать страницу» ещё раз.",
              "Появится новая строка версии с текущими датой и временем.",
            ],
          },
          {
            type: "note",
            text: "Чтобы сравнить «как было» и «как стало», нужны минимум две версии. Скачайте страницу сейчас, затем повторите скачивание, когда контент мог измениться.",
          },
        ],
      },
      {
        id: "compare",
        title: "Как сверить разные версии",
        blocks: [
          {
            type: "steps",
            items: [
              "В шапке выберите способ сверки файлов: «Хеш» или «Модель» (если модель доступна).",
              "Слева раскройте сайт и отметьте галочками две версии. Первая получит метку «1», вторая — «2». Третью отметить нельзя, пока не снимете одну из выбранных.",
              "Версии должны быть у одного сайта. Если кликнуть другой сайт, выбор сбросится.",
              "Нажмите «Показать дельту».",
            ],
          },
          {
            type: "p",
            text: "Без двух отмеченных версий кнопка «Показать дельту» не сработает.",
          },
        ],
      },
      {
        id: "delta",
        title: "Что показывает сверка",
        blocks: [
          {
            type: "ul",
            items: [
              "Текст страницы: какие строки добавлены, удалены или изменены.",
              "Короткое объяснение — если настроен анализатор дельты.",
              "Файлы на сайте: сколько документов в каждой версии.",
              "Сверка файлов: добавленные, удалённые и изменённые документы. Одинаковые по имени и содержимому в список не попадают.",
              "Фильтры: «нет в» левой или правой версии и «изменено по содержимому».",
              "У изменённого файла можно раскрыть различия: построчно (Хеш) или пары по смыслу (Модель).",
            ],
          },
          {
            type: "p",
            text: "В режиме «Модель» пары помечаются так: смысл тот же, смысл изменился, только слева, только справа. Модель ищет соответствие даже если выше вставили абзац, и не путает сдвиг текста с правкой.",
          },
        ],
      },
      {
        id: "engines",
        title: "Хеш и Модель",
        blocks: [
          {
            type: "ul",
            items: [
              "Хеш — сверка по байтам и номеру строки. Быстро, без внешней модели. Подходит, когда файлы почти не двигались.",
              "Модель — смысловая сверка файлов (договоры, формы, регламенты). Нужен запущенный сервер модели. Если кнопка серая, модель недоступна.",
              "Список моделей появляется справа от кнопки «Модель», когда сервер отвечает.",
            ],
          },
        ],
      },
      {
        id: "model",
        title: "Как подключить модель",
        blocks: [
          {
            type: "p",
            text: "Для сверки файлов в шапке («Модель») нужен OpenAI-совместимый сервер. Обычно это LM Studio на этом же компьютере.",
          },
          {
            type: "steps",
            items: [
              "Установите LM Studio, скачайте модель и включите локальный сервер (по умолчанию http://127.0.0.1:1234/v1).",
              "Загрузите модель в LM Studio, чтобы она реально отвечала на запросы.",
              "В файле .env рядом с приложением (у portable Windows — рядом с WebDelta.exe) задайте FILEDIFF_BASE_URL=http://127.0.0.1:1234/v1 и FILEDIFF_API_KEY=lm-studio. FILEDIFF_MODEL можно оставить пустым — тогда берётся первая доступная модель.",
              "Перезапустите ВебДельту. Кнопка «Модель» должна стать активной, в списке появятся имена моделей.",
              "Выберите «Модель», нужную модель в списке и снова нажмите «Показать дельту».",
            ],
          },
          {
            type: "p",
            text: "Отдельно можно включить короткое объяснение изменений текста страницы. В .env: ANALYZER_PROVIDER=lmstudio и POST_ANALYZER_OPENAI_BASE_URL (тот же LM Studio) либо ANALYZER_PROVIDER=openai, OPENAI_API_KEY и OPENAI_MODEL.",
          },
          {
            type: "note",
            text: "Расход токенов сверки файлов пишется в FILEDIFF_USAGE_PATH (по умолчанию results/filediff-usage.jsonl). Платный API подключается той же схемой: другой FILEDIFF_BASE_URL и ключ.",
          },
        ],
      },
      {
        id: "storage",
        title: "Файлы и база данных (Supabase)",
        blocks: [
          {
            type: "p",
            text: "Каждое чтение страницы всегда сохраняется локально в папку results/<сайт>/<дата>/<время>/: текст в page.json, документы в files/. Это основной архив. Каталог results не попадает в Git.",
          },
          {
            type: "ul",
            items: [
              "«Файлы» в шапке — работа только с этой папкой. Так приложение работает сразу, без облака.",
              "«Supabase» — дополнительная облачная копия тех же снимков. Кнопка активна, только если в .env заданы SUPABASE_URL и SUPABASE_SERVICE_ROLE_KEY.",
              "Схема таблиц: backend/supabase/schema.sql (выполнить в SQL Editor проекта Supabase под service role).",
              "Список слева показывает данные выбранного источника. Переключение сбрасывает выбранные версии и текущую дельту.",
            ],
          },
          {
            type: "note",
            text: "Локальные файлы и Supabase — два независимых хранилища. Снимок, сделанный в «Файлы», не появится в «Supabase», пока вы не скачаете страницу уже с включённым Supabase (тогда пишется и локально, и в облако).",
          },
        ],
      },
      {
        id: "list",
        title: "Список сайтов, версии и удаление",
        blocks: [
          {
            type: "ul",
            items: [
              "Клик по сайту подставляет URL и название проверки.",
              "Стрелка слева сворачивает и разворачивает версии.",
              "Метки: «Сохранено», «Сверка», «Ошибка».",
              "Корзина у сайта удаляет всю проверку. Корзина у времени удаляет только эту версию и её файлы.",
            ],
          },
        ],
      },
      {
        id: "dev",
        title: "Как запустить и закрыть разработку (Mac)",
        blocks: [
          {
            type: "p",
            text: "В режиме разработки интерфейс и API работают отдельно: Next.js на http://localhost:3000, backend на http://127.0.0.1:8000.",
          },
          {
            type: "steps",
            items: [
              "В корне проекта выполните ./dev.sh или запустите run.py из Cursor (Run Python File).",
              "Откроются два окна Terminal: одно с backend (uvicorn), другое с frontend (npm run dev).",
              "Откройте в браузере http://localhost:3000.",
            ],
          },
          {
            type: "p",
            text: "Остановка:",
          },
          {
            type: "steps",
            items: [
              "В каждом окне Terminal, где крутится WebDelta, нажмите Ctrl+C — или просто закройте окно.",
              "Нужно остановить оба процесса: и backend (порт 8000), и frontend (порт 3000). Если закрыть только одно окно, второй сервис продолжит работать.",
              "При следующем запуске run.py может сам освободить занятые порты 3000 и 8000. Если dev.sh пишет, что порт занят, сначала закройте старые окна Terminal или завершите процесс на этом порту.",
            ],
          },
          {
            type: "note",
            text: "Windows portable (WebDelta.exe) — не режим разработки: там один адрес и остановка — закрытие окна консоли у exe (см. раздел ниже).",
          },
        ],
      },
      {
        id: "more",
        title: "Ещё полезно знать",
        blocks: [
          {
            type: "ul",
            items: [
              "Язык RU / EN меняет подписи интерфейса и язык заметок модели.",
              "На Windows portable запускайте WebDelta.exe: интерфейс и API на одном адресе (обычно http://127.0.0.1:8765/). Закройте окно консоли, чтобы остановить программу. Модель по-прежнему нужна отдельно (LM Studio).",
              "Журналы работы пишутся в log/ по дням: успехи, ошибки, список файлов.",
              "Если сверка файлов «Моделью» выглядит странно, убедитесь, что сравниваются две реальные версии одного документа, а LM Studio отвечает без обрыва.",
            ],
          },
        ],
      },
    ],
  },
  en: {
    title: "Help",
    leadTitle: "Why WebDelta exists",
    lead: [
      "WebDelta is built so you can keep a snapshot of how a page looked on a given day and later compare it with another date — without reading the whole page and every attachment by hand.",
      "A typical case: rules, contracts, application forms, and document lists change quietly. You download the page now, download it again in a week, and see exactly what changed in the text and in the files.",
    ],
    sections: [
      {
        id: "can",
        title: "What the app can do",
        blocks: [
          {
            type: "ul",
            items: [
              "Open a page in a real browser (as a user would see it) and save its text.",
              "Download linked documents: PDF, Word, Excel, PowerPoint, ODF, CSV, RTF, TXT, and archives. Images and tracking pixels are not downloaded.",
              "Keep several versions of the same check, grouped by date and time.",
              "Compare any two saved versions: page text and each file.",
              "Compare files by hash (bytes and line numbers) or by meaning with a local model.",
              "Work from the local Files folder and, if configured, from a Supabase database.",
              "Show a short explanation of the delta when an analyzer model is configured.",
              "Switch the interface language: RU / EN.",
            ],
          },
        ],
      },
      {
        id: "screen",
        title: "Layout",
        blocks: [
          {
            type: "ul",
            items: [
              "Left: list of sites and their versions.",
              "Top right: check name, URL, and the Download page / Show Delta buttons.",
              "Header: data source (Files / Supabase), compare mode (Hash / Model), language, and this help.",
            ],
          },
        ],
      },
      {
        id: "download",
        title: "How to read a page the first time",
        blocks: [
          {
            type: "steps",
            items: [
              "Enter a clear name in Check name (it becomes the title in the left list). If you leave it empty, the page title is used.",
              "Paste the full page URL, including https://.",
              "Click Download page.",
              "Wait for “Page saved” and the number of attachments found.",
              "The site appears on the left with a snapshot: date, time, and how many files were saved.",
            ],
          },
          {
            type: "note",
            text: "The app opens the page the way a browser renders it. If the site needs a login or is blocked, the read fails — the left list shows Error; open the red badge for details.",
          },
        ],
      },
      {
        id: "new-version",
        title: "How to read a new version of the same page",
        blocks: [
          {
            type: "p",
            text: "Each download is a separate snapshot. Older versions stay in the list by date and time.",
          },
          {
            type: "steps",
            items: [
              "Select the site on the left (URL and name are filled in) or enter the same URL.",
              "Click Download page again.",
              "A new version row appears with the current date and time.",
            ],
          },
          {
            type: "note",
            text: "To compare “before” and “after” you need at least two versions. Download now, then download again when the content may have changed.",
          },
        ],
      },
      {
        id: "compare",
        title: "How to compare versions",
        blocks: [
          {
            type: "steps",
            items: [
              "In the header, pick a file compare mode: Hash or Model (if a model is available).",
              "On the left, expand the site and tick two versions. The first is labeled 1, the second 2. You cannot tick a third until you uncheck one.",
              "Both versions must belong to the same site. Selecting another site clears the choice.",
              "Click Show Delta.",
            ],
          },
          {
            type: "p",
            text: "Show Delta will not run until two versions are selected.",
          },
        ],
      },
      {
        id: "delta",
        title: "What the delta shows",
        blocks: [
          {
            type: "ul",
            items: [
              "Page text: which lines were added, removed, or changed.",
              "A short explanation — if the delta analyzer is configured.",
              "Files on the site: how many documents each version has.",
              "File comparison: added, removed, and modified documents. Files that match by name and content are omitted.",
              "Filters: missing from the left or right version, and changed by content.",
              "You can expand a modified file: line-by-line (Hash) or meaning pairs (Model).",
            ],
          },
          {
            type: "p",
            text: "In Model mode, pairs are labeled same meaning, meaning changed, left only, or right only. The model still matches a fragment if text was inserted above it, so a shift is not treated as an edit.",
          },
        ],
      },
      {
        id: "engines",
        title: "Hash and Model",
        blocks: [
          {
            type: "ul",
            items: [
              "Hash compares bytes and line numbers. It is fast and needs no external model. Use it when files barely moved.",
              "Model compares file meaning (contracts, forms, policies). It needs a running model server. If the button is disabled, the model is unavailable.",
              "The model list appears next to Model when the server responds.",
            ],
          },
        ],
      },
      {
        id: "model",
        title: "How to connect a model",
        blocks: [
          {
            type: "p",
            text: "File comparison in the header (Model) needs an OpenAI-compatible server. That is usually LM Studio on the same computer.",
          },
          {
            type: "steps",
            items: [
              "Install LM Studio, download a model, and start the local server (default http://127.0.0.1:1234/v1).",
              "Load the model in LM Studio so it actually answers requests.",
              "In the .env file next to the app (for portable Windows, next to WebDelta.exe) set FILEDIFF_BASE_URL=http://127.0.0.1:1234/v1 and FILEDIFF_API_KEY=lm-studio. FILEDIFF_MODEL may stay empty — the first available model is used.",
              "Restart WebDelta. The Model button should become active and names should appear in the list.",
              "Select Model, pick a model, and click Show Delta again.",
            ],
          },
          {
            type: "p",
            text: "You can also enable a short explanation of page-text changes. In .env set ANALYZER_PROVIDER=lmstudio and POST_ANALYZER_OPENAI_BASE_URL (the same LM Studio), or ANALYZER_PROVIDER=openai with OPENAI_API_KEY and OPENAI_MODEL.",
          },
          {
            type: "note",
            text: "File-compare token usage is written to FILEDIFF_USAGE_PATH (default results/filediff-usage.jsonl). A paid API uses the same settings with a different FILEDIFF_BASE_URL and key.",
          },
        ],
      },
      {
        id: "storage",
        title: "Files and the database (Supabase)",
        blocks: [
          {
            type: "p",
            text: "Every page read is always stored locally under results/<site>/<date>/<time>/: text in page.json, documents in files/. This is the main archive. The results folder is not committed to Git.",
          },
          {
            type: "ul",
            items: [
              "Files in the header uses only that folder. The app works this way with no cloud setup.",
              "Supabase is an extra cloud copy of the same snapshots. The button is enabled only when .env has SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.",
              "Table schema: backend/supabase/schema.sql (run it in the Supabase SQL Editor with the service role).",
              "The left list shows the selected source. Switching source clears selected versions and the current delta.",
            ],
          },
          {
            type: "note",
            text: "Local files and Supabase are independent stores. A snapshot made under Files will not appear in Supabase until you download the page with Supabase selected (then it is written both locally and to the cloud).",
          },
        ],
      },
      {
        id: "list",
        title: "Site list, versions, and deletion",
        blocks: [
          {
            type: "ul",
            items: [
              "Click a site to fill in the URL and check name.",
              "The arrow on the left collapses and expands versions.",
              "Badges: Saved, Compared, Error.",
              "The site trash can deletes the whole check. The time trash can deletes only that version and its files.",
            ],
          },
        ],
      },
      {
        id: "dev",
        title: "How to start and stop development (Mac)",
        blocks: [
          {
            type: "p",
            text: "In dev mode the UI and API run separately: Next.js at http://localhost:3000, backend at http://127.0.0.1:8000.",
          },
          {
            type: "steps",
            items: [
              "From the project root run ./dev.sh or start run.py from Cursor (Run Python File).",
              "Two Terminal windows open: one for backend (uvicorn), one for frontend (npm run dev).",
              "Open http://localhost:3000 in your browser.",
            ],
          },
          {
            type: "p",
            text: "To stop:",
          },
          {
            type: "steps",
            items: [
              "In each Terminal window running WebDelta, press Ctrl+C — or close the window.",
              "Stop both processes: backend (port 8000) and frontend (port 3000). If you close only one window, the other service keeps running.",
              "The next run.py launch may free busy ports 3000 and 8000 automatically. If dev.sh says a port is busy, close the old Terminal windows or end the process on that port first.",
            ],
          },
          {
            type: "note",
            text: "Windows portable (WebDelta.exe) is not dev mode: one address; stop by closing the exe console window (see section below).",
          },
        ],
      },
      {
        id: "more",
        title: "Good to know",
        blocks: [
          {
            type: "ul",
            items: [
              "RU / EN changes interface labels and the language of model notes.",
              "On Windows portable, run WebDelta.exe: UI and API share one address (usually http://127.0.0.1:8765/). Close the console window to stop. A model still needs a separate LM Studio process.",
              "App logs go to log/ by day: successes, errors, and file lists.",
              "If Model file comparison looks odd, confirm you selected two real versions of the same document and that LM Studio answers without dropping the request.",
            ],
          },
        ],
      },
    ],
  },
};
