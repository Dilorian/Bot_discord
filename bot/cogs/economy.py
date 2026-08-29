from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from bot.services import economy_service as eco
from bot.services.db import async_session_factory
from bot.services.log_service import log_audit_action
from bot.utils.embeds import BRAND_COLOR, error_embed, info_embed, success_embed
from bot.utils.permissions import require_permission


def money(value: int) -> str:
    return f"${value:,}".replace(",", " ")


class EconomyCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="balance", description="Показать баланс")
    async def balance(self, interaction: discord.Interaction, member: discord.Member | None = None):
        target = member or interaction.user
        async with async_session_factory() as session:
            value = await eco.get_balance(session, interaction.guild_id, target.id)
        await interaction.response.send_message(embed=info_embed("💰 Баланс", f"{target.mention}: **{money(value)}**"), ephemeral=target.id != interaction.user.id)

    @app_commands.command(name="pay", description="Перевести деньги участнику")
    async def pay(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if member.bot:
            await interaction.response.send_message("Нельзя переводить деньги ботам.", ephemeral=True); return
        try:
            async with async_session_factory() as session:
                out, _ = await eco.transfer(session, interaction.guild_id, interaction.user.id, member.id, amount)
        except ValueError as exc:
            await interaction.response.send_message(embed=error_embed("Перевод не выполнен", str(exc)), ephemeral=True); return
        await interaction.response.send_message(embed=success_embed("💸 Перевод выполнен", f"Получатель: {member.mention}\nСумма: **{money(amount)}**\nБаланс: **{money(out.balance_after or 0)}**\nТранзакция: `#{out.id}`"))

    @app_commands.command(name="transfer", description="Алиас команды /pay")
    async def transfer(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        await self.pay.callback(self, interaction, member, amount)

    @app_commands.command(name="daily", description="Получить ежедневный бонус")
    async def daily(self, interaction: discord.Interaction):
        await self._bonus(interaction, "daily", eco.DAILY_AMOUNT)

    @app_commands.command(name="weekly", description="Получить недельный бонус")
    async def weekly(self, interaction: discord.Interaction):
        await self._bonus(interaction, "weekly", eco.WEEKLY_AMOUNT)

    async def _bonus(self, interaction: discord.Interaction, kind: str, amount: int):
        async with async_session_factory() as session:
            tx = await eco.claim_bonus(session, interaction.guild_id, interaction.user.id, kind, amount)
        if tx is None:
            await interaction.response.send_message(embed=error_embed("Бонус уже получен", "Попробуйте снова после окончания периода."), ephemeral=True); return
        await interaction.response.send_message(embed=success_embed("🎁 Бонус получен", f"+**{money(amount)}**\nБаланс: **{money(tx.balance_after or 0)}**"))

    @app_commands.command(name="transactions", description="История денежных операций")
    async def transactions(self, interaction: discord.Interaction, limit: app_commands.Range[int, 1, 25] = 10):
        async with async_session_factory() as session:
            rows = await eco.list_transactions(session, interaction.guild_id, interaction.user.id, limit)
        if not rows:
            await interaction.response.send_message("История пуста.", ephemeral=True); return
        lines = []
        for row in rows:
            sign = "+" if row.amount > 0 else ""
            lines.append(f"`#{row.id}` **{sign}{money(row.amount)}** · {row.transaction_type} · {row.description}")
        await interaction.response.send_message(embed=info_embed("📜 История", "\n".join(lines)), ephemeral=True)

    @app_commands.command(name="shop", description="Открыть магазин семьи")
    async def shop(self, interaction: discord.Interaction):
        async with async_session_factory() as session:
            items = await eco.list_shop(session, interaction.guild_id)
        if not items:
            await interaction.response.send_message("Магазин пока пуст.", ephemeral=True); return
        lines = []
        for item in items[:25]:
            stock = "∞" if item.stock is None else str(item.stock)
            lines.append(f"`{item.item_key}` **{item.name}** — {money(item.price)} · {stock}\n{item.description}")
        await interaction.response.send_message(embed=discord.Embed(title="🛒 Магазин", description="\n\n".join(lines), color=BRAND_COLOR), ephemeral=True)

    @app_commands.command(name="buy", description="Купить товар")
    async def buy(self, interaction: discord.Interaction, item_key: str):
        try:
            async with async_session_factory() as session:
                item = await eco.buy_shop_item(session, interaction.guild_id, interaction.user.id, item_key.strip().lower())
                balance = await eco.get_balance(session, interaction.guild_id, interaction.user.id)
        except ValueError as exc:
            await interaction.response.send_message(embed=error_embed("Покупка не выполнена", str(exc)), ephemeral=True); return
        await interaction.response.send_message(embed=success_embed("🛒 Покупка", f"**{item.name}**\nСписано: {money(item.price)}\nБаланс: {money(balance)}"))

    @app_commands.command(name="inventory", description="Показать инвентарь")
    async def inventory(self, interaction: discord.Interaction, member: discord.Member | None = None):
        target = member or interaction.user
        async with async_session_factory() as session:
            items = await eco.list_inventory(session, interaction.guild_id, target.id)
        desc = "Инвентарь пуст." if not items else "\n".join(f"• **{i.name}** × {i.quantity} · `{i.item_key}`" for i in items)
        await interaction.response.send_message(embed=info_embed(f"🎒 Инвентарь — {target.display_name}", desc), ephemeral=target.id != interaction.user.id)

    @app_commands.command(name="bank", description="Показать семейный банк")
    async def bank(self, interaction: discord.Interaction):
        async with async_session_factory() as session:
            bank = await eco.get_bank(session, interaction.guild_id)
        await interaction.response.send_message(embed=info_embed("🏦 Семейный банк", f"Баланс: **{money(bank.balance)}**"), ephemeral=True)

    @app_commands.command(name="bank_deposit", description="Внести деньги в семейный банк")
    async def bank_deposit(self, interaction: discord.Interaction, amount: int):
        try:
            async with async_session_factory() as session:
                bank, balance = await eco.bank_deposit(session, interaction.guild_id, interaction.user.id, amount)
        except ValueError as exc:
            await interaction.response.send_message(embed=error_embed("Операция не выполнена", str(exc)), ephemeral=True); return
        await interaction.response.send_message(embed=success_embed("🏦 Пополнение банка", f"Внесено: {money(amount)}\nБанк: {money(bank)}\nВаш баланс: {money(balance)}"))

    @app_commands.command(name="bank_withdraw", description="Снять деньги из семейного банка")
    @require_permission("manage_economy")
    async def bank_withdraw(self, interaction: discord.Interaction, amount: int):
        try:
            async with async_session_factory() as session:
                bank, balance = await eco.bank_withdraw(session, interaction.guild_id, interaction.user.id, amount)
        except ValueError as exc:
            await interaction.response.send_message(embed=error_embed("Операция не выполнена", str(exc)), ephemeral=True); return
        await interaction.response.send_message(embed=success_embed("🏦 Снятие из банка", f"Снято: {money(amount)}\nБанк: {money(bank)}\nВаш баланс: {money(balance)}"))

    economy_group = app_commands.Group(name="economy", description="Администрирование экономики")

    @economy_group.command(name="give", description="Выдать валюту")
    @require_permission("manage_economy")
    async def economy_give(self, interaction: discord.Interaction, member: discord.Member, amount: int, reason: str = "Административная награда"):
        try:
            async with async_session_factory() as session:
                tx = await eco.credit(session, interaction.guild_id, member.id, amount, transaction_type="admin_give", actor_discord_id=interaction.user.id, description=reason)
                await log_audit_action(session, interaction.guild_id, interaction.user.id, "economy.give", str(member.id), {"amount": amount, "reason": reason})
        except ValueError as exc:
            await interaction.response.send_message(embed=error_embed("Не выполнено", str(exc)), ephemeral=True); return
        await interaction.response.send_message(embed=success_embed("💰 Валюта выдана", f"{member.mention}: +{money(amount)}\nБаланс: {money(tx.balance_after or 0)}"), ephemeral=True)

    @economy_group.command(name="take", description="Списать валюту")
    @require_permission("manage_economy")
    async def economy_take(self, interaction: discord.Interaction, member: discord.Member, amount: int, reason: str = "Административный штраф"):
        try:
            async with async_session_factory() as session:
                tx = await eco.debit(session, interaction.guild_id, member.id, amount, transaction_type="admin_take", actor_discord_id=interaction.user.id, description=reason)
                await log_audit_action(session, interaction.guild_id, interaction.user.id, "economy.take", str(member.id), {"amount": amount, "reason": reason})
        except ValueError as exc:
            await interaction.response.send_message(embed=error_embed("Не выполнено", str(exc)), ephemeral=True); return
        await interaction.response.send_message(embed=success_embed("💰 Валюта списана", f"{member.mention}: -{money(amount)}\nБаланс: {money(tx.balance_after or 0)}"), ephemeral=True)

    @economy_group.command(name="shop_add", description="Добавить товар")
    @require_permission("manage_economy")
    async def shop_add(self, interaction: discord.Interaction, item_key: str, name: str, price: int, item_type: str = "item", description: str = "", stock: int | None = None):
        try:
            async with async_session_factory() as session:
                item = await eco.create_shop_item(session, interaction.guild_id, item_key=item_key.lower().strip(), name=name, price=price, item_type=item_type, description=description, stock=stock, created_by=interaction.user.id)
                await log_audit_action(session, interaction.guild_id, interaction.user.id, "economy.shop_add", str(item.id))
        except Exception as exc:
            await interaction.response.send_message(embed=error_embed("Не удалось добавить товар", str(exc)), ephemeral=True); return
        await interaction.response.send_message(embed=success_embed("Товар добавлен", f"`{item.item_key}` · {item.name} · {money(item.price)}"), ephemeral=True)

    @economy_group.command(name="case_add", description="Создать кейс")
    @require_permission("manage_economy")
    async def case_add(self, interaction: discord.Interaction, key: str, name: str, price: int, description: str = "", stock: int | None = None):
        try:
            async with async_session_factory() as session:
                case = await eco.create_case(session, interaction.guild_id, key.lower().strip(), name, price, description, stock, interaction.user.id)
                await log_audit_action(session, interaction.guild_id, interaction.user.id, "economy.case_add", str(case.id))
        except Exception as exc:
            await interaction.response.send_message(embed=error_embed("Не удалось создать кейс", str(exc)), ephemeral=True); return
        await interaction.response.send_message(embed=success_embed("Кейс создан", f"`{case.key}` · {case.name} · {money(case.price)}"), ephemeral=True)

    @app_commands.command(name="cases", description="Список кейсов")
    async def cases(self, interaction: discord.Interaction):
        async with async_session_factory() as session:
            cases = await eco.list_cases(session, interaction.guild_id)
        if not cases:
            await interaction.response.send_message("Кейсов пока нет.", ephemeral=True); return
        await interaction.response.send_message(embed=info_embed("🎁 Кейсы", "\n".join(f"`{c.key}` **{c.name}** — {money(c.price)}" for c in cases[:25])), ephemeral=True)

    @app_commands.command(name="case", description="Открыть кейс")
    async def case_open(self, interaction: discord.Interaction, key: str):
        try:
            async with async_session_factory() as session:
                case, reward, balance = await eco.open_case(session, interaction.guild_id, interaction.user.id, key.lower().strip())
        except ValueError as exc:
            await interaction.response.send_message(embed=error_embed("Кейс не открыт", str(exc)), ephemeral=True); return
        reward_text = f"**{reward.rarity}** · {reward.reward_type} · {reward.reward_value}"
        if reward.reward_type == "money": reward_text += f" (+{money(reward.amount or int(reward.reward_value))})"
        await interaction.response.send_message(embed=success_embed("🎁 Кейс открыт", f"Кейс: **{case.name}**\nВыпало: {reward_text}\nБаланс: {money(balance)}"))

    @economy_group.command(name="case_reward_add", description="Добавить награду кейсу")
    @require_permission("manage_economy")
    async def case_reward_add(self, interaction: discord.Interaction, key: str, reward_type: str, reward_value: str, weight: int, amount: int = 0, rarity: str = "Common"):
        async with async_session_factory() as session:
            case = (await session.execute(__import__("sqlalchemy").select(__import__("bot.models.economy", fromlist=["Case"]).Case).where(__import__("bot.models.economy", fromlist=["Case"]).Case.guild_id == interaction.guild_id, __import__("bot.models.economy", fromlist=["Case"]).Case.key == key.lower().strip()))).scalar_one_or_none()
            if case is None:
                await interaction.response.send_message("Кейс не найден.", ephemeral=True); return
            try:
                reward = await eco.add_case_reward(session, case.id, reward_type, reward_value, weight, amount, rarity)
            except ValueError as exc:
                await interaction.response.send_message(str(exc), ephemeral=True); return
        await interaction.response.send_message(embed=success_embed("Награда кейса добавлена", f"{case.name}: {reward.rarity} · вес {reward.weight}"), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(EconomyCog(bot))
