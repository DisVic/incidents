"""
User Service — сервис управления пользователями, ролями и отделами.

Основные функции:
- Аутентификация и авторизация (JWT-токены)
- CRUD пользователей
- Управление отделами
- Валидация данных с русскими сообщениями об ошибках
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from routers import auth, users, departments
from shared import settings

# Словарь русских сообщений для ошибок валидации по полям
VALIDATION_MESSAGES = {
    'email': {
        'missing': 'Email обязателен',
        'value_error.email': 'Некорректный формат email',
        'string_type': 'Email должен быть строкой',
        'value_error': 'Некорректный формат email',
    },
    'password': {
        'missing': 'Пароль обязателен',
        'string_too_short': 'Пароль должен содержать минимум 8 символов',
        'value_error': 'Пароль должен содержать минимум 8 символов',
    },
    'full_name': {
        'missing': 'ФИО обязательно',
        'string_too_short': 'ФИО должно содержать минимум 2 символа',
        'value_error': 'ФИО должно содержать минимум 2 символа',
    },
    'role_id': {
        'missing': 'Роль обязательна',
        'uuid_type': 'Некорректный ID роли',
    },
    'department_id': {
        'uuid_type': 'Некорректный ID отдела',
    },
}

def translate_validation_error(error: dict) -> str:
    """Преобразует ошибку валидации в русскоязычное сообщение."""
    loc = error.get('loc', [])
    error_type = error.get('type', '')
    msg = error.get('msg', '')
    
    # Находим имя поля в локации ошибки
    field_name = None
    for loc_item in reversed(loc):
        if isinstance(loc_item, str):
            field_name = loc_item
            break
    
    # Ищем готовое сообщение для этого поля и типа ошибки
    if field_name and field_name in VALIDATION_MESSAGES:
        field_messages = VALIDATION_MESSAGES[field_name]
        if error_type in field_messages:
            return field_messages[error_type]
        # Пытаемся найти по префиксу (например, value_error.email → value_error)
        if 'value_error' in field_messages and 'value_error' in error_type:
            return field_messages['value_error']
        # Специальная проверка для email
        if 'email' in field_name.lower() or '@' in msg.lower():
            return 'Некорректный формат email'
    
    # Генерируем сообщение по типу ошибки, если нет готового
    if error_type == 'missing':
        return f'Поле {field_name or "обязательное поле"} не заполнено'
    if 'string_too_short' in error_type:
        ctx = error.get('ctx', {})
        min_length = ctx.get('min_length', 8)
        return f'Минимум {min_length} символов'
    if 'email' in error_type.lower() or '@' in msg.lower() or 'email' in field_name.lower():
        return 'Некорректный формат email'
    
    return msg

# Основное приложение User Service
# root_path="/user" — префикс для корректной работы за API Gateway
app = FastAPI(
    title="User Service",
    version="1.0.0",
    description="Управление пользователями, ролями и отделами",
    root_path="/user",
)

# CORS-middleware для разрешения запросов с фронтенда
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Кастомный обработчик ошибок валидации — возвращает русские сообщения."""
    errors = []
    for error in exc.errors():
        # Извлекаем имя поля из локации ошибки
        loc = error.get('loc', [])
        field_name = None
        for loc_item in reversed(loc):
            if isinstance(loc_item, str):
                field_name = loc_item
                break
        
        # Переводим сообщение на русский
        translated_msg = translate_validation_error(error)
        errors.append({
            'field': field_name,
            'message': translated_msg
        })
    
    return JSONResponse(
        status_code=422,  # Unprocessable Entity
        content={'detail': errors}
    )


# Подключение роутеров (группы endpoint'ов)
app.include_router(auth.router, prefix="/auth", tags=["Auth"])           # Аутентификация
app.include_router(users.router, prefix="/users", tags=["Users"])         # Пользователи
app.include_router(departments.router, prefix="/departments", tags=["Departments"])  # Отделы


@app.get("/health")
async def health():
    """Health check endpoint для мониторинга статуса сервиса."""
    return {"service": "user-service", "status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    # Запуск на порту 8001 (для локальной разработки без Docker)
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
