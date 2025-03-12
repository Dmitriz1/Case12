import json
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

from unicodedata import category


class Handler(BaseHTTPRequestHandler):
    def not_found(self):
        self.send_response(404)
        self.send_header("Content-Type", "text/html; charset=UTF-8")
        self.end_headers()
        self.wfile.write("<h1>Не найдено 404</h1>".encode("utf-8"))

    def first_page(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=UTF-8")
        self.end_headers()

        html_content = """
        <!DOCTYPE html>
        <html> 
        <head><title>Трекер трат</title></head>
        <body>
            <h1>Трекер Трат</h1>
            <form method="post" action="/" class="auth-window__form">
                <div class="form__data">
                    <label>
                        <span>Название траты</span>
                        <input type="text" name="expense_name" class="data__field">
                    </label>
                </div>
                
                <div class="form__data">
                    <label>
                        <span>Категория</span>                                    
                        <input type="text" name="category" class="data__field">
                    </label>
                </div>

                <div class="form__data">
                    <label>
                        <span>Сумма</span>                                    
                        <input type="number" name="amount" class="data__field">
                    </label>
                </div>

                <div class="form__data">
                    <label>
                        <span>Дата</span>                                    
                        <input type="date" name="date" class="data__field">
                    </label>
                </div>

                <div class="send__data">                                
                    <input type="submit" value="Подтвердить" class="submit-btn">
                </div>
            </form>
        </body>
        </html>
        """
        self.wfile.write(html_content.encode("utf-8"))

    def file_page(self, filename):
        try:
            with open(filename, 'rb') as f:
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=UTF-8")
                self.end_headers()
                self.wfile.write(f.read())
        except FileNotFoundError:
            self.not_found()

    def do_GET(self):
        if self.path == "/":
            self.first_page()
        elif self.path.startswith("/index"):
            self.file_page("index.html")
        else:
            self.not_found()

    def _process_post_urlencoded(self) -> dict[str, str]:
        length = int(self.headers["Content-Length"])
        data = self.rfile.read(length).decode("utf-8")
        return urllib.parse.parse_qs(data)

    def do_POST(self):
        content_type = self.headers.get("Content-Type", "")

        post_data = self._process_post_urlencoded()

        new_expense = {
            "expense_name": post_data.get("expense_name", [""])[0],
            "category": post_data.get("category", [""])[0],
            "amount": post_data.get("amount", [""])[0],
            "date": post_data.get("date", [""])[0]

        }

        try:
            with open('expenses.json', 'r', encoding='utf-8') as file:
                existing_data = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            existing_data = []

        existing_data.append(new_expense)

        with open('expenses.json', 'w', encoding='utf-8') as file:
            json.dump(existing_data, file, ensure_ascii=False, indent=4)

        print("Данные добавлены в expenses.json")

        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()


def run(server_class=HTTPServer, handler_class=Handler):
    server_address = ('', 8000)
    httpd = server_class(server_address, handler_class)
    print("Сервер запущен на порту 8000...")
    httpd.serve_forever()


if __name__ == "__main__":
    run()