"""
Notification Service - Уведомления (Internal, Email)
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import notifications, email

app = FastAPI(
    title="Notification Service",
    version="1.0.0",
    description="Сервис уведомлений: внутренние, Email",
    root_path="/notification",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
app.include_router(email.router, prefix="/email", tags=["Email"])


@app.get("/health")
async def health():
    return {"service": "notification-service", "status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8004, reload=True)
