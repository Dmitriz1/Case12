/* ---------- Вспомогательные утилиты ---------- */
const $ = sel => document.querySelector(sel);

/* ---------- Инициализация формы ---------- */
// Сегодняшняя дата по умолчанию
$('#date').value = new Date().toISOString().split('T')[0];

// Выравниваем размеры инпутов/кнопок
const inputText = $('.input-text');
const inputDate = $('.input-date');
const btnAdd = $('.button-add');
const inputMonth = $('.input-month');
const selectAdd = $('.select-add');

inputDate.style.width = getComputedStyle(inputText).width;
inputMonth.style.height = getComputedStyle(btnAdd).height;
selectAdd.style.height = getComputedStyle(btnAdd).height;

/* ---------- Загрузка всех категорий ---------- */
function loadAllCategories() {
    fetch('/expenses')
        .then(r => r.json())
        .then(expenses => {
            const select = $('#category-select');
            const categories = new Set(expenses.map(e => e.category));
            categories.forEach(cat => {
                const opt = document.createElement('option');
                opt.value = cat;
                opt.textContent = cat;
                select.appendChild(opt);
            });
        })
        .catch(console.error);
}

loadAllCategories();

/* ---------- Статистика по выбранной категории ---------- */
function fetchCategoryStats(month, category) {
    fetch(`/stats/biggest-expense?month=${month}&category=${encodeURIComponent(category)}`)
        .then(r => {
            const out = $('#category-stat-output');
            if (r.status === 204) {
                out.innerHTML = `<p class="month-txt">Нет данных по категории за выбранный месяц.</p>`;
                return null;
            }
            return r.json();
        })
        .then(data => {
            if (!data) return;
            $('#category-stat-output').innerHTML =
                `<p class="month-txt"><strong>Самая крупная трата в категории "${category}":</strong>
                 ${data.name} — ${data.amount}р (${data.date})</p>`;
        })
        .catch(err => {
            console.error(err);
            alert('Не удалось получить данные.');
        });
}

/* ---------- Обновление списка категорий при смене месяца ---------- */
function updateCategoriesForMonth(monthValue) {
    const select = $('#category-select');
    const out = $('#category-stat-output');
    select.innerHTML = '<option value="">Выберите категорию</option>';
    out.innerHTML = '';

    const month = monthValue.split('-')[1];
    fetch(`/stats/categories-by-month?month=${month}`)
        .then(r => r.json())
        .then(cats => {
            cats.forEach(cat => {
                const opt = document.createElement('option');
                opt.value = cat;
                opt.textContent = cat;
                select.appendChild(opt);
            });
        })
        .catch(err => console.error('Ошибка при загрузке категорий:', err));
}

/* ---------- Статистика «самая затратная категория месяца» ---------- */
function fetchMostExpensiveCategory(monthValue) {
    const month = monthValue.split('-')[1];
    fetch(`/stats/most-expensive-category?month=${month}`)
        .then(r => {
            const out = $('#monthly-info-output');
            if (r.status === 204) {
                out.innerHTML = `<p class="month-txt">Нет данных за выбранный месяц.</p>`;
                return null;
            }
            if (!r.ok) throw new Error(`Ошибка запроса: ${r.status}`);
            return r.json();
        })
        .then(data => {
            if (!data) return;
            $('#monthly-info-output').innerHTML =
                `<p class="month-txt"><strong>Самая затратная категория:</strong> ${data.category} — ${data.total_amount}р</p>
                 <p class="month-txt"><strong>Самая крупная трата за месяц:</strong> ${data.expense_name}
                 (${data.category}) — ${data.total_amount_expanse_name}р</p>`;
        })
        .catch(err => {
            console.error(err);
            alert('Произошла ошибка при выполнении запроса.');
        });
}

/* ---------- Селекторы/кнопки, завязанные на месяц ---------- */
$('#category-select').addEventListener('change', e => {
    const month = $('#month-input').value;
    const category = e.target.value;
    if (!month || !category) {
        $('#category-stat-output').innerHTML = '';
        return;
    }
    fetchCategoryStats(month.split('-')[1], category);
});

$('#month-submit').addEventListener('click', () => {
    const monthValue = $('#month-input').value;
    if (!monthValue) {
        alert('Пожалуйста, выберите месяц.');
        return;
    }
    fetchMostExpensiveCategory(monthValue);
    updateCategoriesForMonth(monthValue);

    $('#category-select').value = '';
    $('#category-stat-output').innerHTML = '';
});

/* Текущий месяц при загрузке */
document.addEventListener('DOMContentLoaded', () => {
    const now = new Date();
    const cur = now.toISOString().slice(0, 7);
    $('#month-input').value = cur;
    fetchMostExpensiveCategory(cur);
});

/* ---------- Добавление новой траты ---------- */
$('.button-input').addEventListener('click', evt => {
    evt.preventDefault();
    const data = {
        expense_name: $('input[name="expense_name"]').value,
        category: $('input[name="category"]').value,
        amount: $('input[name="amount"]').value,
        date: $('input[name="date"]').value
    };
    if (!data.expense_name || !data.category || !data.amount || !data.date) {
        alert('Пожалуйста, заполните все поля!');
        return;
    }
    fetch('/', {
        method: 'POST',
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: new URLSearchParams(data)
    })
        .then(r => r.ok ? location.reload() : alert(`Ошибка: ${r.status}`))
        .catch(err => {
            console.error(err);
            alert('Не удалось отправить данные.');
        });
});

/* ---------- Загрузка и отрисовка всех трат ---------- */
function renderExpenses() {
    fetch('/expenses')
        .then(r => r.json())
        .then(data => {
            const cont = document.querySelector('.monthly-statistics');
            cont.innerHTML = '';                       // очищаем старый вывод

            data.forEach(expense => {
                /* --- разметка --- */
                const div = document.createElement('div');
                div.className = 'el-inf-db';
                div.dataset.id = expense._id['$oid'];

                const txtBlock = document.createElement('div');
                txtBlock.className = 'div-txt';

                const btnBlock = document.createElement('div');
                btnBlock.className = 'div-btn';

                const dateCat = document.createElement('div');
                dateCat.className = 'date-cat';

                const spanDate = document.createElement('span');
                spanDate.className = 'mongodb-info';
                spanDate.textContent = expense.date;

                const spanCat = document.createElement('span');
                spanCat.className = 'mongodb-info-cat';
                spanCat.textContent = `${expense.expense_name} | ${expense.category}`;

                const spanAmt = document.createElement('span');
                spanAmt.className = 'mongodb-info';
                spanAmt.textContent = `${expense.amount}р`;

                const btnEdit = document.createElement('button');
                btnEdit.className = 'button-edit';
                const btnDelete = document.createElement('button');
                btnDelete.className = 'button-delete';

                const imgEdit = document.createElement('img');
                imgEdit.src = '/static/img/edit.png';
                const imgDelete = document.createElement('img');
                imgDelete.src = '/static/img/delete.png';

                /* --- сборка DOM --- */
                cont.appendChild(div);
                div.appendChild(txtBlock);
                div.appendChild(btnBlock);

                dateCat.appendChild(spanDate);
                dateCat.appendChild(spanCat);
                txtBlock.appendChild(dateCat);
                txtBlock.appendChild(spanAmt);

                btnBlock.appendChild(btnEdit);
                btnBlock.appendChild(btnDelete);
                btnEdit.appendChild(imgEdit);
                btnDelete.appendChild(imgDelete);

                /* ---- НОВОЕ: обработчики редактирования и удаления ---- */

                // Удаление
                btnDelete.addEventListener('click', () => {
                    if (!confirm('Удалить запись?')) return;
                    fetch(`/expenses/${div.dataset.id}`, {method: 'DELETE'})
                        .then(r => r.ok ? div.remove() :
                            alert(`Ошибка удаления: ${r.status}`))
                        .catch(err => {
                            console.error(err);
                            alert('Ошибка при удалении.');
                        });
                });

                // Редактирование
                btnEdit.addEventListener('click', () => {
                    const newName = prompt('Новое название', expense.expense_name);
                    if (newName === null) return;
                    const newCat = prompt('Категория', expense.category);
                    if (newCat === null) return;
                    const newAmt = prompt('Сумма', expense.amount);
                    if (newAmt === null) return;
                    const newDate = prompt('Дата (YYYY-MM-DD)', expense.date);
                    if (newDate === null) return;

                    fetch(`/expenses/${div.dataset.id}`, {
                        method: 'PUT',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            expense_name: newName,
                            category: newCat,
                            amount: newAmt,
                            date: newDate
                        })
                    })
                        .then(r => r.ok ? location.reload() :
                            alert(`Ошибка изменения: ${r.status}`))
                        .catch(err => {
                            console.error(err);
                            alert('Ошибка при изменении.');
                        });
                });
            });
        })
        .catch(console.error);
}

renderExpenses();
