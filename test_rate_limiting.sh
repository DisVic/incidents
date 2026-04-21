#!/bin/bash

echo "=============================================="
echo "  ТЕСТИРОВАНИЕ RATE LIMITING"
echo "=============================================="
echo ""

# Проверка доступности API Gateway
echo "Проверка доступности API Gateway..."
if ! curl -s http://localhost:8000/docs > /dev/null; then
    echo "❌ API Gateway недоступен на http://localhost:8000"
    echo "Запустите: cd /workspace/backend && uvicorn api-gateway.main:app --host 0.0.0.0 --port 8000"
    exit 1
fi
echo "✓ API Gateway доступен"
echo ""

# ТЕСТ 1
echo "=============================================="
echo "  ТЕСТ 1: Login endpoint (5 запросов/мин)"
echo "=============================================="
for i in {1..7}; do
    HTTP_CODE=$(curl -s -o /tmp/response.json -w "%{http_code}" \
         -X POST http://localhost:8000/api/auth/login \
         -H "Content-Type: application/json" \
         -d '{"email":"test@test.com","password":"wrong"}')
    
    if [ "$HTTP_CODE" == "429" ]; then
        echo "Запрос #$i: HTTP $HTTP_CODE ✓ (Rate Limit сработал!)"
        cat /tmp/response.json | python3 -m json.tool 2>/dev/null || cat /tmp/response.json
    else
        echo "Запрос #$i: HTTP $HTTP_CODE"
    fi
done
echo ""

# ТЕСТ 2
echo "=============================================="
echo "  ТЕСТ 2: Forgot Password (3 запроса/час)"
echo "=============================================="
for i in {1..5}; do
    HTTP_CODE=$(curl -s -o /tmp/response.json -w "%{http_code}" \
         -X POST http://localhost:8000/api/auth/forgot-password \
         -H "Content-Type: application/json" \
         -d '{"email":"test@test.com"}')
    
    if [ "$HTTP_CODE" == "429" ]; then
        echo "Запрос #$i: HTTP $HTTP_CODE ✓ (Rate Limit сработал!)"
        cat /tmp/response.json | python3 -m json.tool 2>/dev/null || cat /tmp/response.json
    else
        echo "Запрос #$i: HTTP $HTTP_CODE"
    fi
done
echo ""

# ТЕСТ 3
echo "=============================================="
echo "  ТЕСТ 3: Reset Password (5 запросов/5 мин)"
echo "=============================================="
for i in {1..7}; do
    HTTP_CODE=$(curl -s -o /tmp/response.json -w "%{http_code}" \
         -X POST http://localhost:8000/api/auth/reset-password \
         -H "Content-Type: application/json" \
         -d '{"token":"fake-token","password":"new_pass123"}')
    
    if [ "$HTTP_CODE" == "429" ]; then
        echo "Запрос #$i: HTTP $HTTP_CODE ✓ (Rate Limit сработал!)"
        cat /tmp/response.json | python3 -m json.tool 2>/dev/null || cat /tmp/response.json
    else
        echo "Запрос #$i: HTTP $HTTP_CODE"
    fi
done
echo ""

echo "=============================================="
echo "  ТЕСТИРОВАНИЕ ЗАВЕРШЕНО"
echo "=============================================="
echo ""
echo "Для очистки счётчиков Redis выполните:"
echo "  docker exec redis redis-cli FLUSHALL"
echo ""
