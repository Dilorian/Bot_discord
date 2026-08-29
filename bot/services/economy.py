import random
from datetime import datetime, timedelta
from typing import Optional, Tuple, Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from bot.models.economy import (
    Wallet, Transaction, ShopItem, InventoryItem,
    Case, CaseReward, BankAccount
)

class EconomyService:
    def __init__(self, session: AsyncSession, guild_id: int):
        self.session = session
        self.guild_id = guild_id

    async def get_or_create_wallet(self, discord_id: int) -> Wallet:
        stmt = select(Wallet).where(Wallet.guild_id == self.guild_id, Wallet.discord_id == discord_id)
        result = await self.session.execute(stmt)
        wallet = result.scalar_one_or_none()
        if not wallet:
            wallet = Wallet(guild_id=self.guild_id, discord_id=discord_id, balance=0)
            self.session.add(wallet)
            await self.session.commit()
            await self.session.refresh(wallet)
        return wallet

    async def get_balance(self, discord_id: int) -> int:
        wallet = await self.get_or_create_wallet(discord_id)
        return wallet.balance

    async def add_money(self, discord_id: int, amount: int, description: str,
                        transaction_type: str = "income", reference: str = None,
                        actor_discord_id: int = None) -> Transaction:
        if amount <= 0:
            raise ValueError("Amount must be positive")
        wallet = await self.get_or_create_wallet(discord_id)
        wallet.balance += amount
        wallet.lifetime_earned += amount
        wallet.updated_at = datetime.utcnow()
        tx = Transaction(
            guild_id=self.guild_id,
            actor_discord_id=actor_discord_id,
            to_discord_id=discord_id,
            amount=amount,
            balance_after=wallet.balance,
            transaction_type=transaction_type,
            description=description,
            reference=reference
        )
        self.session.add(tx)
        await self.session.commit()
        await self.session.refresh(tx)
        return tx

    async def remove_money(self, discord_id: int, amount: int, description: str,
                           transaction_type: str = "withdraw", reference: str = None,
                           actor_discord_id: int = None) -> Transaction:
        if amount <= 0:
            raise ValueError("Amount must be positive")
        wallet = await self.get_or_create_wallet(discord_id)
        if wallet.balance < amount:
            raise ValueError("Insufficient balance")
        wallet.balance -= amount
        wallet.lifetime_spent += amount
        wallet.updated_at = datetime.utcnow()
        tx = Transaction(
            guild_id=self.guild_id,
            actor_discord_id=actor_discord_id,
            from_discord_id=discord_id,
            amount=-amount,
            balance_after=wallet.balance,
            transaction_type=transaction_type,
            description=description,
            reference=reference
        )
        self.session.add(tx)
        await self.session.commit()
        await self.session.refresh(tx)
        return tx

    async def transfer_money(self, from_discord_id: int, to_discord_id: int,
                             amount: int, description: str = None,
                             actor_discord_id: int = None) -> Tuple[Transaction, Transaction]:
        if amount <= 0:
            raise ValueError("Amount must be positive")
        if from_discord_id == to_discord_id:
            raise ValueError("Cannot transfer to yourself")
        async with self.session.begin():
            from_wallet = await self.get_or_create_wallet(from_discord_id)
            if from_wallet.balance < amount:
                raise ValueError("Insufficient balance")
            from_wallet.balance -= amount
            from_wallet.lifetime_spent += amount
            from_wallet.updated_at = datetime.utcnow()
            tx_from = Transaction(
                guild_id=self.guild_id,
                actor_discord_id=actor_discord_id or from_discord_id,
                from_discord_id=from_discord_id,
                to_discord_id=to_discord_id,
                amount=-amount,
                balance_after=from_wallet.balance,
                transaction_type="transfer",
                description=description or f"Перевод пользователю <@{to_discord_id}>",
            )
            self.session.add(tx_from)
            to_wallet = await self.get_or_create_wallet(to_discord_id)
            to_wallet.balance += amount
            to_wallet.lifetime_earned += amount
            to_wallet.updated_at = datetime.utcnow()
            tx_to = Transaction(
                guild_id=self.guild_id,
                actor_discord_id=actor_discord_id or from_discord_id,
                from_discord_id=from_discord_id,
                to_discord_id=to_discord_id,
                amount=amount,
                balance_after=to_wallet.balance,
                transaction_type="transfer",
                description=description or f"Перевод от <@{from_discord_id}>",
            )
            self.session.add(tx_to)
            await self.session.flush()
        return tx_from, tx_to

    async def get_bank_account(self) -> BankAccount:
        stmt = select(BankAccount).where(BankAccount.guild_id == self.guild_id)
        result = await self.session.execute(stmt)
        bank = result.scalar_one_or_none()
        if not bank:
            bank = BankAccount(guild_id=self.guild_id, balance=0)
            self.session.add(bank)
            await self.session.commit()
            await self.session.refresh(bank)
        return bank

    async def get_bank_balance(self) -> int:
        bank = await self.get_bank_account()
        return bank.balance

    async def deposit_to_bank(self, discord_id: int, amount: int, description: str = None) -> Transaction:
        if amount <= 0:
            raise ValueError("Amount must be positive")
        wallet = await self.get_or_create_wallet(discord_id)
        if wallet.balance < amount:
            raise ValueError("Insufficient balance")
        bank = await self.get_bank_account()
        async with self.session.begin():
            wallet.balance -= amount
            wallet.lifetime_spent += amount
            wallet.updated_at = datetime.utcnow()
            bank.balance += amount
            bank.updated_at = datetime.utcnow()
            tx = Transaction(
                guild_id=self.guild_id,
                actor_discord_id=discord_id,
                from_discord_id=discord_id,
                amount=-amount,
                balance_after=wallet.balance,
                transaction_type="bank_deposit",
                description=description or f"Пополнение семейного банка на {amount}",
                reference=f"bank_{bank.id}"
            )
            self.session.add(tx)
            await self.session.flush()
        return tx

    async def withdraw_from_bank(self, discord_id: int, amount: int, description: str = None) -> Transaction:
        if amount <= 0:
            raise ValueError("Amount must be positive")
        bank = await self.get_bank_account()
        if bank.balance < amount:
            raise ValueError("Insufficient bank balance")
        wallet = await self.get_or_create_wallet(discord_id)
        async with self.session.begin():
            bank.balance -= amount
            bank.updated_at = datetime.utcnow()
            wallet.balance += amount
            wallet.lifetime_earned += amount
            wallet.updated_at = datetime.utcnow()
            tx = Transaction(
                guild_id=self.guild_id,
                actor_discord_id=discord_id,
                to_discord_id=discord_id,
                amount=amount,
                balance_after=wallet.balance,
                transaction_type="bank_withdraw",
                description=description or f"Снятие из семейного банка {amount}",
                reference=f"bank_{bank.id}"
            )
            self.session.add(tx)
            await self.session.flush()
        return tx

    async def claim_daily(self, discord_id: int) -> Tuple[int, bool]:
        wallet = await self.get_or_create_wallet(discord_id)
        now = datetime.utcnow()
        today = now.date()
        if wallet.daily_claimed_at and wallet.daily_claimed_at.date() == today:
            return 0, False
        bonus = 5000
        await self.add_money(discord_id, bonus, "Ежедневный бонус", transaction_type="daily")
        wallet.daily_claimed_at = now
        await self.session.commit()
        return bonus, True

    async def claim_weekly(self, discord_id: int) -> Tuple[int, bool]:
        wallet = await self.get_or_create_wallet(discord_id)
        now = datetime.utcnow()
        if wallet.weekly_claimed_at and (now - wallet.weekly_claimed_at).days < 7:
            return 0, False
        bonus = 25000
        await self.add_money(discord_id, bonus, "Еженедельный бонус", transaction_type="weekly")
        wallet.weekly_claimed_at = now
        await self.session.commit()
        return bonus, True

    async def get_shop_items(self, item_type: str = None, active_only: bool = True) -> list[ShopItem]:
        stmt = select(ShopItem).where(ShopItem.guild_id == self.guild_id)
        if active_only:
            stmt = stmt.where(ShopItem.is_active == True)
        if item_type:
            stmt = stmt.where(ShopItem.item_type == item_type)
        stmt = stmt.order_by(ShopItem.price)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_shop_item_by_key(self, item_key: str) -> ShopItem | None:
        stmt = select(ShopItem).where(
            ShopItem.guild_id == self.guild_id,
            ShopItem.item_key == item_key,
            ShopItem.is_active == True
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def purchase_item(self, discord_id: int, item_key: str, quantity: int = 1) -> InventoryItem:
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        item = await self.get_shop_item_by_key(item_key)
        if not item:
            raise ValueError("Товар не найден или недоступен")
        total_price = item.price * quantity
        if item.stock is not None and item.stock < quantity:
            raise ValueError("Недостаточно товара на складе")
        async with self.session.begin():
            await self.remove_money(discord_id, total_price,
                                    description=f"Покупка: {item.name} x{quantity}",
                                    transaction_type="purchase",
                                    actor_discord_id=discord_id)
            if item.stock is not None:
                item.stock -= quantity
                self.session.add(item)
            stmt = select(InventoryItem).where(
                InventoryItem.guild_id == self.guild_id,
                InventoryItem.discord_id == discord_id,
                InventoryItem.item_key == item_key
            )
            result = await self.session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                existing.quantity += quantity
                existing.updated_at = datetime.utcnow()
                self.session.add(existing)
                inv = existing
            else:
                inv = InventoryItem(
                    guild_id=self.guild_id,
                    discord_id=discord_id,
                    item_key=item_key,
                    name=item.name,
                    item_type=item.item_type,
                    quantity=quantity,
                    extra_data={}
                )
                self.session.add(inv)
            await self.session.flush()
        return inv

    async def get_inventory(self, discord_id: int) -> list[InventoryItem]:
        stmt = select(InventoryItem).where(
            InventoryItem.guild_id == self.guild_id,
            InventoryItem.discord_id == discord_id,
            InventoryItem.quantity > 0
        ).order_by(InventoryItem.created_at)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_cases(self, active_only: bool = True) -> list[Case]:
        stmt = select(Case).where(Case.guild_id == self.guild_id)
        if active_only:
            stmt = stmt.where(Case.is_active == True)
        stmt = stmt.order_by(Case.price)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_case_by_key(self, key: str) -> Case | None:
        stmt = select(Case).where(
            Case.guild_id == self.guild_id,
            Case.key == key,
            Case.is_active == True
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def open_case(self, discord_id: int, case_key: str) -> dict:
        case = await self.get_case_by_key(case_key)
        if not case:
            raise ValueError("Кейс не найден или недоступен")
        if case.stock is not None and case.stock <= 0:
            raise ValueError("Кейс закончился")
        if case.expires_at and case.expires_at < datetime.utcnow():
            raise ValueError("Кейс истёк")
        wallet = await self.get_or_create_wallet(discord_id)
        if wallet.balance < case.price:
            raise ValueError("Недостаточно средств")
        async with self.session.begin():
            await self.remove_money(discord_id, case.price,
                                    description=f"Открытие кейса: {case.name}",
                                    transaction_type="case_open",
                                    reference=f"case_{case.id}",
                                    actor_discord_id=discord_id)
            if case.stock is not None:
                case.stock -= 1
                self.session.add(case)
            stmt = select(CaseReward).where(CaseReward.case_id == case.id)
            result = await self.session.execute(stmt)
            rewards = result.scalars().all()
            if not rewards:
                raise ValueError("В кейсе нет наград")
            total_weight = sum(r.weight for r in rewards)
            rand = random.randint(1, total_weight)
            cumulative = 0
            chosen = None
            for r in rewards:
                cumulative += r.weight
                if rand <= cumulative:
                    chosen = r
                    break
            if not chosen:
                chosen = rewards[-1]
            reward_type = chosen.reward_type
            reward_value = chosen.reward_value
            amount = chosen.amount
            result_info = {"type": reward_type, "value": reward_value, "amount": amount}
            if reward_type == "money":
                if amount > 0:
                    await self.add_money(discord_id, amount,
                                         description=f"Кейс: {case.name}",
                                         transaction_type="case_reward",
                                         reference=f"case_{case.id}",
                                         actor_discord_id=discord_id)
            elif reward_type == "xp":
                result_info["xp"] = amount
            elif reward_type == "item":
                if reward_value:
                    shop_item = await self.get_shop_item_by_key(reward_value)
                    if shop_item:
                        inv = InventoryItem(
                            guild_id=self.guild_id,
                            discord_id=discord_id,
                            item_key=reward_value,
                            name=shop_item.name,
                            item_type=shop_item.item_type,
                            quantity=1,
                            extra_data={}
                        )
                        self.session.add(inv)
                        result_info["item_key"] = reward_value
            elif reward_type == "title":
                result_info["title"] = reward_value
            elif reward_type == "role":
                result_info["role_id"] = int(reward_value) if reward_value.isdigit() else reward_value
            await self.session.flush()
        return result_info

    # Админские методы
    async def create_shop_item(self, name: str, price: int, item_type: str, item_key: str,
                               description: str = "", stock: int = None,
                               created_by: int = None) -> ShopItem:
        existing = await self.get_shop_item_by_key(item_key)
        if existing:
            raise ValueError("Товар с таким item_key уже существует")
        item = ShopItem(
            guild_id=self.guild_id,
            name=name,
            description=description,
            item_type=item_type,
            item_key=item_key,
            price=price,
            stock=stock,
            created_by=created_by
        )
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def update_shop_item(self, item_key: str, **kwargs) -> ShopItem:
        item = await self.get_shop_item_by_key(item_key)
        if not item:
            raise ValueError("Товар не найден")
        for key, value in kwargs.items():
            if hasattr(item, key):
                setattr(item, key, value)
        item.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def delete_shop_item(self, item_key: str) -> bool:
        item = await self.get_shop_item_by_key(item_key)
        if item:
            await self.session.delete(item)
            await self.session.commit()
            return True
        return False

    async def create_case(self, key: str, name: str, price: int,
                          description: str = "", stock: int = None,
                          expires_at: datetime = None, created_by: int = None) -> Case:
        existing = await self.get_case_by_key(key)
        if existing:
            raise ValueError("Кейс с таким key уже существует")
        case = Case(
            guild_id=self.guild_id,
            key=key,
            name=name,
            description=description,
            price=price,
            stock=stock,
            expires_at=expires_at,
            created_by=created_by
        )
        self.session.add(case)
        await self.session.commit()
        await self.session.refresh(case)
        return case

    async def update_case(self, key: str, **kwargs) -> Case:
        case = await self.get_case_by_key(key)
        if not case:
            raise ValueError("Кейс не найден")
        for k, v in kwargs.items():
            if hasattr(case, k):
                setattr(case, k, v)
        case.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(case)
        return case

    async def delete_case(self, key: str) -> bool:
        case = await self.get_case_by_key(key)
        if case:
            await self.session.delete(case)
            await self.session.commit()
            return True
        return False

    async def add_case_reward(self, case_key: str, reward_type: str, reward_value: str,
                              amount: int = 0, weight: int = 1, rarity: str = "Common") -> CaseReward:
        case = await self.get_case_by_key(case_key)
        if not case:
            raise ValueError("Кейс не найден")
        reward = CaseReward(
            case_id=case.id,
            reward_type=reward_type,
            reward_value=reward_value,
            amount=amount,
            weight=weight,
            rarity=rarity
        )
        self.session.add(reward)
        await self.session.commit()
        await self.session.refresh(reward)
        return reward

    async def remove_case_reward(self, reward_id: int) -> bool:
        stmt = select(CaseReward).where(CaseReward.id == reward_id)
        result = await self.session.execute(stmt)
        reward = result.scalar_one_or_none()
        if reward:
            await self.session.delete(reward)
            await self.session.commit()
            return True
        return False
