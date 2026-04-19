from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from config import Config
from services.stock_analyzer import get_stock_data
from services.perplexity import analyze_stock

app = FastAPI(title="StockBot API")

class StockRequest(BaseModel):
    symbol: str = "IAM.SN"

@app.get("/health")
async def health():
    """Public health check endpoint.

    Returns:
        dict: Status indicator.
    """
    return {"status": "ok"}

@app.post("/analyze")
async def analyze(
    req: StockRequest,
    x_api_key: str = Header(..., alias="X-API-Key"),
):
    """Analyze a stock symbol using market data and AI.

    Requires a valid ``X-API-Key`` header matching the configured API_KEY.

    Args:
        req: Request body containing the ticker symbol.
        x_api_key: API key provided via the ``X-API-Key`` HTTP header.

    Returns:
        dict: Symbol, raw indicator data, and AI analysis text.

    Raises:
        HTTPException 401: If the provided API key is invalid or not configured.
        HTTPException 400: On data retrieval or analysis failure.
    """
    if not Config.API_KEY or x_api_key != Config.API_KEY:
        raise HTTPException(status_code=401, detail="Clave de API inválida o no autorizada.")
    try:
        ind = await get_stock_data(req.symbol)
        analisis = await analyze_stock(req.symbol, ind)
        return {"symbol": req.symbol, "data": ind, "analisis": analisis}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/metrics/{telegram_user_id}")
async def get_portfolio_metrics(telegram_user_id: int):
    """Return quantitative portfolio metrics for a Telegram user.

    Args:
        telegram_user_id: Telegram user ID.

    Returns:
        dict: Sharpe, Beta, Max Drawdown, HHI, and supporting data.

    Raises:
        HTTPException 404: If the user has no positions.
        HTTPException 500: On computation failure.
    """
    try:
        from services.portfolio_metrics import compute_portfolio_metrics
        from services.portfolio_service import build_portfolio_snapshot

        snap = await build_portfolio_snapshot(telegram_user_id)
        if not snap["detalle"]:
            raise HTTPException(status_code=404, detail="El usuario no tiene posiciones activas.")

        metrics = await compute_portfolio_metrics(snap["detalle"])
        return {"telegram_user_id": telegram_user_id, "metrics": metrics}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("endpoints:app", host="0.0.0.0", port=8000)
