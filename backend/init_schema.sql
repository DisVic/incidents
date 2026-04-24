-- Создаём таблицы
CREATE TABLE roles (id UUID PRIMARY KEY, name VARCHAR(50) UNIQUE NOT NULL, description TEXT);
CREATE TABLE priorities (id UUID PRIMARY KEY, name VARCHAR(50) UNIQUE NOT NULL, level INTEGER NOT NULL, color VARCHAR(20));
CREATE TABLE sla_policies (id UUID PRIMARY KEY, priority_id UUID UNIQUE NOT NULL REFERENCES priorities(id), resolution_hours INTEGER NOT NULL, description TEXT);

-- Вставляем роли
INSERT INTO roles VALUES 
('00000000-0000-0000-0000-000000000001', 'User', 'Обычный пользователь'),
('00000000-0000-0000-0000-000000000002', 'Executor', 'Исполнитель инцидентов'),
('00000000-0000-0000-0000-000000000003', 'Manager', 'Руководитель'),
('00000000-0000-0000-0000-000000000004', 'Admin', 'Администратор системы');

-- Вставляем приоритеты
INSERT INTO priorities VALUES
('20000000-0000-0000-0000-000000000001', 'Низкий', 1, '#6B7280'),
('20000000-0000-0000-0000-000000000002', 'Средний', 2, '#3B82F6'),
('20000000-0000-0000-0000-000000000003', 'Высокий', 3, '#F59E0B'),
('20000000-0000-0000-0000-000000000004', 'Критический', 4, '#EF4444');

-- Вставляем SLA-политики (часы)
INSERT INTO sla_policies VALUES
(gen_random_uuid(), '20000000-0000-0000-0000-000000000001', 72, 'Низкий - 72 часа (3 дня)'),
(gen_random_uuid(), '20000000-0000-0000-0000-000000000002', 24, 'Средний - 24 часа (1 день)'),
(gen_random_uuid(), '20000000-0000-0000-0000-000000000003', 8, 'Высокий - 8 часов'),
(gen_random_uuid(), '20000000-0000-0000-0000-000000000004', 4, 'Критический - 4 часа');
