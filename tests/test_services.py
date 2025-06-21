from __future__ import annotations

import json
import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import mongomock
from bson import ObjectId
from pymongo.errors import ServerSelectionTimeoutError
from http import HTTPStatus

from app.main import Handler
import io


# ---------- утилиты ----------------------------------------------------------
@contextmanager
def _silent_handle(cls):
    """Контекстный менеджер: временно отключает BaseHTTPRequestHandler.handle во время __init__()."""
    original = cls.handle
    cls.handle = lambda self: None
    try:
        yield
    finally:
        cls.handle = original


def _make_handler() -> Handler:
    """Создаёт Handler с подменёнными сетевыми методами для юнит-тестов."""
    with _silent_handle(Handler):
        h = Handler(MagicMock(), MagicMock(), MagicMock())
    h.command = "GET"
    h.requestline = ""
    h.log_message = MagicMock()
    h.log_error = MagicMock()
    h.send_response = MagicMock()
    h.send_header = MagicMock()
    h.end_headers = MagicMock()
    h.send_error = MagicMock()
    h.wfile = MagicMock()
    h.wfile.write = MagicMock()
    return h


# ---------- тесты ------------------------------------------------------------
class TestServices(unittest.TestCase):
    """Набор unit-тестов для CRUD, маршрутизации и бизнес-логики сервера учёта трат."""

    @classmethod
    def setUpClass(cls):
        """Создаёт фикстуры и тестовую коллекцию MongoDB (mongomock)."""
        cls.mongo = mongomock.MongoClient()
        cls.db = cls.mongo["test_db"]
        cls.col = cls.db["test_collection"]
        cls.fixtures = [
            {"expense_name": "Grocery", "category": "Food", "amount": "50", "date": "2024-07-01"},
            {"expense_name": "Restaurant", "category": "Food", "amount": "100", "date": "2024-07-15"},
            {"expense_name": "Train ticket", "category": "Transportation", "amount": "30", "date": "2024-07-20"},
            {"expense_name": "Gas", "category": "Transportation", "amount": "70", "date": "2024-08-10"},
            {"expense_name": "Concert", "category": "Entertainment", "amount": "120", "date": "2024-08-25"},
            {"expense_name": "Book", "category": "Entertainment", "amount": "40", "date": "2024-08-05"},
        ]

    def setUp(self):
        """Очищает коллекцию и наполняет её тестовыми данными перед каждым тестом."""
        self.col.delete_many({})
        self.col.insert_many(self.fixtures)
        self.h = _make_handler()
        self.h.expenses = self.col

    # ---------- бизнес-логика ------------------------------------------------

    def test_get_expenses_by_category_biggest(self):
        """Проверяет возврат самой крупной траты в категории и отсутствие данных по месяцу."""
        self.h.get_expenses_by_category(
            "Food", {"month": ["07"], "biggest": ["true"]}
        )
        self.h.send_response.assert_called_with(HTTPStatus.OK)
        raw = self.h.wfile.write.call_args[0][0]
        data = json.loads(raw.decode())
        self.assertEqual(data["expense_name"], "Restaurant")
        self.assertEqual(data["amount"], 100)
        self.h.send_response.reset_mock()
        self.h.wfile.write.reset_mock()
        self.h.get_expenses_by_category(
            "Food", {"month": ["09"], "biggest": ["true"]}
        )
        self.h.send_response.assert_called_with(HTTPStatus.NO_CONTENT)

    def test_get_top_category(self):
        """Проверяет возврат самой затратной категории за месяц."""
        self.h.get_top_category({"month": ["07"]})
        self.h.send_response.assert_called_with(HTTPStatus.OK)
        raw = self.h.wfile.write.call_args[0][0]
        data = json.loads(raw.decode())
        self.assertEqual(data["category"], "Food")
        self.assertEqual(data["total_amount"], 150)

    def test_get_categories_by_month(self):
        """Проверяет возврат всех уникальных категорий за месяц."""
        self.h.get_categories_by_month({"month": ["08"]})
        self.h.send_response.assert_called_with(HTTPStatus.OK)
        raw = self.h.wfile.write.call_args[0][0]
        cats = set(json.loads(raw.decode()))
        self.assertEqual(cats, {"Transportation", "Entertainment"})

    def test_get_all_expenses(self):
        """Проверяет возврат всех трат."""
        self.h.get_all_expenses()
        self.h.send_response.assert_called_with(HTTPStatus.OK)
        raw = self.h.wfile.write.call_args[0][0]
        docs = json.loads(raw.decode())
        self.assertEqual(len(docs), len(self.fixtures))

    # ---------- таймаут MongoDB ---------------------------------------------
    @patch("app.main.MongoClient")
    def test_server_selection_timeout_error(self, _):
        """Проверяет обработку ошибок подключения к MongoDB (таймаут)."""
        broken = _make_handler()
        broken.expenses = MagicMock()
        for m in ("find", "find_one", "insert_one", "delete_one", "update_one"):
            getattr(broken.expenses, m).side_effect = ServerSelectionTimeoutError()
        broken.get_all_expenses()
        broken.get_categories_by_month({"month": ["01"]})
        broken.get_top_category({"month": ["01"]})
        broken.get_expenses_by_category("Food", {"month": ["01"], "biggest": ["true"]})
        last = broken.send_error.call_args[0][0] if broken.send_error.called else \
            broken.send_response.call_args[0][0]
        self.assertEqual(last, HTTPStatus.GATEWAY_TIMEOUT)

    # ---------- маршруты -----------------------------------------------------
    def _call_path(self, url: str):
        """Вспомогательный метод для вызова self.h.do_GET() с нужным url."""
        self.h.path = url
        self.h.do_GET()

    @patch("app.main.Path.open", create=True)
    def test_do_GET_root(self, mopen):
        """Проверяет возврат главной страницы (index.html)."""
        mfile = MagicMock()
        mfile.read.return_value = b"<html></html>"
        mopen.return_value = mfile
        self._call_path("/")
        self.h.send_response.assert_called_with(HTTPStatus.OK)

    def test_do_GET_restful_paths(self):
        """Проверяет возврат успешных ответов для основных RESTful путей."""
        for url in (
                "/categories/top?month=07",
                "/categories?month=07",
                "/categories/Food/expenses?month=07&biggest=true",
                "/expenses",
        ):
            self._call_path(url)
            self.h.send_response.assert_called_with(HTTPStatus.OK)

    # ---------- статика ------------------------------------------------------
    @patch("app.main.Path.open", create=True)
    def test_static_ok(self, mopen):
        """Проверяет корректную отдачу статических файлов и Content-Type."""
        mfile = MagicMock()
        mfile.read.return_value = b"dummy"
        mopen.return_value = mfile
        mapping = (
            ("/static/css/x.css", "text/css; charset=utf-8"),
            ("/static/img/x.png", "image/png"),
            ("/static/js/x.js", "application/javascript; charset=utf-8"),
        )
        for url, ctype in mapping:
            self._call_path(url)
            self.h.send_header.assert_called_with("Content-Type", ctype)

    @patch("app.main.Path.open", side_effect=FileNotFoundError)
    def test_static_not_found(self, _mopen):
        self._call_path("/static/css/no.css")
        self.h.send_error.assert_called_with(HTTPStatus.NOT_FOUND)

    # ---------- POST ---------------------------------------------------------
    def test_do_POST(self):
        # Создаём новую трату через POST /expenses
        doc = {
            "expense_name": "Test",
            "category": "Food",
            "amount": "100",
            "date": "2024-01-01",
        }
        body = "&".join(f"{k}={v}" for k, v in doc.items()).encode()
        self.h.path = "/expenses"
        self.h.headers = {"Content-Length": str(len(body))}
        self.h.rfile = MagicMock()
        self.h.rfile.read.return_value = body
        self.h.do_POST()
        self.h.send_response.assert_called_with(HTTPStatus.CREATED)

    def test_do_POST_invalid_data(self):
        # Тут специально ломаем разные поля, чтобы убедиться, что сервер не пропустит мусор
        self.h.path = "/expenses"
        self.h.headers = {"Content-Length": "100"}
        self.h.rfile = MagicMock()
        # amount не число
        self.h.rfile.read.return_value = (
            b"expense_name=Test&category=Food&amount=abc&date=2024-01-01"
        )
        self.h.do_POST()
        self.h.send_error.assert_called_with(HTTPStatus.BAD_REQUEST)
        # Пустое название
        self.h.rfile.read.return_value = (
            b"expense_name=&category=Food&amount=100&date=2024-01-01"
        )
        self.h.do_POST()
        self.h.send_error.assert_called_with(HTTPStatus.BAD_REQUEST)
        # Кривая дата
        self.h.rfile.read.return_value = (
            b"expense_name=Test&category=Food&amount=100&date=invalid"
        )
        self.h.do_POST()
        self.h.send_error.assert_called_with(HTTPStatus.BAD_REQUEST)

    # ---------- PUT ----------------------------------------------------------
    def test_do_PUT_ok(self):
        doc_id = str(self.col.insert_one({
            "expense_name": "Old",
            "category": "Food",
            "amount": "10",
            "date": "2024-01-01"
        }).inserted_id)
        self.h.path = f"/expenses/{doc_id}"
        update_data = {
            "expense_name": "Updated Expense",
            "category": "Food",
            "amount": "20",
            "date": "2024-01-01"
        }
        body = json.dumps(update_data).encode("utf-8")
        self.h.headers = {"Content-Length": str(len(body))}
        self.h.rfile = MagicMock()
        self.h.rfile.read.return_value = body
        self.h.do_PUT()
        self.h.send_response.assert_called_with(HTTPStatus.OK)
        updated = self.col.find_one({"_id": ObjectId(doc_id)})
        self.assertEqual(updated["expense_name"], "Updated Expense")
        self.assertEqual(updated["category"], "Food")
        self.assertEqual(updated["amount"], "20")
        self.assertEqual(updated["date"], "2024-01-01")

    def test_do_PUT_bad_json(self):
        self.h.path = "/expenses/64537fff0000000000000000"
        self.h.headers = {"Content-Length": "13"}
        self.h.rfile = MagicMock()
        self.h.rfile.read.return_value = b'not-a-json'
        self.h.do_PUT()
        self.h.send_error.assert_called_with(HTTPStatus.BAD_REQUEST)

    # ---------- DELETE ---------------------------------------------------------
    def test_do_DELETE(self):
        # Проверяем, что реально удаляется
        doc = {
            "expense_name": "To Delete",
            "category": "Misc",
            "amount": "10",
            "date": "2024-09-01",
        }
        inserted_id = str(self.col.insert_one(doc).inserted_id)
        self.assertIsNotNone(self.col.find_one({"_id": ObjectId(inserted_id)}))
        self.h.path = f"/expenses/{inserted_id}"
        self.h.do_DELETE()
        self.h.send_response.assert_called_with(HTTPStatus.NO_CONTENT)
        self.assertIsNone(self.col.find_one({"_id": ObjectId(inserted_id)}))

    # ---------- редактирование --------------------------------------------------------
    def test_update_expense_invalid_date(self):
        # Дата — не дата
        expense = self.col.find_one()
        update_data = {
            "expense_name": "Updated",
            "category": "Food",
            "amount": "50",
            "date": "abcd",
        }
        body = json.dumps(update_data).encode("utf-8")
        self.h.rfile = io.BytesIO(body)
        self.h.headers = {"Content-Length": str(len(body))}
        self.h.update_expense(str(expense["_id"]))
        self.h.send_error.assert_called_with(HTTPStatus.BAD_REQUEST)
        # Проверяем, что ничего не поменялось
        new = self.col.find_one({"_id": expense["_id"]})
        self.assertEqual(new["expense_name"], expense["expense_name"])
        self.assertEqual(new["category"], expense["category"])
        self.assertEqual(new["amount"], expense["amount"])
        self.assertEqual(new["date"], expense["date"])

    def test_update_expense_invalid_amount(self):
        # Сумма — не число
        expense = self.col.find_one()
        update_data = {
            "expense_name": "Updated",
            "category": "Food",
            "amount": "abc",
            "date": "2024-01-01",
        }
        body = json.dumps(update_data).encode("utf-8")
        self.h.rfile = io.BytesIO(body)
        self.h.headers = {"Content-Length": str(len(body))}
        self.h.update_expense(str(expense["_id"]))
        self.h.send_error.assert_called_with(HTTPStatus.BAD_REQUEST)
        new = self.col.find_one({"_id": expense["_id"]})
        self.assertEqual(new["expense_name"], expense["expense_name"])
        self.assertEqual(new["category"], expense["category"])
        self.assertEqual(new["amount"], expense["amount"])
        self.assertEqual(new["date"], expense["date"])

    def test_update_expense_empty_fields(self):
        # Пустые строки в обязательных полях
        expense = self.col.find_one()
        update_data = {
            "expense_name": "",
            "category": "",
            "amount": "100",
            "date": "2024-01-01",
        }
        body = json.dumps(update_data).encode("utf-8")
        self.h.rfile = io.BytesIO(body)
        self.h.headers = {"Content-Length": str(len(body))}
        self.h.update_expense(str(expense["_id"]))
        self.h.send_error.assert_called_with(HTTPStatus.BAD_REQUEST)
        new = self.col.find_one({"_id": expense["_id"]})
        self.assertEqual(new["expense_name"], expense["expense_name"])
        self.assertEqual(new["category"], expense["category"])
        self.assertEqual(new["amount"], expense["amount"])
        self.assertEqual(new["date"], expense["date"])

    def test_do_PUT_valid(self):
        # Обычное обновление — всё должно пройти
        expense = {
            "expense_name": "Original Expense",
            "category": "Original Category",
            "amount": "100",
            "date": "2024-01-01",
        }
        expense_id = str(self.col.insert_one(expense).inserted_id)
        updated_data = {
            "expense_name": "Updated Expense",
            "category": "Updated Category",
            "amount": "200",
            "date": "2024-09-15",
        }
        body = json.dumps(updated_data).encode("utf-8")
        self.h.path = f"/expenses/{expense_id}"
        self.h.headers = {'Content-Length': str(len(body))}
        self.h.rfile = MagicMock()
        self.h.rfile.read.return_value = body
        self.h.do_PUT()
        self.h.send_response.assert_called_with(HTTPStatus.OK)
        updated = self.col.find_one({"_id": ObjectId(expense_id)})
        self.assertEqual(updated["expense_name"], "Updated Expense")
        self.assertEqual(updated["amount"], "200")

    def test_get_single_expense(self):
        expense = self.col.find_one()
        self.h.get_single_expense(str(expense["_id"]))
        self.h.send_response.assert_called_with(HTTPStatus.OK)
        raw = self.h.wfile.write.call_args[0][0]
        data = json.loads(raw.decode())
        self.assertEqual(data["expense_name"], expense["expense_name"])
        self.assertEqual(data["category"], expense["category"])
        self.assertEqual(data["amount"], expense["amount"])
        self.assertEqual(data["date"], expense["date"])
        # Не найден
        self.h.get_single_expense(str(ObjectId()))
        self.h.send_error.assert_called_with(HTTPStatus.NOT_FOUND)
        # Кривой ID
        self.h.get_single_expense("invalid-id")
        self.h.send_error.assert_called_with(HTTPStatus.BAD_REQUEST)

    def test_do_GET_single_expense(self):
        expense = self.col.find_one()
        self.h.path = f"/expenses/{str(expense['_id'])}"
        self.h.do_GET()
        self.h.send_response.assert_called_with(HTTPStatus.OK)
        raw = self.h.wfile.write.call_args[0][0]
        data = json.loads(raw.decode())
        self.assertEqual(data["expense_name"], expense["expense_name"])

    def test_mongodb_errors(self):
        # Здесь эмулируем падение монги на всех операциях
        error_collection = MagicMock()
        error_collection.find_one.side_effect = ServerSelectionTimeoutError()
        error_collection.update_one.side_effect = ServerSelectionTimeoutError()
        error_collection.delete_one.side_effect = ServerSelectionTimeoutError()
        self.h.expenses = error_collection
        self.h.get_single_expense("507f1f77bcf86cd799439011")
        self.h.send_error.assert_called_with(HTTPStatus.GATEWAY_TIMEOUT)
        update_data = {
            "expense_name": "Test",
            "category": "Food",
            "amount": "100",
            "date": "2024-01-01"
        }
        body = json.dumps(update_data).encode("utf-8")
        self.h.rfile = io.BytesIO(body)
        self.h.headers = {"Content-Length": str(len(body))}
        self.h.update_expense("507f1f77bcf86cd799439011")
        self.h.send_error.assert_called_with(HTTPStatus.GATEWAY_TIMEOUT)

    def test_invalid_expense_id(self):
        # Кривой ID при обновлении
        update_data = {
            "expense_name": "Test",
            "category": "Food",
            "amount": "100",
            "date": "2024-01-01"
        }
        body = json.dumps(update_data).encode("utf-8")
        self.h.rfile = io.BytesIO(body)
        self.h.headers = {"Content-Length": str(len(body))}
        self.h.update_expense("invalid-id")
        self.h.send_error.assert_called_with(HTTPStatus.BAD_REQUEST)

    def test_categories_by_month_no_param(self):
        self.h.get_categories_by_month({})
        self.h.send_error.assert_called_with(HTTPStatus.BAD_REQUEST)

    def test_top_category_no_param(self):
        self.h.get_top_category({})
        self.h.send_error.assert_called_with(HTTPStatus.BAD_REQUEST)

    def test_top_category_empty_month(self):
        self.h.get_top_category({"month": ["99"]})
        self.h.send_response.assert_called_with(HTTPStatus.NO_CONTENT)

    def test_expenses_by_category_no_param(self):
        self.h.get_expenses_by_category("Food", {})
        self.h.send_error.assert_called_with(HTTPStatus.BAD_REQUEST)

    def test_expenses_by_category_empty_month(self):
        self.h.get_expenses_by_category("Food", {"month": ["99"]})
        self.h.send_response.assert_called_with(HTTPStatus.NO_CONTENT)

    def test_routing_not_found(self):
        # Проверяем, что сервер честно шлёт 404 на любые несуществующие пути
        for method in ["GET", "POST", "PUT", "DELETE"]:
            self.h.path = "/nonexistent"
            if method == "GET":
                self.h.do_GET()
            elif method == "POST":
                self.h.do_POST()
            elif method == "PUT":
                self.h.do_PUT()
            else:
                self.h.do_DELETE()
            self.h.send_error.assert_called_with(HTTPStatus.NOT_FOUND)

    def test_static_content_types(self):
        # Проверяем, что сервер правильно определяет Content-Type для разных файлов
        test_files = [
            ("/static/unknown.txt", "application/octet-stream"),
            ("/static/test.js", "application/javascript; charset=utf-8"),
            ("/static/test.css", "text/css; charset=utf-8"),
            ("/static/test.png", "image/png"),
        ]
        for path, content_type in test_files:
            with patch("app.main.Path.open", create=True) as mopen:
                mfile = MagicMock()
                mfile.read.return_value = b"test content"
                mopen.return_value = mfile
                self.h.path = path
                self.h.do_GET()
                self.h.send_response.assert_called_with(HTTPStatus.OK)
                self.h.send_header.assert_any_call("Content-Type", content_type)

    def test_create_expense_errors(self):
        self.h.path = "/expenses"
        self.h.headers = {"Content-Length": "0"}
        self.h.rfile = MagicMock()
        # Пустой запрос
        self.h.rfile.read.return_value = b""
        self.h.create_expense()
        self.h.send_error.assert_called_with(HTTPStatus.BAD_REQUEST)
        # Слишком большая сумма
        self.h.rfile.read.return_value = (
            b"expense_name=Test&category=Food&amount=12345678&date=2024-01-01"
        )
        self.h.create_expense()
        self.h.send_error.assert_called_with(HTTPStatus.BAD_REQUEST)
        # Кривая дата
        self.h.rfile.read.return_value = (
            b"expense_name=Test&category=Food&amount=100&date=2024-13-01"
        )
        self.h.create_expense()
        self.h.send_error.assert_called_with(HTTPStatus.BAD_REQUEST)

    def test_update_expense_errors(self):
        expense = self.col.find_one()
        self.h.path = f"/expenses/{str(expense['_id'])}"
        self.h.headers = {"Content-Length": "0"}
        self.h.rfile = MagicMock()
        # Пустой запрос
        self.h.rfile.read.return_value = b""
        self.h.update_expense(str(expense["_id"]))
        self.h.send_error.assert_called_with(HTTPStatus.BAD_REQUEST)
        # Слишком большая сумма
        update_data = {
            "expense_name": "Test",
            "category": "Food",
            "amount": "12345678",
            "date": "2024-01-01"
        }
        self.h.rfile.read.return_value = json.dumps(update_data).encode("utf-8")
        self.h.update_expense(str(expense["_id"]))
        self.h.send_error.assert_called_with(HTTPStatus.BAD_REQUEST)
        # Кривая дата
        update_data["amount"] = "100"
        update_data["date"] = "2024-13-01"
        self.h.rfile.read.return_value = json.dumps(update_data).encode("utf-8")
        self.h.update_expense(str(expense["_id"]))
        self.h.send_error.assert_called_with(HTTPStatus.BAD_REQUEST)

    @patch("http.server.HTTPServer.__init__")
    def test_run_server(self, mock_init):
        # Проверяем, что сервер стартует и не падает на старте
        from app.main import run
        mock_init.return_value = None
        with patch("http.server.HTTPServer.serve_forever") as mock_serve:
            run()
            mock_init.assert_called_once()
            args = mock_init.call_args[0]
            self.assertEqual(args[0], ("", 8000))
            mock_serve.assert_called_once()



if __name__ == "__main__":
    unittest.main()
