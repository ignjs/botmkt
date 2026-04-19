from __future__ import annotations

from typing import Callable, Dict, Optional, Tuple

from telegram import Update
from telegram.ext import ApplicationHandlerStop, ContextTypes

from db import get_investment_profile, save_investment_profile

PROFILE_FLOW_KEY = "investment_profile_flow"
PROFILE_VIEW_COMMANDS = {"/mi_perfil"}
PROFILE_ENTRY_COMMANDS = {"/perfil", "/perfil_inversion", "configurar perfil"}
PROFILE_EDIT_COMMANDS = {"/editar_perfil", "editar perfil"}
PROFILE_START_COMMANDS = PROFILE_ENTRY_COMMANDS | PROFILE_EDIT_COMMANDS
PROFILE_UPDATE_CONFIRM_RESPONSES = {"si", "sí", "actualizar", "editar", "/editar_perfil"}
PROFILE_CANCEL_RESPONSES = {"cancelar", "/cancelar", "no"}
PROFILE_KEEP_CURRENT_RESPONSES = {"mantener", "igual", "skip", "omitir"}
ALLOWED_HORIZONS = {"corto", "mediano", "largo"}
ALLOWED_STRATEGIES = {"growth", "dividendos", "valor", "mixta"}


def _normalize_percentage(text: str, field_name: str) -> float:
    try:
        value = float(text.replace(",", ".").strip())
    except ValueError as exc:
        raise ValueError(f"{field_name} debe ser un número entre 0 y 100.") from exc

    if not 0 <= value <= 100:
        raise ValueError(f"{field_name} debe estar entre 0 y 100.")
    return round(value, 2)


def _validate_risk_tolerance(text: str) -> int:
    try:
        value = int(text.strip())
    except ValueError as exc:
        raise ValueError("El riesgo tolerado debe ser un entero del 1 al 10.") from exc

    if not 1 <= value <= 10:
        raise ValueError("El riesgo tolerado debe estar entre 1 y 10.")
    return value


def _validate_horizon(text: str) -> str:
    normalized = text.strip().lower()
    aliases = {"medio": "mediano"}
    normalized = aliases.get(normalized, normalized)
    if normalized not in ALLOWED_HORIZONS:
        raise ValueError("El horizonte debe ser: corto, mediano o largo.")
    return normalized


def _validate_strategy(text: str) -> str:
    normalized = text.strip().lower()
    if normalized not in ALLOWED_STRATEGIES:
        raise ValueError("La estrategia debe ser: growth, dividendos, valor o mixta.")
    return normalized


PROFILE_STEPS: Tuple[Tuple[str, str, Callable[[str], object]], ...] = (
    ("risk_tolerance", "1/8 Riesgo tolerado (1-10). Ejemplo: `4`", _validate_risk_tolerance),
    ("investment_horizon", "2/8 Horizonte de inversión: `corto`, `mediano` o `largo`.", _validate_horizon),
    ("max_position_pct", "3/8 Máximo por posición individual (%). Ejemplo: `25`", lambda text: _normalize_percentage(text, "max_position_pct")),
    ("max_country_pct", "4/8 Máximo por país o mercado (%). Ejemplo: `70`", lambda text: _normalize_percentage(text, "max_country_pct")),
    ("max_sector_pct", "5/8 Máximo por sector (%). Ejemplo: `45`", lambda text: _normalize_percentage(text, "max_sector_pct")),
    ("max_drawdown_pct", "6/8 Drawdown máximo tolerado (%). Ejemplo: `12`", lambda text: _normalize_percentage(text, "max_drawdown_pct")),
    ("preferred_strategy", "7/8 Estrategia preferida: `growth`, `dividendos`, `valor` o `mixta`.", _validate_strategy),
    ("cash_buffer_pct", "8/8 Caja objetivo (%). Ejemplo: `10`", lambda text: _normalize_percentage(text, "cash_buffer_pct")),
)


def _format_profile(profile: Dict) -> str:
    return (
        "🧭 *Tu perfil de inversión*\n"
        f"- Riesgo tolerado: *{profile['risk_tolerance']}/10*\n"
        f"- Horizonte: *{profile['investment_horizon']}*\n"
        f"- Máx. por posición: *{profile['max_position_pct']}%*\n"
        f"- Máx. por país: *{profile['max_country_pct']}%*\n"
        f"- Máx. por sector: *{profile['max_sector_pct']}%*\n"
        f"- Drawdown máximo: *{profile['max_drawdown_pct']}%*\n"
        f"- Estrategia preferida: *{profile['preferred_strategy']}*\n"
        f"- Caja objetivo: *{profile['cash_buffer_pct']}%*"
    )


def _build_step_prompt(step_index: int, existing_profile: Optional[Dict] = None) -> str:
    field_name, prompt, _ = PROFILE_STEPS[step_index]
    if existing_profile and field_name in existing_profile:
        return f"{prompt}\nValor actual: `{existing_profile[field_name]}`. Si quieres conservarlo, escribe `mantener`."
    return prompt


def _start_questionnaire(context: ContextTypes.DEFAULT_TYPE, existing_profile: Optional[Dict] = None):
    context.user_data[PROFILE_FLOW_KEY] = {
        "mode": "questionnaire",
        "step": 0,
        "data": {},
        "existing_profile": existing_profile or {},
    }


async def investment_profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return

    text = message.text.strip()
    normalized = text.lower()
    user_id = update.effective_user.id

    if normalized in PROFILE_VIEW_COMMANDS:
        profile = await get_investment_profile(user_id)
        if not profile:
            await message.reply_text("Aún no tienes perfil guardado. Usa `/perfil` para configurarlo.", parse_mode="Markdown")
            raise ApplicationHandlerStop

        await message.reply_text(
            f"{_format_profile(profile)}\n\nSi quieres actualizarlo, usa `/editar_perfil`.",
            parse_mode="Markdown",
        )
        raise ApplicationHandlerStop

    if normalized in PROFILE_START_COMMANDS:
        existing = await get_investment_profile(user_id)

        if normalized in PROFILE_EDIT_COMMANDS:
            _start_questionnaire(context, existing)
            intro = "Vamos a actualizar tu perfil actual." if existing else "Aún no tienes perfil. Vamos a crearlo."
            await message.reply_text(
                f"{intro} Responde una pregunta a la vez o escribe `cancelar`.\n\n{_build_step_prompt(0, existing)}",
                parse_mode="Markdown",
            )
            raise ApplicationHandlerStop

        if existing:
            context.user_data[PROFILE_FLOW_KEY] = {
                "mode": "confirm_update",
                "existing_profile": existing,
            }
            await message.reply_text(
                f"{_format_profile(existing)}\n\nYa existe un perfil asociado a tu usuario. Responde `actualizar` para modificarlo o `cancelar` para dejarlo igual.",
                parse_mode="Markdown",
            )
            raise ApplicationHandlerStop

        _start_questionnaire(context)
        await message.reply_text(
            f"Vamos a crear tu perfil. Responde una pregunta a la vez o escribe `cancelar`.\n\n{_build_step_prompt(0)}",
            parse_mode="Markdown",
        )
        raise ApplicationHandlerStop

    flow = context.user_data.get(PROFILE_FLOW_KEY)
    if not flow:
        return

    mode = flow.get("mode", "questionnaire")
    if mode == "confirm_update":
        if normalized in PROFILE_UPDATE_CONFIRM_RESPONSES:
            existing = flow.get("existing_profile") or {}
            _start_questionnaire(context, existing)
            await message.reply_text(
                f"Vamos a actualizar tu perfil actual. Responde una pregunta a la vez o escribe `cancelar`.\n\n{_build_step_prompt(0, existing)}",
                parse_mode="Markdown",
            )
            raise ApplicationHandlerStop

        if normalized in PROFILE_CANCEL_RESPONSES:
            context.user_data.pop(PROFILE_FLOW_KEY, None)
            await message.reply_text(
                "Perfecto, mantengo tu perfil actual. Usa `/plan_semana` cuando quieras tu plan accionable.",
                parse_mode="Markdown",
            )
            raise ApplicationHandlerStop

        await message.reply_text(
            "Ya encontré tu perfil actual. Responde `actualizar` para modificarlo o `cancelar` para salir.",
            parse_mode="Markdown",
        )
        raise ApplicationHandlerStop

    if normalized in PROFILE_CANCEL_RESPONSES:
        context.user_data.pop(PROFILE_FLOW_KEY, None)
        await message.reply_text("Perfil cancelado. Cuando quieras retomarlo, usa `/perfil`.", parse_mode="Markdown")
        raise ApplicationHandlerStop

    step_index = int(flow.get("step", 0))
    if step_index >= len(PROFILE_STEPS):
        context.user_data.pop(PROFILE_FLOW_KEY, None)
        return

    field_name, prompt, validator = PROFILE_STEPS[step_index]
    existing_profile = flow.get("existing_profile") or {}

    try:
        if normalized in PROFILE_KEEP_CURRENT_RESPONSES and field_name in existing_profile:
            flow.setdefault("data", {})[field_name] = existing_profile[field_name]
        else:
            flow.setdefault("data", {})[field_name] = validator(text)
    except ValueError as exc:
        await message.reply_text(
            f"⚠️ {exc}\n\n{_build_step_prompt(step_index, existing_profile)}",
            parse_mode="Markdown",
        )
        raise ApplicationHandlerStop

    flow["step"] = step_index + 1
    if flow["step"] >= len(PROFILE_STEPS):
        await save_investment_profile(user_id, flow["data"])
        context.user_data.pop(PROFILE_FLOW_KEY, None)
        profile = await get_investment_profile(user_id)
        await message.reply_text(
            f"✅ Perfil guardado correctamente.\n\n{_format_profile(profile)}\n\nUsa `/plan_semana` para recibir un plan accionable.",
            parse_mode="Markdown",
        )
        raise ApplicationHandlerStop

    await message.reply_text(_build_step_prompt(flow["step"], existing_profile), parse_mode="Markdown")
    raise ApplicationHandlerStop
