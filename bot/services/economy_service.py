from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.economy import BankAccount, Case, CaseReward, InventoryItem, ShopItem, Transaction, Wallet

DAILY_AMOUNT = 500
WEEKLY_AMOUNT = 2500


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def get_wallet(session: AsyncSession, guild_id: int, discord_id: int, *, lock: bool = False) -> Wallet:
    stmt = select(Wallet).where(Wallet.guild_id == guild_id, Wallet.discord_id == discord_id)
    if lock:
        stmt = stmt.with_for_update()
    wallet = (await session.execute(stmt)).scalar_one_or_none()
    if wallet is None:
        wallet = Wallet(guild_id=guild_id, discord_id=discord_id)
        session.add(wallet)
        await session.flush()
        if lock:
            # Newly inserted row is owned by this transaction; no second lock needed.
            return wallet
    return wallet


async def get_balance(session: AsyncSession, guild_id: int, discord_id: int) -> int:
    return (await get_wallet(session, guild_id, discord_id)).balance


async def credit(
    session: AsyncSession, guild_id: int, discord_id: int, amount: int,
    *, transaction_type: str = "reward", actor_discord_id: int | None = None,
    description: str = "", reference: str | None = None,
) -> Transaction:
    if amount <= 0:
        raise ValueError("Сумма должна быть больше нуля.")
    wallet = await get_wallet(session, guild_id, discord_id, lock=True)
    wallet.balance += amount
    wallet.lifetime_earned += amount
    tx = Transaction(
        guild_id=guild_id, actor_discord_id=actor_discord_id,
        to_discord_id=discord_id, amount=amount, balance_after=wallet.balance,
        transaction_type=transaction_type, description=description, reference=reference,
    )
    session.add(tx)
    await session.commit()
    await session.refresh(tx)
    return tx


async def debit(
    session: AsyncSession, guild_id: int, discord_id: int, amount: int,
    *, transaction_type: str = "spend", actor_discord_id: int | None = None,
    description: str = "", reference: str | None = None,
) -> Transaction:
    if amount <= 0:
        raise ValueError("Сумма должна быть больше нуля.")
    wallet = await get_wallet(session, guild_id, discord_id, lock=True)
    if wallet.balance < amount:
        raise ValueError("Недостаточно средств.")
    wallet.balance -= amount
    wallet.lifetime_spent += amount
    tx = Transaction(
        guild_id=guild_id, actor_discord_id=actor_discord_id,
        from_discord_id=discord_id, amount=-amount, balance_after=wallet.balance,
        transaction_type=transaction_type, description=description, reference=reference,
    )
    session.add(tx)
    await session.commit()
    await session.refresh(tx)
    return tx


async def transfer(session: AsyncSession, guild_id: int, sender_id: int, receiver_id: int, amount: int):
    if sender_id == receiver_id:
        raise ValueError("Нельзя переводить деньги самому себе.")
    if amount <= 0:
        raise ValueError("Сумма должна быть больше нуля.")
    ids = sorted((sender_id, receiver_id))
    wallets = {}
    for uid in ids:
        wallets[uid] = await get_wallet(session, guild_id, uid, lock=True)
    sender, receiver = wallets[sender_id], wallets[receiver_id]
    if sender.balance < amount:
        raise ValueError("Недостаточно средств.")
    sender.balance -= amount
    sender.lifetime_spent += amount
    receiver.balance += amount
    receiver.lifetime_earned += amount
    out_tx = Transaction(
        guild_id=guild_id, actor_discord_id=sender_id,
        from_discord_id=sender_id, to_discord_id=receiver_id, amount=-amount,
        balance_after=sender.balance, transaction_type="transfer", description="Исходящий перевод",
    )
    in_tx = Transaction(
        guild_id=guild_id, actor_discord_id=sender_id,
        from_discord_id=sender_id, to_discord_id=receiver_id, amount=amount,
        balance_after=receiver.balance, transaction_type="transfer", description="Входящий перевод",
    )
    session.add_all([out_tx, in_tx])
    await session.commit()
    await session.refresh(out_tx)
    return out_tx, in_tx


async def claim_bonus(session: AsyncSession, guild_id: int, discord_id: int, kind: str, amount: int) -> Optional[Transaction]:
    if kind not in {"daily", "weekly"}:
        raise ValueError("Неизвестный тип бонуса.")
    wallet = await get_wallet(session, guild_id, discord_id, lock=True)
    now = _now()
    last = wallet.daily_claimed_at if kind == "daily" else wallet.weekly_claimed_at
    period = timedelta(days=1 if kind == "daily" else 7)
    if last and now - last < period:
        return None
    if kind == "daily":
        wallet.daily_claimed_at = now
    else:
        wallet.weekly_claimed_at = now
    wallet.balance += amount
    wallet.lifetime_earned += amount
    tx = Transaction(
        guild_id=guild_id, actor_discord_id=discord_id, to_discord_id=discord_id,
        amount=amount, balance_after=wallet.balance, transaction_type=kind,
        description=f"{kind} bonus",
    )
    session.add(tx)
    await session.commit()
    await session.refresh(tx)
    return tx


async def list_transactions(session: AsyncSession, guild_id: int, discord_id: int, limit: int = 15) -> list[Transaction]:
    result = await session.execute(
        select(Transaction).where(
            Transaction.guild_id == guild_id,
            (Transaction.from_discord_id == discord_id) | (Transaction.to_discord_id == discord_id),
        ).order_by(Transaction.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def list_shop(session: AsyncSession, guild_id: int) -> list[ShopItem]:
    result = await session.execute(select(ShopItem).where(ShopItem.guild_id == guild_id, ShopItem.is_active.is_(True)).order_by(ShopItem.id))
    return list(result.scalars().all())


async def create_shop_item(session: AsyncSession, guild_id: int, **kwargs) -> ShopItem:
    if kwargs.get("price", 0) < 0:
        raise ValueError("Цена не может быть отрицательной.")
    item = ShopItem(guild_id=guild_id, **kwargs)
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


async def buy_shop_item(session: AsyncSession, guild_id: int, discord_id: int, item_key: str) -> ShopItem:
    item = (await session.execute(
        select(ShopItem).where(ShopItem.guild_id == guild_id, ShopItem.item_key == item_key, ShopItem.is_active.is_(True)).with_for_update()
    )).scalar_one_or_none()
    if item is None:
        raise ValueError("Товар не найден.")
    if item.stock is not None and item.stock <= 0:
        raise ValueError("Товар закончился.")
    wallet = await get_wallet(session, guild_id, discord_id, lock=True)
    if wallet.balance < item.price:
        raise ValueError("Недостаточно средств.")
    wallet.balance -= item.price
    wallet.lifetime_spent += item.price
    if item.stock is not None:
        item.stock -= 1
    inv = (await session.execute(select(InventoryItem).where(
        InventoryItem.guild_id == guild_id, InventoryItem.discord_id == discord_id,
        InventoryItem.item_key == item.item_key,
    ).with_for_update())).scalar_one_or_none()
    if inv is None:
        inv = InventoryItem(guild_id=guild_id, discord_id=discord_id, item_key=item.item_key,
                            name=item.name, item_type=item.item_type, quantity=1,
                            metadata={"value": item.item_key})
        session.add(inv)
    else:
        inv.quantity += 1
    session.add(Transaction(
        guild_id=guild_id, actor_discord_id=discord_id, from_discord_id=discord_id,
        amount=-item.price, balance_after=wallet.balance, transaction_type="purchase",
        description=f"Покупка: {item.name}", reference=f"shop:{item.id}",
    ))
    await session.commit()
    return item


async def list_inventory(session: AsyncSession, guild_id: int, discord_id: int) -> list[InventoryItem]:
    result = await session.execute(select(InventoryItem).where(
        InventoryItem.guild_id == guild_id, InventoryItem.discord_id == discord_id,
        InventoryItem.quantity > 0,
    ).order_by(InventoryItem.name))
    return list(result.scalars().all())


async def add_inventory(session: AsyncSession, guild_id: int, discord_id: int, item_key: str, name: str, item_type: str = "item", quantity: int = 1, metadata: dict | None = None) -> InventoryItem:
    if quantity <= 0:
        raise ValueError("Количество должно быть больше нуля.")
    inv = (await session.execute(select(InventoryItem).where(
        InventoryItem.guild_id == guild_id, InventoryItem.discord_id == discord_id, InventoryItem.item_key == item_key,
    ).with_for_update())).scalar_one_or_none()
    if inv is None:
        inv = InventoryItem(guild_id=guild_id, discord_id=discord_id, item_key=item_key, name=name,
                            item_type=item_type, quantity=quantity, metadata=metadata or {})
        session.add(inv)
    else:
        inv.quantity += quantity
    await session.flush()
    return inv


async def list_cases(session: AsyncSession, guild_id: int) -> list[Case]:
    return list((await session.execute(select(Case).where(Case.guild_id == guild_id, Case.is_active.is_(True)).order_by(Case.id))).scalars().all())


async def create_case(session: AsyncSession, guild_id: int, key: str, name: str, price: int, description: str = "", stock: int | None = None, created_by: int | None = None) -> Case:
    if price < 0:
        raise ValueError("Цена не может быть отрицательной.")
    case = Case(guild_id=guild_id, key=key, name=name, description=description, price=price, stock=stock, created_by=created_by)
    session.add(case)
    await session.commit()
    await session.refresh(case)
    return case


async def add_case_reward(session: AsyncSession, case_id: int, reward_type: str, reward_value: str, weight: int, amount: int = 0, rarity: str = "Common") -> CaseReward:
    if weight <= 0:
        raise ValueError("Вес должен быть больше нуля.")
    reward = CaseReward(case_id=case_id, reward_type=reward_type, reward_value=reward_value, weight=weight, amount=amount, rarity=rarity)
    session.add(reward)
    await session.commit()
    await session.refresh(reward)
    return reward


async def open_case(session: AsyncSession, guild_id: int, discord_id: int, key: str):
    case = (await session.execute(select(Case).where(Case.guild_id == guild_id, Case.key == key, Case.is_active.is_(True)).with_for_update())).scalar_one_or_none()
    if case is None:
        raise ValueError("Кейс не найден.")
    if case.stock is not None and case.stock <= 0:
        raise ValueError("Кейсы закончились.")
    rewards = list((await session.execute(select(CaseReward).where(CaseReward.case_id == case.id))).scalars().all())
    if not rewards:
        raise ValueError("У кейса нет настроенных наград.")
    wallet = await get_wallet(session, guild_id, discord_id, lock=True)
    if wallet.balance < case.price:
        raise ValueError("Недостаточно средств.")
    chosen = random.choices(rewards, weights=[r.weight for r in rewards], k=1)[0]
    wallet.balance -= case.price
    wallet.lifetime_spent += case.price
    if case.stock is not None:
        case.stock -= 1
    session.add(Transaction(guild_id=guild_id, actor_discord_id=discord_id, from_discord_id=discord_id,
                            amount=-case.price, balance_after=wallet.balance, transaction_type="case",
                            description=f"Открытие кейса: {case.name}", reference=f"case:{case.id}"))
    if chosen.reward_type == "money":
        reward_amount = chosen.amount or int(chosen.reward_value)
        wallet.balance += reward_amount
        wallet.lifetime_earned += reward_amount
        session.add(Transaction(guild_id=guild_id, actor_discord_id=discord_id, to_discord_id=discord_id,
                                amount=reward_amount, balance_after=wallet.balance, transaction_type="case_reward",
                                description=f"Награда кейса: {chosen.rarity}", reference=f"case_reward:{chosen.id}"))
    elif chosen.reward_type in {"item", "title", "role", "xp"}:
        await add_inventory(session, guild_id, discord_id, chosen.reward_value, chosen.reward_value,
                            item_type=chosen.reward_type, quantity=1)
    await session.commit()
    return case, chosen, wallet.balance


async def get_bank(session: AsyncSession, guild_id: int, *, lock: bool = False) -> BankAccount:
    stmt = select(BankAccount).where(BankAccount.guild_id == guild_id)
    if lock:
        stmt = stmt.with_for_update()
    bank = (await session.execute(stmt)).scalar_one_or_none()
    if bank is None:
        bank = BankAccount(guild_id=guild_id)
        session.add(bank)
        await session.flush()
    return bank


async def bank_deposit(session: AsyncSession, guild_id: int, discord_id: int, amount: int):
    if amount <= 0:
        raise ValueError("Сумма должна быть больше нуля.")
    wallet = await get_wallet(session, guild_id, discord_id, lock=True)
    bank = await get_bank(session, guild_id, lock=True)
    if wallet.balance < amount:
        raise ValueError("Недостаточно средств.")
    wallet.balance -= amount
    wallet.lifetime_spent += amount
    bank.balance += amount
    session.add(Transaction(guild_id=guild_id, actor_discord_id=discord_id, from_discord_id=discord_id,
                            amount=-amount, balance_after=wallet.balance, transaction_type="bank_deposit",
                            description="Пополнение семейного банка"))
    await session.commit()
    return bank.balance, wallet.balance


async def bank_withdraw(session: AsyncSession, guild_id: int, discord_id: int, amount: int):
    if amount <= 0:
        raise ValueError("Сумма должна быть больше нуля.")
    wallet = await get_wallet(session, guild_id, discord_id, lock=True)
    bank = await get_bank(session, guild_id, lock=True)
    if bank.balance < amount:
        raise ValueError("В семейном банке недостаточно средств.")
    bank.balance -= amount
    wallet.balance += amount
    wallet.lifetime_earned += amount
    session.add(Transaction(guild_id=guild_id, actor_discord_id=discord_id, to_discord_id=discord_id,
                            amount=amount, balance_after=wallet.balance, transaction_type="bank_withdraw",
                            description="Снятие из семейного банка"))
    await session.commit()
    return bank.balance, wallet.balance
