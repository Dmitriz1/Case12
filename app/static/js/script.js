// По умолчанию ставит сегодняшнюю дату
        document.getElementById('date').value = new Date().toISOString().split('T')[0];
        // Делает инпут с датой такого же размера, как и остальные инпуты
        const input_text = document.querySelector('.input-text')
        const input_date = document.querySelector('.input-date')
        input_date.style.width = getComputedStyle(input_text).width
        // Делает высоту выбора категории и выбор месяца такими же, как высоту кнопки "Добавить"
        const input_button = document.querySelector('.button-add')
        const input_date_month = document.querySelector('.input-month')
        const choose_cat = document.querySelector('.select-add')
        input_date_month.style.height = getComputedStyle(input_button).height
        choose_cat.style.height = getComputedStyle(input_button).height

        // Получить список всех категорий
        fetch('/expenses')
            .then(response => response.json())
            .then(data => {
                const select = document.getElementById('category-select');
                const categories = new Set(data.map(e => e.category));
                categories.forEach(cat => {
                    const option = document.createElement('option');
                    option.value = cat;
                    option.textContent = cat;
                    select.appendChild(option);
                });
            });

        // При изменении категории — подгружаем статистику
        document.getElementById("category-select").addEventListener("change", function () {
            const selectedMonth = document.getElementById("month-input").value;
            const selectedCategory = this.value;
            const output = document.getElementById("category-stat-output");

            if (!selectedMonth || !selectedCategory) {
                output.innerHTML = '';
                return;
            }

            const month = selectedMonth.split("-")[1];

            fetch(`/stats/biggest-expense?month=${month}&category=${encodeURIComponent(selectedCategory)}`)
                .then(response => {
                    if (response.status === 204) {
                        output.innerHTML = `<p class='month-txt'>Нет данных по категории за выбранный месяц.</p>`;
                        return;
                    }
                    return response.json();
                })
                .then(data => {
                    if (data) {
                        output.innerHTML = `
                    <p class='month-txt'><strong>Самая крупная трата в категории "${selectedCategory}":</strong> ${data.name} — ${data.amount}р (${data.date})</p>
                `;
                    }
                })
                .catch(error => {
                    console.error("Ошибка:", error);
                    alert("Не удалось получить данные.");
                });
        });

        function updateCategoriesForMonth(monthValue) {
            const select = document.getElementById('category-select');
            const output = document.getElementById('category-stat-output');
            select.innerHTML = '<option value="">Выберите категорию</option>';
            output.innerHTML = '';

            const month = monthValue.split("-")[1];

            fetch(`/stats/categories-by-month?month=${month}`)
                .then(response => response.json())
                .then(categories => {
                    categories.forEach(cat => {
                        const option = document.createElement('option');
                        option.value = cat;
                        option.textContent = cat;
                        select.appendChild(option);
                    });
                })
                .catch(error => {
                    console.error("Ошибка при загрузке категорий:", error);
                });
        }

        document.getElementById("month-submit").addEventListener("click", function () {
            const selectedMonth = document.getElementById("month-input").value;

            fetchMostExpensiveCategory(selectedMonth);
            updateCategoriesForMonth(selectedMonth);

            // Сброс категории
            const categorySelect = document.getElementById("category-select");
            categorySelect.value = "";
            document.getElementById("category-stat-output").innerHTML = "";
        });

        // Выводим данные из бд на страницу
        fetch('/expenses')
            .then(response => response.json())
            .then(data => {
                const container = document.querySelector('.monthly-statistics');
                data.forEach(expense => {
                    const div = document.createElement('div');
                    div.className = 'el-inf-db';
                    div.dataset.id = expense._id["$oid"];
                    const div_txt = document.createElement('div');
                    div_txt.className = 'div-txt'
                    const div_btn = document.createElement('div');
                    div_btn.className = 'div-btn'
                    const div_date_cat = document.createElement('div');
                    div_date_cat.className = 'date-cat'


                    const span_date = document.createElement('span');
                    span_date.className = 'mongodb-info';
                    span_date.textContent = `${expense.date}`;

                    const span_category = document.createElement('span');
                    span_category.className = 'mongodb-info-cat';
                    span_category.textContent = `${expense.expense_name} | ${expense.category}`;

                    const span_amount = document.createElement('span');
                    span_amount.className = 'mongodb-info';
                    span_amount.textContent = `${expense.amount}р`;

                    const button_edit = document.createElement('button')
                    button_edit.className = 'button-edit'
                    button_edit.type = 'button'
                    const button_delete = document.createElement('button')
                    button_delete.className = 'button-delete'
                    button_delete.type = 'button'

                    const img_edit = document.createElement('img');
                    img_edit.src = '/static/img/edit.png';
                    const img_delete = document.createElement('img');
                    img_delete.src = '/static/img/delete.png';

                    container.appendChild(div);
                    div.appendChild(div_txt);
                    div.appendChild(div_btn);
                    div_date_cat.appendChild(span_date);
                    div_date_cat.appendChild(span_category);
                    div_txt.appendChild(div_date_cat);
                    div_txt.appendChild(span_amount);
                    div_btn.appendChild(button_edit);
                    div_btn.appendChild(button_delete);
                    button_edit.appendChild(img_edit);
                    button_delete.appendChild(img_delete);
                });
            });

        // Отправляем запрос для добавления данных в бд
        document.querySelector('.button-input').addEventListener('click', function (event) {
            event.preventDefault(); // Предотвращаем стандартное поведение формы

            // Получаем данные из инпутов
            const expenseName = document.querySelector('input[name="expense_name"]').value;
            const category = document.querySelector('input[name="category"]').value;
            const amount = document.querySelector('input[name="amount"]').value;
            const date = document.querySelector('input[name="date"]').value;

            // Формируем объект данных
            const data = {
                expense_name: expenseName,
                category: category,
                amount: amount,
                date: date
            };

            // Проверка на заполненность полей
            if (!data.expense_name || !data.category || !data.amount || !data.date) {
                alert('Пожалуйста, заполните все поля!');
                return;
            }

            // Отправляем POST-запрос на сервер
            fetch('/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                body: new URLSearchParams(data)
            })
                .then(response => {
                    if (response.ok) {
                        location.reload();
                        // Очищаем инпуты (нужно для браузеров, которые не на chrome)
                        document.querySelector('input[name="expense_name"]').value = '';
                        document.querySelector('input[name="category"]').value = '';
                        document.querySelector('input[name="amount"]').value = '';
                        document.querySelector('input[name="date"]').value = new Date().toISOString().split('T')[0];

                    } else {
                        alert(`Ошибка: ${response.status}`);
                    }
                })
                .catch(error => {
                    console.error('Ошибка:', error);
                    alert('Не удалось отправить данные.');
                });
        });
        // Функция запроса статистики по месяцу
        function fetchMostExpensiveCategory(monthValue) {
            if (!monthValue) {
                alert("Пожалуйста, выберите месяц.");
                return;
            }

            const month = monthValue.split("-")[1];
            fetch(`/stats/most-expensive-category?month=${month}`)
                .then(response => {
                    const output = document.getElementById('monthly-info-output');
                    if (response.status === 204) {
                        output.innerHTML = `<p class='month-txt'>Нет данных за выбранный месяц.</p>`;
                        return;
                    }
                    if (!response.ok) {
                        throw new Error(`Ошибка запроса: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    if (data) {
                        const output = document.getElementById('monthly-info-output');
                        output.innerHTML = `
                    <p class='month-txt'><strong>Самая затратная категория:</strong> ${data.category} — ${data.total_amount}р</p>
                    <p class='month-txt'><strong>Самая крупная трата за месяц:</strong> ${data.expense_name} (${data.category}) — ${data.total_amount_expanse_name}р</p>
                `;
                    }
                })
                .catch(error => {
                    console.error("Ошибка:", error);
                    alert("Произошла ошибка при выполнении запроса.");
                });
        }


        // Установка текущего месяца в инпут и авто-запрос статистики при загрузке
        document.addEventListener("DOMContentLoaded", function () {
            const now = new Date();
            const currentMonth = now.toISOString().slice(0, 7); // YYYY-MM
            const monthInput = document.getElementById("month-input");
            monthInput.value = currentMonth;

            fetchMostExpensiveCategory(currentMonth);
        });

        // Обработка кнопки "Показать статистику"
        document.getElementById("month-submit").addEventListener("click", function () {
            const selectedMonth = document.getElementById("month-input").value;
            fetchMostExpensiveCategory(selectedMonth);
        });