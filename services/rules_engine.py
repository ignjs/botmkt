from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

import yfinance as yf

from services.portfolio_service import build_portfolio_snapshot
from services.stock_analyzer import get_stock_data, get_stock_data_fallback

CASH_EQUIVALENTS = {"CASH", "CASH.USD", "CASH.CLP", "BIL", "SHV", "SGOV"}
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _clamp(value: float, min_value: float = 0, max_value: float = 10) -> float:
    return max(min_value, min(max_value, value))


def _guess_country(symbol: str, info: Dict) -> str:
    if info.get("country"):
        return str(info["country"])
    if symbol.endswith(".SN"):
        return "Chile"
    if symbol.endswith(".BA"):
        return "Argentina"
    if symbol.endswith(".MX"):
        return "México"
    if symbol.startswith("^"):
        return "Índice global"
    if symbol.endswith("=X"):
        return "FX"
    return str(info.get("market") or "Desconocido")


def _guess_sector(symbol: str, info: Dict) -> str:
    if info.get("sector"):
        return str(info["sector"])
    quote_type = str(info.get("quoteType") or "").lower()
    if symbol.startswith("^") or quote_type in {"etf", "index"}:
        return "Índices / ETF"
    if symbol in CASH_EQUIVALENTS:
        return "Caja"
    return "Sin clasificar"


async def _enrich_position(position: Dict, total_value: float) -> Dict:
    symbol = position["symbol"]
    try:
        indicators = await get_stock_data(symbol)
    except Exception:
        indicators = await get_stock_data_fallback(symbol)

    try:
        info = yf.Ticker(symbol).info or {}
    except Exception:
        info = {}

    weight_pct = round((float(position["valor"]) / total_value) * 100, 2) if total_value else 0.0
    return {
        **position,
        "weight_pct": weight_pct,
        "country": _guess_country(symbol, info),
        "sector": _guess_sector(symbol, info),
        "exchange": str(info.get("exchange") or "Desconocido"),
        "quote_type": str(info.get("quoteType") or "equity"),
        "rsi": indicators.get("rsi"),
        "macd": indicators.get("macd"),
        "cambio_7d": indicators.get("cambio_7d", 0),
        "precio_actual": indicators.get("precio_actual", position.get("precio")),
    }


def _severity_for_overweight(actual_pct: float, threshold_pct: float) -> str:
    if threshold_pct <= 0:
        return "high"
    return "high" if actual_pct >= threshold_pct * 1.25 else "medium"


def _append_action(actions: List[Dict], priority: str, action: str, reason: str):
    if any(existing["action"] == action for existing in actions):
        return
    actions.append({"priority": priority, "action": action, "reason": reason})


def _sort_by_severity(items: List[Dict]) -> List[Dict]:
    return sorted(items, key=lambda item: SEVERITY_ORDER.get(item.get("severity", "low"), 99))


def _compute_risk_score(profile: Dict, positions: List[Dict], country_weights: Dict[str, float], cash_like_pct: float) -> int:
    if not positions:
        return 1

    risk_score = 3.0
    largest_weight = max((pos["weight_pct"] for pos in positions), default=0)
    worst_drawdown = min((float(pos.get("pl", 0)) for pos in positions), default=0)
    top_country_pct = max(country_weights.values(), default=0)

    if largest_weight > 35:
        risk_score += 2
    elif largest_weight > 25:
        risk_score += 1

    if top_country_pct > 75:
        risk_score += 2
    elif top_country_pct > 60:
        risk_score += 1

    if any(abs(float(pos.get("cambio_7d", 0) or 0)) >= 8 for pos in positions):
        risk_score += 1

    if worst_drawdown <= -float(profile.get("max_drawdown_pct", 12)):
        risk_score += 2

    target_cash = float(profile.get("cash_buffer_pct", 0) or 0)
    if target_cash and cash_like_pct < target_cash:
        risk_score += 1

    return int(round(_clamp(risk_score, 1, 10)))


async def analyze_portfolio_rules(telegram_user_id: int, profile: Dict) -> Dict:
    snapshot = await build_portfolio_snapshot(telegram_user_id)
    total_value = float(snapshot.get("valor_total", 0) or 0)
    raw_positions = snapshot.get("detalle", [])

    if not raw_positions:
        return {
            "portfolio_summary": {
                "total_value": 0,
                "position_count": 0,
                "risk_score": 1,
                "risk_label": "bajo",
                "cash_like_pct": 0,
            },
            "rule_breaches": [],
            "warnings": [],
            "opportunities": [],
            "suggested_actions": [],
            "positions": [],
        }

    positions = []
    for position in raw_positions:
        positions.append(await _enrich_position(position, total_value))

    country_weights: Dict[str, float] = defaultdict(float)
    sector_weights: Dict[str, float] = defaultdict(float)
    exchange_weights: Dict[str, float] = defaultdict(float)
    cash_like_pct = 0.0

    for pos in positions:
        country_weights[pos["country"]] += float(pos["weight_pct"])
        sector_weights[pos["sector"]] += float(pos["weight_pct"])
        exchange_weights[pos["exchange"]] += float(pos["weight_pct"])
        if pos["symbol"] in CASH_EQUIVALENTS or pos["sector"] == "Caja":
            cash_like_pct += float(pos["weight_pct"])

    rule_breaches: List[Dict] = []
    warnings: List[Dict] = []
    opportunities: List[Dict] = []
    suggested_actions: List[Dict] = []

    max_position_pct = float(profile.get("max_position_pct", 25) or 25)
    max_country_pct = float(profile.get("max_country_pct", 65) or 65)
    max_sector_pct = float(profile.get("max_sector_pct", 50) or 50)
    max_drawdown_pct = float(profile.get("max_drawdown_pct", 12) or 12)
    risk_tolerance = int(profile.get("risk_tolerance", 5) or 5)
    target_cash = float(profile.get("cash_buffer_pct", 0) or 0)

    for pos in positions:
        if pos["weight_pct"] > max_position_pct:
            severity = _severity_for_overweight(pos["weight_pct"], max_position_pct)
            rule_breaches.append({
                "type": "max_position_pct",
                "severity": severity,
                "symbol": pos["symbol"],
                "message": f"{pos['symbol']} pesa {pos['weight_pct']:.1f}% y supera tu límite de {max_position_pct:.1f}%.",
            })
            _append_action(
                suggested_actions,
                "Alta" if severity == "high" else "Media",
                f"Reducir {pos['symbol']} hasta volver debajo de {max_position_pct:.0f}% del portafolio.",
                "Evita que una sola posición domine el riesgo semanal.",
            )

        if float(pos.get("pl", 0)) <= -max_drawdown_pct:
            rule_breaches.append({
                "type": "max_drawdown_pct",
                "severity": "high",
                "symbol": pos["symbol"],
                "message": f"{pos['symbol']} cae {float(pos.get('pl', 0)):.1f}% vs tu tolerancia máxima de -{max_drawdown_pct:.1f}%.",
            })
            _append_action(
                suggested_actions,
                "Alta",
                f"Revisar la tesis de {pos['symbol']} y definir si recortas o congelas nuevas compras.",
                "El drawdown actual ya excede lo que declaraste tolerar.",
            )

        if float(pos.get("rsi", 50) or 50) >= 70 and pos["weight_pct"] >= max_position_pct * 0.8:
            opportunities.append({
                "type": "take_profit_review",
                "severity": "medium",
                "message": f"{pos['symbol']} está exigida por RSI y además pesa {pos['weight_pct']:.1f}%.",
            })
            _append_action(
                suggested_actions,
                "Media",
                f"Evaluar toma parcial de ganancias en {pos['symbol']} si ya cumplió tu objetivo táctico.",
                "Combina momentum exigido con alto peso relativo.",
            )

    for country, weight in country_weights.items():
        if weight > max_country_pct:
            severity = _severity_for_overweight(weight, max_country_pct)
            rule_breaches.append({
                "type": "max_country_pct",
                "severity": severity,
                "country": country,
                "message": f"Exposición a {country}: {weight:.1f}% vs límite de {max_country_pct:.1f}%.",
            })
            _append_action(
                suggested_actions,
                "Alta" if severity == "high" else "Media",
                f"No agregues más exposición a {country} esta semana hasta rebalancear.",
                "La cartera quedó demasiado cargada a un solo mercado.",
            )

    for sector, weight in sector_weights.items():
        if weight > max_sector_pct:
            severity = _severity_for_overweight(weight, max_sector_pct)
            rule_breaches.append({
                "type": "max_sector_pct",
                "severity": severity,
                "sector": sector,
                "message": f"El sector {sector} representa {weight:.1f}% y supera tu límite de {max_sector_pct:.1f}%.",
            })
            _append_action(
                suggested_actions,
                "Media",
                f"Posponer nuevas compras en el sector {sector} y buscar diversificación fuera de ese bloque.",
                "Reduce correlación interna del portafolio.",
            )

    dominant_exchange = max(exchange_weights.values(), default=0)
    if dominant_exchange >= 75:
        warnings.append({
            "type": "single_market_dependency",
            "severity": "medium",
            "message": "Más del 75% de la cartera depende de un solo mercado/exchange.",
        })
        _append_action(
            suggested_actions,
            "Media",
            "Agregar una posición pequeña fuera de tu mercado dominante para bajar correlación.",
            "Tu cartera hoy está demasiado atada al mismo driver macro.",
        )

    if target_cash and cash_like_pct < target_cash:
        warnings.append({
            "type": "cash_buffer",
            "severity": "medium",
            "message": f"Caja estimada {cash_like_pct:.1f}% vs objetivo de {target_cash:.1f}%.",
        })
        _append_action(
            suggested_actions,
            "Media",
            f"Reservar al menos {max(target_cash - cash_like_pct, 0):.1f}% de nuevas compras como caja táctica.",
            "Te ayudará a ejecutar sin forzarte si aparece volatilidad.",
        )

    risk_score = _compute_risk_score(profile, positions, country_weights, cash_like_pct)
    profile_risk_band = "bajo" if risk_tolerance <= 3 else "medio" if risk_tolerance <= 7 else "alto"
    risk_label = "alto" if risk_score >= 8 else "medio" if risk_score >= 5 else "bajo"

    if risk_tolerance <= 4 and risk_score >= 7:
        rule_breaches.append({
            "type": "risk_mismatch",
            "severity": "high",
            "message": f"La cartera hoy se comporta con riesgo {risk_label} ({risk_score}/10), por encima de tu perfil {profile_risk_band}.",
        })
        _append_action(
            suggested_actions,
            "Alta",
            "Congelar compras agresivas hasta que el riesgo total vuelva a tu rango declarado.",
            "La cartera está fuera del nivel de disciplina que definiste.",
        )

    if not rule_breaches and not warnings:
        opportunities.append({
            "type": "disciplined_follow_up",
            "severity": "low",
            "message": "La cartera está razonablemente alineada con tu perfil; el foco es mantener disciplina de seguimiento.",
        })

    if len(suggested_actions) < 3:
        _append_action(
            suggested_actions,
            "Media",
            "Revisar las 2 posiciones más grandes y confirmar si siguen cumpliendo tu tesis original.",
            "Disciplina antes de agregar complejidad.",
        )
        _append_action(
            suggested_actions,
            "Baja",
            "Documentar un precio o condición concreta para tu próxima compra, en vez de improvisar.",
            "Convierte estrategia en ejecución repetible.",
        )
        _append_action(
            suggested_actions,
            "Baja",
            f"Alinear cualquier nueva entrada con tu estrategia preferida: {profile.get('preferred_strategy', 'mixta')}.",
            "Evita mezclar estilos sin criterio explícito.",
        )

    top_position = max(positions, key=lambda item: item["weight_pct"])
    top_country = max(country_weights.items(), key=lambda item: item[1])
    top_sector = max(sector_weights.items(), key=lambda item: item[1])

    return {
        "portfolio_summary": {
            "total_value": round(total_value, 2),
            "position_count": len(positions),
            "cash_like_pct": round(cash_like_pct, 2),
            "top_position": {"symbol": top_position["symbol"], "weight_pct": round(top_position["weight_pct"], 2)},
            "top_country": {"name": top_country[0], "weight_pct": round(top_country[1], 2)},
            "top_sector": {"name": top_sector[0], "weight_pct": round(top_sector[1], 2)},
            "country_breakdown": [{"name": key, "weight_pct": round(value, 2)} for key, value in sorted(country_weights.items(), key=lambda item: item[1], reverse=True)],
            "sector_breakdown": [{"name": key, "weight_pct": round(value, 2)} for key, value in sorted(sector_weights.items(), key=lambda item: item[1], reverse=True)],
            "risk_score": risk_score,
            "risk_label": risk_label,
        },
        "rule_breaches": _sort_by_severity(rule_breaches),
        "warnings": _sort_by_severity(warnings),
        "opportunities": _sort_by_severity(opportunities),
        "suggested_actions": suggested_actions[:5],
        "positions": sorted(positions, key=lambda item: item["weight_pct"], reverse=True),
    }
