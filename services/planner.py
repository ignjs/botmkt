from __future__ import annotations

from typing import Dict, List

from db import get_investment_profile
from services.perplexity import generate_telegram_plan_summary, generate_weekly_plan_text
from services.rules_engine import analyze_portfolio_rules

URGENCY_ORDER = {"high": "Alta", "medium": "Media", "low": "Baja"}


def _general_status(diagnosis: Dict) -> str:
    breaches = diagnosis.get("rule_breaches", [])
    warnings = diagnosis.get("warnings", [])
    if any(item.get("severity") == "high" for item in breaches):
        return "La cartera está desalineada con tu perfil y requiere correcciones esta semana."
    if breaches or warnings:
        return "La cartera es operable, pero ya muestra desvíos que conviene corregir pronto."
    return "La cartera está alineada; el foco es sostener disciplina y no sobreoperar."


def _urgency(diagnosis: Dict) -> str:
    breaches = diagnosis.get("rule_breaches", [])
    warnings = diagnosis.get("warnings", [])
    if any(item.get("severity") == "high" for item in breaches):
        return "Alta"
    if breaches or warnings:
        return "Media"
    return "Baja"


def _format_misalignments(diagnosis: Dict) -> List[str]:
    items = diagnosis.get("rule_breaches", [])[:3] or diagnosis.get("warnings", [])[:3]
    return [f"- {item['message']}" for item in items] or ["- No se detectan quiebres relevantes de disciplina."]


def _format_actions(diagnosis: Dict) -> List[str]:
    actions = diagnosis.get("suggested_actions", [])[:5]
    if not actions:
        return ["1. Mantener el plan actual y revisar solo una vez tus pesos relativos."]
    return [f"{index}. {item['action']}" for index, item in enumerate(actions, start=1)]


def build_rules_based_plan(profile: Dict, diagnosis: Dict) -> str:
    summary = diagnosis.get("portfolio_summary", {})
    risk_score = summary.get("risk_score", 1)
    risk_label = summary.get("risk_label", "bajo").capitalize()
    urgency = _urgency(diagnosis)

    misalignments = "\n".join(_format_misalignments(diagnosis))
    actions = "\n".join(_format_actions(diagnosis))

    return (
        "🗂️ *Plan semanal de ejecución*\n\n"
        f"1. *Estado general:* {_general_status(diagnosis)}\n"
        f"2. *Desalineaciones clave:*\n{misalignments}\n"
        f"3. *Acciones concretas para esta semana:*\n{actions}\n"
        f"4. *Riesgo general actual:* {risk_label} ({risk_score}/10).\n"
        f"5. *Urgencia:* {urgency}.\n\n"
        f"Perfil base: {profile.get('preferred_strategy', 'mixta')} | horizonte {profile.get('investment_horizon', 'largo')} | riesgo {profile.get('risk_tolerance', 5)}/10."
    )


async def build_weekly_execution_plan(telegram_user_id: int) -> Dict:
    profile = await get_investment_profile(telegram_user_id)
    if not profile:
        return {
            "status": "missing_profile",
            "plan_markdown": "Primero configura tu perfil con `/perfil` para que el plan tenga reglas reales.",
        }

    diagnosis = await analyze_portfolio_rules(telegram_user_id, profile)
    if diagnosis["portfolio_summary"].get("position_count", 0) == 0:
        return {
            "status": "empty_portfolio",
            "profile": profile,
            "diagnosis": diagnosis,
            "plan_markdown": "No tienes posiciones cargadas. Agrega tu cartera con `+SYM cantidad precio` y luego usa `/plan_semana`.",
        }

    fallback_plan = build_rules_based_plan(profile, diagnosis)
    final_plan = fallback_plan

    try:
        ai_plan = await generate_weekly_plan_text(profile, diagnosis)
        if ai_plan:
            short_plan = await generate_telegram_plan_summary(ai_plan, diagnosis)
            final_plan = short_plan or ai_plan
    except Exception:
        final_plan = fallback_plan

    return {
        "status": "ok",
        "profile": profile,
        "diagnosis": diagnosis,
        "plan_markdown": final_plan,
        "fallback_markdown": fallback_plan,
        "urgency": _urgency(diagnosis),
    }
