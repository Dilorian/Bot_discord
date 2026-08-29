import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional

from bot.services.economy import EconomyService
from bot.utils.decorators import check_permissions

class EconomyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="balance", description="Показать баланс (личный или другого участника)")
    @app_commands.describe(member="Участник, чей баланс показать")
    async def balance(self, interaction: discord.Interaction, member: discord.Member = None):
        user_id = member.id if member else interaction.user.id
        async with self.bot.db_session() as session:
            service = EconomyService(session, interaction.guild.id)
            wallet = await service.get_or_create_wallet(user_id)
            bank = await service.get_bank_account()
            embed = discord.Embed(
                title=f"💰 Баланс {member.display_name if member else interaction.user.display_name}",
                color=discord.Color.gold()
            )
            embed.add_field(name="Личный баланс", value=f"${wallet.balance:,}", inline=True)
            embed.add_field(name="Семейный банк", value=f"${bank.balance:,}", inline=True)
            embed.add_field(name="Всего заработано", value=f"${wallet.lifetime_earned:,}", inline=True)
            embed.add_field(name="Всего потрачено", value=f"${wallet.lifetime_spent:,}", inline=True)
            if member:
                embed.set_footer(text=f"Запросил {interaction.user.display_name}")
            await interaction.response.send_message(embed=embed)

    @app_commands.command(name="pay", description="Перевести деньги другому участнику")
    @app_commands.describe(recipient="Кому перевести", amount="Сумма", reason="Причина перевода")
    async def pay(self, interaction: discord.Interaction, recipient: discord.Member,
                  amount: app_commands.Range[int, 1], reason: str = None):
        if recipient.id == interaction.user.id:
            await interaction.response.send_message("❌ Нельзя перевести самому себе.", ephemeral=True)
            return
        async with self.bot.db_session() as session:
            service = EconomyService(session, interaction.guild.id)
            try:
                tx_from, tx_to = await service.transfer_money(
                    interaction.user.id, recipient.id, amount,
                    description=reason, actor_discord_id=interaction.user.id
                )
                embed = discord.Embed(
                    title="✅ Перевод выполнен",
                    description=f"Вы перевели **${amount:,}** участнику {recipient.mention}",
                    color=discord.Color.green()
                )
                if reason:
                    embed.add_field(name="Причина", value=reason, inline=False)
                await interaction.response.send_message(embed=embed)
            except ValueError as e:
                await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)

    @app_commands.command(name="daily", description="Получить ежедневный бонус")
    async def daily(self, interaction: discord.Interaction):
        async with self.bot.db_session() as session:
            service = EconomyService(session, interaction.guild.id)
            bonus, claimed = await service.claim_daily(interaction.user.id)
            if claimed:
                embed = discord.Embed(
                    title="🎁 Ежедневный бонус",
                    description=f"Вы получили **${bonus:,}**!",
                    color=discord.Color.blue()
                )
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message("❌ Вы уже получали бонус сегодня. Возвращайтесь завтра!", ephemeral=True)

    @app_commands.command(name="weekly", description="Получить еженедельный бонус")
    async def weekly(self, interaction: discord.Interaction):
        async with self.bot.db_session() as session:
            service = EconomyService(session, interaction.guild.id)
            bonus, claimed = await service.claim_weekly(interaction.user.id)
            if claimed:
                embed = discord.Embed(
                    title="🎁 Еженедельный бонус",
                    description=f"Вы получили **${bonus:,}**!",
                    color=discord.Color.purple()
                )
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message("❌ Вы уже получали бонус на этой неделе. Возвращайтесь через неделю!", ephemeral=True)

    @app_commands.command(name="bank", description="Управление семейным банком (депозит/вывод)")
    @app_commands.describe(action="deposit или withdraw", amount="Сумма")
    async def bank(self, interaction: discord.Interaction, action: str, amount: app_commands.Range[int, 1]):
        async with self.bot.db_session() as session:
            service = EconomyService(session, interaction.guild.id)
            try:
                if action.lower() == "deposit":
                    tx = await service.deposit_to_bank(interaction.user.id, amount)
                    embed = discord.Embed(
                        title="🏦 Депозит в банк",
                        description=f"Вы положили **${amount:,}** в семейный банк.",
                        color=discord.Color.green()
                    )
                elif action.lower() == "withdraw":
                    tx = await service.withdraw_from_bank(interaction.user.id, amount)
                    embed = discord.Embed(
                        title="🏦 Вывод из банка",
                        description=f"Вы сняли **${amount:,}** из семейного банка.",
                        color=discord.Color.green()
                    )
                else:
                    await interaction.response.send_message("❌ Действие должно быть `deposit` или `withdraw`.", ephemeral=True)
                    return
                wallet = await service.get_or_create_wallet(interaction.user.id)
                bank = await service.get_bank_account()
                embed.add_field(name="Личный баланс", value=f"${wallet.balance:,}", inline=True)
                embed.add_field(name="Банк", value=f"${bank.balance:,}", inline=True)
                await interaction.response.send_message(embed=embed)
            except ValueError as e:
                await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)

    @app_commands.command(name="shop", description="Просмотр магазина")
    @app_commands.describe(item_type="Категория (title, role, item, ticket, booster)")
    async def shop(self, interaction: discord.Interaction, item_type: str = None):
        async with self.bot.db_session() as session:
            service = EconomyService(session, interaction.guild.id)
            items = await service.get_shop_items(item_type)
            if not items:
                await interaction.response.send_message("🛒 В магазине пока нет товаров.", ephemeral=True)
                return
            embed = discord.Embed(
                title="🛒 Магазин",
                description=f"Категория: {item_type or 'Все'}",
                color=discord.Color.blue()
            )
            for item in items[:10]:
                stock_str = "∞" if item.stock is None else str(item.stock)
                embed.add_field(
                    name=f"{item.name} (${item.price:,})",
                    value=f"`{item.item_key}` — {item.description or 'Нет описания'}\nВ наличии: {stock_str}",
                    inline=False
                )
            if len(items) > 10:
                embed.set_footer(text="Показаны первые 10. Используйте /buy <item_key> для покупки.")
            await interaction.response.send_message(embed=embed)

    @app_commands.command(name="buy", description="Купить товар из магазина")
    @app_commands.describe(item_key="Ключ товара (из /shop)", quantity="Количество (по умолчанию 1)")
    async def buy(self, interaction: discord.Interaction, item_key: str, quantity: int = 1):
        if quantity <= 0:
            await interaction.response.send_message("❌ Количество должно быть положительным.", ephemeral=True)
            return
        async with self.bot.db_session() as session:
            service = EconomyService(session, interaction.guild.id)
            try:
                inv = await service.purchase_item(interaction.user.id, item_key, quantity)
                embed = discord.Embed(
                    title="✅ Покупка успешна",
                    description=f"Вы купили **{inv.name}** в количестве {quantity}.",
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=embed)
            except ValueError as e:
                await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)

    @app_commands.command(name="inventory", description="Показать ваш инвентарь")
    async def inventory(self, interaction: discord.Interaction):
        async with self.bot.db_session() as session:
            service = EconomyService(session, interaction.guild.id)
            inv_items = await service.get_inventory(interaction.user.id)
            if not inv_items:
                await interaction.response.send_message("📭 Ваш инвентарь пуст.", ephemeral=True)
                return
            embed = discord.Embed(
                title="📦 Ваш инвентарь",
                color=discord.Color.gold()
            )
            for inv in inv_items[:10]:
                expires = f" (до {inv.expires_at.strftime('%d.%m.%Y')})" if inv.expires_at else ""
                embed.add_field(
                    name=f"{inv.name} x{inv.quantity}",
                    value=f"Тип: {inv.item_type}{expires}",
                    inline=False
                )
            if len(inv_items) > 10:
                embed.set_footer(text="Показаны первые 10 предметов.")
            await interaction.response.send_message(embed=embed)

    @app_commands.command(name="cases", description="Список доступных кейсов")
    async def cases(self, interaction: discord.Interaction):
        async with self.bot.db_session() as session:
            service = EconomyService(session, interaction.guild.id)
            cases = await service.get_cases()
            if not cases:
                await interaction.response.send_message("📭 Кейсов пока нет.", ephemeral=True)
                return
            embed = discord.Embed(
                title="🎁 Кейсы",
                description="Откройте кейс и получите награду!",
                color=discord.Color.magenta()
            )
            for case in cases:
                stock = "∞" if case.stock is None else str(case.stock)
                expires = f" (до {case.expires_at.strftime('%d.%m.%Y')})" if case.expires_at else ""
                embed.add_field(
                    name=f"{case.name}",
                    value=f"Цена: ${case.price:,}\n{case.description or ''}\nОсталось: {stock}{expires}\nКлюч: `{case.key}`",
                    inline=False
                )
            await interaction.response.send_message(embed=embed)

    @app_commands.command(name="open_case", description="Открыть кейс")
    @app_commands.describe(case_key="Ключ кейса из /cases")
    async def open_case(self, interaction: discord.Interaction, case_key: str):
        async with self.bot.db_session() as session:
            service = EconomyService(session, interaction.guild.id)
            try:
                result = await service.open_case(interaction.user.id, case_key)
                embed = discord.Embed(
                    title="🎉 Вы открыли кейс!",
                    color=discord.Color.gold()
                )
                if result["type"] == "money":
                    embed.description = f"Вы получили **${result['amount']:,}**!"
                elif result["type"] == "xp":
                    embed.description = f"Вы получили **{result['amount']} XP**!"
                elif result["type"] == "item":
                    embed.description = f"Вы получили предмет (ключ: {result['item_key']})!"
                elif result["type"] == "title":
                    embed.description = f"Вы получили титул **{result['title']}**!"
                elif result["type"] == "role":
                    embed.description = f"Вам выдана роль (ID: {result['role_id']})!"
                else:
                    embed.description = "Вы получили что-то необычное!"
                await interaction.response.send_message(embed=embed)
            except ValueError as e:
                await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(EconomyCog(bot))
