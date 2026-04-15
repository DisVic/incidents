"""
User Service - Управление пользователями, ролями, отделами
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from routers import auth, users, departments
from shared import settings

# Русские сообщения об ошибках валидации
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
    """Перевод ошибки валидации на русский"""
    loc = error.get('loc', [])
    error_type = error.get('type', '')
    msg = error.get('msg', '')
    
    # Получаем имя поля (последний элемент loc)
    field_name = None
    for loc_item in reversed(loc):
        if isinstance(loc_item, str):
            field_name = loc_item
            break
    
    if field_name and field_name in VALIDATION_MESSAGES:
        field_messages = VALIDATION_MESSAGES[field_name]
        if error_type in field_messages:
            return field_messages[error_type]
        if 'value_error' in field_messages and 'value_error' in error_type:
            return field_messages['value_error']
        # Если сообщение содержит email-related слова
        if 'email' in field_name.lower() or '@' in msg.lower():
            return 'Некорректный формат email'
    
    # Специфические сообщения по типу ошибки
    if error_type == 'missing':
        return f'Поле {field_name or "обязательное поле"} не заполнено'
    if 'string_too_short' in error_type:
        ctx = error.get('ctx', {})
        min_length = ctx.get('min_length', 8)
        return f'Минимум {min_length} символов'
    if 'email' in error_type.lower() or '@' in msg.lower() or 'email' in field_name.lower():
        return 'Некорректный формат email'
    
    return msg

app = FastAPI(
    title="User Service",
    version="1.0.0",
    description="Управление пользователями, ролями и отделами",
    root_path="/user",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Обработчик ошибок валидации с русскими сообщениями"""
    errors = []
    for error in exc.errors():
        loc = error.get('loc', [])
        field_name = None
        for loc_item in reversed(loc):
            if isinstance(loc_item, str):
                field_name = loc_item
                break
        
        translated_msg = translate_validation_error(error)
        errors.append({
            'field': field_name,
            'message': translated_msg
        })
    
    return JSONResponse(
        status_code=422,
        content={'detail': errors}
    )


app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(departments.router, prefix="/departments", tags=["Departments"])


@app.get("/health")
async def health():
    return {"service": "user-service", "status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
