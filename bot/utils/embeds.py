from __future__ import annotations

import discord

BRAND_COLOR = discord.Color.from_str("#8e5cff")


def success_embed(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(title=f"✅ {title}", description=description, color=discord.Color.green())


def error_embed(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(title=f"❌ {title}", description=description, color=discord.Color.red())


def info_embed(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(title=title, description=description, color=BRAND_COLOR)
