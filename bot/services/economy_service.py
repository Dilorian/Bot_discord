from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.economy import EconomyAccount, FamilyBank, InventoryItem, ShopItem, Transaction


async def get_account(session: AsyncSession, guild_id: int, user_id: int) -> EconomyAccount:
    result = await session.execute(select(EconomyAccount).where(EconomyAccount.guild_id == guild_id, EconomyAccount.user_id == user_id).with_for_update())
    account = result.scalar_one_or_none()
    if account is None:
        account = EconomyAccount(guild_id=guild_id, user_id=user_id)
        session.add(account)
        await session.flush()
    return account


async def transfer(session: AsyncSession, guild_id: int, from_id: int, to_id: int, amount: int, reason: str) -> None:
    if amount <= 0 or from_id == to_id:
        raise ValueError("Некорректная сумма перевода")
    sender = await get_account(session, guild_id, from_id)
    receiver = await get_account(session, guild_id, to_id)
    if sender.balance < amount:
        raise ValueError("Недостаточно средств")
    sender.balance -= amount
    receiver.balance += amount
    session.add(Transaction(guild_id=guild_id, from_user_id=from_id, to_user_id=to_id, amount=amount, transaction_type="transfer", reason=reason))
    await session.commit()


async def claim_daily(session: AsyncSession, guild_id: int, user_id: int) -> tuple[int, int]:
    account = await get_account(session, guild_id, user_id)
    today = date.today()
    if account.last_daily == today.isoformat():
        raise ValueError("Daily уже получен сегодня")
    yesterday = (today - timedelta(days=1)).isoformat()
    account.daily_streak = account.daily_streak + 1 if account.last_daily == yesterday else 1
    reward = 10_000 + min(account.daily_streak, 30) * 500
    account.balance += reward
    account.last_daily = today.isoformat()
    session.add(Transaction(guild_id=guild_id, to_user_id=user_id, amount=reward, transaction_type="daily", reason="Ежедневная награда"))
    await session.commit()
    return reward, account.daily_streak


async def claim_weekly(session: AsyncSession, guild_id: int, user_id: int) -> int:
    account = await get_account(session, guild_id, user_id)
    today = date.today()
    week_key = f"{today.isocalendar().year}-{today.isocalendar().week}"
    if account.last_weekly == week_key:
        raise ValueError("Weekly уже получен на этой неделе")
    reward = 75_000
    account.balance += reward
    account.last_weekly = week_key
    session.add(Transaction(guild_id=guild_id, to_user_id=user_id, amount=reward, transaction_type="weekly", reason="Еженедельная награда"))
    await session.commit()
    return reward


async def buy_item(session: AsyncSession, guild_id: int, user_id: int, item: ShopItem, quantity: int = 1) -> int:
    if quantity <= 0 or not item.active:
        raise ValueError("Некорректное количество или товар недоступен")
    if item.stock is not None and item.stock < quantity:
        raise ValueError("Недостаточно товара на складе")
    account = await get_account(session, guild_id, user_id)
    total = item.price * quantity
    if account.balance < total:
        raise ValueError("Недостаточно средств")
    account.balance -= total
    if item.stock is not None:
        item.stock -= quantity
    result = await session.execute(select(InventoryItem).where(InventoryItem.guild_id == guild_id, InventoryItem.user_id == user_id, InventoryItem.item_id == item.id).with_for_update())
    inv = result.scalar_one_or_none()
    if inv is None:
        inv = InventoryItem(guild_id=guild_id, user_id=user_id, item_id=item.id, quantity=0)
        session.add(inv)
    inv.quantity += quantity
    session.add(Transaction(guild_id=guild_id, from_user_id=user_id, amount=total, transaction_type="purchase", reason=f"Покупка: {item.name}", meta={"item_id": item.id, "quantity": quantity}))
    await session.commit()
    return total


async def sell_item(session: AsyncSession, guild_id: int, user_id: int, item: ShopItem, quantity: int = 1) -> int:
    result = await session.execute(select(InventoryItem).where(InventoryItem.guild_id == guild_id, InventoryItem.user_id == user_id, InventoryItem.item_id == item.id).with_for_update())
    inv = result.scalar_one_or_none()
    if inv is None or inv.quantity < quantity:
        raise ValueError("Недостаточно предметов")
    value = (item.price * quantity) // 2
    inv.quantity -= quantity
    account = await get_account(session, guild_id, user_id)
    account.balance += value
    session.add(Transaction(guild_id=guild_id, to_user_id=user_id, amount=value, transaction_type="sell", reason=f"Продажа: {item.name}", meta={"item_id": item.id, "quantity": quantity}))
    await session.commit()
    return value


async def get_family_bank(session: AsyncSession, guild_id: int) -> FamilyBank:
    bank = await session.get(FamilyBank, guild_id, with_for_update=True)
    if bank is None:
        bank = FamilyBank(guild_id=guild_id, balance=0)
        session.add(bank)
        await session.flush()
    return bank
