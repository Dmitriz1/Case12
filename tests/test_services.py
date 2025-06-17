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


# ---------- утилиты ----------------------------------------------------------
@contextmanager
def _silent_handle(cls):
    """Отключаем BaseHTTPRequestHandler.handle на время __init__()."""
    original = cls.handle
    cls.handle = lambda self: None
    try:
        yield
    finally:
        cls.handle = original


def _make_handler() -> Handler:
    """Handler с подменёнными сетевыми методами, пригодный для юнит-тестов."""
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
    @classmethod
    def setUpClass(cls):
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
        # очистить и заполнить фикстуры
        self.col.delete_many({})
        self.col.insert_many(self.fixtures)

        self.h = _make_handler()
        self.h.expenses = self.col

    # ---------- бизнес-логика ------------------------------------------------

    def test_get_expenses_by_category_biggest(self):
        # самая крупная трата в категории Food за 07
        self.h.get_expenses_by_category(
            "Food", {"month": ["07"], "biggest": ["true"]}
        )
        self.h.send_response.assert_called_with(HTTPStatus.OK)
        raw = self.h.wfile.write.call_args[0][0]
        data = json.loads(raw.decode())
        self.assertEqual(data["expense_name"], "Restaurant")
        self.assertEqual(data["amount"], 100)
        # для месяца без данных
        self.h.send_response.reset_mock()
        self.h.wfile.write.reset_mock()
        self.h.get_expenses_by_category(
            "Food", {"month": ["09"], "biggest": ["true"]}
        )
        self.h.send_response.assert_called_with(HTTPStatus.NO_CONTENT)

    def test_get_top_category(self):
        self.h.get_top_category({"month": ["07"]})
        self.h.send_response.assert_called_with(HTTPStatus.OK)
        raw = self.h.wfile.write.call_args[0][0]
        data = json.loads(raw.decode())
        self.assertEqual(data["category"], "Food")
        self.assertEqual(data["total_amount"], 150)

    def test_get_categories_by_month(self):
        self.h.get_categories_by_month({"month": ["08"]})
        self.h.send_response.assert_called_with(HTTPStatus.OK)
        raw = self.h.wfile.write.call_args[0][0]
        cats = set(json.loads(raw.decode()))
        self.assertEqual(cats, {"Transportation", "Entertainment"})

    def test_get_all_expenses(self):
        self.h.get_all_expenses()
        self.h.send_response.assert_called_with(HTTPStatus.OK)
        raw = self.h.wfile.write.call_args[0][0]
        docs = json.loads(raw.decode())
        self.assertEqual(len(docs), len(self.fixtures))

    # ---------- таймаут MongoDB ---------------------------------------------
    @patch("app.main.MongoClient")
    def test_server_selection_timeout_error(self, _):
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
        self.h.path = url
        self.h.do_GET()

    @patch("app.main.Path.open", create=True)
    def test_do_GET_root(self, mopen):
        mfile = MagicMock()
        mfile.read.return_value = b"<html></html>"
        mopen.return_value = mfile
        self._call_path("/")
        self.h.send_response.assert_called_with(HTTPStatus.OK)

    def test_do_GET_restful_paths(self):
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
        # создаём новую трату через POST /expenses
        self.h.path = "/expenses"
        self.h.headers = {"Content-Length": "70"}
        self.h.rfile = MagicMock()
        self.h.rfile.read.return_value = (
            b"expense_name=X&category=Y&amount=100&date=2024-01-01"
        )
        self.h.do_POST()
        self.h.send_response.assert_called_with(HTTPStatus.CREATED)
        args = self.h.send_header.call_args[0]
        self.assertEqual(args[0], "Location")
        self.assertTrue(str(args[1]).startswith("/expenses/"))

    # ---------- PUT ----------------------------------------------------------
    def test_do_PUT_ok(self):
        doc_id = str(self.col.insert_one({
            "expense_name": "Old",
            "category": "X",
            "amount": "10",
            "date": "2024-01-01"
        }).inserted_id)

        self.h.path = f"/expenses/{doc_id}"
        self.h.headers = {"Content-Length": "37"}
        self.h.rfile = MagicMock()
        self.h.rfile.read.return_value = b'{"amount": "20"}'
        self.h.do_PUT()
        self.h.send_response.assert_called_with(HTTPStatus.OK)
        self.assertEqual(self.col.find_one({"_id": ObjectId(doc_id)})["amount"], "20")

    def test_do_PUT_bad_json(self):
        self.h.path = "/expenses/64537fff0000000000000000"
        self.h.headers = {"Content-Length": "13"}
        self.h.rfile = MagicMock()
        self.h.rfile.read.return_value = b'not-a-json'
        self.h.do_PUT()
        self.h.send_error.assert_called_with(HTTPStatus.BAD_REQUEST)

    # ---------- DELETE ----------------------------------------------------------
    def test_do_DELETE_ok(self):
        handler = _make_handler()
        item = {
            "expense_name": "To delete",
            "category": "Misc",
            "amount": "10",
            "date": "2024-08-01"
        }
        inserted = self.col.insert_one(item)

        handler.path = f"/expenses/{inserted.inserted_id}"
        handler.command = "DELETE"
        handler.expenses = self.col

        Handler.do_DELETE(handler)

        handler.send_response.assert_called_with(HTTPStatus.NO_CONTENT)
        assert self.col.find_one({"_id": inserted.inserted_id}) is None

    def test_do_DELETE_not_found(self):
        handler = _make_handler()
        fake_id = ObjectId()
        handler.path = f"/expenses/{fake_id}"
        handler.command = "DELETE"
        handler.expenses = self.col

        Handler.do_DELETE(handler)

        handler.send_error.assert_called_with(HTTPStatus.NOT_FOUND)
    
    # ---------- GET ----------------------------------------------------------
    def test_do_GET_by_id(self):
        inserted = self.col.insert_one({
            "expense_name": "Taxi", "category": "Transport", "amount": "25", "date": "2024-05-10"
        })

        self.h.path = f"/expenses/{inserted.inserted_id}"
        self.h.command = "GET"
        self.h.expenses = self.col

        Handler.do_GET(self.h)

        self.h.send_response.assert_called_with(HTTPStatus.OK)
        self.h.send_header.assert_any_call("Content-Type", unittest.mock.ANY)
        args = [call[0][1] for call in self.h.send_header.call_args_list if call[0][0] == "Content-Type"]
        self.assertTrue(any(arg.startswith("application/json") for arg in args))
    def test_GET_many_expenses(self):
        items = [{"expense_name": f"Item {i}", "category": "Test", "amount": "1", "date": "2024-01-01"} for i in range(1000)]
        self.col.insert_many(items)

        self.h.path = "/expenses"
        self.h.command = "GET"
        self.h.expenses = self.col

        Handler.do_GET(self.h)
        self.h.send_response.assert_called_with(HTTPStatus.OK)
        self.assertTrue(self.h.wfile.write.called)

    
    # ---------- TIME ----------------------------------------------------------
    def test_response_time_under_limit(self):
        import time
        start = time.time()
        self.h.path = "/expenses"
        self.h.command = "GET"
        self.h.expenses = self.col
        Handler.do_GET(self.h)
        duration = time.time() - start
        self.assertLess(duration, 1.0)  # например, < 1 секунды

if __name__ == "__main__":
    unittest.main()
