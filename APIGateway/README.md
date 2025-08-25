# API Gateway

FastAPI-based API Gateway for the E-commerce store.

## Run

1. Create a `.env` from `.env.example` and set URLs for downstream services.
2. Install deps:

   pip install -r requirements.txt

3. Start:

   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

## Endpoints
- GET /health
- POST /compose/product-price
- POST /proxy/notifications/send
- GET /proxy/analytics/sales-summary
