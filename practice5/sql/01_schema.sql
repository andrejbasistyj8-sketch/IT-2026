-- Схема PostgreSQL 16: реєстр документів, індекси та обмеження цілісності.
CREATE TABLE IF NOT EXISTS documents (
    id BIGSERIAL PRIMARY KEY,
    registration_number VARCHAR(50) NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    category VARCHAR(70) NOT NULL DEFAULT 'Інший',
    sender VARCHAR(150) NOT NULL,
    received_date DATE NOT NULL,
    due_date DATE,
    status VARCHAR(20) NOT NULL DEFAULT 'Новий'
        CHECK (status IN ('Новий', 'В роботі', 'Виконано')),
    priority VARCHAR(20) NOT NULL DEFAULT 'Звичайний'
        CHECK (priority IN ('Низький', 'Звичайний', 'Високий')),
    assignee VARCHAR(150) NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT due_date_valid CHECK (due_date IS NULL OR due_date >= received_date)
);
CREATE INDEX IF NOT EXISTS idx_docs_received ON documents (received_date DESC);
CREATE INDEX IF NOT EXISTS idx_docs_status ON documents (status);
CREATE INDEX IF NOT EXISTS idx_docs_category ON documents (category);
CREATE INDEX IF NOT EXISTS idx_docs_due_date ON documents (due_date)
    WHERE status <> 'Виконано';
