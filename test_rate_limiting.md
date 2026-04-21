# Тестирование Rate Limiting

## Цель
Проверить, что защита от brute-force атак работает корректно для критических endpoints.

## Предварительные требования

1. **Запущен Redis** (для хранения счётчиков):
```bash
docker run -d -p 6379:6379 --name redis redis:latest
```

2. **Установлены зависимости**:
```bash
cd /workspace/backend/api-gateway
pip install -r requirements.txt
```

3. **Запущен API Gateway**:
```bash
cd /workspace/backend
uvicorn api-gateway.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## ТЕСТ 1: Проверка лимита на /api/auth/login (5 запросов в минуту)

### Описание
После 5 попыток входа в течение минуты должен вернуться статус 429.

### Команда для тестирования
```bash
echo "=== ТЕСТ 1: Rate limiting на login endpoint ==="
for i in {1..8}; do
    echo "Запрос #$i:"
    curl -s -w "\nHTTP Status: %{http_code}\n" \
         -X POST http://localhost:8000/api/auth/login \
         -H "Content-Type: application/json" \
         -d '{"email":"test@test.com","password":"wrong_password"}'
    echo "---"
done
```

### Ожидаемый результат
- Запросы 1-5: Возвращается ответ от сервиса (401 Unauthorized или другой)
- Запросы 6-8: Возвращается **429 Too Many Requests** с сообщением:
```json
{"detail": "Слишком много запросов. Попробуйте позже."}
```

---

## ТЕСТ 2: Проверка лимита на /api/auth/forgot-password (3 запроса в час)

### Описание
После 3 запросов сброса пароля в течение часа должен вернуться статус 429.

### Команда для тестирования
```bash
echo "=== ТЕСТ 2: Rate limiting на forgot-password endpoint ==="
for i in {1..5}; do
    echo "Запрос #$i:"
    curl -s -w "\nHTTP Status: %{http_code}\n" \
         -X POST http://localhost:8000/api/auth/forgot-password \
         -H "Content-Type: application/json" \
         -d '{"email":"test@test.com"}'
    echo "---"
done
```

### Ожидаемый результат
- Запросы 1-3: Возвращается ответ от сервиса (200 OK или другой)
- Запросы 4-5: Возвращается **429 Too Many Requests**

---

## ТЕСТ 3: Проверка лимита на /api/auth/reset-password (5 запросов за 5 минут)

### Описание
После 5 попыток установки пароля за 5 минут должен вернуться статус 429.

### Команда для тестирования
```bash
echo "=== ТЕСТ 3: Rate limiting на reset-password endpoint ==="
for i in {1..8}; do
    echo "Запрос #$i:"
    curl -s -w "\nHTTP Status: %{http_code}\n" \
         -X POST http://localhost:8000/api/auth/reset-password \
         -H "Content-Type: application/json" \
         -d '{"token":"fake-token","password":"new_password123"}'
    echo "---"
done
```

### Ожидаемый результат
- Запросы 1-5: Возвращается ответ от сервиса (400 Bad Request или другой)
- Запросы 6-8: Возвращается **429 Too Many Requests**

---

## ТЕСТ 4: Проверка, что другие endpoints НЕ затронуты

### Описание
Endpoints без rate limiting должны работать без ограничений.

### Команда для тестирования
```bash
echo "=== ТЕСТ 4: Проверка endpoint без rate limiting ==="
for i in {1..10}; do
    echo "Запрос #$i:"
    curl -s -w "\nHTTP Status: %{http_code}\n" \
         -X GET http://localhost:8000/api/auth/me \
         -H "Authorization: Bearer fake-token"
    echo "---"
done
```

### Ожидаемый результат
- Все 10 запросов возвращают один и тот же статус (обычно 401 Unauthorized)
- **Никаких 429 ошибок**

---

## ТЕСТ 5: Проверка Redis storage

### Описание
Убедиться, что счётчики хранятся в Redis.

### Команда для тестирования
```bash
# Подключиться к Redis и проверить ключи
docker exec -it redis redis-cli KEYS "*"
```

### Ожидаемый результат
Должны быть ключи вида:
```
LIMITER/<IP-адрес>/api/auth/login
LIMITER/<IP-адрес>/api/auth/forgot-password
LIMITER/<IP-адрес>/api/auth/reset-password
```

---

## ТЕСТ 6: Проверка сброса лимита после истечения окна

### Описание
Подождать 1 минуту и проверить, что лимит на login сбросился.

### Команда для тестирования
```bash
echo "=== ТЕСТ 6: Проверка сброса лимита ==="
echo "Ждём 61 секунду..."
sleep 61
echo "Проверка после ожидания:"
curl -s -w "\nHTTP Status: %{http_code}\n" \
     -X POST http://localhost:8000/api/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"test@test.com","password":"test"}'
```

### Ожидаемый результат
- После ожидания возвращается обычный ответ (не 429)
- Счётчик сбросился

---

## Быстрая проверка (одной командой)

```bash
# Запустить все тесты последовательно
cd /workspace && bash test_rate_limiting.sh
```

---

## Устранение неполадок

### Проблема: Все запросы возвращают 429 сразу
**Причина:** Лимитеры уже активны из предыдущих тестов.  
**Решение:** Очистить Redis:
```bash
docker exec redis redis-cli FLUSHALL
```

### Проблема: 429 не возвращается никогда
**Причина:** Не запущен Redis или неверный REDIS_URL.  
**Решение:** 
1. Проверить, что Redis запущен: `docker ps | grep redis`
2. Проверить REDIS_URL в .env: `cat /workspace/backend/.env | grep REDIS`

### Проблема: Ошибка импорта slowapi
**Причина:** Не установлена зависимость.  
**Решение:** 
```bash
pip install slowapi==0.1.9
```

---

## Критерии успешного прохождения

- [ ] Тест 1: 429 после 5 запросов на login
- [ ] Тест 2: 429 после 3 запросов на forgot-password
- [ ] Тест 3: 429 после 5 запросов на reset-password
- [ ] Тест 4: Нет 429 на endpoints без rate limiting
- [ ] Тест 5: Ключи видны в Redis
- [ ] Тест 6: Лимит сбрасывается после истечения окна
- [ ] Сообщение об ошибке на русском языке

---

## Примечания

1. **IP-адрес для тестирования:** Все запросы с localhost имеют IP `127.0.0.1`, поэтому лимиты считаются для этого адреса.

2. **Окна времени:**
   - login: 1 минута
   - forgot-password: 1 час (для теста можно временно уменьшить)
   - reset-password: 5 минут

3. **Production настройка:** В продакшене рекомендуется использовать более строгие лимиты и добавить исключение для доверенных IP-адресов.
