"""
API Gateway - единая точка входа для всех микросервисов

Этот модуль выступает в роли обратного прокси-сервера, который:
- Принимает все входящие запросы от фронтенда
- Перенаправляет их на соответствующие микросервисы
- Возвращает ответы клиенту

Архитектура: все сервисы общаются только через Gateway,
прямые запросы к микросервисам из фронтенда запрещены.
"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, Response
import httpx

from shared import settings

# =============================================================================
# RATE LIMITING - ЗАЩИТА ОТ BRUTE-FORCE АТАК
# =============================================================================
# Slowapi ограничивает количество запросов к критическим endpoints:
# - /auth/login: 5 запросов в минуту (защита от подбора пароля)
# - /auth/forgot-password: 3 запроса в час (защита от спама)
# - /auth/reset-password: 5 запросов за 5 минут (защита от перебора токенов)
#
# Используется Redis для хранения счётчиков (распределённое хранение,
# работает при масштабировании на несколько экземпляров Gateway).
# =============================================================================
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Инициализация лимитера с Redis-backed хранилищем
# key_func=get_remote_address — использует IP-адрес клиента для идентификации
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URL  # Redis URL из настроек
)

# Основное приложение FastAPI
# title/description отображаются в Swagger UI (/docs)
app = FastAPI(
    title="API Gateway",
    version="1.0.0",
    description="API Gateway для микросервисной архитектуры",
)

# Подключаем limiter к приложению
app.state.limiter = limiter

# Обработчик исключения при превышении лимита
# Возвращает понятное сообщение на русском языке со статусом 429
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """
    Глобальный обработчик превышения rate limit.
    
    Вызывается автоматически, когда клиент превышает установленный лимит запросов.
    Возвращает JSON-ответ со статусом 429 Too Many Requests.
    
    Args:
        request: Исходный HTTP-запрос
        exc: Исключение RateLimitExceeded с информацией о лимите
    
    Returns:
        JSONResponse: Ответ с сообщением об ошибке
    """
    return JSONResponse(
        status_code=429,
        content={"detail": "Слишком много запросов. Попробуйте позже."},
        headers={"Retry-After": "60"}  # Подсказка клиенту, когда повторить
    )

# Добавляем стандартный обработчик slowapi
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Настройка CORS (Cross-Origin Resource Sharing)
# Разрешает запросы с фронтенда (порт 5173) к бэкенду (порт 8000)
# allow_origins=["*"] - в продакшене лучше указать конкретный домен
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# КОНФИГУРАЦИЯ МИКРОСЕРВИСОВ
# =============================================================================
# Словарь с адресами всех микросервисов в Docker-сети
# Ключи используются в функциях проксирования для выбора нужного сервиса
# Формат: http://<имя-контейнера>:<порт> - так контейнеры видят друг друга в Docker
SERVICES = {
    "user": "http://user-service:8001",           # Сервис управления пользователями
    "incident": "http://incident-service:8002",   # Сервис управления инцидентами
    "sla": "http://sla-service:8003",             # Сервис SLA-мониторинга
    "notification": "http://notification-service:8004",  # Сервис уведомлений
}


async def proxy_request(service: str, path: str, request: Request) -> Response:
    """
    Универсальная функция проксирования запросов на микросервисы.
    
    Эта функция принимает входящий запрос и пересылает его на нужный микросервис,
    сохраняя метод, заголовки, тело запроса и параметры.
    
    Args:
        service: Ключ сервиса из словаря SERVICES (например, "user", "incident")
        path: Путь endpoint'а внутри микросервиса (например, "/auth/login")
        request: Исходный HTTP-запрос от клиента
    
    Returns:
        Response: Ответ от микросервиса (JSON или бинарные данные)
    
    Raises:
        HTTPException 404: Если сервис не найден в конфигурации
        HTTPException 504: Если микросервис не ответил за 30 секунд
        HTTPException 502: Если произошла ошибка соединения с микросервисом
    """
    # Проверка: существует ли сервис в конфигурации
    if service not in SERVICES:
        raise HTTPException(status_code=404, detail=f"Service {service} not found")
    
    # Формирование полного URL для запроса к микросервису
    url = f"{SERVICES[service]}{path}"
    
    async with httpx.AsyncClient() as client:
        try:
            # Получаем тело запроса (для POST/PUT запросов с данными)
            body = await request.body()
            
            # Копируем заголовки оригинального запроса
            headers = dict(request.headers)
            # Удаляем заголовок "host" - он будет установлен автоматически для целевого сервиса
            headers.pop("host", None)
            
            # Отправляем запрос на микросервис с сохранением всех параметров
            response = await client.request(
                method=request.method,      # GET, POST, PUT, DELETE и т.д.
                url=url,
                content=body,               # Тело запроса (JSON, form-data и т.п.)
                headers=headers,            # Заголовки (авторизация, content-type и др.)
                params=request.query_params,  # Query-параметры (?key=value&...)
                timeout=30.0                # Таймаут ожидания ответа от сервиса
            )
            
            # Проверка типа контента в ответе
            # Это нужно для корректной обработки файлов (аватарки, вложения)
            content_type = response.headers.get("content-type", "")
            if not content_type.startswith("application/json"):
                # Бинарный ответ (файл) - возвращаем как есть
                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    headers=dict(response.headers)
                )
            
            # JSON-ответ - оборачиваем в JSONResponse для правильной сериализации
            return JSONResponse(
                content=response.json() if response.content else {},
                status_code=response.status_code
            )
        except httpx.TimeoutException:
            # Микросервис не ответил за 30 секунд
            raise HTTPException(status_code=504, detail="Service timeout")
        except Exception as e:
            # Другие ошибки соединения (сервис недоступен, ошибка сети и т.п.)
            raise HTTPException(status_code=502, detail=str(e))


# =============================================================================
# МАРШРУТЫ USER SERVICE (СЕРВИС ПОЛЬЗОВАТЕЛЕЙ)
# =============================================================================
# Все маршруты, начинающиеся с /api/auth и /api/users, перенаправляются
# на user-service (порт 8001). Этот сервис отвечает за:
# - Аутентификацию и авторизацию
# - Управление пользователями (CRUD)
# - Управление отделами (departments)
# - Загрузку аватарок

# -----------------------------------------------------------------------------
# RATE LIMITING ДЛЯ КРИТИЧЕСКИХ ENDPOINTS
# -----------------------------------------------------------------------------
# Применяем ограничения к endpoint'ам аутентификации для защиты от brute-force:
# - login: 5 попыток в минуту (защита от подбора пароля)
# - forgot-password: 3 запроса в час (защита от спама)
# - reset-password: 5 попыток за 5 минут (защита от перебора токенов)
# -----------------------------------------------------------------------------

@app.post("/api/auth/login")
@limiter.limit("5/minute")  # 5 попыток входа в минуту с одного IP
async def proxy_auth_login(request: Request):
    """
    Проксирование запроса на вход с rate limiting.
    
    Защита от brute-force атак: после 5 неудачных попыток входа
    в течение минуты дальнейшие запросы блокируются на 1 минуту.
    
    Лимит считается по IP-адресу клиента.
    
    Returns:
        Response: Ответ от user-service или 429 Too Many Requests
    """
    return await proxy_request("user", "/auth/login", request)


@app.post("/api/auth/forgot-password")
@limiter.limit("3/hour")  # 3 запроса сброса пароля в час с одного IP
async def proxy_auth_forgot_password(request: Request):
    """
    Проксирование запроса на сброс пароля с rate limiting.
    
    Защита от спама: не более 3 запросов на сброс пароля в час.
    Это предотвращает массовую рассылку писем со ссылками для сброса.
    
    Лимит считается по IP-адресу клиента.
    
    Returns:
        Response: Ответ от user-service или 429 Too Many Requests
    """
    return await proxy_request("user", "/auth/forgot-password", request)


@app.post("/api/auth/reset-password")
@limiter.limit("5/5minutes")  # 5 попыток установки пароля за 5 минут
async def proxy_auth_reset_password(request: Request):
    """
    Проксирование запроса на установку нового пароля с rate limiting.
    
    Защита от перебора токенов: не более 5 попыток установки пароля
    за 5 минут. Это предотвращает brute-force атаку на токен сброса.
    
    Лимит считается по IP-адресу клиента.
    
    Returns:
        Response: Ответ от user-service или 429 Too Many Requests
    """
    return await proxy_request("user", "/auth/reset-password", request)


@app.api_route("/api/auth/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_auth(path: str, request: Request):
    """
    Проксирование всех остальных запросов аутентификации.
    
    Этот маршрут обрабатывает все auth-запросы, кроме тех,
    для которых определены отдельные обработчики выше:
    - POST /login (обработан отдельно с rate limiting)
    - POST /forgot-password (обработан отдельно с rate limiting)
    - POST /reset-password (обработан отдельно с rate limiting)
    
    Примеры маршрутов:
    - POST /api/auth/logout       - Выход из системы
    - POST /api/auth/refresh      - Обновление токена
    - GET  /api/auth/me           - Получение данных текущего пользователя
    
    Args:
        path: Остаток пути после /api/auth/ (например, "logout", "refresh")
        request: Исходный HTTP-запрос
    
    Returns:
        Response: Ответ от user-service
    """
    return await proxy_request("user", f"/auth/{path}", request)


@app.api_route("/api/users/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
@app.api_route("/api/users", methods=["GET", "POST"])
async def proxy_users(request: Request, path: str = ""):
    """
    Проксирование запросов к ресурсу пользователей.
    
    Два декоратора @app.api_route нужны для обработки двух случаев:
    1. /api/users (без path) - список пользователей или создание нового
    2. /api/users/{id} (с path) - операции с конкретным пользователем
    
    Примеры маршрутов:
    - GET    /api/users              - Получить список всех пользователей
    - POST   /api/users              - Создать нового пользователя
    - GET    /api/users/123          - Получить пользователя по ID
    - PUT    /api/users/123          - Обновить данные пользователя
    - DELETE /api/users/123          - Удалить пользователя
    """
    return await proxy_request("user", f"/users/{path}" if path else "/users", request)


@app.api_route("/api/users/{user_id}/avatar", methods=["POST"])
async def proxy_user_avatar(user_id: str, request: Request):
    """
    Проксирование загрузки аватарки пользователя.
    
    Выделен в отдельный маршрут, чтобы корректно обрабатывать
    multipart/form-data запросы с файлами.
    
    Пример:
    - POST /api/users/123/avatar    - Загрузить аватарку для пользователя 123
    
    Args:
        user_id: ID пользователя (из URL)
        request: Запрос с файлом аватарки в теле
    """
    return await proxy_request("user", f"/users/{user_id}/avatar", request)


@app.api_route("/api/departments/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
@app.api_route("/api/departments", methods=["GET", "POST"])
async def proxy_departments(request: Request, path: str = ""):
    """
    Проксирование запросов к ресурсу отделов.
    
    Отделы используются для группировки пользователей и фильтрации инцидентов.
    
    Примеры маршрутов:
    - GET    /api/departments         - Получить список всех отделов
    - POST   /api/departments         - Создать новый отдел
    - GET    /api/departments/it      - Получить отдел по коду
    - PUT    /api/departments/it      - Обновить отдел
    - DELETE /api/departments/it      - Удалить отдел
    """
    return await proxy_request("user", f"/departments/{path}" if path else "/departments", request)


# =============================================================================
# МАРШРУТЫ INCIDENT SERVICE (СЕРВИС ИНЦИДЕНТОВ)
# =============================================================================
# Сервис инцидентов отвечает за:
# - Создание и управление инцидентами (заявками)
# - Комментарии к инцидентам
# - Вложения (файлы) к комментариям
# - Справочники (категории, статусы, приоритеты)
# - Отчёты и аналитика для дашборда
#
# ВАЖНО: В FastAPI более специфичные маршруты должны быть объявлены
# ДО общих маршрутов с {path:path}. Иначе общий маршрут перехватит запрос первым.

# -----------------------------------------------------------------------------
# ОТЧЁТЫ И ДАШБОРД
# -----------------------------------------------------------------------------
# Все endpoint'ы для главной страницы дашборда и аналитических отчётов.
# Возвращают статистику в формате JSON для отображения графиков и метрик.

@app.api_route("/api/reports/dashboard", methods=["GET"])
async def proxy_dashboard(request: Request):
    """
    Данные для главной страницы дашборда.
    
    Возвращает сводную статистику:
    - Количество инцидентов по статусам
    - Просроченные инциденты
    - Последние активности
    """
    return await proxy_request("incident", "/reports/dashboard", request)

@app.api_route("/api/reports/sla-stats", methods=["GET"])
async def proxy_sla_stats(request: Request):
    """
    Статистика по SLA (Service Level Agreement).
    
    Возвращает процент инцидентов, обработанных в срок,
    по различным временным интервалам.
    """
    return await proxy_request("incident", "/reports/sla-stats", request)

@app.api_route("/api/reports/overdue-incidents", methods=["GET"])
async def proxy_overdue_incidents(request: Request):
    """
    Список просроченных инцидентов.
    
    Инциденты, у которых дедлайн прошёл, но статус не "Закрыт".
    """
    return await proxy_request("incident", "/reports/overdue-incidents", request)

@app.api_route("/api/reports/executor-overdue-stats", methods=["GET"])
async def proxy_executor_overdue_stats(request: Request):
    """
    Статистика просрочек по исполнителям.
    
    Используется для отчёта о нагрузке и дисциплине исполнителей.
    """
    return await proxy_request("incident", "/reports/executor-overdue-stats", request)

@app.api_route("/api/reports/user/{user_id}", methods=["GET"])
async def proxy_user_stats(request: Request, user_id: str):
    """
    Статистика по конкретному пользователю.
    
    Возвращает метрики для карточки пользователя:
    - Количество созданных/назначенных инцидентов
    - Среднее время решения
    - Процент просрочек
    
    Args:
        user_id: ID пользователя из URL
    """
    return await proxy_request("incident", f"/reports/user/{user_id}", request)

@app.api_route("/api/reports/status-stats", methods=["GET"])
async def proxy_status_stats(request: Request):
    """
    Статистика по статусам инцидентов.
    
    Количество инцидентов в каждом статусе (Новый, В работе, На проверке и т.д.).
    """
    return await proxy_request("incident", "/reports/status-stats", request)

@app.api_route("/api/reports/activity", methods=["GET"])
async def proxy_activity(request: Request):
    """
    Лента последних активностей.
    
    История действий: создание инцидентов, комментарии, смена статусов.
    """
    return await proxy_request("incident", "/reports/activity", request)

@app.api_route("/api/reports/executors", methods=["GET"])
async def proxy_executors(request: Request):
    """
    Список исполнителей с краткой статистикой.
    
    Базовая информация для таблицы исполнителей.
    """
    return await proxy_request("incident", "/reports/executors", request)

@app.api_route("/api/reports/executors-detailed", methods=["GET"])
async def proxy_executors_detailed(request: Request):
    """
    Расширенная статистика по исполнителям.
    
    Детальные метрики для анализа эффективности каждого исполнителя.
    """
    return await proxy_request("incident", "/reports/executors-detailed", request)

@app.api_route("/api/reports/departments", methods=["GET"])
async def proxy_departments_report(request: Request):
    """
    Статистика по отделам.
    
    Количество инцидентов и метрики эффективности по каждому отделу.
    """
    return await proxy_request("incident", "/reports/departments", request)

@app.api_route("/api/reports/priorities", methods=["GET"])
async def proxy_priorities_report(request: Request):
    """
    Статистика по приоритетам.
    
    Распределение инцидентов по уровням приоритета (Низкий, Средний, Высокий).
    """
    return await proxy_request("incident", "/reports/priorities", request)

@app.api_route("/api/reports/sla-analytics", methods=["GET"])
async def proxy_sla_analytics(request: Request):
    """
    Глубокая аналитика SLA.
    
    Динамика соблюдения SLA во времени, тренды, проблемные зоны.
    """
    return await proxy_request("incident", "/reports/sla-analytics", request)

# -----------------------------------------------------------------------------
# КОММЕНТАРИИ И ВЛОЖЕНИЯ ИНЦИДЕНТОВ
# -----------------------------------------------------------------------------
# Специфичные маршруты для работы с комментариями и файлами.
# Объявлены до общего маршрута /api/incidents/{path:path}.

@app.api_route("/api/incidents/{incident_id}/comments", methods=["GET", "POST"])
async def proxy_incident_comments(incident_id: str, request: Request):
    """
    Комментарии к конкретному инциденту.
    
    - GET:  Получить все комментарии инцидента
    - POST: Добавить новый комментарий
    
    Args:
        incident_id: ID инцидента из URL
    """
    return await proxy_request("incident", f"/incidents/{incident_id}/comments", request)

@app.api_route("/api/incidents/{incident_id}/attachments", methods=["GET", "POST"])
async def proxy_incident_attachments(incident_id: str, request: Request):
    """
    Вложения (файлы) к комментариям инцидента.
    
    - GET:  Список вложений
    - POST: Загрузка нового файла
    
    Args:
        incident_id: ID инцидента из URL
    """
    return await proxy_request("incident", f"/incidents/{incident_id}/attachments", request)

@app.api_route("/api/incidents/{incident_id}/history", methods=["GET"])
async def proxy_incident_history(incident_id: str, request: Request):
    """
    История изменений инцидента.
    
    Лог всех изменений: кто, когда и что изменил (статус, исполнитель, приоритет и т.д.).
    
    Args:
        incident_id: ID инцидента из URL
    """
    return await proxy_request("incident", f"/incidents/{incident_id}/history", request)

@app.api_route("/api/incidents/{incident_id}/deadline", methods=["PUT"])
async def proxy_incident_deadline(incident_id: str, request: Request):
    """
    Изменение дедлайна инцидента.
    
    Позволяет вручную установить или изменить срок решения инцидента.
    
    Args:
        incident_id: ID инцидента из URL
    """
    return await proxy_request("incident", f"/incidents/{incident_id}/deadline", request)

# -----------------------------------------------------------------------------
# ОБЩИЕ МАРШРУТЫ ИНЦИДЕНТОВ
# -----------------------------------------------------------------------------
# Универсальный маршрут для CRUD-операций с инцидентами.
# Должен быть ПОСЛЕ всех специфичных маршрутов выше!

@app.api_route("/api/incidents/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
@app.api_route("/api/incidents", methods=["GET", "POST"])
async def proxy_incidents(request: Request, path: str = ""):
    """
    Универсальный обработчик запросов к инцидентам.
    
    Примеры маршрутов:
    - GET    /api/incidents              - Список всех инцидентов (с фильтрацией)
    - POST   /api/incidents              - Создать новый инцидент
    - GET    /api/incidents/123          - Получить инцидент по ID
    - PUT    /api/incidents/123          - Обновить инцидент
    - DELETE /api/incidents/123          - Удалить инцидент
    """
    return await proxy_request("incident", f"/incidents/{path}" if path else "/incidents", request)

@app.api_route("/api/incidents-internal/reset-executor/{user_id}", methods=["POST"])
async def proxy_reset_executor(user_id: str, request: Request):
    """
    Внутренний endpoint для сброса исполнителя.
    
    Используется user-service при удалении пользователя:
    снимает все назначенные инциденты с удаляемого исполнителя.
    
    Префикс "incidents-internal" подчёркивает, что endpoint
    не предназначен для прямого вызова из фронтенда.
    
    Args:
        user_id: ID удаляемого пользователя
    """
    return await proxy_request("incident", f"/incidents/reset-executor/{user_id}", request)

@app.api_route("/api/comments/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_comments(path: str, request: Request):
    """
    Проксирование запросов к комментариям (прямой доступ).
    
    Используется для операций с конкретными комментариями:
    - GET    /api/comments/123     - Получить комментарий
    - POST   /api/comments          - Создать комментарий
    - PUT    /api/comments/123      - Обновить комментарий
    - DELETE /api/comments/123      - Удалить комментарий
    """
    return await proxy_request("incident", f"/comments/{path}", request)

@app.api_route("/api/attachments/{path:path}", methods=["GET", "DELETE"])
async def proxy_attachments(path: str, request: Request):
    """
    Проксирование запросов к вложениям (файлам).
    
    - GET    /api/attachments/abc123/download    - Скачать файл по ID
    - DELETE /api/attachments/abc123             - Удалить файл
    
    Args:
        path: ID файла или путь к нему
    """
    return await proxy_request("incident", f"/attachments/{path}", request)

# -----------------------------------------------------------------------------
# СПРАВОЧНИКИ (REFERENCE DATA)
# -----------------------------------------------------------------------------
# Статические данные для заполнения выпадающих списков в интерфейсе:
# категории инцидентов, приоритеты, статусы, роли пользователей.

@app.api_route("/api/categories", methods=["GET", "POST"])
async def proxy_categories(request: Request):
    """
    Категории инцидентов.
    
    - GET:  Получить список всех категорий
    - POST: Создать новую категорию
    """
    return await proxy_request("incident", "/reference/categories", request)

@app.api_route("/api/categories/{category_id}", methods=["PUT", "DELETE"])
async def proxy_category_update(category_id: str, request: Request):
    """
    Обновление или удаление категории.
    
    Args:
        category_id: ID категории из URL
    """
    return await proxy_request("incident", f"/reference/categories/{category_id}", request)

@app.api_route("/api/priorities", methods=["GET"])
async def proxy_priorities(request: Request):
    """
    Приоритеты инцидентов (только чтение).
    
    Возвращает список приоритетов: Низкий, Средний, Высокий, Критический.
    """
    return await proxy_request("incident", "/reference/priorities", request)

@app.api_route("/api/priorities/{priority_id}", methods=["PUT"])
async def proxy_priority_update(priority_id: str, request: Request):
    """
    Обновление приоритета.
    
    Args:
        priority_id: ID приоритета из URL
    """
    return await proxy_request("incident", f"/reference/priorities/{priority_id}", request)

@app.api_route("/api/statuses", methods=["GET", "POST"])
async def proxy_statuses(request: Request):
    """
    Статусы инцидентов.
    
    - GET:  Получить список всех статусов
    - POST: Создать новый статус
    """
    return await proxy_request("incident", "/reference/statuses", request)

@app.api_route("/api/statuses/{status_id}", methods=["PUT", "DELETE"])
async def proxy_status_update(status_id: str, request: Request):
    """
    Обновление или удаление статуса.
    
    Args:
        status_id: ID статуса из URL
    """
    return await proxy_request("incident", f"/reference/statuses/{status_id}", request)

@app.api_route("/api/roles", methods=["GET"])
async def proxy_roles(request: Request):
    """
    Роли пользователей.
    
    Возвращает список ролей: Admin, User, Executor, Manager.
    Только чтение, роли определяются в коде.
    """
    return await proxy_request("incident", "/reference/roles", request)


# =============================================================================
# МАРШРУТЫ SLA SERVICE (СЕРВИС SLA-МОНИТОРИНГА)
# =============================================================================
# SLA (Service Level Agreement) — соглашение об уровне обслуживания.
# Этот сервис отвечает за:
# - Политики SLA (время реакции и решения для разных категорий/приоритетов)
# - Эскалацию (автоматическое уведомление руководителей при просрочках)
# - Расчёт и отслеживание сроков инцидентов

@app.api_route("/api/sla/policies", methods=["GET", "POST"])
async def proxy_sla_policies(request: Request):
    """
    Политики SLA.
    
    Политики определяют целевое время реакции и решения для инцидентов
    в зависимости от категории и приоритета.
    
    - GET:  Получить список всех политик SLA
    - POST: Создать новую политику SLA
    """
    return await proxy_request("sla", "/sla/policies", request)

@app.api_route("/api/sla/policies/{policy_id}", methods=["PUT", "DELETE"])
async def proxy_sla_policy(policy_id: str, request: Request):
    """
    Обновление или удаление политики SLA.
    
    Args:
        policy_id: ID политики из URL
    """
    return await proxy_request("sla", f"/sla/policies/{policy_id}", request)

@app.api_route("/api/sla/{path:path}", methods=["GET", "POST"])
async def proxy_sla(path: str, request: Request):
    """
    Универсальный маршрут для SLA-данных.
    
    Используется для получения SLA-информации по конкретным инцидентам,
    расчёта сроков и других операций.
    """
    return await proxy_request("sla", f"/sla/{path}", request)


@app.api_route("/api/escalation/{path:path}", methods=["GET", "POST"])
async def proxy_escalation(path: str, request: Request):
    """
    Эскалация инцидентов.
    
    Эскалация — это автоматический процесс уведомления вышестоящих лиц
    при нарушении сроков решения инцидента.
    
    - GET:  Получить историю эскалаций
    - POST: Создать правило эскалации или запустить эскалацию вручную
    """
    return await proxy_request("sla", f"/escalation/{path}", request)


# =============================================================================
# МАРШРУТЫ NOTIFICATION SERVICE (СЕРВИС УВЕДОМЛЕНИЙ)
# =============================================================================
# Сервис уведомлений отвечает за отправку сообщений пользователям:
# - Email-уведомления о новых инцидентах, назначениях, комментариях
# - Внутрисистемные уведомления (колокольчик в интерфейсе)
# - Настройки уведомлений для каждого пользователя

@app.api_route("/api/notifications/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
@app.api_route("/api/notifications", methods=["GET", "POST"])
async def proxy_notifications(request: Request, path: str = ""):
    """
    Универсальный обработчик запросов к уведомлениям.
    
    Примеры маршрутов:
    - GET    /api/notifications              - Получить уведомления текущего пользователя
    - POST   /api/notifications              - Создать уведомление (внутренний вызов)
    - GET    /api/notifications/123          - Получить уведомление по ID
    - PUT    /api/notifications/123/read     - Отметить как прочитанное
    - DELETE /api/notifications/123          - Удалить уведомление
    """
    return await proxy_request("notification", f"/notifications/{path}" if path else "/notifications", request)


# =============================================================================
# СЛУЖЕБНЫЕ ENDPOINT'Ы (HEALTH & INFO)
# =============================================================================

@app.get("/")
async def root():
    """
    Корневой endpoint системы.
    
    Возвращает общую информацию о системе:
    - Название и версию
    - Тип архитектуры
    - Список доступных микросервисов
    - Ссылку на документацию
    
    Используется для быстрой проверки, что система запущена.
    """
    return {
        "name": "Incident Management System",
        "version": "1.0.0",
        "architecture": "microservices",
        "services": list(SERVICES.keys()),
        "docs": "/api/docs"
    }


@app.get("/health")
async def health():
    """
    Проверка здоровья всех микросервисов.
    
    Этот endpoint используется:
    - Docker healthcheck для мониторинга контейнеров
    - Системами оркестрации (Kubernetes)
    - Мониторинговыми системами
    
    Делает запрос к каждому микросервису и возвращает их статус.
    
    Returns:
        dict: {
            "status": "healthy" | "degraded",  # Общее состояние системы
            "services": {                       # Статус каждого сервиса
                "user": {"status": "healthy"},
                "incident": {"status": "healthy"},
                ...
            }
        }
    
    Status коды:
    - healthy: Сервис ответил 200 OK
    - unhealthy: Сервис ответил с ошибкой
    - unreachable: Сервис не ответил (таймаут или недоступен)
    """
    results = {}
    async with httpx.AsyncClient() as client:
        for name, url in SERVICES.items():
            try:
                response = await client.get(f"{url}/health", timeout=5.0)
                results[name] = response.json() if response.status_code == 200 else {"status": "unhealthy"}
            except:
                results[name] = {"status": "unreachable"}
    
    # Система считается здоровой, только если ВСЕ сервисы работают
    all_healthy = all(r.get("status") == "healthy" for r in results.values())
    return {
        "status": "healthy" if all_healthy else "degraded",
        "services": results
    }


# =============================================================================
# ТОЧКА ВХОДА ДЛЯ ЗАПУСКА (LOCAL DEVELOPMENT)
# =============================================================================
# Этот блок выполняется только при прямом запуске файла:
# python main.py
#
# При работе через Docker используется uvicorn через docker-compose.
# При работе через gunicorn/uvicorn в продакшене этот блок игнорируется.

if __name__ == "__main__":
    import uvicorn
    # Запуск сервера разработки с автоперезагрузкой при изменении кода
    # host="0.0.0.0" — слушать все сетевые интерфейсы
    # port=8000 — порт API Gateway
    # reload=True — автоперезагрузка при изменениях (только для разработки!)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
