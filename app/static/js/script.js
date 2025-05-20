/* ---------- Вспомогательные утилиты ---------- */
const $ = sel => document.querySelector(sel);

/* ---------- Инициализация дат и размеров ---------- */
$('#date').value = new Date().toISOString().split('T')[0];
const inputText = $('.input-text');
const inputDate = $('.input-date');
const btnAdd = $('.button-add');
const inputMonth = $('.input-month');
const selectAdd = $('.select-add');

inputDate.style.width = getComputedStyle(inputText).width;
inputMonth.style.height = getComputedStyle(btnAdd).height;
selectAdd.style.height = getComputedStyle(btnAdd).height;

/* ---------- Статистика «самая затратная категория» ---------- */
function fetchMostExpensiveCategory(monthValue) {
    const month = monthValue.split('-')[1];
    fetch(`/categories/top?month=${month}`)
        .then(r => {
            const out = $('#monthly-info-output');
            if (r.status === 204) {
                out.innerHTML = `<p class="month-txt">Нет данных за выбранный месяц.</p>`;
                return null;
            }
            if (!r.ok) throw new Error(`Ошибка: ${r.status}`);
            return r.json();
        })
        .then(data => {
            if (!data) return;
            $('#monthly-info-output').innerHTML =
                `<p class="month-txt">
           <strong>Самая затратная категория:</strong> ${data.category} — ${data.total_amount}р
         </p>
         <p class="month-txt">
           <strong>Самая крупная трата за месяц в этой категории:</strong><br>
           ${data.expense_name} — ${data.amount}р (${data.date})
         </p>`;
        })
        .catch(err => {
            console.error(err);
            alert('Ошибка при получении общей статистики.');
        });
}

/* ---------- Загрузка категорий за месяц ---------- */
function updateCategoriesForMonth(monthValue) {
    const month = monthValue.split('-')[1];
    const select = $('#category-select');
    // очистим старые опции, оставив только дефолтную
    select.innerHTML = `<option value="">Выберите категорию</option>`;
    $('#category-stat-output').innerHTML = '';

    fetch(`/categories?month=${month}`)
        .then(r => {
            if (!r.ok) throw new Error(`Ошибка: ${r.status}`);
            return r.json();
        })
        .then(cats => {
            cats.forEach(cat => {
                const opt = document.createElement('option');
                opt.value = cat;
                opt.textContent = cat;
                select.appendChild(opt);
            });
        })
        .catch(err => {
            console.error('Ошибка при загрузке категорий:', err);
        });
}

/* ---------- Статистика по выбранной категории ---------- */
function fetchCategoryStats(monthValue, category) {
    const month = monthValue.split('-')[1];
    fetch(`/categories/${encodeURIComponent(category)}/expenses?month=${month}&biggest=true`)
        .then(r => {
            const out = $('#category-stat-output');
            if (r.status === 204) {
                out.innerHTML = `<p class="month-txt">Нет данных по категории за выбранный месяц.</p>`;
                return null;
            }
            if (!r.ok) throw new Error(`Ошибка: ${r.status}`);
            return r.json();
        })
        .then(data => {
            if (!data) return;
            $('#category-stat-output').innerHTML =
                `<p class="month-txt">
           <strong>Самая крупная трата в категории "${category}":</strong><br>
           ${data.expense_name} — ${data.amount}р (${data.date})
         </p>`;
        })
        .catch(err => {
            console.error(err);
            alert('Ошибка при получении статистики по категории.');
        });
}

/* ---------- Обработчики событий ---------- */
$('#month-submit').addEventListener('click', () => {
    const mv = $('#month-input').value;
    if (!mv) {
        alert('Пожалуйста, выберите месяц.');
        return;
    }
    fetchMostExpensiveCategory(mv);
    updateCategoriesForMonth(mv);
});

$('#category-select').addEventListener('change', e => {
    const mv = $('#month-input').value;
    const cat = e.target.value;
    if (!mv || !cat) {
        $('#category-stat-output').innerHTML = '';
        return;
    }
    fetchCategoryStats(mv, cat);
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
    fetch('/expenses', {
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

/* ---------- Рендер списка трат ---------- */
function renderExpenses() {
    fetch('/expenses')
        .then(r => r.json())
        .then(data => {
            const cont = document.querySelector('.monthly-statistics');
            cont.innerHTML = '';
            data.forEach(exp => {
                const div = document.createElement('div');
                div.className = 'el-inf-db';
                div.dataset.id = exp._id['$oid'];

                const txt = document.createElement('div');
                txt.className = 'div-txt';
                txt.innerHTML = `<span class="mongodb-info">${exp.date}</span>
                         <span class="mongodb-info-cat">${exp.expense_name} | ${exp.category}</span>
                         <span class="mongodb-info">${exp.amount}р</span>`;

                const btns = document.createElement('div');
                btns.className = 'div-btn';
                btns.innerHTML = `
          <button class="button-edit"><img src="/static/img/edit.png" alt="edit"></button>
          <button class="button-delete"><img src="/static/img/delete.png" alt="delete"></button>
        `;

                div.append(txt, btns);
                cont.append(div);

                // обработчики
                btns.querySelector('.button-delete').addEventListener('click', () => {
                    if (!confirm('Удалить запись?')) return;
                    fetch(`/expenses/${div.dataset.id}`, {method: 'DELETE'})
                        .then(r => r.ok ? div.remove() : alert(`Ошибка удаления: ${r.status}`))
                        .catch(err => {
                            console.error(err);
                            alert('Ошибка при удалении.');
                        });
                });
                btns.querySelector('.button-edit').addEventListener('click', () => {
                    const newName = prompt('Новое название', exp.expense_name);
                    if (newName === null) return;
                    const newCat = prompt('Категория', exp.category);
                    if (newCat === null) return;
                    const newAmt = prompt('Сумма', exp.amount);
                    if (newAmt === null) return;
                    const newDate = prompt('Дата (YYYY-MM-DD)', exp.date);
                    if (newDate === null) return;

                    fetch(`/expenses/${div.dataset.id}`, {
                        method: 'PUT',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({expense_name: newName, category: newCat, amount: newAmt, date: newDate})
                    })
                        .then(r => r.ok ? location.reload() : alert(`Ошибка изменения: ${r.status}`))
                        .catch(err => {
                            console.error(err);
                            alert('Ошибка при изменении.');
                        });
                });
            });
        })
        .catch(console.error);
}

/* ---------- Инициализация при загрузке страницы ---------- */
document.addEventListener('DOMContentLoaded', () => {
    const now = new Date().toISOString().slice(0, 7);
    $('#month-input').value = now;
    fetchMostExpensiveCategory(now);
    updateCategoriesForMonth(now);
    renderExpenses();
});
