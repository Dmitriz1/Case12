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

import bson
from bson import ObjectId
from config import LOGIN, MONGODB_COLLECTION, MONGODB_DB, PASSWORD
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError


class Handler(BaseHTTPRequestHandler):
    """Обработчик HTTP-запросов.

    Атрибуты класса:
        mongo_client (MongoClient): клиент MongoDB.
        db (Database): выбранная БД.
        expenses (Collection): коллекция расходов.
    """

    mongo_client = MongoClient(
        f"mongodb+srv://{LOGIN}:{PASSWORD}@cluster0.bxpsiw0.mongodb.net/"
        "?retryWrites=true&w=majority&appName=Cluster0"
    )
    db = mongo_client[MONGODB_DB]
    expenses = db[MONGODB_COLLECTION]

    # ---------- ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ----------------------------------

    def get_most_expensive_spending(self, month_in_request, category_in_request):
        """Вернёт самую крупную трату в категории за месяц.

        Args:
            month_in_request (dict): query-параметры с ключом `month`.
            category_in_request (dict): query-параметры с ключом `category`.

        Response:
            200 JSON: `{"name": str, "amount": int, "date": str}`
            204: нет данных.
            524: таймаут подключения к БД.
        """
        month = month_in_request["month"][0]
        category = category_in_request["category"][0]

        try:
            matched = [
                exp
                for exp in self.expenses.find()
                if exp["date"].split("-")[1] == month and exp["category"] == category
            ]

            if not matched:
                self.send_response(HTTPStatus.NO_CONTENT)
                self.end_headers()
                return

            max_expense = max(matched, key=lambda x: int(x["amount"]))
            response_data = {
                "name": max_expense["expense_name"],
                "amount": int(max_expense["amount"]),
                "date": max_expense["date"],
            }

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps(response_data, ensure_ascii=False).encode("utf-8")
            )

        except ServerSelectionTimeoutError:
            self.send_response(524, "Таймаут подключения к базе данных")
            self.end_headers()

    def get_most_expensive_category(self, month_in_request):
        """Вернёт самую затратную категорию и крупную трату месяца.

        Args:
            month_in_request (dict): параметры запроса, содержащие ключ `month`.

        Response:
            200 JSON: статистика по месяцу.
            204: нет данных.
            524: таймаут БД.
        """
        month = month_in_request["month"][0]

        try:
            month_expenses = [
                exp
                for exp in self.expenses.find()
                if exp["date"].split("-")[1] == month
            ]

            if not month_expenses:
                self.send_response(HTTPStatus.NO_CONTENT)
                self.end_headers()
                return

            # Сумма по категориям
            totals = {}
            for exp in month_expenses:
                cat = exp["category"]
                totals[cat] = totals.get(cat, 0) + int(exp["amount"])

            most_expensive_category = max(totals, key=totals.get)
            total_amount = totals[most_expensive_category]

            most_expensive_overall = max(month_expenses, key=lambda x: int(x["amount"]))

            most_exp_in_cat = max(
                (e for e in month_expenses if e["category"] == most_expensive_category),
                key=lambda x: int(x["amount"]),
            )

            response_data = {
                "category": most_expensive_category,
                "total_amount": total_amount,
                "expense_name": most_expensive_overall["expense_name"],
                "total_amount_expanse_name": int(most_expensive_overall["amount"]),
                "total_amount_category": int(most_exp_in_cat["amount"]),
            }

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps(response_data, ensure_ascii=False).encode("utf-8")
            )

        except ServerSelectionTimeoutError:
            self.send_response(524, "Таймаут подключения к базе данных")
            self.end_headers()

    def get_categories_by_month(self, month_in_request):
        """Возвращает список категорий, в которых были траты за указанный месяц.

        Args:
            month_in_request (dict): параметры запроса с ключом `month`.

        Response:
            200 JSON: список строк-категорий.
            524: таймаут БД.
        """
        month = month_in_request["month"][0]

        try:
            categories = {
                exp["category"]
                for exp in self.expenses.find()
                if exp["date"].split("-")[1] == month
            }

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps(list(categories), ensure_ascii=False).encode("utf-8")
            )

        except ServerSelectionTimeoutError:
            self.send_response(524, "Таймаут подключения к базе данных")
            self.end_headers()

    def get_all_expenses(self):
        """Отдаёт все траты как JSON.

        Response:
            200 JSON: массив документов MongoDB.
            524: таймаут БД.
        """
        try:
            all_expenses = list(self.expenses.find())

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    all_expenses, default=bson.json_util.default, ensure_ascii=False
                ).encode("utf-8")
            )
        except ServerSelectionTimeoutError:
            self.send_response(524, "Таймаут подключения к базе данных")
            self.end_headers()

    # ---------- HTTP-МЕТОДЫ ------------------------------------------------

    def do_GET(self):
        """Обрабатывает HTTP GET-запросы."""
        parsed_url = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed_url.query)
        path = parsed_url.path

        # Главная страница
        if path == "/":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            with open("index.html", "rb") as file:
                self.wfile.write(file.read())

        # Статистика
        elif path == "/stats/most-expensive-category":
            self.get_most_expensive_category(params)

        elif path == "/stats/biggest-expense":
            self.get_most_expensive_spending(params, params)

        elif path == "/stats/categories-by-month":
            self.get_categories_by_month(params)

        # Все траты
        elif path == "/expenses":
            self.get_all_expenses()

        # Cтатические файлы
        elif path.startswith("/static/css"):
            self._serve_static(path, "text/css; charset=utf-8")

        elif path.startswith("/static/img"):
            self._serve_static(path, "image/png")

        elif path.startswith("/static/js"):
            self._serve_static(path, "application/javascript; charset=utf-8")

        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Ресурс не найден")

    def do_POST(self):
        """Добавляет новую трату (форма на главной)."""
        if self.path != "/":
            self.send_error(HTTPStatus.NOT_FOUND, "Маршрут не найден")
            return

        content_length = int(self.headers["Content-Length"])
        post_data = self.rfile.read(content_length).decode("utf-8")
        parsed = urllib.parse.parse_qs(post_data)

        new_expense = {
            "expense_name": parsed.get("expense_name", [""])[0],
            "category": parsed.get("category", [""])[0],
            "amount": parsed.get("amount", [""])[0],
            "date": parsed.get("date", [""])[0],
        }

        try:
            self.expenses.insert_one(new_expense)
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("Location", "/")
            self.end_headers()
        except ServerSelectionTimeoutError:
            self.send_response(524, "Таймаут подключения к базе данных")
            self.end_headers()

    def do_DELETE(self):
        """Удаляет трату по её `ObjectId`."""
        if not self.path.startswith("/expenses/"):
            self.send_error(HTTPStatus.NOT_FOUND, "Маршрут не найден")
            return

        exp_id = self.path.split("/")[2]
        try:
            result = self.expenses.delete_one({"_id": ObjectId(exp_id)})
            if result.deleted_count:
                self.send_response(HTTPStatus.NO_CONTENT)
            else:
                self.send_error(HTTPStatus.NOT_FOUND, "Трата не найдена")
        except ServerSelectionTimeoutError:
            self.send_error(
                HTTPStatus.GATEWAY_TIMEOUT, "Таймаут подключения к базе данных"
            )
        self.end_headers()

    def do_PUT(self):
        """Редактирует трату по её `ObjectId` (ожидает JSON-тело)."""
        if not self.path.startswith("/expenses/"):
            self.send_error(HTTPStatus.NOT_FOUND, "Маршрут не найден")
            return

        exp_id = self.path.split("/")[2]
        length = int(self.headers["Content-Length"])
        payload = self.rfile.read(length).decode()

        try:
            update = json.loads(payload)
            self.expenses.update_one(
                {"_id": ObjectId(exp_id)},
                {"$set": update},
            )
            self.send_response(HTTPStatus.OK)
        except ValueError:
            self.send_error(HTTPStatus.BAD_REQUEST, "Некорректный JSON")
        except ServerSelectionTimeoutError:
            self.send_error(
                HTTPStatus.GATEWAY_TIMEOUT, "Таймаут подключения к базе данных"
            )
        self.end_headers()

    # ---------- ВНУТРЕННИЙ МЕТОД -------------------------------------------

    def _serve_static(self, path, content_type):
        """Отдаёт статический файл.

        Args:
            path (str): URL-путь, начинающийся с `/static/`.
            content_type (str): заголовок `Content-Type`.
        """
        try:
            with open("." + path, "rb") as file:
                content = file.read()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", content_type)
                self.end_headers()
                self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(HTTPStatus.NOT_FOUND, "Файл не найден")


# ---------------------------------------------------------------------------


def run(server_class=HTTPServer, handler_class=Handler):
    """Запускает HTTP-сервер на `localhost:8000`."""
    server_address = ("", 8000)
    httpd = server_class(server_address, handler_class)
    print("Сервер запущен на http://localhost:8000")
    httpd.serve_forever()


if __name__ == "__main__":
    run()
