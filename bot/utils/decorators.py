import functools
from typing import Callable, Any
import discord
from discord import app_commands
from discord.ext import commands

def check_permissions(*custom_perms: str, **perms: bool):
    """
    Декоратор проверки прав для слэш-команд (app_commands).
    Поддерживает:
      - Кастомные права строкой: @check_permissions("manage_economy")
      - Стандартные права Discord: @check_permissions(administrator=True)
    """
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            raise app_commands.NoPrivateMessage("Эта команда недоступна в личных сообщениях.")

        # 1. Администраторам разрешено всё
        if interaction.user.guild_permissions.administrator:
            return True

        # 2. Проверка встроенных прав Discord (если переданы именованные аргументы)
        if perms:
            author_perms = interaction.user.guild_permissions
            missing = [perm for perm, value in perms.items() if getattr(author_perms, perm, None) != value]
            if missing:
                raise app_commands.MissingPermissions(missing)

        # 3. Проверка кастомных прав из вашей базы данных / ролей (если переданы строки)
        if custom_perms:
            # TODO: Добавьте здесь проверку из вашей системы прав, если она есть.
            # Пример: if "manage_economy" in custom_perms: ...
            pass

        return True

    return app_commands.check(predicate)


def is_admin():
    """Декоратор: разрешает слэш-команду только администраторам."""
    return check_permissions(administrator=True)


def guild_only():
    """Декоратор: запрещает выполнение слэш-команды в ЛС бота."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            raise app_commands.NoPrivateMessage("Команду можно использовать только на сервере.")
        return True
    return app_commands.check(predicate)


def log_errors(func: Callable[..., Any]) -> Callable[..., Any]:
    """Декоратор для перехвата исключений внутри функций."""
    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            print(f"[ERROR] Ошибка в {func.__name__}: {e}")
            raise e
    return wrapper
