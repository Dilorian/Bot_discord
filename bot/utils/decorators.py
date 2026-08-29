import functools
from typing import Callable, Any
import discord
from discord.ext import commands


def check_permissions(**perms: bool):
    """
    Декоратор для проверки прав пользователя на сервере Discord.
    Пример использования: @check_permissions(administrator=True) или @check_permissions(manage_messages=True)
    """
    async def predicate(ctx: commands.Context) -> bool:
        if ctx.guild is None:
            raise commands.NoPrivateMessage("Эта команда недоступна в личных сообщениях.")
        
        # Администраторам разрешено всё
        if ctx.author.guild_permissions.administrator:
            return True

        author_perms = ctx.author.guild_permissions
        missing = [perm for perm, value in perms.items() if getattr(author_perms, perm, None) != value]
        
        if missing:
            raise commands.MissingPermissions(missing)
        return True

    return commands.check(predicate)


def is_admin():
    """Декоратор: разрешает команду только администраторам."""
    return check_permissions(administrator=True)


def guild_only():
    """Декоратор: запрещает выполнение команды в ЛС бота."""
    async def predicate(ctx: commands.Context) -> bool:
        if ctx.guild is None:
            raise commands.NoPrivateMessage("Команду можно использовать только на сервере.")
        return True
    return commands.check(predicate)


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
