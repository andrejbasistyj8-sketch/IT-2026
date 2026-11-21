# ДокументКонтроль — інформаційно-аналітична система реєстрації документів

**Тема 1.4, групове заняття.** Власна навчальна ІАС на основі **PostgreSQL + Flask + HTML (`templates/`) + CSS/JavaScript (`static/`)**. Виконано за матеріалами [RomanMykolaichuk/mi2024-1](https://github.com/RomanMykolaichuk/mi2024-1/tree/main/Theme%201/1.4_1.5) — варіант «Облік вхідних документів», розширений аналітикою.

## Можливості

- Додавання й реєстрація документа, перегляд, редагування та видалення.
- Реєстраційний номер (унікальний), назва, категорія, відправник, дати, статус, пріоритет, виконавець, опис.
- Пошук за номером, назвою та відправником; фільтри за статусом, категорією, періодом.
- Аналітика: кількість документів, нові, в роботі, прострочені; розподіл за статусами/категоріями та динаміка надходження.
- Експорт поточної вибірки у **CSV** для Excel (UTF-8 із BOM).
- REST API з перевіркою вхідних даних і параметризованими SQL-запитами.
- Адаптивний інтерфейс українською без зовнішніх JS/CSS-бібліотек.
- Docker Compose для швидкого локального запуску разом із PostgreSQL.

## Склад проєкту

```text
practice5/
├── app.py                  # Flask API, PostgreSQL, аналітика, CSV
├── templates/
│   └── index.html          # HTML-шаблон вебсторінки
├── static/
│   ├── style.css           # оформлення та адаптивність
│   └── app.js              # інтерфейс, запити до API, графіки
├── sql/
│   ├── 01_schema.sql       # таблиця, обмеження та індекси
│   └── 02_demo_data.sql    # навчальні демонстраційні дані
├── tests/
│   └── test_app.py         # автоматизовані тести
├── Dockerfile
├── compose.yaml
├── requirements.txt
├── requirements-dev.txt
├── .env.example
├── .gitignore
└── README.md
```

## Швидкий запуск із Docker (рекомендовано)

1. Установіть [Docker Desktop](https://www.docker.com/products/docker-desktop/) та запустіть його.
2. Відкрийте термінал у папці `practice5`.
3. Виконайте:

   ```bash
   docker compose up --build -d
   ```

4. Відкрийте у браузері **http://127.0.0.1:5000**.

PostgreSQL створить таблицю та заповнить її 10 **вигаданими** прикладами з `sql/02_demo_data.sql`. Це відбувається **лише за першої ініціалізації порожнього тому**. Дані між перезапусками зберігаються в Docker volume. Перевірка API: http://127.0.0.1:5000/health.

> Docker-конфігурація призначена **тільки для локальної демонстрації**. Типовий пароль у `compose.yaml` необхідно змінити перед будь-яким мережевим розгортанням. За потреби вкажіть власний `POSTGRES_PASSWORD` у середовищі або локальному `.env` (не комітьте його до Git).

Зупинка: `docker compose down`. **Видалення усіх даних:** `docker compose down -v` — ця команда видалить volume бази даних.

## Запуск без Docker (Python + PostgreSQL)

**Потрібно:** Python 3.10+ та PostgreSQL 13+ (рекомендовано 16).

1. Створіть базу `documents_db` у PostgreSQL (через pgAdmin або SQL `CREATE DATABASE documents_db;`).
2. Виконайте SQL із `sql/01_schema.sql`, потім за бажанням із `sql/02_demo_data.sql` в контексті `documents_db`. Наприклад, через `psql`:

   ```bash
   psql -U postgres -d documents_db -f sql/01_schema.sql
   psql -U postgres -d documents_db -f sql/02_demo_data.sql
   ```

3. У папці `practice5` виконайте:

   ```bash
   python -m venv .venv
   # Windows PowerShell:
   .venv\Scripts\Activate.ps1
   # Linux/macOS:
   # source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. Скопіюйте `.env.example` у `.env`, внесіть **свій** логін і пароль PostgreSQL.
5. Запустіть:

   ```bash
   python app.py
   ```

6. Відкрийте http://127.0.0.1:5000.

## REST API

| Метод | URL | Призначення |
|---|---|---|
| `GET` | `/api/documents` | Перелік документів, пошук і фільтрація |
| `GET` | `/api/documents/1` | Один документ |
| `POST` | `/api/documents` | Додавання документа |
| `PUT` | `/api/documents/1` | Оновлення документа |
| `DELETE` | `/api/documents/1` | Видалення документа |
| `GET` | `/api/stats` | Показники, розподіли й динаміка |
| `GET` | `/api/export.csv` | CSV-експорт з урахуванням фільтрів |
| `GET` | `/health` | Перевірка підключення до PostgreSQL |

Параметри фільтрації для `GET /api/documents` і `/api/export.csv`: `q`, `status`, `category`, `date_from`, `date_to` (дата `YYYY-MM-DD`). Для списку обмеження — 500 документів на запит; CSV експортує всю відповідну вибірку.

Приклад запиту:

```bash
curl -X POST http://127.0.0.1:5000/api/documents \
  -H 'Content-Type: application/json' \
  -d '{"registration_number":"ВХ-2026/011","title":"Навчальний документ","category":"Лист","sender":"Навчальна група","received_date":"2026-11-21","due_date":"2026-11-30","status":"Новий","priority":"Звичайний","assignee":"Аналітик","description":"Приклад документа"}'
```

**Обмеження:** `status` — `Новий`, `В роботі`, `Виконано`; `priority` — `Низький`, `Звичайний`, `Високий`. Строк виконання не раніше дати отримання. Реєстраційний номер унікальний.

## Тестування

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

Тести перевіряють валідацію, параметри пошуку, обробку неправильних запитів, HTML-сторінку та можливість виконати CRUD на підміненому DB-адаптері. Для **повноцінної перевірки роботи PostgreSQL** необхідно запустити Docker Compose і відкрити застосунок.

## Архітектура

Браузер виконує `fetch()` → Flask REST API → SQL через `psycopg2` → PostgreSQL. Flask передає HTML через `render_template()`, CSS і JavaScript знаходяться в папці `static`, а SQL-агрегації виконуються **в PostgreSQL**, а не в браузері.

## Примітки з безпеки

Це навчальна локальна система, **не призначена для використання з реальними службовими, персональними чи конфіденційними документами**. Паролі беруться зі змінних оточення, SQL параметризовано, інтерфейс виводить динамічні тексти через `textContent`, CSV екранує значення, які можуть інтерпретуватися як формули. Перед публічним розгортанням необхідно окремо реалізувати аутентифікацію, авторизацію, CSRF-захист, HTTPS, аудит дій та керування секретами.

## Як опублікувати у GitHub

Переконайтеся, що файли проєкту лежать у директорії `practice5` власного репозиторію. Наприклад:

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cp -R /path/to/practice5 /path/to/YOUR_REPO/practice5
cd /path/to/YOUR_REPO
git add practice5
git commit -m "Add practice5 document analytics system"
git push origin main
```

Або створіть **новий** репозиторій і завантажте в нього вміст цього проєкту. Файл `.env` не завантажуйте.

---
**Призначення:** навчальна демонстрація методів інформаційно-аналітичного забезпечення. Дані в SQL-демо повністю вигадані.
