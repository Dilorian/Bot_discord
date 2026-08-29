import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from typing import Optional

from bot.services.economy import EconomyService
from bot.utils.decorators import check_permissions

# Pre-defined choices for type safety in Discord UI
ITEM_TYPES = [
    app_commands.Choice(name="Title", value="title"),
    app_commands.Choice(name="Role", value="role"),
    app_commands.Choice(name="Item", value="item"),
    app_commands.Choice(name="Ticket", value="ticket"),
    app_commands.Choice(name="Booster", value="booster"),
]

REWARD_TYPES = [
    app_commands.Choice(name="Money", value="money"),
    app_commands.Choice(name="XP", value="xp"),
    app_commands.Choice(name="Item", value="item"),
    app_commands.Choice(name="Title", value="title"),
    app_commands.Choice(name="Role", value="role"),
]

@app_commands.guild_only()
class EconomyAdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="economy_add", description="Начислить деньги участнику")
    @app_commands.describe(member="Участник", amount="Сумма", reason="Причина")
    @check_permissions("manage_economy")
    async def economy_add(
        self, 
        interaction: discord.Interaction, 
        member: discord.Member,
        amount: app_commands.Range[int, 1], 
        reason: Optional[str] = None
    ):
        await interaction.response.defer()
        async with self.bot.db_session() as session:
            service = EconomyService(session, interaction.guild.id)
            await service.add_money(
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
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="economy_remove", description="Снять деньги с участника")
    @app_commands.describe(member="Участник", amount="Сумма", reason="Причина")
    @check_permissions("manage_economy")
    async def economy_remove(
        self, 
        interaction: discord.Interaction, 
        member: discord.Member,
        amount: app_commands.Range[int, 1], 
        reason: Optional[str] = None
    ):
        await interaction.response.defer()
        async with self.bot.db_session() as session:
            service = EconomyService(session, interaction.guild.id)
            try:
                await service.remove_money(
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
                await interaction.followup.send(embed=embed)
            except ValueError as e:
                await interaction.followup.send(f"❌ {str(e)}", ephemeral=True)

    @app_commands.command(name="shop_create", description="Создать товар в магазине")
    @app_commands.describe(
        name="Название", price="Цена", item_type="Тип товара",
        item_key="Уникальный ключ", description="Описание", stock="Количество (оставьте пустым для бесконечного)"
    )
    @app_commands.choices(item_type=ITEM_TYPES)
    @check_permissions("manage_shop")
    async def shop_create(
        self, 
        interaction: discord.Interaction, 
        name: str, 
        price: app_commands.Range[int, 0],
        item_type: app_commands.Choice[str], 
        item_key: str, 
        description: Optional[str] = None, 
        stock: Optional[int] = None
    ):
        await interaction.response.defer()
        async with self.bot.db_session() as session:
            service = EconomyService(session, interaction.guild.id)
            try:
                item = await service.create_shop_item(
                    name=name,
                    price=price,
                    item_type=item_type.value,
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
                await interaction.followup.send(embed=embed)
            except ValueError as e:
                await interaction.followup.send(f"❌ {str(e)}", ephemeral=True)

    @app_commands.command(name="case_reward_add", description="Добавить награду в кейс")
    @app_commands.describe(
        case_key="Ключ кейса", reward_type="Тип награды",
        reward_value="Значение (сумма, ключ предмета, название титула, ID роли)",
        amount="Количество (для money/xp)", weight="Вес (шанс выпадения)", rarity="Редкость"
    )
    @app_commands.choices(reward_type=REWARD_TYPES)
    @check_permissions("manage_cases")
    async def case_reward_add(
        self, 
        interaction: discord.Interaction, 
        case_key: str,
        reward_type: app_commands.Choice[str], 
        reward_value: str, 
        amount: int = 0,
        weight: int = 1, 
        rarity: str = "Common"
    ):
        await interaction.response.defer()
        async with self.bot.db_session() as session:
            service = EconomyService(session, interaction.guild.id)
            try:
                await service.add_case_reward(
                    case_key=case_key,
                    reward_type=reward_type.value,
                    reward_value=reward_value,
                    amount=amount,
                    weight=weight,
                    rarity=rarity
                )
                embed = discord.Embed(
                    title="✅ Награда добавлена",
                    description=f"Награда типа `{reward_type.value}` добавлена в кейс `{case_key}`.",
                    color=discord.Color.green()
                )
                await interaction.followup.send(embed=embed)
            except ValueError as e:
                await interaction.followup.send(f"❌ {str(e)}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(EconomyAdminCog(bot))
