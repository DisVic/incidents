"""
SLA Service — контроль SLA и эскалация.

Основные функции:
- Расчёт дедлайнов по SLA-политикам
- Управление политиками SLA (время решения по приоритетам)
- Правила эскалации (уведомления при приближении к дедлайну)

Роутеры:
- /sla — политики SLA, расчёт дедлайнов
- /escalation — правила эскалации
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import sla, escalation
from shared import settings

app = FastAPI(
    title="SLA Service",
    version="1.0.0",
    description="Контроль SLA и управление эскалацией",
    root_path="/sla",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутеров
app.include_router(sla.router, prefix="", tags=["SLA"])
app.include_router(escalation.router, prefix="/escalation", tags=["Escalation"])


@app.get("/health")
async def health():
    """Health check endpoint для мониторинга статуса сервиса."""
    return {"service": "sla-service", "status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    # Запуск на порту 8003 (для локальной разработки без Docker)
    uvicorn.run("main:app", host="0.0.0.0", port=8003, reload=True)
