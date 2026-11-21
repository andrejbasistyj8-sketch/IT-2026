/* ДокументКонтроль: клієнт без зовнішніх бібліотек та CDN. */
'use strict';

const $ = (selector) => document.querySelector(selector);
const tbody = $('#documentsBody');
const dialog = $('#documentDialog');
const form = $('#documentForm');
const statusColors = {
  'Новий': '#2dbda6',
  'В роботі': '#f4b455',
  'Виконано': '#6f8aff'
};
let documents = [];
let editingId = null;
let listRequest = 0;
let toastTimer;

function localToday() {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

function humanDate(iso) {
  if (!iso) return '—';
  const [year, month, day] = iso.split('-');
  return `${day}.${month}.${year}`;
}

function showToast(message, error = false) {
  const toast = $('#toast');
  toast.textContent = message;
  toast.classList.toggle('error', error);
  toast.classList.add('visible');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('visible'), 3500);
}

async function api(url, options = {}) {
  let response;
  try {
    response = await fetch(url, { headers: { 'Accept': 'application/json', ...options.headers }, ...options });
  } catch (_error) {
    throw new Error('Немає з’єднання із сервером. Перевірте запуск застосунку.');
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error((data && data.error) || `Помилка сервера (${response.status}).`);
  }
  return data;
}

function filterParams() {
  const values = {
    q: $('#searchInput').value.trim(),
    status: $('#statusFilter').value,
    category: $('#categoryFilter').value,
    date_from: $('#dateFrom').value,
    date_to: $('#dateTo').value
  };
  return new URLSearchParams(Object.entries(values).filter(([, value]) => Boolean(value)));
}

function setEmpty(message) {
  tbody.replaceChildren();
  const row = document.createElement('tr');
  const cell = document.createElement('td');
  cell.colSpan = 7;
  cell.className = 'empty-state';
  cell.textContent = message;
  row.append(cell);
  tbody.append(row);
}

function td(text, className = '') {
  const cell = document.createElement('td');
  cell.textContent = text == null ? '' : String(text);
  if (className) cell.className = className;
  return cell;
}

function makeBadge(text, cls, baseClass) {
  const span = document.createElement('span');
  span.className = `${baseClass} ${cls}`;
  span.textContent = text;
  return span;
}

function renderDocuments(items) {
  tbody.replaceChildren();
  $('#resultCount').textContent = `${items.length} записів`;
  if (!items.length) {
    setEmpty('Документів за обраними фільтрами немає. Додайте перший документ або змініть фільтри.');
    return;
  }
  const fragment = document.createDocumentFragment();
  for (const item of items) {
    const row = document.createElement('tr');
    row.append(td(item.registration_number, 'doc-number'));
    const titleCell = document.createElement('td');
    const name = document.createElement('div');
    name.className = 'doc-title';
    name.textContent = item.title;
    name.title = item.title;
    const category = document.createElement('div');
    category.className = 'doc-subtitle';
    category.textContent = item.category;
    titleCell.append(name, category);
    row.append(titleCell);
    row.append(td(item.sender));
    row.append(td(humanDate(item.received_date)));
    const status = document.createElement('td');
    status.append(makeBadge(item.status, `status-${item.status.replaceAll(' ', '-')}`, 'status-badge'));
    row.append(status);
    const priority = document.createElement('td');
    priority.append(makeBadge(item.priority, `priority-${item.priority}`, 'priority-badge'));
    row.append(priority);
    const actionsCell = document.createElement('td');
    const buttons = document.createElement('div');
    buttons.className = 'row-buttons';
    const editButton = document.createElement('button');
    editButton.type = 'button';
    editButton.className = 'row-btn';
    editButton.title = 'Редагувати';
    editButton.setAttribute('aria-label', `Редагувати ${item.registration_number}`);
    editButton.textContent = '✎';
    editButton.addEventListener('click', () => openEdit(item));
    const deleteButton = document.createElement('button');
    deleteButton.type = 'button';
    deleteButton.className = 'row-btn delete';
    deleteButton.title = 'Видалити';
    deleteButton.setAttribute('aria-label', `Видалити ${item.registration_number}`);
    deleteButton.textContent = '×';
    deleteButton.addEventListener('click', () => removeDocument(item));
    buttons.append(editButton, deleteButton);
    actionsCell.append(buttons);
    row.append(actionsCell);
    fragment.append(row);
  }
  tbody.append(fragment);
}

async function loadDocuments() {
  const currentRequest = ++listRequest;
  try {
    const items = await api(`/api/documents?${filterParams().toString()}`);
    if (currentRequest !== listRequest) return;
    documents = items;
    renderDocuments(items);
  } catch (error) {
    if (currentRequest !== listRequest) return;
    $('#resultCount').textContent = 'Немає даних';
    setEmpty(error.message);
    showToast(error.message, true);
  }
}

function buildDonut(stats) {
  const total = stats.totals.total || 0;
  const legend = $('#statusLegend');
  legend.replaceChildren();
  let used = 0;
  const stops = [];
  for (const name of ['Новий', 'В роботі', 'Виконано']) {
    const count = stats.statuses.find((entry) => entry.name === name)?.count || 0;
    const start = total ? (used / total * 100) : 0;
    used += count;
    const end = total ? (used / total * 100) : 0;
    stops.push(`${statusColors[name]} ${start}% ${end}%`);
    const line = document.createElement('div');
    line.className = 'legend-line';
    const dot = document.createElement('span');
    dot.className = 'legend-dot';
    dot.style.backgroundColor = statusColors[name];
    const label = document.createElement('span');
    label.textContent = name;
    const value = document.createElement('span');
    value.className = 'legend-count';
    value.textContent = count;
    line.append(dot, label, value);
    legend.append(line);
  }
  $('#statusDonut').style.background = total
    ? `conic-gradient(${stops.join(', ')})`
    : '#e9eef7';
  $('#statusDonut').setAttribute('aria-label', `Розподіл ${total} документів за статусами`);
  $('#donutTotal').textContent = total;
}

function buildCategories(categories) {
  const root = $('#categoryChart');
  root.replaceChildren();
  if (!categories.length) {
    root.append(textNode('Немає даних для аналізу.'));
    return;
  }
  const max = Math.max(1, ...categories.map((x) => x.count));
  for (const item of categories) {
    const row = document.createElement('div');
    row.className = 'category-row';
    const name = document.createElement('span');
    name.className = 'name';
    name.textContent = item.name;
    name.title = item.name;
    const track = document.createElement('div');
    track.className = 'track';
    const fill = document.createElement('div');
    fill.className = 'fill';
    fill.style.width = `${(item.count / max) * 100}%`;
    track.append(fill);
    const count = document.createElement('span');
    count.className = 'count';
    count.textContent = item.count;
    row.append(name, track, count);
    root.append(row);
  }
}

function textNode(value) {
  const p = document.createElement('p');
  p.className = 'muted';
  p.textContent = value;
  return p;
}

function buildMonths(months) {
  const root = $('#monthlyChart');
  root.replaceChildren();
  if (!months.length) {
    root.append(textNode('Після реєстрації документів тут з’явиться динаміка.'));
    return;
  }
  const max = Math.max(1, ...months.map((x) => x.count));
  const monthsShort = ['січ', 'лют', 'бер', 'кві', 'тра', 'чер', 'лип', 'сер', 'вер', 'жов', 'лис', 'гру'];
  for (const item of months) {
    const col = document.createElement('div');
    col.className = 'month-column';
    const count = document.createElement('div');
    count.className = 'month-count';
    count.textContent = item.count;
    const bar = document.createElement('div');
    bar.className = 'month-bar';
    bar.style.height = `${Math.max(5, item.count / max * 130)}px`;
    const label = document.createElement('div');
    label.className = 'month-label';
    const monthNumber = Number(item.month.split('-')[1]);
    label.textContent = monthsShort[monthNumber - 1] || item.month;
    col.title = `${item.month}: ${item.count} документів`;
    col.append(count, bar, label);
    root.append(col);
  }
}

async function loadStats() {
  try {
    const stats = await api('/api/stats');
    $('#statTotal').textContent = stats.totals.total;
    $('#statNew').textContent = stats.totals.new;
    $('#statProgress').textContent = stats.totals.in_progress;
    $('#statOverdue').textContent = stats.totals.overdue;
    buildDonut(stats);
    buildCategories(stats.categories);
    buildMonths(stats.months);
  } catch (error) {
    showToast(error.message, true);
    $('#categoryChart').replaceChildren(textNode('Немає з’єднання з базою даних.'));
    $('#monthlyChart').replaceChildren(textNode('Немає з’єднання з базою даних.'));
  }
}

function openCreate() {
  editingId = null;
  form.reset();
  form.elements.received_date.value = localToday();
  $('#dialogTitle').textContent = 'Новий документ';
  $('#saveButton').textContent = 'Зареєструвати документ';
  $('#formError').hidden = true;
  dialog.showModal();
  form.elements.registration_number.focus();
}

function openEdit(item) {
  editingId = item.id;
  form.reset();
  for (const field of Object.keys(item)) {
    if (form.elements[field]) form.elements[field].value = item[field] || '';
  }
  $('#dialogTitle').textContent = 'Редагування документа';
  $('#saveButton').textContent = 'Зберегти зміни';
  $('#formError').hidden = true;
  dialog.showModal();
}

async function saveDocument(event) {
  event.preventDefault();
  if (!form.reportValidity()) return;
  const data = Object.fromEntries(new FormData(form));
  const errorBox = $('#formError');
  errorBox.hidden = true;
  if (data.due_date && data.due_date < data.received_date) {
    errorBox.textContent = 'Строк виконання не може бути раніше дати надходження.';
    errorBox.hidden = false;
    return;
  }
  const saveButton = $('#saveButton');
  saveButton.disabled = true;
  try {
    await api(editingId === null ? '/api/documents' : `/api/documents/${editingId}`, {
      method: editingId === null ? 'POST' : 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    dialog.close();
    showToast(editingId === null ? 'Документ зареєстровано.' : 'Зміни збережено.');
    await Promise.all([loadDocuments(), loadStats()]);
  } catch (error) {
    errorBox.textContent = error.message;
    errorBox.hidden = false;
  } finally {
    saveButton.disabled = false;
  }
}

async function removeDocument(item) {
  if (!window.confirm(`Видалити документ ${item.registration_number}? Цю дію неможливо скасувати.`)) return;
  try {
    await api(`/api/documents/${item.id}`, { method: 'DELETE' });
    showToast('Документ видалено.');
    await Promise.all([loadDocuments(), loadStats()]);
  } catch (error) {
    showToast(error.message, true);
  }
}

function init() {
  $('#todayLabel').textContent = new Intl.DateTimeFormat('uk-UA', {
    day: 'numeric', month: 'long', year: 'numeric'
  }).format(new Date());
  $('#addButton').addEventListener('click', openCreate);
  $('#closeDialog').addEventListener('click', () => dialog.close());
  $('#cancelDialog').addEventListener('click', () => dialog.close());
  form.addEventListener('submit', saveDocument);
  dialog.addEventListener('click', (event) => {
    if (event.target === dialog) dialog.close();
  });
  let searchTimer;
  $('#searchInput').addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(loadDocuments, 250);
  });
  for (const name of ['statusFilter', 'categoryFilter', 'dateFrom', 'dateTo']) {
    $(`#${name}`).addEventListener('change', loadDocuments);
  }
  $('#resetFilters').addEventListener('click', () => {
    for (const field of ['searchInput', 'statusFilter', 'categoryFilter', 'dateFrom', 'dateTo']) {
      $(`#${field}`).value = '';
    }
    loadDocuments();
  });
  $('#exportButton').addEventListener('click', () => {
    window.location.assign(`/api/export.csv?${filterParams().toString()}`);
  });
  document.querySelectorAll('.side-nav a').forEach((link) => {
    link.addEventListener('click', () => {
      document.querySelectorAll('.side-nav a').forEach((item) => item.classList.remove('active'));
      link.classList.add('active');
    });
  });
  loadDocuments();
  loadStats();
}

document.addEventListener('DOMContentLoaded', init);
