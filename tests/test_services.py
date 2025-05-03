from __future__ import annotations

import json
import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch, ANY

from bson import ObjectId
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError

from app.config import LOGIN, PASSWORD
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
        cls.mongo = MongoClient(
            f"mongodb+srv://{LOGIN}:{PASSWORD}@cluster0.bxpsiw0.mongodb.net/"
            "?retryWrites=true&w=majority&appName=Cluster0"
        )
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
        self.col.delete_many({})
        self.col.insert_many(self.fixtures)

        self.h = _make_handler()
        self.h.expenses = self.col

    # ---------- бизнес-логика ------------------------------------------------
    def test_get_most_expensive_spending(self):
        self.h.get_most_expensive_spending({"month": ["07"]}, {"category": ["Food"]})
        self.h.send_response.assert_called_with(200)

        data = json.loads(self.h.wfile.write.call_args[0][0].decode())
        self.assertEqual(data["name"], "Restaurant")
        self.assertEqual(data["amount"], 100)

        self.h.get_most_expensive_spending({"month": ["09"]}, {"category": ["Food"]})
        self.h.send_response.assert_called_with(204)

    def test_get_most_expensive_category(self):
        self.h.get_most_expensive_category({"month": ["07"]})
        self.h.send_response.assert_called_with(200)

        data = json.loads(self.h.wfile.write.call_args[0][0].decode())
        self.assertEqual(data["category"], "Food")
        self.assertEqual(data["total_amount"], 150)

    def test_get_categories_by_month(self):
        self.h.get_categories_by_month({"month": ["08"]})
        cats = set(json.loads(self.h.wfile.write.call_args[0][0].decode()))
        self.assertEqual(cats, {"Transportation", "Entertainment"})

    def test_get_all_expenses(self):
        self.h.get_all_expenses()
        docs = json.loads(self.h.wfile.write.call_args[0][0].decode())
        self.assertEqual(len(docs), len(self.fixtures))

    # ---------- таймаут MongoDB ---------------------------------------------
    @patch("app.main.MongoClient")
    def test_server_selection_timeout_error(self, _):
        broken = _make_handler()
        broken.expenses = MagicMock()
        for m in ("find", "insert_one", "delete_one", "update_one"):
            getattr(broken.expenses, m).side_effect = ServerSelectionTimeoutError()

        scenarios = [
            (broken.get_most_expensive_spending, ({"month": ["07"]}, {"category": ["Food"]})),
            (broken.get_most_expensive_category, ({"month": ["07"]},)),
            (broken.get_categories_by_month, ({"month": ["07"]},)),
            (broken.get_all_expenses, ()),
        ]
        for fn, args in scenarios:
            fn(*args)
            # send_response может быть вызвано как (524) так и (524, <msg>)
            self.assertEqual(broken.send_response.call_args[0][0], 524)

    # ---------- маршруты -----------------------------------------------------
    def _call_path(self, url: str):
        self.h.path = url
        self.h.do_GET()

    @patch("app.main.open", create=True)
    def test_do_GET_root(self, mopen):
        mfile = MagicMock()
        mfile.read.return_value = b"<html></html>"
        mopen.return_value = mfile
        self._call_path("/")
        self.h.send_response.assert_called_with(200)

    def test_do_GET_stats_paths(self):
        for url in (
                "/stats/most-expensive-category?month=07",
                "/stats/biggest-expense?month=07&category=Food",
                "/stats/categories-by-month?month=07",
                "/expenses",
        ):
            self._call_path(url)
            self.h.send_response.assert_called_with(200)

    # ---------- статика ------------------------------------------------------
    @patch("app.main.open", create=True)
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

    @patch("app.main.open", side_effect=FileNotFoundError)
    def test_static_not_found(self, _mopen):
        self._call_path("/static/css/no.css")
        self.h.send_error.assert_called_with(404, "Файл не найден")

    # ---------- POST ---------------------------------------------------------
    def test_do_POST(self):
        self.h.path = "/"
        self.h.headers = {"Content-Length": "70"}
        self.h.rfile = MagicMock()
        self.h.rfile.read.return_value = (
            b"expense_name=X&category=Y&amount=100&date=2024-01-01"
        )
        self.h.do_POST()
        self.h.send_response.assert_called_with(303)
        self.h.send_header.assert_called_with("Location", "/")

    def test_do_PUT_ok(self):
        # создаём запись и запоминаем её _id
        doc_id = str(self.col.insert_one({
            "expense_name": "Old",
            "category": "X",
            "amount": "10",
            "date": "2024-01-01"
        }).inserted_id)

        self.h.path = f"/expenses/{doc_id}"
        self.h.headers = {"Content-Length": "37"}
        self.h.rfile = MagicMock()
        self.h.rfile.read.return_value = b'{"amount": "20"}'  # валидное JSON
        self.h.do_PUT()

        self.h.send_response.assert_called_with(200)
        assert self.col.find_one({"_id": ObjectId(doc_id)})["amount"] == "20"

    def test_do_PUT_bad_json(self):
        self.h.path = "/expenses/64537fff0000000000000000"
        self.h.headers = {"Content-Length": "13"}
        self.h.rfile = MagicMock()
        self.h.rfile.read.return_value = b'not-a-json'
        self.h.do_PUT()
        self.h.send_error.assert_called_with(400, "Некорректный JSON")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
