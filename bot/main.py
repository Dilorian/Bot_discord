from __future__ import annotations

import asyncio
import logging
import os
import signal

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("bot.main")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")

INITIAL_EXTENSIONS = [
    "bot.cogs.events",
    "bot.cogs.admin",
    "bot.cogs.ranks",
    "bot.cogs.profile",
    "bot.cogs.activity",
    "bot.cogs.activity_admin",
    "bot.cogs.quests",
    "bot.cogs.achievements",
    "bot.cogs.ratings",
    "bot.cogs.season",
]


class FamilyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True  # нужно для on_member_join/remove и профилей
        intents.message_content = False  # включим на Этапе про XP за сообщения

        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        for extension in INITIAL_EXTENSIONS:
            try:
                await self.load_extension(extension)
                logger.info("Загружен модуль: %s", extension)
            except Exception:
                logger.exception("Не удалось загрузить модуль %s", extension)

        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info("Slash-команды синхронизированы для гильдии %s (мгновенно)", GUILD_ID)

    async def on_error(self, event_method: str, /, *args, **kwargs):
        logger.exception("Необработанное исключение в событии %s", event_method)


async def main():
    if not DISCORD_TOKEN:
        raise RuntimeError("DISCORD_TOKEN не задан в переменных окружения")

    bot = FamilyBot()

    stop_event = asyncio.Event()

    def _handle_signal():
        logger.info("Получен сигнал остановки, выполняется graceful shutdown...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except NotImplementedError:
            # Windows не поддерживает add_signal_handler для всех сигналов
            pass

    async with bot:
        bot_task = asyncio.create_task(bot.start(DISCORD_TOKEN))
        stop_task = asyncio.create_task(stop_event.wait())

        done, pending = await asyncio.wait(
            {bot_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
        )

        if stop_task in done:
            logger.info("Закрываю соединение с Discord...")
            await bot.close()

        for task in pending:
            task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
