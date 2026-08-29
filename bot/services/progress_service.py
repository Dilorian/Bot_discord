from __future__ import annotations

import logging
from typing import Sequence

import discord

from bot.services import achievement_service, quest_service, season_service
from bot.services.db import async_session_factory
from bot.services.log_service import send_log_embed
from bot.services.profile_service import days_in_family, get_or_create_profile
from bot.services.settings_service import get_or_create_settings
from bot.services.user_service import get_or_create_user
from bot.services.xp_service import add_xp

logger = logging.getLogger("bot.progress")

DEFAULT_ACHIEVEMENT_METRICS: Sequence[str] = (
    "total_xp",
    "voice_seconds",
    "message_count",
    "reputation",
    "days_in_family",
)


async def handle_metric_event(
    bot: discord.Client,
    guild: discord.Guild,
    member: discord.Member,
    requirement_deltas: dict[str, int],
    achievement_metrics: Sequence[str] = DEFAULT_ACHIEVEMENT_METRICS,
) -> None:
    """
    Единая точка входа, которую вызывают Cogs после события активности
    (сообщение, Voice-сессия, ручное начисление XP/репутации и т.д.):
    - обновляет прогресс автоматически отслеживаемых заданий (Этап 3, раздел 6);
    - начисляет XP в активный сезон / Family Pass (раздел 9);
    - проверяет условия достижений и разблокирует новые (раздел 7);
    - выдаёт награду за достижение (XP, титул) и уведомляет в канал логов.

    requirement_deltas: приращения за это событие, например
        {"messages": 1, "xp": 12} или {"voice_minutes": 3, "xp": 15} или {"xp": 100}.
    """
    try:
        async with async_session_factory() as session:
            settings = await get_or_create_settings(session, guild.id)
            user = await get_or_create_user(session, member, guild.id)
            profile = await get_or_create_profile(session, user)

            completed_quests = []
            for requirement_type, amount in requirement_deltas.items():
                if amount > 0:
                    completed_quests += await quest_service.add_progress(
                        session, guild.id, member.id, requirement_type, amount
                    )

            xp_delta = requirement_deltas.get("xp", 0)
            if xp_delta > 0:
                await season_service.add_season_xp(session, guild.id, member.id, xp_delta)

            totals = {
                "total_xp": profile.total_xp,
                "voice_seconds": profile.voice_seconds,
                "message_count": profile.message_count,
                "reputation": profile.reputation,
                "days_in_family": days_in_family(user),
            }
            unlocked = []
            for metric in achievement_metrics:
                if metric in totals:
                    unlocked += await achievement_service.check_and_unlock(
                        session, guild.id, member.id, metric, totals[metric]
                    )

            for achievement in unlocked:
                if achievement.reward_xp:
                    await add_xp(
                        session, profile, member.id, achievement.reward_xp,
                        reason=f"achievement:{achievement.key}",
                    )
                if achievement.reward_title and not profile.title:
                    profile.title = achievement.reward_title
            if any(a.reward_title for a in unlocked):
                await session.commit()

        for quest in completed_quests:
            await send_log_embed(
                bot,
                settings.log_channel_id,
                title="🎯 Задание выполнено",
                description=(
                    f"{member.mention} выполнил(а) задание **{quest.title}**!\n"
                    f"Заберите награду командой `/quests`."
                ),
            )

        for achievement in unlocked:
            emoji = "🔒" if achievement.rarity == "secret" else "🏆"
            await send_log_embed(
                bot,
                settings.log_channel_id,
                title=f"{emoji} Новое достижение",
                description=(
                    f"{member.mention} получил(а) достижение "
                    f"**{achievement.name}** ({achievement.rarity})!"
                ),
            )
    except Exception:
        # Прогресс заданий/достижений не должен ронять обработку XP/сообщений/voice.
        logger.exception("Ошибка при обработке прогресса заданий/достижений для %s", member.id)
