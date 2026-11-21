"""Автоматичні тести без залежності від живої бази даних."""
from contextlib import contextmanager
from datetime import date

import pytest

import app as application


@pytest.fixture
def client():
    application.app.config.update(TESTING=True)
    with application.app.test_client() as test_client:
        yield test_client


@pytest.fixture
def document_payload():
    return {
        "registration_number": "ВХ-2026/011",
        "title": "Тестовий документ",
        "sender": "Навчальна група",
        "category": "Лист",
        "received_date": "2026-11-21",
        "due_date": "2026-11-30",
        "status": "Новий",
        "priority": "Звичайний",
        "assignee": "Аналітик",
        "description": "Тестові дані",
    }


def test_home_renders_document_dashboard(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Реєстр вхідних документів" in response.get_data(as_text=True)
    assert b"static/style.css" in response.data
    assert b"static/app.js" in response.data


def test_payload_validation(document_payload):
    clean = application.validate_document(document_payload)
    assert clean["received_date"] == date(2026, 11, 21)
    assert clean["status"] == "Новий"
    assert clean["registration_number"] == "ВХ-2026/011"


@pytest.mark.parametrize("changes,expected", [
    ({"title": ""}, "обов'язкове"),
    ({"received_date": "bad"}, "формат"),
    ({"due_date": "2026-11-01"}, "раніше"),
    ({"status": "Невідомий"}, "статус"),
    ({"priority": "Критичний"}, "пріоритет"),
    ({"registration_number": "x" * 51}, "перевищує"),
])
def test_validation_rejects_bad_data(document_payload, changes, expected):
    document_payload.update(changes)
    with pytest.raises(ValueError, match=expected):
        application.validate_document(document_payload)


def test_search_is_parameterized():
    clause, params = application.filters_from_request({"q": "' OR 1=1 --", "status": "Новий"})
    assert "ILIKE %s" in clause
    assert "' OR 1=1 --" not in clause
    assert "%' OR 1=1 --%" in params
    assert "Новий" in params


def test_invalid_status_filter_returns_400(client):
    response = client.get("/api/documents?status=unknown")
    assert response.status_code == 400
    assert "error" in response.json


def test_invalid_json_returns_400(client):
    response = client.post("/api/documents", data="not json", content_type="application/json")
    assert response.status_code == 400
    assert "error" in response.json


def test_csv_excel_formula_prevention():
    assert application.safe_excel("=SUM(A1:A2)") == "'=SUM(A1:A2)"
    assert application.safe_excel("+123") == "'+123"
    assert application.safe_excel("звичайний текст") == "звичайний текст"


def test_create_and_list_with_fake_db(client, document_payload, monkeypatch):
    class FakeCursor:
        def __init__(self):
            self.rows = []
            self.row = None
            self.query = ""

        def execute(self, query, params=None):
            self.query = query
            if query.startswith("INSERT"):
                self.row = {"id": 17, **application.validate_document(document_payload), "created_at": date(2026, 11, 21)}
            elif query.startswith("SELECT"):
                self.rows = [{"id": 17, **application.validate_document(document_payload), "created_at": date(2026, 11, 21)}]

        def fetchone(self):
            return self.row

        def fetchall(self):
            return self.rows

    fake = FakeCursor()

    @contextmanager
    def fake_db(write=False):
        yield fake

    monkeypatch.setattr(application, "db_cursor", fake_db)
    created = client.post("/api/documents", json=document_payload)
    assert created.status_code == 201
    assert created.json["id"] == 17
    assert created.json["received_date"] == "2026-11-21"
    assert "%s" in fake.query
    listed = client.get("/api/documents")
    assert listed.status_code == 200
    assert listed.json[0]["registration_number"] == "ВХ-2026/011"


def test_delete_missing_returns_404(client, monkeypatch):
    class FakeCursor:
        def execute(self, query, params):
            pass
        def fetchone(self):
            return None

    @contextmanager
    def fake_db(write=False):
        yield FakeCursor()

    monkeypatch.setattr(application, "db_cursor", fake_db)
    result = client.delete("/api/documents/9999")
    assert result.status_code == 404
    assert result.json["error"] == "Документ не знайдено."
