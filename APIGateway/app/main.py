import os
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Depends, Header, Query
from fastapi.middleware.cors import CORSMiddleware
import httpx
from pydantic import BaseModel, Field

# PUBLIC_INTERFACE
def get_settings() -> Dict[str, Any]:
    """Return settings loaded from environment variables. Do not hardcode configuration."""
    return {
        "SERVICE_NAME": os.getenv("API_GATEWAY_SERVICE_NAME", "API Gateway"),
        "ENV": os.getenv("ENV", "development"),
        "PRICE_SERVICE_URL": os.getenv("PRICE_SERVICE_URL", "http://localhost:8001"),
        "NOTIFICATION_SERVICE_URL": os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8002"),
        "ANALYTICS_SERVICE_URL": os.getenv("ANALYTICS_SERVICE_URL", "http://localhost:8003"),
        "ALLOWED_ORIGINS": os.getenv("ALLOWED_ORIGINS", "*"),
        "API_KEY": os.getenv("API_GATEWAY_API_KEY"),  # optional
        "TIMEOUT": float(os.getenv("GATEWAY_HTTP_TIMEOUT", "20")),
    }


app = FastAPI(
    title="E-commerce API Gateway",
    description="Central entry point for clients. Proxies requests to services, performs basic auth, and composes responses.",
    version="1.0.0",
    openapi_tags=[
        {"name": "health", "description": "Service health and readiness checks"},
        {"name": "prices", "description": "Price service proxy and composition endpoints"},
        {"name": "notifications", "description": "Notification service proxy"},
        {"name": "analytics", "description": "Analytics service proxy and dashboards"},
        {"name": "websocket", "description": "WebSocket usage notes"},
    ],
)

# CORS
settings = get_settings()
allow_origins = [o.strip() for o in settings["ALLOWED_ORIGINS"].split(",")] if settings["ALLOWED_ORIGINS"] else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Models for composite endpoints
class ProductPriceQuery(BaseModel):
    product_id: str = Field(..., description="Unique product identifier")
    currency: str = Field(..., description="ISO Currency code, e.g., USD")
    include_promotions: bool = Field(True, description="Whether to apply active promotions")


class SendNotification(BaseModel):
    to_email: str = Field(..., description="Recipient email address")
    subject: str = Field(..., description="Email subject")
    body: str = Field(..., description="Email plaintext body")
    template_id: Optional[str] = Field(None, description="Optional template id for provider")


async def require_api_key(x_api_key: Optional[str] = Header(default=None)):
    """Simple header API key enforcement if configured via environment."""
    configured = settings.get("API_KEY")
    if configured and x_api_key != configured:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True


@app.get("/health", tags=["health"], summary="Liveness probe", description="Returns basic liveness status.")
async def health():
    return {"status": "ok", "service": settings["SERVICE_NAME"], "env": settings["ENV"]}


@app.get("/docs/websocket", tags=["websocket"], summary="WebSocket usage help", description="This project currently does not implement WebSocket endpoints. For real-time features, add FastAPI WebSocket routes here, document operation_id, and ensure clients connect to ws(s)://<host>/ws.")
async def websocket_help():
    return {
        "message": "No WebSocket routes currently implemented.",
        "note": "Add WebSocket routes in future if needed for real-time pricing or analytics streaming."
    }


# PUBLIC_INTERFACE
@app.post("/compose/product-price", tags=["prices"], summary="Get composed product price", description="Fetch product price from Price service and attach analytics/tracking id for the request.")
async def composed_price(payload: ProductPriceQuery, _: bool = Depends(require_api_key)):
    """Proxy composition: fetch price details and return minimal composition."""
    async with httpx.AsyncClient(timeout=settings["TIMEOUT"]) as client:
        price_url = f'{settings["PRICE_SERVICE_URL"].rstrip("/")}/api/v1/prices/query'
        resp = await client.post(price_url, json=payload.dict())
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        price = resp.json()
        return {"price": price, "tracking_id": os.getenv("TRACKING_ID", "na")}


# PUBLIC_INTERFACE
@app.post("/proxy/notifications/send", tags=["notifications"], summary="Send notification", description="Proxy call to Notification service to send an email.")
async def proxy_send_notification(body: SendNotification, _: bool = Depends(require_api_key)):
    async with httpx.AsyncClient(timeout=settings["TIMEOUT"]) as client:
        url = f'{settings["NOTIFICATION_SERVICE_URL"].rstrip("/")}/api/v1/notifications/send'
        resp = await client.post(url, json=body.dict())
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()


# PUBLIC_INTERFACE
@app.get("/proxy/analytics/sales-summary", tags=["analytics"], summary="Get sales summary", description="Proxy call to Analytics service for basic sales summary.")
async def proxy_sales_summary(range: str = Query("7d", description="Time range like '24h', '7d', '30d'"), _: bool = Depends(require_api_key)):
    async with httpx.AsyncClient(timeout=settings["TIMEOUT"]) as client:
        url = f'{settings["ANALYTICS_SERVICE_URL"].rstrip("/")}/api/v1/analytics/sales-summary?range={range}'
        resp = await client.get(url)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()
