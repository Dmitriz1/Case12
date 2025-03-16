import urllib.parse
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from tkinter.font import names

from unicodedata import category


class Handler(BaseHTTPRequestHandler):

    def get_most_expensive_spending(self,month_in_request, category_in_request):
        month = month_in_request["month"][0]
        category = category_in_request["category"][0]

        with open("expenses.json", "r", encoding="utf-8") as file:
            data = json.load(file)
        new_list = []
        for a in data:
            if a["date"].split("-")[1] == month and a["category"] == category:
                new_list.append(a)

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

    def get_most_expensive_category(self, month_in_request):
        month=month_in_request["month"][0]

        with open("expenses.json", "r", encoding="utf-8") as file:
            data = json.load(file)
        new_list = []
        for a in data:
            if a["date"].split("-")[1] == month:
                new_list.append(a)

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
                with open("expenses.json", 'r', encoding="utf-8") as file:
                    expenses = json.load(file)
            except(FileNotFoundError, json.JSONDecodeError):
                expenses = []

            expenses.append(new_expense)

            with open("expenses.json", "w",encoding="utf-8") as file:
                json.dump(expenses, file, ensure_ascii=False, indent=4)

            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()

def run(server_class=HTTPServer, handler_class=Handler):
    server_address = ('', 8000)
    httpd = server_class(server_address, handler_class)
    httpd.serve_forever()

if __name__ == "__main__":
    run()