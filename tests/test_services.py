import unittest
import json
from unittest.mock import MagicMock, patch
from http.server import BaseHTTPRequestHandler
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError
import urllib.parse
import bson
from bson.objectid import ObjectId

from __main__ import LOGIN, PASSWORD, MONGODB_DB, MONGODB_COLLECTION

from __main__ import Handler

class test_services(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Set up a test MongoDB client and database
        cls.mongo_client = MongoClient(f"mongodb+srv://{LOGIN}:{PASSWORD}@cluster0.bxpsiw0.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
        cls.db = cls.mongo_client["test_db"]  # Use a test database
        cls.expenses = cls.db["test_collection"]  # Use a test collection

        # Clear the test collection before running tests
        cls.expenses.delete_many({})

        # Insert some test data
        cls.test_data = [
            {"expense_name": "Grocery", "category": "Food", "amount": "50", "date": "2024-07-01"},
            {"expense_name": "Restaurant", "category": "Food", "amount": "100", "date": "2024-07-15"},
            {"expense_name": "Train ticket", "category": "Transportation", "amount": "30", "date": "2024-07-20"},
            {"expense_name": "Gas", "category": "Transportation", "amount": "70", "date": "2024-08-10"},
            {"expense_name": "Concert", "category": "Entertainment", "amount": "120", "date": "2024-08-25"},
            {"expense_name": "Book", "category": "Entertainment", "amount": "40", "date": "2024-08-05"}
        ]
        cls.expenses.insert_many(cls.test_data)

    @classmethod
    def tearDownClass(cls):
        # Clean up the test collection after running tests
        cls.expenses.delete_many({})

        # Close the MongoDB connection
        cls.mongo_client.close()

    def setUp(self):
        # Create a mock request handler
        self.handler = Handler(MagicMock(), MagicMock())
        self.handler.expenses = self.expenses  # Use the test collection
        self.handler.send_response = MagicMock()
        self.handler.send_header = MagicMock()
        self.handler.end_headers = MagicMock()
        self.handler.wfile = MagicMock()
        self.handler.wfile.write = MagicMock()

    def test_get_most_expensive_spending(self):
        # Test case 1: Valid month and category
        month_in_request = {"month": ["07"]}
        category_in_request = {"category": ["Food"]}
        self.handler.get_most_expensive_spending(month_in_request, category_in_request)

        self.handler.send_response.assert_called_with(200)
        response_data = json.loads(self.handler.wfile.write.call_args[0][0].decode("utf-8"))
        self.assertEqual(response_data["name"], "Restaurant")
        self.assertEqual(response_data["amount"], 100)
        self.assertEqual(response_data["date"], "2024-07-15")

        # Test case 2: No expenses found for the given month and category
        month_in_request = {"month": ["09"]}
        category_in_request = {"category": ["Food"]}
        self.handler.get_most_expensive_spending(month_in_request, category_in_request)
        self.handler.send_response.assert_called_with(204)

    def test_get_most_expensive_category(self):
        # Test case 1: Valid month
        month_in_request = {"month": ["07"]}
        self.handler.get_most_expensive_category(month_in_request)

        self.handler.send_response.assert_called_with(200)
        response_data = json.loads(self.handler.wfile.write.call_args[0][0].decode("utf-8"))
        self.assertEqual(response_data["category"], "Food")
        self.assertEqual(response_data["total_amount"], 150)
        self.assertEqual(response_data["expense_name"], "Restaurant")
        self.assertEqual(response_data["total_amount_expanse_name"], 100)
        self.assertEqual(response_data["total_amount_category"], 100)

        # Test case 2: No expenses found for the given month
        month_in_request = {"month": ["09"]}
        self.handler.get_most_expensive_category(month_in_request)
        self.handler.send_response.assert_called_with(204)

    def test_get_categories_by_month(self):
        # Test case 1: Valid month
        month_in_request = {"month": ["08"]}
        self.handler.get_categories_by_month(month_in_request)

        self.handler.send_response.assert_called_with(200)
        response_data = json.loads(self.handler.wfile.write.call_args[0][0].decode("utf-8"))
        self.assertEqual(set(response_data), {"Transportation", "Entertainment"})

    def test_get_all_expenses(self):
        self.handler.get_all_expenses()

        self.handler.send_response.assert_called_with(200)
        response_data = json.loads(self.handler.wfile.write.call_args[0][0].decode("utf-8"))
        self.assertEqual(len(response_data), len(self.test_data))  # Check if all expenses are returned

    @patch('__main__.MongoClient')
    def test_server_selection_timeout_error(self, MockMongoClient):
        # Mock MongoClient to raise ServerSelectionTimeoutError
        MockMongoClient.return_value.configure_mock(**{'__getitem__.side_effect': ServerSelectionTimeoutError()})
        handler = Handler(MagicMock(), MagicMock())

        # Call methods that might raise ServerSelectionTimeoutError
        handler.get_most_expensive_spending({"month": ["07"]}, {"category": ["Food"]})
        handler.send_response.assert_called_with(524)

        handler.get_most_expensive_category({"month": ["07"]})
        handler.send_response.assert_called_with(524)

        handler.get_categories_by_month({"month": ["07"]})
        handler.send_response.assert_called_with(524)

        handler.get_all_expenses()
        handler.send_response.assert_called_with(524)

    def test_do_GET_root(self):
        self.handler.path = "/"
        self.handler.do_GET()
        self.handler.send_response.assert_called_with(200)

    def test_do_GET_most_expensive_category(self):
        self.handler.path = "/stats/most-expensive-category?month=07"
        self.handler.do_GET()
        self.handler.send_response.assert_called_with(200)

    def test_do_GET_biggest_expense(self):
        self.handler.path = "/stats/biggest-expense?month=07&category=Food"
        self.handler.do_GET()
        self.handler.send_response.assert_called_with(200)

    def test_do_GET_expenses(self):
        self.handler.path = "/expenses"
        self.handler.do_GET()
        self.handler.send_response.assert_called_with(200)

    def test_do_GET_categories_by_month(self):
        self.handler.path = "/stats/categories-by-month?month=07"
        self.handler.do_GET()
        self.handler.send_response.assert_called_with(200)

    @patch('__main__.open', create=True)
    def test_do_GET_static_css(self, mock_open):
        mock_file = MagicMock()
        mock_file.read.return_value = b'body { background-color: #f0f0f0; }'
        mock_open.return_value = mock_file
        self.handler.path = "/static/css/styles.css"
        self.handler.do_GET()
        self.handler.send_response.assert_called_with(200)
        self.handler.send_header.assert_called_with("Content-type", "text/css; charset=utf-8")

    @patch('__main__.open', create=True)
    def test_do_GET_static_img(self, mock_open):
        mock_file = MagicMock()
        mock_file.read.return_value = b'PNGData'
        mock_open.return_value = mock_file
        self.handler.path = "/static/img/logo.png"
        self.handler.do_GET()
        self.handler.send_response.assert_called_with(200)
        self.handler.send_header.assert_called_with("Content-type", "image/png")

    @patch('__main__.open', create=True)
    def test_do_GET_static_js(self, mock_open):
        mock_file = MagicMock()
        mock_file.read.return_value = b'console.log("Hello, world!");'
        mock_open.return_value = mock_file
        self.handler.path = "/static/js/script.js"
        self.handler.do_GET()
        self.handler.send_response.assert_called_with(200)
        self.handler.send_header.assert_called_with("Content-type", "application/javascript; charset=utf-8")

    @patch('__main__.open', side_effect=FileNotFoundError)
    def test_do_GET_file_not_found(self, mock_open):
        self.handler.path = "/static/css/nonexistent.css"
        self.handler.do_GET()
        self.handler.send_error.assert_called_with(404, "Файл не найден")

    def test_do_POST(self):
        self.handler.path = "/"
        self.handler.headers = {"Content-Length": "70"}
        self.handler.rfile = MagicMock()
        self.handler.rfile.read.return_value = b"expense_name=TestExpense&category=TestCategory&amount=100&date=2024-01-01"
        self.handler.do_POST()
        self.handler.send_response.assert_called_with(303)
        self.handler.send_header.assert_called_with("Location", "/")

if __name__ == '__main__':
    unittest.main()
