from __future__ import annotations

import random
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select

from bot.models.economy import Case, CaseReward, InventoryItem, ShopItem
from bot.services.db import async_session_factory
from bot.services.economy_service import buy_item, claim_daily, claim_weekly, get_account, sell_item, transfer
from bot.services.log_service import log_audit_action
from bot.services.user_service import get_or_create_user
from bot.utils.embeds import error_embed, info_embed, success_embed
from bot.utils.permissions import require_permission


class EconomyCog(commands.Cog):
    """Этап 4: внутренняя валюта, магазин, инвентарь, кейсы и семейный банк."""
    def __init__(self, bot: commands.Bot): self.bot = bot

    shop = app_commands.Group(name="shop", description="Магазин семьи")
    bank = app_commands.Group(name="bank", description="Семейный банк")
    case = app_commands.Group(name="case", description="Кейсы")

    @app_commands.command(name="balance", description="Показать баланс")
    async def balance(self, interaction: discord.Interaction, member: discord.Member | None = None):
        target = member or interaction.user
        async with async_session_factory() as session:
            user = await get_or_create_user(session, target, interaction.guild_id)
            account = await get_account(session, interaction.guild_id, user.id)
            await session.commit()
        await interaction.response.send_message(embed=info_embed("💰 Баланс", f"{target.mention}\nНаличные: **${account.balance:,}**\nБанк: **${account.bank_balance:,}**"), ephemeral=target.id != interaction.user.id)

    @app_commands.command(name="pay", description="Перевести деньги участнику")
    async def pay(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if member.bot or member.id == interaction.user.id or amount <= 0:
            return await interaction.response.send_message(embed=error_embed("Ошибка", "Укажите другого участника и положительную сумму."), ephemeral=True)
        async with async_session_factory() as session:
            sender = await get_or_create_user(session, interaction.user, interaction.guild_id)
            receiver = await get_or_create_user(session, member, interaction.guild_id)
            try: await transfer(session, interaction.guild_id, sender.id, receiver.id, amount, "Перевод между участниками")
            except ValueError as e: return await interaction.response.send_message(embed=error_embed("Перевод отклонён", str(e)), ephemeral=True)
        await interaction.response.send_message(embed=success_embed("Перевод выполнен", f"{member.mention} получил **${amount:,}**."))

    @app_commands.command(name="daily", description="Получить ежедневную награду")
    async def daily(self, interaction: discord.Interaction):
        async with async_session_factory() as session:
            user = await get_or_create_user(session, interaction.user, interaction.guild_id)
            try: reward, streak = await claim_daily(session, interaction.guild_id, user.id)
            except ValueError as e: return await interaction.response.send_message(embed=error_embed("Daily", str(e)), ephemeral=True)
        await interaction.response.send_message(embed=success_embed("Daily получен", f"+**${reward:,}**\nСерия: **{streak}** 🔥"), ephemeral=True)

    @app_commands.command(name="weekly", description="Получить еженедельную награду")
    async def weekly(self, interaction: discord.Interaction):
        async with async_session_factory() as session:
            user = await get_or_create_user(session, interaction.user, interaction.guild_id)
            try: reward = await claim_weekly(session, interaction.guild_id, user.id)
            except ValueError as e: return await interaction.response.send_message(embed=error_embed("Weekly", str(e)), ephemeral=True)
        await interaction.response.send_message(embed=success_embed("Weekly получен", f"+**${reward:,}**"), ephemeral=True)

    @shop.command(name="list", description="Показать магазин")
    async def shop_list(self, interaction: discord.Interaction):
        async with async_session_factory() as session:
            rows = (await session.execute(select(ShopItem).where(ShopItem.guild_id == interaction.guild_id, ShopItem.active.is_(True)).order_by(ShopItem.id))).scalars().all()
        lines = [f"**#{x.id} {x.name}** — ${x.price:,}\n{x.description} • Остаток: {'∞' if x.stock is None else x.stock}" for x in rows]
        await interaction.response.send_message(embed=info_embed("🛒 Магазин", "\n\n".join(lines) or "Магазин пуст."))

    @shop.command(name="add", description="Добавить товар")
    @require_permission("manage_economy")
    async def shop_add(self, interaction: discord.Interaction, name: str, price: int, description: str, stock: int | None = None, item_type: str = "item", item_value: str = ""):
        if price < 0 or (stock is not None and stock < 0): return await interaction.response.send_message(embed=error_embed("Ошибка", "Цена/остаток не могут быть отрицательными."), ephemeral=True)
        async with async_session_factory() as session:
            row = ShopItem(guild_id=interaction.guild_id, name=name, description=description, price=price, stock=stock, item_type=item_type, item_value=item_value); session.add(row); await session.flush(); await log_audit_action(session, interaction.guild_id, interaction.user.id, "shop.add", str(row.id)); await session.commit()
        await interaction.response.send_message(embed=success_embed("Товар добавлен", f"#{row.id} {name}"), ephemeral=True)

    @shop.command(name="remove", description="Отключить товар")
    @require_permission("manage_economy")
    async def shop_remove(self, interaction: discord.Interaction, item_id: int):
        async with async_session_factory() as session:
            row = await session.get(ShopItem, item_id)
            if not row or row.guild_id != interaction.guild_id: return await interaction.response.send_message(embed=error_embed("Не найдено", "Товар не найден."), ephemeral=True)
            row.active = False; await session.commit()
        await interaction.response.send_message(embed=success_embed("Товар отключён", f"#{item_id}"), ephemeral=True)

    @app_commands.command(name="buy", description="Купить товар")
    async def buy(self, interaction: discord.Interaction, item_id: int, quantity: int = 1):
        async with async_session_factory() as session:
            user = await get_or_create_user(session, interaction.user, interaction.guild_id); item = await session.get(ShopItem, item_id)
            if not item or item.guild_id != interaction.guild_id: return await interaction.response.send_message(embed=error_embed("Не найдено", "Товар не найден."), ephemeral=True)
            try: total = await buy_item(session, interaction.guild_id, user.id, item, quantity)
            except ValueError as e: return await interaction.response.send_message(embed=error_embed("Покупка отклонена", str(e)), ephemeral=True)
        await interaction.response.send_message(embed=success_embed("Покупка выполнена", f"{item.name} × {quantity}\nСписано: **${total:,}**"), ephemeral=True)

    @app_commands.command(name="sell", description="Продать товар")
    async def sell(self, interaction: discord.Interaction, item_id: int, quantity: int = 1):
        async with async_session_factory() as session:
            user = await get_or_create_user(session, interaction.user, interaction.guild_id); item = await session.get(ShopItem, item_id)
            if not item or item.guild_id != interaction.guild_id: return await interaction.response.send_message(embed=error_embed("Не найдено", "Товар не найден."), ephemeral=True)
            try: value = await sell_item(session, interaction.guild_id, user.id, item, quantity)
            except ValueError as e: return await interaction.response.send_message(embed=error_embed("Продажа отклонена", str(e)), ephemeral=True)
        await interaction.response.send_message(embed=success_embed("Продажа выполнена", f"{item.name} × {quantity}\nПолучено: **${value:,}**"), ephemeral=True)

    @app_commands.command(name="inventory", description="Показать инвентарь")
    async def inventory(self, interaction: discord.Interaction):
        async with async_session_factory() as session:
            user = await get_or_create_user(session, interaction.user, interaction.guild_id)
            rows = (await session.execute(select(InventoryItem, ShopItem).join(ShopItem, ShopItem.id == InventoryItem.item_id).where(InventoryItem.guild_id == interaction.guild_id, InventoryItem.user_id == user.id, InventoryItem.quantity > 0))).all()
        await interaction.response.send_message(embed=info_embed("🎒 Инвентарь", "\n".join(f"**{item.name}** × {inv.quantity}" for inv, item in rows) or "Инвентарь пуст."), ephemeral=True)

    @case.command(name="list", description="Показать кейсы")
    async def case_list(self, interaction: discord.Interaction):
        async with async_session_factory() as session:
            rows = (await session.execute(select(Case).where(Case.guild_id == interaction.guild_id, Case.active.is_(True)))).scalars().all()
        await interaction.response.send_message(embed=info_embed("🎁 Кейсы", "\n".join(f"**#{c.id} {c.name}** — ${c.price:,}\n{c.description}" for c in rows) or "Кейсов нет."))

    @case.command(name="create", description="Создать кейс")
    @require_permission("manage_cases")
    async def case_create(self, interaction: discord.Interaction, name: str, price: int, description: str):
        if price < 0: return await interaction.response.send_message(embed=error_embed("Ошибка", "Цена не может быть отрицательной."), ephemeral=True)
        async with async_session_factory() as session:
            row = Case(guild_id=interaction.guild_id, name=name, price=price, description=description); session.add(row); await session.flush(); await session.commit()
        await interaction.response.send_message(embed=success_embed("Кейс создан", f"#{row.id} {name}"), ephemeral=True)

    @case.command(name="reward", description="Добавить награду в кейс")
    @require_permission("manage_cases")
    async def case_reward(self, interaction: discord.Interaction, case_id: int, reward_type: str, reward_value: str, weight: int = 1):
        if weight <= 0 or reward_type not in {"money", "xp", "item"}: return await interaction.response.send_message(embed=error_embed("Ошибка", "Тип: money/xp/item; вес > 0."), ephemeral=True)
        async with async_session_factory() as session:
            case = await session.get(Case, case_id)
            if not case or case.guild_id != interaction.guild_id: return await interaction.response.send_message(embed=error_embed("Не найдено", "Кейс не найден."), ephemeral=True)
            session.add(CaseReward(case_id=case_id, reward_type=reward_type, reward_value=reward_value, weight=weight)); await session.commit()
        await interaction.response.send_message(embed=success_embed("Награда добавлена", f"{reward_type}: {reward_value}"), ephemeral=True)

    @case.command(name="open", description="Открыть кейс")
    async def case_open(self, interaction: discord.Interaction, case_id: int):
        async with async_session_factory() as session:
            user = await get_or_create_user(session, interaction.user, interaction.guild_id); case = await session.get(Case, case_id)
            if not case or case.guild_id != interaction.guild_id or not case.active: return await interaction.response.send_message(embed=error_embed("Не найдено", "Кейс недоступен."), ephemeral=True)
            rewards = (await session.execute(select(CaseReward).where(CaseReward.case_id == case_id))).scalars().all()
            if not rewards: return await interaction.response.send_message(embed=error_embed("Кейс пуст", "Администратор ещё не добавил награды."), ephemeral=True)
            account = await get_account(session, interaction.guild_id, user.id)
            if account.balance < case.price: return await interaction.response.send_message(embed=error_embed("Недостаточно средств", f"Нужно ${case.price:,}."), ephemeral=True)
            account.balance -= case.price
            chosen = random.choices(rewards, weights=[r.weight for r in rewards], k=1)[0]
            text = chosen.reward_value
            if chosen.reward_type == "money": account.balance += int(chosen.reward_value); text = f"${int(chosen.reward_value):,}"
            elif chosen.reward_type == "xp":
                from bot.models.profile import Profile
                profile = (await session.execute(select(Profile).where(Profile.user_id == user.id))).scalar_one()
                await __import__("bot.services.xp_service", fromlist=["add_xp"]).add_xp(session, profile, user.id, int(chosen.reward_value), "case")
                text = f"{chosen.reward_value} XP"
            else:
                item_id = int(chosen.reward_value)
                inv = (await session.execute(select(InventoryItem).where(InventoryItem.user_id == user.id, InventoryItem.item_id == item_id).with_for_update())).scalar_one_or_none()
                if inv is None: inv = InventoryItem(guild_id=interaction.guild_id, user_id=user.id, item_id=item_id, quantity=0); session.add(inv)
                inv.quantity += 1
                item = await session.get(ShopItem, item_id); text = item.name if item else f"предмет #{item_id}"
            await session.commit()
        await interaction.response.send_message(embed=success_embed("🎁 Кейс открыт!", f"Выпало: **{text}**"))

    @bank.command(name="balance", description="Баланс семейного банка")
    @require_permission("view_bank")
    async def bank_balance(self, interaction: discord.Interaction):
        from bot.models.economy import FamilyBank
        async with async_session_factory() as session:
            bank = await session.get(FamilyBank, interaction.guild_id)
            value = bank.balance if bank else 0
        await interaction.response.send_message(embed=info_embed("🏦 Семейный банк", f"Баланс: **${value:,}**"), ephemeral=True)

    @bank.command(name="deposit", description="Внести деньги в семейный банк")
    @require_permission("manage_bank")
    async def bank_deposit(self, interaction: discord.Interaction, amount: int):
        from bot.models.economy import FamilyBank
        if amount <= 0: return await interaction.response.send_message(embed=error_embed("Ошибка", "Сумма должна быть положительной."), ephemeral=True)
        async with async_session_factory() as session:
            user = await get_or_create_user(session, interaction.user, interaction.guild_id); account = await get_account(session, interaction.guild_id, user.id)
            if account.balance < amount: return await interaction.response.send_message(embed=error_embed("Ошибка", "Недостаточно средств."), ephemeral=True)
            bank = await session.get(FamilyBank, interaction.guild_id, with_for_update=True)
            if bank is None: bank = FamilyBank(guild_id=interaction.guild_id); session.add(bank)
            account.balance -= amount; bank.balance += amount; await session.commit()
        await interaction.response.send_message(embed=success_embed("Внесено", f"${amount:,}"), ephemeral=True)

    @bank.command(name="withdraw", description="Снять деньги из семейного банка")
    @require_permission("manage_bank")
    async def bank_withdraw(self, interaction: discord.Interaction, amount: int):
        from bot.models.economy import FamilyBank
        if amount <= 0: return await interaction.response.send_message(embed=error_embed("Ошибка", "Сумма должна быть положительной."), ephemeral=True)
        async with async_session_factory() as session:
            user = await get_or_create_user(session, interaction.user, interaction.guild_id); account = await get_account(session, interaction.guild_id, user.id); bank = await session.get(FamilyBank, interaction.guild_id, with_for_update=True)
            if not bank or bank.balance < amount: return await interaction.response.send_message(embed=error_embed("Ошибка", "Недостаточно средств в семейном банке."), ephemeral=True)
            bank.balance -= amount; account.balance += amount; await session.commit()
        await interaction.response.send_message(embed=success_embed("Снято", f"${amount:,}"), ephemeral=True)


async def setup(bot: commands.Bot): await bot.add_cog(EconomyCog(bot))
