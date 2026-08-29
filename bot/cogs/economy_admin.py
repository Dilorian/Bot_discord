import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from typing import Optional

from bot.services.economy import EconomyService
from bot.utils.decorators import check_permissions

class EconomyAdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="economy_add", description="Начислить деньги участнику")
    @app_commands.describe(member="Участник", amount="Сумма", reason="Причина")
    @check_permissions("manage_economy")
    async def economy_add(self, interaction: discord.Interaction, member: discord.Member,
                          amount: app_commands.Range[int, 1], reason: str = None):
        async with self.bot.db_session() as session:
            service = EconomyService(session, interaction.guild.id)
            tx = await service.add_money(
                member.id, amount,
                description=reason or f"Административное начисление от {interaction.user.display_name}",
                transaction_type="admin_add",
                actor_discord_id=interaction.user.id
            )
            embed = discord.Embed(
                title="✅ Деньги начислены",
                description=f"Участнику {member.mention} начислено **${amount:,}**.",
                color=discord.Color.green()
            )
            if reason:
                embed.add_field(name="Причина", value=reason)
            await interaction.response.send_message(embed=embed)

    @app_commands.command(name="economy_remove", description="Снять деньги с участника")
    @app_commands.describe(member="Участник", amount="Сумма", reason="Причина")
    @check_permissions("manage_economy")
    async def economy_remove(self, interaction: discord.Interaction, member: discord.Member,
                             amount: app_commands.Range[int, 1], reason: str = None):
        async with self.bot.db_session() as session:
            service = EconomyService(session, interaction.guild.id)
            try:
                tx = await service.remove_money(
                    member.id, amount,
                    description=reason or f"Административное списание от {interaction.user.display_name}",
                    transaction_type="admin_remove",
                    actor_discord_id=interaction.user.id
                )
                embed = discord.Embed(
                    title="✅ Деньги сняты",
                    description=f"С участника {member.mention} снято **${amount:,}**.",
                    color=discord.Color.red()
                )
                if reason:
                    embed.add_field(name="Причина", value=reason)
                await interaction.response.send_message(embed=embed)
            except ValueError as e:
                await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)

    @app_commands.command(name="shop_create", description="Создать товар в магазине")
    @app_commands.describe(
        name="Название", price="Цена", item_type="Тип (title, role, item, ticket, booster)",
        item_key="Уникальный ключ", description="Описание", stock="Количество (оставьте пустым для бесконечного)"
    )
    @check_permissions("manage_shop")
    async def shop_create(self, interaction: discord.Interaction, name: str, price: app_commands.Range[int, 0],
                          item_type: str, item_key: str, description: str = None, stock: Optional[int] = None):
        async with self.bot.db_session() as session:
            service = EconomyService(session, interaction.guild.id)
            try:
                item = await service.create_shop_item(
                    name=name,
                    price=price,
                    item_type=item_type,
                    item_key=item_key,
                    description=description or "",
                    stock=stock,
                    created_by=interaction.user.id
                )
                embed = discord.Embed(
                    title="✅ Товар создан",
                    description=f"Товар **{item.name}** (ключ: `{item.item_key}`) добавлен в магазин.",
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=embed)
            except ValueError as e:
                await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)

    @app_commands.command(name="shop_edit", description="Изменить товар")
    @app_commands.describe(
        item_key="Ключ товара", name="Новое название", price="Новая цена",
        item_type="Новый тип", description="Новое описание", stock="Новый склад (число или null)",
        is_active="Активен (true/false)"
    )
    @check_permissions("manage_shop")
    async def shop_edit(self, interaction: discord.Interaction, item_key: str,
                        name: str = None, price: app_commands.Range[int, 0] = None,
                        item_type: str = None, description: str = None,
                        stock: Optional[int] = None, is_active: bool = None):
        async with self.bot.db_session() as session:
            service = EconomyService(session, interaction.guild.id)
            try:
                updates = {}
                if name is not None:
                    updates['name'] = name
                if price is not None:
                    updates['price'] = price
                if item_type is not None:
                    updates['item_type'] = item_type
                if description is not None:
                    updates['description'] = description
                if stock is not None:
                    updates['stock'] = stock
                if is_active is not None:
                    updates['is_active'] = is_active
                item = await service.update_shop_item(item_key, **updates)
                embed = discord.Embed(
                    title="✅ Товар обновлён",
                    description=f"Товар **{item.name}** (ключ: `{item.item_key}`) обновлён.",
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=embed)
            except ValueError as e:
                await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)

    @app_commands.command(name="shop_delete", description="Удалить товар")
    @app_commands.describe(item_key="Ключ товара")
    @check_permissions("manage_shop")
    async def shop_delete(self, interaction: discord.Interaction, item_key: str):
        async with self.bot.db_session() as session:
            service = EconomyService(session, interaction.guild.id)
            success = await service.delete_shop_item(item_key)
            if success:
                await interaction.response.send_message(f"✅ Товар с ключом `{item_key}` удалён.")
            else:
                await interaction.response.send_message("❌ Товар не найден.", ephemeral=True)

    @app_commands.command(name="case_create", description="Создать кейс")
    @app_commands.describe(
        key="Уникальный ключ кейса", name="Название", price="Цена",
        description="Описание", stock="Количество (оставьте пустым для бесконечного)",
        expires_at="Дата истечения (в формате YYYY-MM-DD HH:MM)"
    )
    @check_permissions("manage_cases")
    async def case_create(self, interaction: discord.Interaction, key: str, name: str,
                          price: app_commands.Range[int, 0], description: str = None,
                          stock: Optional[int] = None, expires_at: str = None):
        expire_dt = None
        if expires_at:
            try:
                expire_dt = datetime.strptime(expires_at, "%Y-%m-%d %H:%M")
            except ValueError:
                await interaction.response.send_message("❌ Неверный формат даты. Используйте YYYY-MM-DD HH:MM", ephemeral=True)
                return
        async with self.bot.db_session() as session:
            service = EconomyService(session, interaction.guild.id)
            try:
                case = await service.create_case(
                    key=key,
                    name=name,
                    price=price,
                    description=description or "",
                    stock=stock,
                    expires_at=expire_dt,
                    created_by=interaction.user.id
                )
                embed = discord.Embed(
                    title="✅ Кейс создан",
                    description=f"Кейс **{case.name}** (ключ: `{case.key}`) создан. Теперь добавьте награды через `/case_reward_add`.",
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=embed)
            except ValueError as e:
                await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)

    @app_commands.command(name="case_edit", description="Изменить кейс")
    @app_commands.describe(
        key="Ключ кейса", name="Новое название", price="Новая цена",
        description="Новое описание", stock="Новый склад (число или null)",
        is_active="Активен (true/false)", expires_at="Дата истечения (YYYY-MM-DD HH:MM)"
    )
    @check_permissions("manage_cases")
    async def case_edit(self, interaction: discord.Interaction, key: str,
                        name: str = None, price: app_commands.Range[int, 0] = None,
                        description: str = None, stock: Optional[int] = None,
                        is_active: bool = None, expires_at: str = None):
        expire_dt = None
        if expires_at:
            try:
                expire_dt = datetime.strptime(expires_at, "%Y-%m-%d %H:%M")
            except ValueError:
                await interaction.response.send_message("❌ Неверный формат даты. Используйте YYYY-MM-DD HH:MM", ephemeral=True)
                return
        async with self.bot.db_session() as session:
            service = EconomyService(session, interaction.guild.id)
            try:
                updates = {}
                if name is not None:
                    updates['name'] = name
                if price is not None:
                    updates['price'] = price
                if description is not None:
                    updates['description'] = description
                if stock is not None:
                    updates['stock'] = stock
                if is_active is not None:
                    updates['is_active'] = is_active
                if expire_dt is not None:
                    updates['expires_at'] = expire_dt
                case = await service.update_case(key, **updates)
                embed = discord.Embed(
                    title="✅ Кейс обновлён",
                    description=f"Кейс **{case.name}** (ключ: `{case.key}`) обновлён.",
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=embed)
            except ValueError as e:
                await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)

    @app_commands.command(name="case_delete", description="Удалить кейс")
    @app_commands.describe(key="Ключ кейса")
    @check_permissions("manage_cases")
    async def case_delete(self, interaction: discord.Interaction, key: str):
        async with self.bot.db_session() as session:
            service = EconomyService(session, interaction.guild.id)
            success = await service.delete_case(key)
            if success:
                await interaction.response.send_message(f"✅ Кейс с ключом `{key}` удалён.")
            else:
                await interaction.response.send_message("❌ Кейс не найден.", ephemeral=True)

    @app_commands.command(name="case_reward_add", description="Добавить награду в кейс")
    @app_commands.describe(
        case_key="Ключ кейса", reward_type="Тип: money, xp, item, title, role",
        reward_value="Значение (например, сумма, ключ предмета, название титула, ID роли)",
        amount="Количество (для money/xp)", weight="Вес (шанс выпадения)", rarity="Редкость"
    )
    @check_permissions("manage_cases")
    async def case_reward_add(self, interaction: discord.Interaction, case_key: str,
                              reward_type: str, reward_value: str, amount: int = 0,
                              weight: int = 1, rarity: str = "Common"):
        async with self.bot.db_session() as session:
            service = EconomyService(session, interaction.guild.id)
            try:
                reward = await service.add_case_reward(
                    case_key=case_key,
                    reward_type=reward_type,
                    reward_value=reward_value,
                    amount=amount,
                    weight=weight,
                    rarity=rarity
                )
                embed = discord.Embed(
                    title="✅ Награда добавлена",
                    description=f"Награда типа `{reward_type}` добавлена в кейс `{case_key}`.",
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=embed)
            except ValueError as e:
                await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)

    @app_commands.command(name="case_reward_remove", description="Удалить награду из кейса")
    @app_commands.describe(reward_id="ID награды (из CaseReward)")
    @check_permissions("manage_cases")
    async def case_reward_remove(self, interaction: discord.Interaction, reward_id: int):
        async with self.bot.db_session() as session:
            service = EconomyService(session, interaction.guild.id)
            success = await service.remove_case_reward(reward_id)
            if success:
                await interaction.response.send_message(f"✅ Награда с ID {reward_id} удалена.")
            else:
                await interaction.response.send_message("❌ Награда не найдена.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(EconomyAdminCog(bot))
