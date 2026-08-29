from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.economy import (
    Case,
    CaseReward,
    EconomyAccount,
    InventoryItem,
    ShopItem,
    Transaction,
)

DAILY_AMOUNT = 10_000
WEEKLY_AMOUNT = 50_000
REWARD_TYPES = {"money", "xp", "item", "title"}


async def get_or_create_account(session: AsyncSession, guild_id: int, discord_id: int) -> EconomyAccount:
    result = await session.execute(
        select(EconomyAccount).where(
            EconomyAccount.guild_id == guild_id, EconomyAccount.discord_id == discord_id
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        account = EconomyAccount(guild_id=guild_id, discord_id=discord_id, balance=0)
        session.add(account)
        await session.flush()
    return account


async def get_balance(session: AsyncSession, guild_id: int, discord_id: int) -> int:
    return (await get_or_create_account(session, guild_id, discord_id)).balance


async def _change_balance(
    session: AsyncSession,
    guild_id: int,
    discord_id: int,
    amount: int,
    transaction_type: str,
    *,
    actor_discord_id: Optional[int] = None,
    target_discord_id: Optional[int] = None,
    description: str = "",
    meta: Optional[dict] = None,
    allow_negative: bool = False,
) -> Transaction:
    # SELECT FOR UPDATE защищает баланс от двойного списания при одновременных запросах.
    result = await session.execute(
        select(EconomyAccount)
        .where(EconomyAccount.guild_id == guild_id, EconomyAccount.discord_id == discord_id)
        .with_for_update()
    )
    account = result.scalar_one_or_none()
    if account is None:
        account = EconomyAccount(guild_id=guild_id, discord_id=discord_id, balance=0)
        session.add(account)
        await session.flush()
    new_balance = account.balance + amount
    if not allow_negative and new_balance < 0:
        raise ValueError("Недостаточно средств.")
    account.balance = new_balance
    tx = Transaction(
        guild_id=guild_id,
        transaction_type=transaction_type,
        discord_id=discord_id,
        target_discord_id=target_discord_id,
        actor_discord_id=actor_discord_id,
        amount=amount,
        balance_after=new_balance,
        description=description,
        meta=meta,
    )
    session.add(tx)
    await session.flush()
    return tx


async def deposit(
    session: AsyncSession, guild_id: int, discord_id: int, amount: int,
    *, actor_discord_id: Optional[int] = None, reason: str = "Пополнение"
) -> Transaction:
    if amount <= 0:
        raise ValueError("Сумма должна быть больше нуля.")
    tx = await _change_balance(
        session, guild_id, discord_id, amount, "money_add",
        actor_discord_id=actor_discord_id, description=reason,
    )
    await session.commit()
    return tx


async def withdraw(
    session: AsyncSession, guild_id: int, discord_id: int, amount: int,
    *, actor_discord_id: Optional[int] = None, reason: str = "Списание"
) -> Transaction:
    if amount <= 0:
        raise ValueError("Сумма должна быть больше нуля.")
    tx = await _change_balance(
        session, guild_id, discord_id, -amount, "money_remove",
        actor_discord_id=actor_discord_id, description=reason,
    )
    await session.commit()
    return tx


async def transfer(
    session: AsyncSession, guild_id: int, sender_id: int, receiver_id: int, amount: int
) -> tuple[Transaction, Transaction]:
    if sender_id == receiver_id:
        raise ValueError("Нельзя переводить деньги самому себе.")
    if amount <= 0:
        raise ValueError("Сумма должна быть больше нуля.")

    # Стабильный порядок блокировок предотвращает deadlock при встречных переводах.
    first, second = sorted((sender_id, receiver_id))
    await get_or_create_account(session, guild_id, first)
    await get_or_create_account(session, guild_id, second)
    result = await session.execute(
        select(EconomyAccount)
        .where(
            EconomyAccount.guild_id == guild_id,
            EconomyAccount.discord_id.in_([first, second]),
        )
        .order_by(EconomyAccount.discord_id)
        .with_for_update()
    )
    accounts = {a.discord_id: a for a in result.scalars().all()}
    sender = accounts[sender_id]
    receiver = accounts[receiver_id]
    if sender.balance < amount:
        raise ValueError("Недостаточно средств.")
    sender.balance -= amount
    receiver.balance += amount

    tx_out = Transaction(
        guild_id=guild_id, transaction_type="transfer",
        discord_id=sender_id, target_discord_id=receiver_id,
        actor_discord_id=sender_id, amount=-amount,
        balance_after=sender.balance, description=f"Перевод пользователю {receiver_id}",
    )
    tx_in = Transaction(
        guild_id=guild_id, transaction_type="transfer",
        discord_id=receiver_id, target_discord_id=sender_id,
        actor_discord_id=sender_id, amount=amount,
        balance_after=receiver.balance, description=f"Получен перевод от {sender_id}",
    )
    session.add_all([tx_out, tx_in])
    await session.commit()
    return tx_out, tx_in


async def claim_bonus(
    session: AsyncSession, guild_id: int, discord_id: int, bonus_type: str, amount: int
) -> Optional[Transaction]:
    """Daily/weekly с блокировкой кошелька: параллельные запросы не дают двойной бонус."""
    if amount <= 0:
        raise ValueError("Размер бонуса должен быть положительным.")
    now = datetime.now(timezone.utc)
    if bonus_type == "daily":
        since = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif bonus_type == "weekly":
        day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        since = day.fromordinal(day.toordinal() - day.weekday())
    else:
        raise ValueError("Неизвестный тип бонуса.")

    # Сначала блокируем кошелёк, затем проверяем историю.
    account_result = await session.execute(
        select(EconomyAccount)
        .where(EconomyAccount.guild_id == guild_id, EconomyAccount.discord_id == discord_id)
        .with_for_update()
    )
    account = account_result.scalar_one_or_none()
    if account is None:
        account = EconomyAccount(guild_id=guild_id, discord_id=discord_id, balance=0)
        session.add(account)
        await session.flush()

    result = await session.execute(
        select(func.count(Transaction.id)).where(
            Transaction.guild_id == guild_id,
            Transaction.discord_id == discord_id,
            Transaction.transaction_type == bonus_type,
            Transaction.created_at >= since,
        )
    )
    if int(result.scalar_one()) > 0:
        return None

    account.balance += amount
    tx = Transaction(
        guild_id=guild_id, transaction_type=bonus_type, discord_id=discord_id,
        actor_discord_id=discord_id, amount=amount, balance_after=account.balance,
        description=f"{bonus_type} bonus",
    )
    session.add(tx)
    await session.commit()
    await session.refresh(tx)
    return tx


async def add_inventory(
    session: AsyncSession, guild_id: int, discord_id: int,
    item_key: str, item_name: str, quantity: int = 1,
    expires_at=None,
) -> InventoryItem:
    if quantity <= 0:
        raise ValueError("Количество должно быть больше нуля.")
    result = await session.execute(
        select(InventoryItem).where(
            InventoryItem.guild_id == guild_id,
            InventoryItem.discord_id == discord_id,
            InventoryItem.item_key == item_key,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        item = InventoryItem(
            guild_id=guild_id, discord_id=discord_id, item_key=item_key,
            item_name=item_name, quantity=quantity, expires_at=expires_at,
        )
        session.add(item)
    else:
        item.quantity += quantity
        if expires_at is not None:
            item.expires_at = expires_at
    await session.flush()
    return item


async def list_inventory(session: AsyncSession, guild_id: int, discord_id: int) -> list[InventoryItem]:
    result = await session.execute(
        select(InventoryItem).where(
            InventoryItem.guild_id == guild_id, InventoryItem.discord_id == discord_id,
            InventoryItem.quantity > 0,
        ).order_by(InventoryItem.item_name)
    )
    return list(result.scalars().all())


async def create_shop_item(session: AsyncSession, guild_id: int, **kwargs) -> ShopItem:
    item = ShopItem(guild_id=guild_id, **kwargs)
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


async def get_shop_item(session: AsyncSession, guild_id: int, item_key: str, *, lock: bool = False) -> Optional[ShopItem]:
    stmt = select(ShopItem).where(ShopItem.guild_id == guild_id, ShopItem.item_key == item_key)
    if lock:
        stmt = stmt.with_for_update()
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_shop(session: AsyncSession, guild_id: int) -> list[ShopItem]:
    result = await session.execute(
        select(ShopItem).where(ShopItem.guild_id == guild_id, ShopItem.is_active.is_(True))
        .order_by(ShopItem.price, ShopItem.name)
    )
    return list(result.scalars().all())


async def buy_shop_item(session: AsyncSession, guild_id: int, discord_id: int, item_key: str) -> ShopItem:
    item = await get_shop_item(session, guild_id, item_key, lock=True)
    if item is None or not item.is_active:
        raise ValueError("Товар не найден или отключён.")
    if item.stock is not None and item.stock <= 0:
        raise ValueError("Товар закончился.")
    await _change_balance(
        session, guild_id, discord_id, -item.price, "purchase",
        actor_discord_id=discord_id, description=f"Покупка {item.name}",
        meta={"item_key": item.item_key},
    )
    if item.stock is not None:
        item.stock -= 1
    if item.item_type in {"item", "title"}:
        await add_inventory(session, guild_id, discord_id, item.item_key, item.name, 1)
    elif item.item_type == "case":
        await add_inventory(session, guild_id, discord_id, f"case:{item.item_value}", item.name, 1)
    await session.commit()
    return item


async def create_case(session: AsyncSession, guild_id: int, **kwargs) -> Case:
    case = Case(guild_id=guild_id, **kwargs)
    session.add(case)
    await session.commit()
    await session.refresh(case)
    return case


async def get_case(session: AsyncSession, guild_id: int, case_key: str, *, lock: bool = False) -> Optional[Case]:
    stmt = select(Case).where(Case.guild_id == guild_id, Case.case_key == case_key)
    if lock:
        stmt = stmt.with_for_update()
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_cases(session: AsyncSession, guild_id: int) -> list[Case]:
    result = await session.execute(
        select(Case).where(Case.guild_id == guild_id, Case.is_active.is_(True)).order_by(Case.price)
    )
    return list(result.scalars().all())


async def add_case_reward(session: AsyncSession, case: Case, **kwargs) -> CaseReward:
    if kwargs.get("weight", 0) <= 0:
        raise ValueError("Вес награды должен быть больше нуля.")
    reward = CaseReward(case_id=case.id, guild_id=case.guild_id, **kwargs)
    session.add(reward)
    await session.commit()
    await session.refresh(reward)
    return reward


async def open_case(session: AsyncSession, guild_id: int, discord_id: int, case_key: str) -> CaseReward:
    case = await get_case(session, guild_id, case_key, lock=True)
    if case is None or not case.is_active:
        raise ValueError("Кейс не найден или отключён.")
    if case.stock is not None and case.stock <= 0:
        raise ValueError("Кейсы закончились.")

    await _change_balance(
        session, guild_id, discord_id, -case.price, "case",
        actor_discord_id=discord_id, description=f"Открытие кейса {case.name}",
        meta={"case_key": case.case_key},
    )
    rewards = list((await session.execute(
        select(CaseReward).where(CaseReward.case_id == case.id)
    )).scalars().all())
    if not rewards:
        raise ValueError("В кейсе нет наград.")
    total_weight = sum(r.weight for r in rewards)
    roll = random.uniform(0, total_weight)
    cursor = 0.0
    selected = rewards[-1]
    for reward in rewards:
        cursor += reward.weight
        if roll <= cursor:
            selected = reward
            break
    if case.stock is not None:
        case.stock -= 1
    if selected.reward_type == "item" or selected.reward_type == "title":
        await add_inventory(
            session, guild_id, discord_id, selected.reward_value, selected.reward_value, selected.quantity
        )
    await session.commit()
    return selected


async def recent_transactions(session: AsyncSession, guild_id: int, discord_id: int, limit: int = 10) -> list[Transaction]:
    result = await session.execute(
        select(Transaction).where(
            Transaction.guild_id == guild_id, Transaction.discord_id == discord_id
        ).order_by(Transaction.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def get_bank(session: AsyncSession, guild_id: int) -> int:
    from bot.models.economy import FamilyBank
    result = await session.execute(select(FamilyBank).where(FamilyBank.guild_id == guild_id).with_for_update())
    bank = result.scalar_one_or_none()
    if bank is None:
        bank = FamilyBank(guild_id=guild_id, balance=0)
        session.add(bank)
        await session.flush()
    return bank.balance


async def bank_deposit(session: AsyncSession, guild_id: int, user_id: int, amount: int) -> int:
    from bot.models.economy import FamilyBank
    if amount <= 0:
        raise ValueError("Сумма должна быть больше нуля.")
    result = await session.execute(
        select(FamilyBank).where(FamilyBank.guild_id == guild_id).with_for_update()
    )
    bank = result.scalar_one_or_none()
    if bank is None:
        bank = FamilyBank(guild_id=guild_id, balance=0)
        session.add(bank)
        await session.flush()
    await _change_balance(session, guild_id, user_id, -amount, "bank_deposit",
                          actor_discord_id=user_id, description="Взнос в семейный банк")
    bank.balance += amount
    await session.commit()
    return bank.balance


async def bank_withdraw(session: AsyncSession, guild_id: int, user_id: int, amount: int) -> int:
    from bot.models.economy import FamilyBank
    if amount <= 0:
        raise ValueError("Сумма должна быть больше нуля.")
    result = await session.execute(
        select(FamilyBank).where(FamilyBank.guild_id == guild_id).with_for_update()
    )
    bank = result.scalar_one_or_none()
    if bank is None or bank.balance < amount:
        raise ValueError("В семейном банке недостаточно средств.")
    await _change_balance(session, guild_id, user_id, amount, "bank_withdraw",
                          actor_discord_id=user_id, description="Получение из семейного банка")
    bank.balance -= amount
    await session.commit()
    return bank.balance
