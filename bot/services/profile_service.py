from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.profile import Profile
from bot.models.user import User


async def get_or_create_profile(session: AsyncSession, user: User) -> Profile:
    result = await session.execute(select(Profile).where(Profile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if profile is None:
        profile = Profile(user_id=user.id, guild_id=user.guild_id)
        session.add(profile)
        await session.commit()
        await session.refresh(profile)
    return profile


async def register_activity(session: AsyncSession, profile: Profile) -> None:
    """
    Обновляет серию активности (activity_streak). Считается по UTC-дате:
    - если участник уже был активен сегодня — ничего не меняем;
    - если был активен вчера — серия продолжается (+1);
    - иначе серия сбрасывается до 1.
    """
    today = date.today()
    if profile.last_activity_date == today:
        return

    if profile.last_activity_date == today - timedelta(days=1):
        profile.activity_streak += 1
    else:
        profile.activity_streak = 1

    profile.last_activity_date = today
    await session.commit()


def days_in_family(user: User) -> int:
    return max((date.today() - user.created_at.date()).days, 0)
