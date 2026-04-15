"""
API Gateway - единая точка входа для всех микросервисов
"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, Response
import httpx

from shared import settings

app = FastAPI(
    title="API Gateway",
    version="1.0.0",
    description="API Gateway для микросервисной архитектуры",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Service URLs
SERVICES = {
    "user": "http://user-service:8001",
    "incident": "http://incident-service:8002",
    "sla": "http://sla-service:8003",
    "notification": "http://notification-service:8004",
}


async def proxy_request(service: str, path: str, request: Request) -> Response:
    """Proxy request to microservice"""
    if service not in SERVICES:
        raise HTTPException(status_code=404, detail=f"Service {service} not found")
    
    url = f"{SERVICES[service]}{path}"
    
    async with httpx.AsyncClient() as client:
        try:
            # Forward request
            body = await request.body()
            headers = dict(request.headers)
            headers.pop("host", None)
            
            response = await client.request(
                method=request.method,
                url=url,
                content=body,
                headers=headers,
                params=request.query_params,
                timeout=30.0
            )
            
            # Check if response is binary (file download)
            content_type = response.headers.get("content-type", "")
            if not content_type.startswith("application/json"):
                # Return binary response
                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    headers=dict(response.headers)
                )
            
            return JSONResponse(
                content=response.json() if response.content else {},
                status_code=response.status_code
            )
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Service timeout")
        except Exception as e:
            raise HTTPException(status_code=502, detail=str(e))


# ============================================
# USER SERVICE ROUTES
# ============================================

@app.api_route("/api/auth/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_auth(path: str, request: Request):
    return await proxy_request("user", f"/auth/{path}", request)


@app.api_route("/api/users/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
@app.api_route("/api/users", methods=["GET", "POST"])
async def proxy_users(request: Request, path: str = ""):
    return await proxy_request("user", f"/users/{path}" if path else "/users", request)


# Avatar upload - specific route before generic users route
@app.api_route("/api/users/{user_id}/avatar", methods=["POST"])
async def proxy_user_avatar(user_id: str, request: Request):
    return await proxy_request("user", f"/users/{user_id}/avatar", request)


@app.api_route("/api/departments/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
@app.api_route("/api/departments", methods=["GET", "POST"])
async def proxy_departments(request: Request, path: str = ""):
    return await proxy_request("user", f"/departments/{path}" if path else "/departments", request)


# ============================================
# INCIDENT SERVICE ROUTES
# ============================================

# IMPORTANT: More specific routes must be defined BEFORE generic {path:path} routes

# Reports (dashboard) - must be before incidents routes
@app.api_route("/api/reports/dashboard", methods=["GET"])
async def proxy_dashboard(request: Request):
    return await proxy_request("incident", "/reports/dashboard", request)

@app.api_route("/api/reports/sla-stats", methods=["GET"])
async def proxy_sla_stats(request: Request):
    return await proxy_request("incident", "/reports/sla-stats", request)

@app.api_route("/api/reports/overdue-incidents", methods=["GET"])
async def proxy_overdue_incidents(request: Request):
    return await proxy_request("incident", "/reports/overdue-incidents", request)

@app.api_route("/api/reports/executor-overdue-stats", methods=["GET"])
async def proxy_executor_overdue_stats(request: Request):
    return await proxy_request("incident", "/reports/executor-overdue-stats", request)

@app.api_route("/api/reports/user/{user_id}", methods=["GET"])
async def proxy_user_stats(request: Request, user_id: str):
    return await proxy_request("incident", f"/reports/user/{user_id}", request)

@app.api_route("/api/reports/status-stats", methods=["GET"])
async def proxy_status_stats(request: Request):
    return await proxy_request("incident", "/reports/status-stats", request)

@app.api_route("/api/reports/activity", methods=["GET"])
async def proxy_activity(request: Request):
    return await proxy_request("incident", "/reports/activity", request)

@app.api_route("/api/reports/executors", methods=["GET"])
async def proxy_executors(request: Request):
    return await proxy_request("incident", "/reports/executors", request)

@app.api_route("/api/reports/executors-detailed", methods=["GET"])
async def proxy_executors_detailed(request: Request):
    return await proxy_request("incident", "/reports/executors-detailed", request)

@app.api_route("/api/reports/departments", methods=["GET"])
async def proxy_departments_report(request: Request):
    return await proxy_request("incident", "/reports/departments", request)

@app.api_route("/api/reports/priorities", methods=["GET"])
async def proxy_priorities_report(request: Request):
    return await proxy_request("incident", "/reports/priorities", request)

@app.api_route("/api/reports/sla-analytics", methods=["GET"])
async def proxy_sla_analytics(request: Request):
    return await proxy_request("incident", "/reports/sla-analytics", request)

# Incident comments (special routes) - must be before generic incidents routes
@app.api_route("/api/incidents/{incident_id}/comments", methods=["GET", "POST"])
async def proxy_incident_comments(incident_id: str, request: Request):
    return await proxy_request("incident", f"/comments/incidents/{incident_id}/comments", request)

# Incident attachments - must be before generic incidents routes
@app.api_route("/api/incidents/{incident_id}/attachments", methods=["GET", "POST"])
async def proxy_incident_attachments(incident_id: str, request: Request):
    return await proxy_request("incident", f"/comments/incidents/{incident_id}/attachments", request)

# Incident history - must be before generic incidents routes
@app.api_route("/api/incidents/{incident_id}/history", methods=["GET"])
async def proxy_incident_history(incident_id: str, request: Request):
    return await proxy_request("incident", f"/incidents/{incident_id}/history", request)

# Incident deadline - must be before generic incidents routes
@app.api_route("/api/incidents/{incident_id}/deadline", methods=["PUT"])
async def proxy_incident_deadline(incident_id: str, request: Request):
    return await proxy_request("incident", f"/incidents/{incident_id}/deadline", request)

# Generic incidents routes - must be AFTER specific routes
@app.api_route("/api/incidents/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
@app.api_route("/api/incidents", methods=["GET", "POST"])
async def proxy_incidents(request: Request, path: str = ""):
    return await proxy_request("incident", f"/incidents/{path}" if path else "/incidents", request)

# Reset executor incidents (internal endpoint for user-service)
@app.api_route("/api/incidents-internal/reset-executor/{user_id}", methods=["POST"])
async def proxy_reset_executor(user_id: str, request: Request):
    return await proxy_request("incident", f"/incidents/reset-executor/{user_id}", request)

@app.api_route("/api/comments/{path:path}", methods=["GET", "POST", "DELETE"])
async def proxy_comments(path: str, request: Request):
    return await proxy_request("incident", f"/comments/{path}", request)

# Attachments download and delete
@app.api_route("/api/attachments/{path:path}", methods=["GET", "DELETE"])
async def proxy_attachments(path: str, request: Request):
    return await proxy_request("incident", f"/comments/attachments/{path}", request)

@app.api_route("/api/categories", methods=["GET", "POST"])
async def proxy_categories(request: Request):
    return await proxy_request("incident", "/reference/categories", request)

@app.api_route("/api/categories/{category_id}", methods=["PUT", "DELETE"])
async def proxy_category_update(category_id: str, request: Request):
    return await proxy_request("incident", f"/reference/categories/{category_id}", request)

@app.api_route("/api/priorities", methods=["GET"])
async def proxy_priorities(request: Request):
    return await proxy_request("incident", "/reference/priorities", request)

@app.api_route("/api/priorities/{priority_id}", methods=["PUT"])
async def proxy_priority_update(priority_id: str, request: Request):
    return await proxy_request("incident", f"/reference/priorities/{priority_id}", request)

@app.api_route("/api/statuses", methods=["GET", "POST"])
async def proxy_statuses(request: Request):
    return await proxy_request("incident", "/reference/statuses", request)

@app.api_route("/api/statuses/{status_id}", methods=["PUT", "DELETE"])
async def proxy_status_update(status_id: str, request: Request):
    return await proxy_request("incident", f"/reference/statuses/{status_id}", request)

@app.api_route("/api/roles", methods=["GET"])
async def proxy_roles(request: Request):
    return await proxy_request("incident", "/reference/roles", request)


# ============================================
# SLA SERVICE ROUTES
# ============================================

@app.api_route("/api/sla/policies", methods=["GET", "POST"])
async def proxy_sla_policies(request: Request):
    return await proxy_request("sla", "/sla/policies", request)

@app.api_route("/api/sla/policies/{policy_id}", methods=["PUT", "DELETE"])
async def proxy_sla_policy(policy_id: str, request: Request):
    return await proxy_request("sla", f"/sla/policies/{policy_id}", request)

@app.api_route("/api/sla/{path:path}", methods=["GET", "POST"])
async def proxy_sla(path: str, request: Request):
    return await proxy_request("sla", f"/sla/{path}", request)


@app.api_route("/api/escalation/{path:path}", methods=["GET", "POST"])
async def proxy_escalation(path: str, request: Request):
    return await proxy_request("sla", f"/escalation/{path}", request)


# ============================================
# NOTIFICATION SERVICE ROUTES
# ============================================

@app.api_route("/api/notifications/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
@app.api_route("/api/notifications", methods=["GET", "POST"])
async def proxy_notifications(request: Request, path: str = ""):
    return await proxy_request("notification", f"/notifications/{path}" if path else "/notifications", request)


# ============================================
# HEALTH & INFO
# ============================================

@app.get("/")
async def root():
    return {
        "name": "Incident Management System",
        "version": "1.0.0",
        "architecture": "microservices",
        "services": list(SERVICES.keys()),
        "docs": "/api/docs"
    }


@app.get("/health")
async def health():
    """Check health of all services"""
    results = {}
    async with httpx.AsyncClient() as client:
        for name, url in SERVICES.items():
            try:
                response = await client.get(f"{url}/health", timeout=5.0)
                results[name] = response.json() if response.status_code == 200 else {"status": "unhealthy"}
            except:
                results[name] = {"status": "unreachable"}
    
    all_healthy = all(r.get("status") == "healthy" for r in results.values())
    return {
        "status": "healthy" if all_healthy else "degraded",
        "services": results
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
