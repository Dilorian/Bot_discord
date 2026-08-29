import functools
from typing import Callable, Any
import discord
from discord.ext import commands

# 1. Проверка прав администратора
def is_admin():
    """Декоратор-проверка: позволяет выполнять команду только администраторам."""
    async def predicate(ctx: commands.Context) -> bool:
        if ctx.guild is None:
            raise commands.NoPrivateMessage("Эта команда недоступна в личных сообщениях.")
        if not ctx.author.guild_permissions.administrator:
            raise commands.MissingPermissions(["administrator"])
        return True
    return commands.check(predicate)

# 2. Кастомный декоратор для проверки работы только на сервере (в гильдии)
def guild_only():
    """Декоратор: запрещает использование команды в ЛС бота."""
    async def predicate(ctx: commands.Context) -> bool:
        if ctx.guild is None:
            raise commands.NoPrivateMessage("Команду можно использовать только на сервере.")
        return True
    return commands.check(predicate)

# 3. Декоратор для обработки асинхронных ошибок / логирования
def log_errors(func: Callable[..., Any]) -> Callable[..., Any]:
    """Декоратор для перехвата и логирования исключений внутри функций cogs."""
    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            print(f"[ERROR] Ошибка при выполнении {func.__name__}: {e}")
            raise e
    return wrapper
