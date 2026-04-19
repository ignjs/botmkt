from telegram import Update
from telegram.ext import ContextTypes

from application.use_cases.get_profile import GetProfileUseCase
from application.use_cases.save_profile import SaveProfileUseCase


class ProfileHandler:
    """Handler de perfil basado en casos de uso."""

    def __init__(self, save_profile: SaveProfileUseCase, get_profile: GetProfileUseCase):
        self._save = save_profile
        self._get = get_profile

    async def handle_view(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        profile = await self._get.execute(user_id)
        if profile is None:
            await update.message.reply_text("Aún no tienes perfil guardado. Usa /perfil para crearlo.")
            return
        await update.message.reply_text(
            f"Riesgo: {profile.risk_tolerance}/10 | Horizonte: {profile.investment_horizon} | Estrategia: {profile.preferred_strategy}"
        )
