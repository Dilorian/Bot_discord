from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from bot.models.rank import KNOWN_PERMISSIONS
from bot.services.db import async_session_factory
from bot.services.log_service import log_audit_action
from bot.services.rank_service import (
    assign_rank,
    create_rank,
    delete_rank,
    get_rank_by_name,
    list_ranks,
    set_permission,
)
from bot.services.user_service import get_or_create_user
from bot.utils.embeds import error_embed, info_embed, success_embed
from bot.utils.permissions import require_permission


class RanksCog(commands.Cog):
    """Раздел ⚙️ Администрирование → Управление рангами / правами доступа (Этап 1)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    rank_group = app_commands.Group(name="rank", description="Управление рангами семьи")

    @rank_group.command(name="create", description="Создать новый ранг")
    @app_commands.describe(
        name="Название ранга",
        level="Уровень в иерархии (больше = выше)",
        role="Связанная Discord-роль (опционально)",
    )
    @require_permission("manage_ranks")
    async def rank_create(
        self,
        interaction: discord.Interaction,
        name: str,
        level: int = 0,
        role: discord.Role | None = None,
    ):
        async with async_session_factory() as session:
            existing = await get_rank_by_name(session, interaction.guild_id, name)
            if existing:
                await interaction.response.send_message(
                    embed=error_embed("Ранг уже существует", f"Ранг «{name}» уже есть на сервере."),
                    ephemeral=True,
                )
                return

            rank = await create_rank(
                session,
                guild_id=interaction.guild_id,
                name=name,
                level=level,
                discord_role_id=role.id if role else None,
            )
            await log_audit_action(
                session,
                interaction.guild_id,
                interaction.user.id,
                action="rank.create",
                target=name,
                details={"level": level, "role_id": role.id if role else None},
            )

        await interaction.response.send_message(
            embed=success_embed("Ранг создан", f"«{rank.name}» (уровень {rank.level})"),
            ephemeral=True,
        )

    @rank_group.command(name="list", description="Показать список рангов")
    async def rank_list(self, interaction: discord.Interaction):
        async with async_session_factory() as session:
            ranks = await list_ranks(session, interaction.guild_id)

        if not ranks:
            await interaction.response.send_message(
                embed=info_embed("Ранги", "На сервере пока не создано ни одного ранга."),
                ephemeral=True,
            )
            return

        lines = []
        for r in ranks:
            role_part = f" — <@&{r.discord_role_id}>" if r.discord_role_id else ""
            lines.append(f"**{r.name}** (уровень {r.level}){role_part}")

        await interaction.response.send_message(
            embed=info_embed("📋 Ранги семьи", "\n".join(lines)), ephemeral=True
        )

    @rank_group.command(name="delete", description="Удалить ранг")
    @require_permission("manage_ranks")
    async def rank_delete(self, interaction: discord.Interaction, name: str):
        async with async_session_factory() as session:
            rank = await get_rank_by_name(session, interaction.guild_id, name)
            if not rank:
                await interaction.response.send_message(
                    embed=error_embed("Ранг не найден", f"Ранга «{name}» не существует."),
                    ephemeral=True,
                )
                return
            await delete_rank(session, rank)
            await log_audit_action(
                session, interaction.guild_id, interaction.user.id, action="rank.delete", target=name
            )

        await interaction.response.send_message(
            embed=success_embed("Ранг удалён", name), ephemeral=True
        )

    @rank_group.command(name="assign", description="Назначить ранг участнику")
    @require_permission("manage_ranks")
    async def rank_assign(
        self, interaction: discord.Interaction, member: discord.Member, name: str
    ):
        async with async_session_factory() as session:
            rank = await get_rank_by_name(session, interaction.guild_id, name)
            if not rank:
                await interaction.response.send_message(
                    embed=error_embed("Ранг не найден", f"Ранга «{name}» не существует."),
                    ephemeral=True,
                )
                return

            user = await get_or_create_user(session, member, interaction.guild_id)
            await assign_rank(session, user, rank)
            await log_audit_action(
                session,
                interaction.guild_id,
                interaction.user.id,
                action="rank.assign",
                target=str(member.id),
                details={"rank": name},
            )

        # Синхронизация с реальной Discord-ролью, если она привязана к рангу
        if rank.discord_role_id:
            discord_role = interaction.guild.get_role(rank.discord_role_id)
            if discord_role:
                try:
                    await member.add_roles(discord_role, reason=f"Назначен ранг {name}")
                except discord.Forbidden:
                    pass

        await interaction.response.send_message(
            embed=success_embed("Ранг назначен", f"{member.mention} → «{name}»"), ephemeral=True
        )

    permission_group = app_commands.Group(
        name="permission", description="Управление правами рангов", parent=rank_group
    )

    @permission_group.command(name="set", description="Выдать/забрать право рангу")
    @app_commands.choices(
        permission=[app_commands.Choice(name=p, value=p) for p in KNOWN_PERMISSIONS]
    )
    @require_permission("manage_permissions")
    async def permission_set(
        self,
        interaction: discord.Interaction,
        rank_name: str,
        permission: app_commands.Choice[str],
        allowed: bool = True,
    ):
        async with async_session_factory() as session:
            rank = await get_rank_by_name(session, interaction.guild_id, rank_name)
            if not rank:
                await interaction.response.send_message(
                    embed=error_embed("Ранг не найден", f"Ранга «{rank_name}» не существует."),
                    ephemeral=True,
                )
                return

            await set_permission(session, rank, permission.value, allowed)
            await log_audit_action(
                session,
                interaction.guild_id,
                interaction.user.id,
                action="rank.permission.set",
                target=rank_name,
                details={"permission": permission.value, "allowed": allowed},
            )

        status = "выдано" if allowed else "отозвано"
        await interaction.response.send_message(
            embed=success_embed(
                "Право обновлено", f"«{permission.value}» {status} для ранга «{rank_name}»"
            ),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(RanksCog(bot))
