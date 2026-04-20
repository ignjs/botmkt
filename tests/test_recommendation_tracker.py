from datetime import datetime, timedelta

import pytest

from services.recommendation_tracker import evaluate_recommendation_result, update_pending_recommendations


def test_evaluate_recommendation_result_rules():
    assert evaluate_recommendation_result("comprar", 3.0) == "acierto"
    assert evaluate_recommendation_result("comprar", 1.0) == "error"
    assert evaluate_recommendation_result("vender", -3.0) == "acierto"
    assert evaluate_recommendation_result("vender", 1.0) == "error"
    assert evaluate_recommendation_result("mantener", 3.0) == "acierto"
    assert evaluate_recommendation_result("mantener", 7.0) == "error"


@pytest.mark.asyncio
async def test_update_pending_recommendations_updates_due_horizons(monkeypatch):
    now = datetime.utcnow()

    async def _fake_pending():
        return [
            {
                "id": 1,
                "user_id": 1,
                "symbol": "AAPL",
                "recommendation": "comprar",
                "price_at_recommendation": 100,
                "recommended_at": now - timedelta(days=15),
                "result_5d": "pendiente",
                "result_10d": "pendiente",
                "result_20d": "pendiente",
            },
            {
                "id": 2,
                "user_id": 1,
                "symbol": "MSFT",
                "recommendation": "vender",
                "price_at_recommendation": 100,
                "recommended_at": now - timedelta(days=15),
                "result_5d": "pendiente",
                "result_10d": "pendiente",
                "result_20d": "pendiente",
            },
            {
                "id": 3,
                "user_id": 1,
                "symbol": "GOOG",
                "recommendation": "mantener",
                "price_at_recommendation": 100,
                "recommended_at": now - timedelta(days=15),
                "result_5d": "pendiente",
                "result_10d": "pendiente",
                "result_20d": "pendiente",
            },
        ]

    updates = []

    async def _fake_update(rec_id, horizon, price, result):
        updates.append((rec_id, horizon, price, result))

    async def _fake_price(symbol, target_date):
        if symbol == "AAPL":
            return 104.0
        if symbol == "MSFT":
            return 95.0
        return 102.0

    monkeypatch.setattr("services.recommendation_tracker.get_pending_ai_recommendations", _fake_pending)
    monkeypatch.setattr("services.recommendation_tracker.update_ai_recommendation_horizon", _fake_update)
    monkeypatch.setattr("services.recommendation_tracker._price_near_horizon", _fake_price)

    await update_pending_recommendations()

    assert any(u[0] == 1 and u[1] == 5 and u[3] == "acierto" for u in updates)
    assert any(u[0] == 2 and u[1] == 5 and u[3] == "acierto" for u in updates)
    assert any(u[0] == 3 and u[1] == 5 and u[3] == "acierto" for u in updates)
