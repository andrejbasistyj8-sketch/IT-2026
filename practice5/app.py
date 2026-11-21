"""ДокументКонтроль — навчальна ІАС реєстрації та аналізу документів."""
import csv
import io
import logging
import os
from contextlib import contextmanager
from datetime import date, datetime

import psycopg2
from psycopg2 import errors
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request

load_dotenv()
app = Flask(__name__)
app.json.ensure_ascii = False

STATUSES = ("Новий", "В роботі", "Виконано")
PRIORITIES = ("Низький", "Звичайний", "Високий")
FIELDS = (
    "registration_number", "title", "category", "sender", "received_date",
    "due_date", "status", "priority", "assignee", "description",
)
SELECT_FIELDS = (
    "id, registration_number, title, category, sender, received_date, "
    "due_date, status, priority, assignee, description, created_at"
)


def get_connection():
    """Під'єднання до PostgreSQL; паролі не зберігаються в коді."""
    if os.getenv("DATABASE_URL"):
        return psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=5)
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "documents_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        connect_timeout=5,
    )


@contextmanager
def db_cursor(write=False):
    connection = get_connection()
    try:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            yield cursor
        if write:
            connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def as_json(row):
    return {
        key: value.isoformat() if isinstance(value, (date, datetime)) else value
        for key, value in dict(row).items()
    }


def parse_date(value, field, required=True):
    if value is None or str(value).strip() == "":
        if required:
            raise ValueError(f"Поле «{field}» обов'язкове.")
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"Поле «{field}» має формат РРРР-ММ-ДД.") from exc


def validate_document(payload):
    """Нормалізація й перевірка даних перед INSERT/UPDATE."""
    if not isinstance(payload, dict):
        raise ValueError("Потрібен JSON-об'єкт із полями документа.")
    cleaned = {}
    limits = {
        "registration_number": 50, "title": 255, "category": 70,
        "sender": 150, "assignee": 150, "description": 3000,
    }
    required = ("registration_number", "title", "sender")
    for field, max_length in limits.items():
        value = str(payload.get(field) or "").strip()
        if field in required and not value:
            raise ValueError(f"Поле «{field}» обов'язкове.")
        if len(value) > max_length:
            raise ValueError(f"Поле «{field}» перевищує {max_length} символів.")
        cleaned[field] = value
    cleaned["category"] = cleaned["category"] or "Інший"
    cleaned["received_date"] = parse_date(payload.get("received_date"), "Дата надходження")
    cleaned["due_date"] = parse_date(payload.get("due_date"), "Строк виконання", required=False)
    if cleaned["due_date"] and cleaned["due_date"] < cleaned["received_date"]:
        raise ValueError("Строк виконання не може бути раніше дати надходження.")
    cleaned["status"] = str(payload.get("status") or "Новий")
    cleaned["priority"] = str(payload.get("priority") or "Звичайний")
    if cleaned["status"] not in STATUSES:
        raise ValueError("Невідомий статус документа.")
    if cleaned["priority"] not in PRIORITIES:
        raise ValueError("Невідомий пріоритет документа.")
    return cleaned


def filters_from_request(args):
    clauses, params = [], []
    search = str(args.get("q", "")).strip()
    if len(search) > 200:
        raise ValueError("Пошуковий запит завеликий.")
    if search:
        clauses.append("(registration_number ILIKE %s OR title ILIKE %s OR sender ILIKE %s)")
        params.extend([f"%{search}%"] * 3)
    status = str(args.get("status", "")).strip()
    if status:
        if status not in STATUSES:
            raise ValueError("Недопустимий статус фільтра.")
        clauses.append("status = %s")
        params.append(status)
    category = str(args.get("category", "")).strip()
    if category:
        if len(category) > 70:
            raise ValueError("Недопустима категорія фільтра.")
        clauses.append("category = %s")
        params.append(category)
    for key, label, op in (("date_from", "Дата від", ">="), ("date_to", "Дата до", "<=")):
        if args.get(key):
            clauses.append(f"received_date {op} %s")
            params.append(parse_date(args[key], label))
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/health")
def health():
    with db_cursor() as cur:
        cur.execute("SELECT 1 AS ok")
        ok = cur.fetchone()["ok"]
    return jsonify({"status": "ok" if ok == 1 else "error"})


@app.get("/api/documents")
def list_documents():
    where, params = filters_from_request(request.args)
    with db_cursor() as cur:
        cur.execute(
            f"SELECT {SELECT_FIELDS} FROM documents{where} "
            "ORDER BY received_date DESC, id DESC LIMIT 500", params,
        )
        rows = cur.fetchall()
    return jsonify([as_json(row) for row in rows])


@app.get("/api/documents/<int:doc_id>")
def get_document(doc_id):
    with db_cursor() as cur:
        cur.execute(f"SELECT {SELECT_FIELDS} FROM documents WHERE id = %s", (doc_id,))
        row = cur.fetchone()
    if row is None:
        return jsonify({"error": "Документ не знайдено."}), 404
    return jsonify(as_json(row))


@app.post("/api/documents")
def create_document():
    data = validate_document(request.get_json(silent=True))
    columns = ", ".join(FIELDS)
    placeholders = ", ".join(["%s"] * len(FIELDS))
    with db_cursor(write=True) as cur:
        cur.execute(
            f"INSERT INTO documents ({columns}) VALUES ({placeholders}) RETURNING {SELECT_FIELDS}",
            tuple(data[field] for field in FIELDS),
        )
        row = cur.fetchone()
    return jsonify(as_json(row)), 201


@app.put("/api/documents/<int:doc_id>")
def update_document(doc_id):
    data = validate_document(request.get_json(silent=True))
    assignments = ", ".join(f"{field} = %s" for field in FIELDS)
    values = tuple(data[field] for field in FIELDS) + (doc_id,)
    with db_cursor(write=True) as cur:
        cur.execute(
            f"UPDATE documents SET {assignments} WHERE id = %s RETURNING {SELECT_FIELDS}",
            values,
        )
        row = cur.fetchone()
    if row is None:
        return jsonify({"error": "Документ не знайдено."}), 404
    return jsonify(as_json(row))


@app.delete("/api/documents/<int:doc_id>")
def delete_document(doc_id):
    with db_cursor(write=True) as cur:
        cur.execute("DELETE FROM documents WHERE id = %s RETURNING id", (doc_id,))
        deleted = cur.fetchone()
    if deleted is None:
        return jsonify({"error": "Документ не знайдено."}), 404
    return jsonify({"message": "Документ видалено.", "id": doc_id})


@app.get("/api/stats")
def stats():
    with db_cursor() as cur:
        cur.execute("""
            SELECT COUNT(*)::int AS total,
                   COUNT(*) FILTER (WHERE status = 'Новий')::int AS new,
                   COUNT(*) FILTER (WHERE status = 'В роботі')::int AS in_progress,
                   COUNT(*) FILTER (WHERE status = 'Виконано')::int AS completed,
                   COUNT(*) FILTER (
                       WHERE due_date < CURRENT_DATE AND status <> 'Виконано'
                   )::int AS overdue
            FROM documents
        """)
        totals = dict(cur.fetchone())
        cur.execute("""
            SELECT status AS name, COUNT(*)::int AS count
            FROM documents GROUP BY status ORDER BY count DESC, status
        """)
        statuses = [dict(row) for row in cur.fetchall()]
        cur.execute("""
            SELECT category AS name, COUNT(*)::int AS count
            FROM documents GROUP BY category ORDER BY count DESC, category LIMIT 7
        """)
        categories = [dict(row) for row in cur.fetchall()]
        cur.execute("""
            SELECT TO_CHAR(DATE_TRUNC('month', received_date), 'YYYY-MM') AS month,
                   COUNT(*)::int AS count
            FROM documents GROUP BY DATE_TRUNC('month', received_date)
            ORDER BY DATE_TRUNC('month', received_date) DESC LIMIT 6
        """)
        months = list(reversed([dict(row) for row in cur.fetchall()]))
    return jsonify({"totals": totals, "statuses": statuses, "categories": categories, "months": months})


def safe_excel(value):
    """Не допускати CSV-ін'єкцію при відкритті експорту в Excel."""
    s = "" if value is None else str(value)
    return "'" + s if s.lstrip().startswith(("=", "+", "-", "@")) else s


@app.get("/api/export.csv")
def export_csv():
    where, params = filters_from_request(request.args)
    with db_cursor() as cur:
        cur.execute(
            f"SELECT {SELECT_FIELDS} FROM documents{where} ORDER BY received_date DESC, id DESC", params
        )
        rows = cur.fetchall()
    stream = io.StringIO()
    writer = csv.writer(stream)
    columns = (
        "id", "registration_number", "title", "category", "sender",
        "received_date", "due_date", "status", "priority", "assignee", "description",
    )
    writer.writerow((
        "ID", "Реєстраційний номер", "Назва", "Категорія", "Відправник",
        "Отримано", "Строк", "Статус", "Пріоритет", "Виконавець", "Опис",
    ))
    for row in rows:
        writer.writerow([safe_excel(row[col]) for col in columns])
    return Response(
        "\ufeff" + stream.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=documents.csv"},
    )


@app.errorhandler(ValueError)
def invalid_request(exc):
    return jsonify({"error": str(exc)}), 400


@app.errorhandler(psycopg2.Error)
def database_error(exc):
    app.logger.exception("Database request failed")
    if isinstance(exc, errors.UniqueViolation):
        return jsonify({"error": "Документ із таким реєстраційним номером уже існує."}), 409
    return jsonify({"error": "База даних недоступна. Перевірте налаштування PostgreSQL."}), 503


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=False)
