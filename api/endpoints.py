from fastapi import APIRouter

from services.portfolio_metrics import calculate_portfolio_metrics

router = APIRouter()


@router.get("/metrics/{telegram_user_id}")
async def get_metrics(telegram_user_id: int):
    metrics = await calculate_portfolio_metrics(telegram_user_id)
    if metrics.get("empty"):
        return {"message": "No hay posiciones para este usuario", **metrics}
    return metrics
