"""
SLA Service - Контроль SLA и эскалация
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

app.include_router(sla.router, prefix="", tags=["SLA"])
app.include_router(escalation.router, prefix="/escalation", tags=["Escalation"])


@app.get("/health")
async def health():
    return {"service": "sla-service", "status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8003, reload=True)
