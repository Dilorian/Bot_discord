from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from bot.models.economy import ShopItem
from bot.services import economy_service
from bot.services.db import async_session_factory
from bot.services.log_service import log_audit_action
from bot.services.profile_service import get_or_create_profile
from bot.services.user_service import get_or_create_user
from bot.services.xp_service import add_xp
from bot.utils.embeds import BRAND_COLOR, error_embed, info_embed, success_embed
from bot.utils.permissions import require_permission


def money(value: int) -> str:
    return f"${value:,}".replace(",", " ")


class EconomyCog(commands.Cog):
    """💰 Этап 4: личная экономика, магазин, инвентарь, кейсы и бонусы."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="balance", description="Показать баланс")
    async def balance(self, interaction: discord.Interaction, member: discord.Member | None = None):
        target = member or interaction.user
        async with async_session_factory() as session:
            value = await economy_service.get_balance(session, interaction.guild_id, target.id)
        await interaction.response.send_message(
            embed=info_embed("💰 Баланс", f"{target.mention}: **{money(value)}**"),
            ephemeral=(target.id != interaction.user.id),
        )

    @app_commands.command(name="pay", description="Перевести деньги участнику")
    async def pay(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if member.bot:
            await interaction.response.send_message("Нельзя переводить деньги ботам.", ephemeral=True)
            return
        try:
            async with async_session_factory() as session:
                tx_out, _ = await economy_service.transfer(
                    session, interaction.guild_id, interaction.user.id, member.id, amount
                )
                balance_after = tx_out.balance_after
        except ValueError as exc:
            await interaction.response.send_message(embed=error_embed("Перевод не выполнен", str(exc)), ephemeral=True)
            return
        await interaction.response.send_message(
            embed=success_embed(
                "💸 Перевод выполнен",
                f"Получатель: {member.mention}\nСумма: **{money(amount)}**\n"
                f"Ваш баланс: **{money(balance_after or 0)}**\nТранзакция: `#{tx_out.id}`",
            )
        )

    @app_commands.command(name="transfer", description="Перевести деньги участнику (алиас /pay)")
    async def transfer(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if member.bot:
            await interaction.response.send_message("Нельзя переводить деньги ботам.", ephemeral=True)
            return
        try:
            async with async_session_factory() as session:
                tx_out, _ = await economy_service.transfer(
                    session, interaction.guild_id, interaction.user.id, member.id, amount
                )
                balance_after = tx_out.balance_after
        except ValueError as exc:
            await interaction.response.send_message(embed=error_embed("Перевод не выполнен", str(exc)), ephemeral=True)
            return
        await interaction.response.send_message(
            embed=success_embed(
                "💸 Перевод выполнен",
                f"Получатель: {member.mention}\nСумма: **{money(amount)}**\n"
                f"Ваш баланс: **{money(balance_after or 0)}**\nТранзакция: `#{tx_out.id}`",
            )
        )

    @app_commands.command(name="daily", description="Получить ежедневный бонус")
    async def daily(self, interaction: discord.Interaction):
        await self._bonus(interaction, "daily", economy_service.DAILY_AMOUNT)

    @app_commands.command(name="weekly", description="Получить недельный бонус")
    async def weekly(self, interaction: discord.Interaction):
        await self._bonus(interaction, "weekly", economy_service.WEEKLY_AMOUNT)

    async def _bonus(self, interaction: discord.Interaction, kind: str, amount: int):
        async with async_session_factory() as session:
            tx = await economy_service.claim_bonus(session, interaction.guild_id, interaction.user.id, kind, amount)
        if tx is None:
            await interaction.response.send_message(
                embed=error_embed("Бонус уже получен", "Попробуйте снова в следующем периоде."),
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            embed=success_embed(
                f"🎁 {kind.title()}",
                f"Вы получили **{money(amount)}**.\nБаланс: **{money(tx.balance_after or 0)}**\n"
                f"Транзакция: `#{tx.id}`",
            )
        )

    @app_commands.command(name="shop", description="Открыть магазин семьи")
    async def shop(self, interaction: discord.Interaction):
        async with async_session_factory() as session:
            items = await economy_service.list_shop(session, interaction.guild_id)
        if not items:
            await interaction.response.send_message("Магазин пока пуст.", ephemeral=True)
            return
        lines = []
        for item in items[:25]:
            stock = "∞" if item.stock is None else str(item.stock)
            lines.append(f"`{item.item_key}` **{item.name}** — {money(item.price)} · Остаток: {stock}\n{item.description}")
        await interaction.response.send_message(embed=discord.Embed(
            title="🛒 Магазин", description="\n\n".join(lines), color=BRAND_COLOR
        ), ephemeral=True)

    @app_commands.command(name="buy", description="Купить товар в магазине")
    async def buy(self, interaction: discord.Interaction, item_key: str):
        try:
            async with async_session_factory() as session:
                item = await economy_service.buy_shop_item(
                    session, interaction.guild_id, interaction.user.id, item_key.lower().strip()
                )
                balance_after = await economy_service.get_balance(session, interaction.guild_id, interaction.user.id)
        except ValueError as exc:
            await interaction.response.send_message(embed=error_embed("Покупка не выполнена", str(exc)), ephemeral=True)
            return
        await interaction.response.send_message(
            embed=success_embed("🛒 Покупка", f"**{item.name}**\nСписано: {money(item.price)}\nБаланс: {money(balance_after)}")
        )

    @app_commands.command(name="inventory", description="Показать инвентарь")
    async def inventory(self, interaction: discord.Interaction, member: discord.Member | None = None):
        target = member or interaction.user
        async with async_session_factory() as session:
            items = await economy_service.list_inventory(session, interaction.guild_id, target.id)
        if not items:
            desc = "Инвентарь пуст."
        else:
            desc = "\n".join(f"• **{i.item_name}** × {i.quantity}" for i in items)
        await interaction.response.send_message(
            embed=info_embed(f"🎒 Инвентарь — {target.display_name}", desc),
            ephemeral=(target.id != interaction.user.id),
        )

    # --------------------------- mini-games
    @app_commands.command(name="coinflip", description="Сыграть в орлянку на внутреннюю валюту")
    async def coinflip(self, interaction: discord.Interaction, amount: int, side: str):
        side = side.lower().strip()
        if side not in {"орёл", "орел", "решка", "heads", "tails"}:
            await interaction.response.send_message("Сторона: `орёл` или `решка`.", ephemeral=True)
            return
        chosen = "орёл" if side in {"орёл", "орел", "heads"} else "решка"
        result = "орёл" if __import__("random").randint(0, 1) == 0 else "решка"
        try:
            async with async_session_factory() as session:
                await economy_service.withdraw(session, interaction.guild_id, interaction.user.id, amount, reason="coinflip bet")
                if result == chosen:
                    tx = await economy_service.deposit(
                        session, interaction.guild_id, interaction.user.id, amount * 2, reason="coinflip win"
                    )
                    desc = f"Выпало: **{result}**\n🎉 Выигрыш: **{money(amount)}**"
                else:
                    tx = None
                    desc = f"Выпало: **{result}**\nВы проиграли **{money(amount)}**."
        except ValueError as exc:
            await interaction.response.send_message(embed=error_embed("Игра не запущена", str(exc)), ephemeral=True)
            return
        await interaction.response.send_message(embed=success_embed("🪙 Орлянка", desc))

    @app_commands.command(name="dice", description="Бросить кубик на внутреннюю валюту")
    async def dice(self, interaction: discord.Interaction, amount: int, guess: int):
        if guess < 1 or guess > 6 or amount <= 0:
            await interaction.response.send_message("Ставка > 0, число от 1 до 6.", ephemeral=True)
            return
        roll = __import__("random").randint(1, 6)
        try:
            async with async_session_factory() as session:
                await economy_service.withdraw(session, interaction.guild_id, interaction.user.id, amount, reason="dice bet")
                if roll == guess:
                    await economy_service.deposit(
                        session, interaction.guild_id, interaction.user.id, amount * 5, reason="dice win"
                    )
                    desc = f"Выпало **{roll}**. 🎉 Выигрыш: **{money(amount * 4)}** чистыми."
                else:
                    desc = f"Выпало **{roll}**. Проигрыш: **{money(amount)}**."
        except ValueError as exc:
            await interaction.response.send_message(embed=error_embed("Игра не запущена", str(exc)), ephemeral=True)
            return
        await interaction.response.send_message(embed=success_embed("🎲 Кубик", desc))

    # --------------------------- administration: shop / cases
    economy_group = app_commands.Group(name="economy", description="Администрирование экономики")

    @economy_group.command(name="give", description="Выдать деньги участнику")
    @require_permission("manage_economy")
    async def economy_give(self, interaction: discord.Interaction, member: discord.Member, amount: int, reason: str):
        try:
            async with async_session_factory() as session:
                tx = await economy_service.deposit(
                    session, interaction.guild_id, member.id, amount,
                    actor_discord_id=interaction.user.id, reason=reason,
                )
                await log_audit_action(
                    session, interaction.guild_id, interaction.user.id, "economy.give",
                    str(member.id), {"amount": amount, "reason": reason},
                )
        except ValueError as exc:
            await interaction.response.send_message(embed=error_embed("Ошибка", str(exc)), ephemeral=True)
            return
        await interaction.response.send_message(
            embed=success_embed("Деньги выданы", f"{member.mention}: **+{money(amount)}**\nТранзакция `#{tx.id}`"),
            ephemeral=True,
        )

    @economy_group.command(name="take", description="Списать деньги у участника")
    @require_permission("manage_economy")
    async def economy_take(self, interaction: discord.Interaction, member: discord.Member, amount: int, reason: str):
        try:
            async with async_session_factory() as session:
                tx = await economy_service.withdraw(
                    session, interaction.guild_id, member.id, amount,
                    actor_discord_id=interaction.user.id, reason=reason,
                )
                await log_audit_action(
                    session, interaction.guild_id, interaction.user.id, "economy.take",
                    str(member.id), {"amount": amount, "reason": reason},
                )
        except ValueError as exc:
            await interaction.response.send_message(embed=error_embed("Ошибка", str(exc)), ephemeral=True)
            return
        await interaction.response.send_message(
            embed=success_embed("Деньги списаны", f"{member.mention}: **-{money(amount)}**\nТранзакция `#{tx.id}`"),
            ephemeral=True,
        )

    @economy_group.command(name="shop_add", description="Добавить товар в магазин")
    @app_commands.choices(item_type=[
        app_commands.Choice(name=x, value=x) for x in ["item", "title", "case", "xp", "role"]
    ])
    @require_permission("manage_economy")
    async def shop_add(
        self, interaction: discord.Interaction, item_key: str, name: str, price: int,
        item_type: app_commands.Choice[str], item_value: str = "", stock: int | None = None,
        description: str = "",
    ):
        if price < 0 or (stock is not None and stock < 0):
            await interaction.response.send_message(embed=error_embed("Ошибка", "Цена и остаток не могут быть отрицательными."), ephemeral=True)
            return
        try:
            async with async_session_factory() as session:
                item = await economy_service.create_shop_item(
                    session, interaction.guild_id, item_key=item_key.lower().strip(), name=name,
                    description=description, item_type=item_type.value, item_value=item_value,
                    price=price, stock=stock,
                )
                await log_audit_action(session, interaction.guild_id, interaction.user.id, "economy.shop_add", item.item_key)
        except Exception as exc:
            await interaction.response.send_message(embed=error_embed("Не удалось создать товар", str(exc)), ephemeral=True)
            return
        await interaction.response.send_message(embed=success_embed("Товар добавлен", f"`{item.item_key}` — {item.name}"), ephemeral=True)

    @economy_group.command(name="case_add", description="Создать кейс")
    @require_permission("manage_economy")
    async def case_add(self, interaction: discord.Interaction, case_key: str, name: str, price: int, stock: int | None = None):
        try:
            async with async_session_factory() as session:
                case = await economy_service.create_case(
                    session, interaction.guild_id, case_key=case_key.lower().strip(),
                    name=name, price=price, stock=stock,
                )
                await log_audit_action(session, interaction.guild_id, interaction.user.id, "economy.case_add", case.case_key)
        except Exception as exc:
            await interaction.response.send_message(embed=error_embed("Не удалось создать кейс", str(exc)), ephemeral=True)
            return
        await interaction.response.send_message(embed=success_embed("Кейс создан", f"`{case.case_key}` — {case.name}"), ephemeral=True)

    @economy_group.command(name="case_reward", description="Добавить награду в кейс")
    @app_commands.choices(reward_type=[
        app_commands.Choice(name=x, value=x) for x in ["money", "xp", "item", "title"]
    ])
    @require_permission("manage_economy")
    async def case_reward(
        self, interaction: discord.Interaction, case_key: str, reward_type: app_commands.Choice[str],
        reward_value: str, weight: int, quantity: int = 1, rarity: str = "common",
    ):
        try:
            async with async_session_factory() as session:
                case = await economy_service.get_case(session, interaction.guild_id, case_key.lower().strip())
                if case is None:
                    raise ValueError("Кейс не найден.")
                reward = await economy_service.add_case_reward(
                    session, case, reward_type=reward_type.value, reward_value=reward_value,
                    weight=weight, quantity=quantity, rarity=rarity,
                )
                await log_audit_action(session, interaction.guild_id, interaction.user.id, "economy.case_reward", str(reward.id))
        except Exception as exc:
            await interaction.response.send_message(embed=error_embed("Ошибка", str(exc)), ephemeral=True)
            return
        await interaction.response.send_message(
            embed=success_embed("Награда кейса добавлена", f"{reward.reward_type}: {reward.reward_value} · вес {reward.weight}"),
            ephemeral=True,
        )

    @app_commands.command(name="case", description="Открыть кейс")
    async def case(self, interaction: discord.Interaction, case_key: str):
        try:
            async with async_session_factory() as session:
                reward = await economy_service.open_case(session, interaction.guild_id, interaction.user.id, case_key.lower().strip())
                if reward.reward_type == "money":
                    tx = await economy_service.deposit(
                        session, interaction.guild_id, interaction.user.id, int(reward.reward_value),
                        reason=f"Награда кейса {case_key}",
                    )
                    text = f"💰 {money(int(reward.reward_value))}"
                elif reward.reward_type == "xp":
                    user = await get_or_create_user(session, interaction.user, interaction.guild_id)
                    profile = await get_or_create_profile(session, user)
                    amount = max(0, int(reward.reward_value))
                    if amount:
                        await add_xp(session, profile, interaction.user.id, amount, reason=f"case:{case_key}")
                    text = f"✨ {amount} XP"
                else:
                    text = f"🎁 {reward.reward_value} × {reward.quantity}"
        except (ValueError, TypeError) as exc:
            await interaction.response.send_message(embed=error_embed("Кейс не открыт", str(exc)), ephemeral=True)
            return
        await interaction.response.send_message(embed=success_embed("🎁 Кейс открыт!", f"Вам выпало: **{text}**\nРедкость: **{reward.rarity}**"))

    @app_commands.command(name="sell", description="Продать предмет из инвентаря")
    async def sell(self, interaction: discord.Interaction, item_key: str, quantity: int, price_each: int):
        if quantity <= 0 or price_each <= 0:
            await interaction.response.send_message("Количество и цена должны быть больше нуля.", ephemeral=True)
            return
        async with async_session_factory() as session:
            items = await economy_service.list_inventory(session, interaction.guild_id, interaction.user.id)
            item = next((i for i in items if i.item_key == item_key), None)
            if item is None or item.quantity < quantity:
                await interaction.response.send_message("Недостаточно предметов.", ephemeral=True)
                return
            item.quantity -= quantity
            await economy_service.deposit(
                session, interaction.guild_id, interaction.user.id, quantity * price_each,
                reason=f"Продажа {item.item_name}",
            )
        await interaction.response.send_message(embed=success_embed("Продажа", f"Продано: {quantity} × {item.item_name}\nПолучено: {money(quantity * price_each)}"))

    @app_commands.command(name="bank", description="Показать баланс семейного банка")
    async def bank(self, interaction: discord.Interaction):
        async with async_session_factory() as session:
            value = await economy_service.get_bank(session, interaction.guild_id)
        await interaction.response.send_message(
            embed=info_embed("🏦 Семейный банк", f"Общий баланс: **{money(value)}**"),
            ephemeral=True,
        )

    @app_commands.command(name="bank_deposit", description="Внести деньги в семейный банк")
    async def bank_deposit(self, interaction: discord.Interaction, amount: int):
        try:
            async with async_session_factory() as session:
                value = await economy_service.bank_deposit(
                    session, interaction.guild_id, interaction.user.id, amount
                )
        except ValueError as exc:
            await interaction.response.send_message(embed=error_embed("Взнос не выполнен", str(exc)), ephemeral=True)
            return
        await interaction.response.send_message(
            embed=success_embed("🏦 Взнос выполнен", f"Внесено: **{money(amount)}**\nБанк: **{money(value)}**")
        )

    @app_commands.command(name="bank_withdraw", description="Получить деньги из семейного банка")
    @require_permission("manage_economy")
    async def bank_withdraw(self, interaction: discord.Interaction, amount: int):
        try:
            async with async_session_factory() as session:
                value = await economy_service.bank_withdraw(
                    session, interaction.guild_id, interaction.user.id, amount
                )
        except ValueError as exc:
            await interaction.response.send_message(embed=error_embed("Снятие не выполнено", str(exc)), ephemeral=True)
            return
        await interaction.response.send_message(
            embed=success_embed("🏦 Снятие выполнено", f"Получено: **{money(amount)}**\nБанк: **{money(value)}**"),
            ephemeral=True,
        )

    @app_commands.command(name="economy_history", description="Последние денежные операции")
    async def economy_history(self, interaction: discord.Interaction, member: discord.Member | None = None):
        target = member or interaction.user
        async with async_session_factory() as session:
            txs = await economy_service.recent_transactions(session, interaction.guild_id, target.id)
        lines = [f"`#{t.id}` {t.amount:+,}$ — {t.description}" for t in txs]
        await interaction.response.send_message(
            embed=info_embed("📜 История транзакций", "\n".join(lines) or "История пуста."),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(EconomyCog(bot))
