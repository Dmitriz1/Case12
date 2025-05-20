"""
Основной HTTP-сервер для учёта трат.

Сервер реализован на чистом `http.server.BaseHTTPRequestHandler`
и хранит данные в MongoDB. Поддерживаются операции CRUD и простая
агрегация статистики.
"""

import json
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import bson
from bson import ObjectId
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError

from .config import LOGIN, MONGODB_COLLECTION, MONGODB_DB, PASSWORD

BASE_DIR = Path(__file__).parent


class Handler(BaseHTTPRequestHandler):
    """RESTful HTTP-сервер для учёта трат.

    Ресурсы:
        /expenses
        /expenses/{id}
        /categories?month={MM}
        /categories/top?month={MM}
        /categories/{category}/expenses?month={MM}[&biggest=true]
    """

    mongo_client = MongoClient(
        f"mongodb+srv://{LOGIN}:{PASSWORD}@cluster0.bxpsiw0.mongodb.net/"
        "?retryWrites=true&w=majority&appName=Cluster0"
    )
    db = mongo_client[MONGODB_DB]
    expenses = db[MONGODB_COLLECTION]

    def _send_json(self, data, status=HTTPStatus.OK):
        """Отправляет JSON-ответ клиенту.

        Args:
            data (Any): Python-объект, который будет сериализован в JSON.
            status (HTTPStatus): HTTP-статус ответа (по умолчанию 200 OK).
        """
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            json.dumps(
                data,
                default=bson.json_util.default,
                ensure_ascii=False,
            ).encode()
        )

    def _parse_month(self, date_str):
        """Извлекает номер месяца из строки даты.

        Args:
            date_str (str): Дата в формате 'YYYY-MM-DD'.

        Returns:
            str: Двухзначный номер месяца, например '05'.
        """
        return date_str.split("-")[1]

    # ---------- CRUD для /expenses ----------------------------------

    def get_all_expenses(self):
        """GET /expenses — возвращает все траты.

        Raises:
            ServerSelectionTimeoutError: Если не удалось подключиться к MongoDB.
        """
        try:
            docs = list(self.expenses.find())
            self._send_json(docs)
        except ServerSelectionTimeoutError:
            self.send_error(HTTPStatus.GATEWAY_TIMEOUT)

    def get_single_expense(self, exp_id):
        """GET /expenses/{id} — возвращает одну трату.

        Args:
            exp_id (str): Строковое представление ObjectId документа.

        Raises:
            HTTPStatus.BAD_REQUEST: Некорректный формат ID.
            HTTPStatus.NOT_FOUND: Документ с таким ID не найден.
            ServerSelectionTimeoutError: Ошибка подключения к MongoDB.
        """
        try:
            doc = self.expenses.find_one({"_id": ObjectId(exp_id)})
            if not doc:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            self._send_json(doc)
        except bson.errors.InvalidId:
            self.send_error(HTTPStatus.BAD_REQUEST)
        except ServerSelectionTimeoutError:
            self.send_error(HTTPStatus.GATEWAY_TIMEOUT)

    def create_expense(self):
        """POST /expenses — создаёт новую трату.

        Читает form-data из тела запроса:
            expense_name, category, amount, date

        Raises:
            ServerSelectionTimeoutError: Ошибка подключения к MongoDB.
        """
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode()
        data = urllib.parse.parse_qs(body)
        new = {
            "expense_name": data.get("expense_name", [""])[0],
            "category": data.get("category", [""])[0],
            "amount": data.get("amount", [""])[0],
            "date": data.get("date", [""])[0],
        }
        try:
            result = self.expenses.insert_one(new)
            self.send_response(HTTPStatus.CREATED)
            self.send_header("Location", f"/expenses/{result.inserted_id}")
            self.end_headers()
        except ServerSelectionTimeoutError:
            self.send_error(HTTPStatus.GATEWAY_TIMEOUT)

    def update_expense(self, exp_id):
        """PUT /expenses/{id} — обновляет существующую трату.

        Args:
            exp_id (str): Строковое представление ObjectId документа.

        Body (JSON):
            Любые поля для обновления: expense_name, category, amount, date.

        Raises:
            HTTPStatus.BAD_REQUEST: Некорректный JSON или ID.
            HTTPStatus.NOT_FOUND: Документ для обновления не найден.
            ServerSelectionTimeoutError: Ошибка подключения к MongoDB.
        """
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = self.rfile.read(length).decode()
            update = json.loads(payload)
            result = self.expenses.update_one(
                {"_id": ObjectId(exp_id)},
                {"$set": update},
            )
            if result.matched_count:
                self.send_response(HTTPStatus.OK)
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except ValueError:
            self.send_error(HTTPStatus.BAD_REQUEST)
        except bson.errors.InvalidId:
            self.send_error(HTTPStatus.BAD_REQUEST)
        except ServerSelectionTimeoutError:
            self.send_error(HTTPStatus.GATEWAY_TIMEOUT)
        finally:
            self.end_headers()

    def delete_expense(self, exp_id):
        """DELETE /expenses/{id} — удаляет трату.

        Args:
            exp_id (str): Строковое представление ObjectId документа.

        Raises:
            HTTPStatus.BAD_REQUEST: Некорректный ID.
            HTTPStatus.NOT_FOUND: Документ не найден.
            ServerSelectionTimeoutError: Ошибка подключения к MongoDB.
        """
        try:
            result = self.expenses.delete_one({"_id": ObjectId(exp_id)})
            if result.deleted_count:
                self.send_response(HTTPStatus.NO_CONTENT)
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except bson.errors.InvalidId:
            self.send_error(HTTPStatus.BAD_REQUEST)
        except ServerSelectionTimeoutError:
            self.send_error(HTTPStatus.GATEWAY_TIMEOUT)
        finally:
            self.end_headers()

    # ---------- Статистика по категориям ----------------------------

    def get_categories_by_month(self, params):
        """GET /categories?month={MM} — список категорий за указанный месяц.

        Args:
            params (dict): Параметры запроса, ключ 'month' обязателен.

        Raises:
            HTTPStatus.BAD_REQUEST: Если параметр month отсутствует.
            ServerSelectionTimeoutError: Ошибка подключения к MongoDB.
        """
        month = params.get("month", [None])[0]
        if not month:
            self.send_error(HTTPStatus.BAD_REQUEST)
            return
        try:
            cats = {
                exp["category"]
                for exp in self.expenses.find()
                if self._parse_month(exp["date"]) == month
            }
            self._send_json(list(cats))
        except ServerSelectionTimeoutError:
            self.send_error(HTTPStatus.GATEWAY_TIMEOUT)

    def get_top_category(self, params):
        """GET /categories/top?month={MM} — самая затратная категория месяца.

        Args:
            params (dict): Параметры запроса, ключ 'month' обязателен.

        Raises:
            HTTPStatus.BAD_REQUEST: Если параметр month отсутствует.
            ServerSelectionTimeoutError: Ошибка подключения к MongoDB.
        """
        month = params.get("month", [None])[0]
        if not month:
            self.send_error(HTTPStatus.BAD_REQUEST)
            return
        try:
            month_exp = [
                e for e in self.expenses.find() if self._parse_month(e["date"]) == month
            ]
            if not month_exp:
                self.send_response(HTTPStatus.NO_CONTENT)
                self.end_headers()
                return

            totals = {}
            for e in month_exp:
                cat = e["category"]
                totals[cat] = totals.get(cat, 0) + int(e["amount"])
            top_cat = max(totals, key=totals.get)
            total_amount = totals[top_cat]

            max_in_cat = max(
                (e for e in month_exp if e["category"] == top_cat),
                key=lambda x: int(x["amount"]),
            )

            resp = {
                "category": top_cat,
                "total_amount": total_amount,
                "expense_name": max_in_cat["expense_name"],
                "amount": int(max_in_cat["amount"]),
                "date": max_in_cat["date"],
            }
            self._send_json(resp)
        except ServerSelectionTimeoutError:
            self.send_error(HTTPStatus.GATEWAY_TIMEOUT)

    def get_expenses_by_category(self, category, params):
        """GET /categories/{category}/expenses?month={MM}[&biggest=true].

        Args:
            category (str): Название категории (URL-decoded).
            params (dict): Параметры запроса, 'month' обязателен,
                'biggest' опционален.

        Raises:
            HTTPStatus.BAD_REQUEST: Если параметр month отсутствует.
            ServerSelectionTimeoutError: Ошибка подключения к MongoDB.
        """
        month = params.get("month", [None])[0]
        if not month:
            self.send_error(HTTPStatus.BAD_REQUEST)
            return
        try:
            filtered = [
                e
                for e in self.expenses.find()
                if self._parse_month(e["date"]) == month and e["category"] == category
            ]
            if not filtered:
                self.send_response(HTTPStatus.NO_CONTENT)
                self.end_headers()
                return

            biggest = params.get("biggest", ["false"])[0].lower() in ("1", "true")
            if biggest:
                largest = max(filtered, key=lambda x: int(x["amount"]))
                result = {
                    "expense_name": largest["expense_name"],
                    "amount": int(largest["amount"]),
                    "date": largest["date"],
                }
                self._send_json(result)
            else:
                self._send_json(filtered)
        except ServerSelectionTimeoutError:
            self.send_error(HTTPStatus.GATEWAY_TIMEOUT)

    # ---------- HTTP-маршрутизация ------------------------------------

    def do_GET(self):
        """Маршрутизирует HTTP GET-запросы к соответствующим методам."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        if path == "/":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            with (BASE_DIR / "index.html").open("rb") as f:
                self.wfile.write(f.read())
            return

        if path.startswith("/static/"):
            content_type = "application/octet-stream"
            if path.endswith(".css"):
                content_type = "text/css; charset=utf-8"
            elif path.endswith(".js"):
                content_type = "application/javascript; charset=utf-8"
            elif path.endswith(".png"):
                content_type = "image/png"
            try:
                with (BASE_DIR / path.lstrip("/")).open("rb") as f:
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", content_type)
                    self.end_headers()
                    self.wfile.write(f.read())
            except FileNotFoundError:
                self.send_error(HTTPStatus.NOT_FOUND)
            return

        if path == "/expenses":
            return self.get_all_expenses()
        if path.startswith("/expenses/"):
            exp_id = path.split("/")[2]
            return self.get_single_expense(exp_id)

        if path == "/categories":
            return self.get_categories_by_month(params)
        if path == "/categories/top":
            return self.get_top_category(params)
        if path.startswith("/categories/") and path.endswith("/expenses"):
            raw_cat = path.split("/")[2]
            category = urllib.parse.unquote(raw_cat)
            return self.get_expenses_by_category(category, params)

        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self):
        """Маршрутизирует HTTP POST-запросы к соответствующим методам."""
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/expenses":
            return self.create_expense()
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_PUT(self):
        """Маршрутизирует HTTP PUT-запросы к соответствующим методам."""
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith("/expenses/"):
            exp_id = parsed.path.split("/")[2]
            return self.update_expense(exp_id)
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_DELETE(self):
        """Маршрутизирует HTTP DELETE-запросы к соответствующим методам."""
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith("/expenses/"):
            exp_id = parsed.path.split("/")[2]
            return self.delete_expense(exp_id)
        self.send_error(HTTPStatus.NOT_FOUND)


def run(server_class=HTTPServer, handler_class=Handler):
    """Запускает HTTP-сервер на `localhost:8000`."""
    server_address = ("", 8000)
    httpd = server_class(server_address, handler_class)
    print("Сервер запущен на http://localhost:8000")
    httpd.serve_forever()


if __name__ == "__main__":
    run()
