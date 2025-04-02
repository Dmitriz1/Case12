import urllib.parse
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from tkinter.font import names
from pymongo.errors import ServerSelectionTimeoutError
from pymongo import MongoClient
from .config import *

from unicodedata import category


class Handler(BaseHTTPRequestHandler):

    mongo_client = MongoClient(MONGODB_HOST, MONGODB_PORT)
    db = mongo_client[MONGODB_DB]
    expenses = db[MONGODB_COLLECTION]

    def get_most_expensive_spending(self,month_in_request, category_in_request):
        month = month_in_request["month"][0]
        category = category_in_request["category"][0]

        try:
            new_list = []
            for expense in self.expenses.find():
                if expense["date"].split("-")[1] == month and expense["category"] == category:
                    new_list.append(expense)

            if not new_list:
                self.send_response(204)
                self.end_headers()
            else:
                max_expense = max(new_list, key=lambda x: x["amount"])
                spending_name = max_expense["expense_name"]
                spending_amount = int(max_expense["amount"])
                spending_date = max_expense["date"]


                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                response_data = {
                    "name" : spending_name,
                    "amount" : spending_amount,
                    "date" : spending_date
                }
                self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode("utf-8"))
        except ServerSelectionTimeoutError:
            self.send_response(524)
            self.end_headers()

    def get_most_expensive_category(self, month_in_request):
        month = month_in_request["month"][0]

        try:
            new_list = []
            for expense in self.expenses.find():
                if expense["date"].split("-")[1] == month:
                    new_list.append(expense)

            if not new_list:
                self.send_response(204)
                self.end_headers()
            else:
                all_category = {}
                for expens in new_list:
                    category = expens["category"]
                    amount = int(expens["amount"])
                    all_category[category] = all_category.get(category, 0) + amount

                most_expensive_category = max(all_category, key=all_category.get)
                total_amount = all_category[most_expensive_category]

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                response_data = {
                    "category": most_expensive_category,
                    "total_amount": total_amount
                }
                self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode("utf-8"))
        except ServerSelectionTimeoutError:
            self.send_response(524)
            self.end_headers()

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        request = urllib.parse.parse_qs(parsed_url.query)
        path = parsed_url.path
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            with open("index.html", "rb") as file:
                self.wfile.write(file.read())
        elif parsed_url.path == "/stats/most-expensive-category":
            self.get_most_expensive_category(request)
        elif parsed_url.path == "/stats/biggest-expense":
            self.get_most_expensive_spending(request,request)

    def do_POST(self):
        if self.path == '/':
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length).decode("utf-8")
            parsed_data = urllib.parse.parse_qs(post_data)

            new_expense = {
                "expense_name": parsed_data.get("expense_name", [""])[0],
                "category": parsed_data.get("category", [""])[0],
                "amount": parsed_data.get("amount", [""])[0],
                "date": parsed_data.get("date", [""])[0]
            }

            try:
                self.expenses.insert_one(new_expense)

                self.send_response(303)
                self.send_header("Location", "/")
                self.end_headers()
            except ServerSelectionTimeoutError:
                self.send_response(524)
                self.end_headers()


def run(server_class=HTTPServer, handler_class=Handler):
    server_address = ('', 8000)
    httpd = server_class(server_address, handler_class)
    httpd.serve_forever()


if __name__ == "__main__":
    run()