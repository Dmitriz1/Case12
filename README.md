# HTTP Expenses Tracker API

Основной HTTP-сервер для учёта трат.

Сервер реализован на чистом `http.server.BaseHTTPRequestHandler` и хранит данные в MongoDB.  
Поддерживаются операции CRUD и простая агрегация статистики.

---

## Содержание

- [1. Главная страница](#1-главная-страница)  
- [2. Получить все траты](#2-получить-все-траты)  
- [3. Получить одну трату по ID](#3-получить-одну-трату-po-id)  
- [4. Добавить новую трату](#4-добавить-новую-трату)  
- [5. Обновить трату по ID](#5-обновить-трату-po-id)  
- [6. Удалить трату по ID](#6-удалить-трату-po-id)  
- [7. Список категорий за месяц](#7-список-категорий-за-месяц)  
- [8. Самая затратная категория за месяц](#8-самая-затратная-категория-за-месяц)  
- [9. Самая крупная трата в категории за месяц](#9-самая-крупная-трата-в-категории-за-месяц)  
- [Статические файлы](#статические-файлы)

---

## 1. Главная страница

- **Метод:** `GET`  
- **Путь:** `/`  
- **Ответ:**
  - `200 OK`  
  - `Content-Type: text/html; charset=utf-8`  
  - Возвращает файл `index.html`

---

## 2. Получить все траты

- **Метод:** `GET`  
- **Путь:** `/expenses`  
- **Ответ:**
  - `200 OK`  
  - `Content-Type: application/json; charset=utf-8`  
  - Тело: JSON-массив документов траты:
    ```json
    [
      {
        "_id": "<ObjectId>",
        "expense_name": "string",
        "category": "string",
        "amount": "string",
        "date": "YYYY-MM-DD"
      },
      …
    ]
    ```
  - `504 Gateway Timeout` — таймаут подключения к БД

---

## 3. Получить одну трату по ID

- **Метод:** `GET`  
- **Путь:** `/expenses/{id}`  
- **Параметры:**
  - `{id}` — строковое представление `ObjectId` документа  
- **Ответ:**
  - `200 OK` + JSON-документ траты  
  - `400 Bad Request` — некорректный формат ID  
  - `404 Not Found` — документ не найден  
  - `504 Gateway Timeout` — таймаут подключения к БД

---

## 4. Добавить новую трату

- **Метод:** `POST`  
- **Путь:** `/expenses`  
- **Content-Type:** `application/x-www-form-urlencoded`  
- **Поля формы:**
  - `expense_name` (string) — название  
  - `category` (string) — категория  
  - `amount` (string) — сумма  
  - `date` (string `YYYY-MM-DD`) — дата  
- **Ответ:**
  - `201 Created`  
  - Заголовок `Location: /expenses/{newId}`  
  - `504 Gateway Timeout` — таймаут подключения к БД

---

## 5. Обновить трату по ID

- **Метод:** `PUT`  
- **Путь:** `/expenses/{id}`  
- **Content-Type:** `application/json`  
- **Параметры:**
  - `{id}` — строковое представление `ObjectId`  
- **Тело:** JSON с любыми полями для обновления:
  ```json
  {
    "expense_name": "Новое имя",
    "amount": "150"
  }
  ```
- **Ответ:**
  - `200 OK` — если обновлено  
  - `400 Bad Request` — некорректный JSON или ID  
  - `404 Not Found` — документ не найден  
  - `504 Gateway Timeout` — таймаут подключения к БД

---

## 6. Удалить трату по ID

- **Метод:** `DELETE`  
- **Путь:** `/expenses/{id}`  
- **Параметры:**
  - `{id}` — `ObjectId` документа  
- **Ответ:**
  - `204 No Content` — удалено успешно  
  - `400 Bad Request` — некорректный ID  
  - `404 Not Found` — документ не найден  
  - `504 Gateway Timeout` — таймаут подключения к БД

---

## 7. Список категорий за месяц

- **Метод:** `GET`  
- **Путь:** `/categories`  
- **Query-параметры:**
  - `month` (обязательный) — номер месяца в формате `MM`  
- **Ответ:**
  - `200 OK`  
  - `Content-Type: application/json; charset=utf-8`  
  - Тело: JSON-массив категорий:
    ```json
    ["Food", "Entertainment", "Transportation", …]
    ```
  - `400 Bad Request` — если `month` не передан  
  - `504 Gateway Timeout` — таймаут подключения к БД

---

## 8. Самая затратная категория за месяц

- **Метод:** `GET`  
- **Путь:** `/categories/top`  
- **Query-параметры:**
  - `month` (обязательный) — `MM`  
- **Ответ:**
  - `200 OK`  
  - `Content-Type: application/json; charset=utf-8`  
  - Тело:
    ```json
    {
      "category": "string",
      "total_amount": number,
      "expense_name": "string",
      "amount": number,
      "date": "YYYY-MM-DD"
    }
    ```
  - `204 No Content` — если нет трат за месяц  
  - `400 Bad Request` — если `month` не передан  
  - `504 Gateway Timeout` — таймаут подключения к БД

---

## 9. Самая крупная трата в категории за месяц

- **Метод:** `GET`  
- **Путь:** `/categories/{category}/expenses`  
- **Query-параметры:**
  - `month` (обязательный) — `MM`  
  - `biggest` (опциональный) — `true` для одной записи  
- **Ответ:**
  - `200 OK`  
  - Если `biggest=true`, тело:
    ```json
    {"expense_name": "string", "amount": number, "date": "YYYY-MM-DD"}
    ```
  - Иначе массив всех трат категории за месяц  
  - `204 No Content` — если нет данных  
  - `400 Bad Request` — если `month` не передан  
  - `504 Gateway Timeout` — таймаут подключения к БД

---

## Статические файлы

- Путь `/static/css/...` — CSS (`text/css; charset=utf-8`)  
- Путь `/static/js/...` — JS (`application/javascript; charset=utf-8`)  
- Путь `/static/img/...` — PNG (`image/png`)  
- Несуществующие файлы — `404 Not Found`
