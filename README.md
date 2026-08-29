# Family Bot — STIFFLER / Majestic RP

Discord-бот семьи STIFFLER. Интерфейс полностью внутри Discord, данные — PostgreSQL, деплой — Railway + Docker.

## Реализовано

### Этап 1 — база
- Discord + slash commands
- PostgreSQL / SQLAlchemy / Alembic
- пользователи, ранги, права, настройки
- audit/bot logs
- graceful shutdown и DB health-check

### Этап 2 — семья
- `/profile`
- XP за сообщения и Voice с cooldown/лимитами
- уровни и роли-награды
- репутация и история
- ручное управление XP

### Этап 3 — активность
- задания: daily/weekly/seasonal/individual/group/random
- прогресс заданий по сообщениям и Voice
- достижения с редкостью и секретными условиями
- рейтинги XP/активности/Voice/денег/репутации/сообщений
- сезоны
- Family Pass с уровнями и наградами

### Этап 4 — экономика
- баланс и переводы
- Daily / Weekly
- магазин и инвентарь
- кейсы с весами выпадения
- семейный банк
- транзакционная блокировка для денежных операций

## Команды

### Участники
- `/profile [member]`
- `/balance [member]`
- `/pay member amount`
- `/daily`
- `/weekly`
- `/inventory`
- `/leaderboard category limit`

### Активность
- `/quest list`
- `/quest progress`
- `/achievement list`
- `/achievement me`
- `/season info`
- `/pass me`
- `/pass claim level`

### Администрация
- `/quest create|delete`
- `/achievement create`
- `/season create|activate`
- `/pass reward`
- `/shop add|remove`
- `/case create|reward`
- `/bank balance|deposit|withdraw`

Все административные команды защищены системой rank permissions/Discord administrator.

## Railway

Variables:
- `DISCORD_TOKEN`
- `DATABASE_URL`
- `GUILD_ID`
- `LOG_CHANNEL_ID` (опционально)
- `ADMIN_ROLE_ID` (опционально)
- `TIMEZONE` (опционально)

Перед деплоем включите в Discord Developer Portal Privileged Gateway Intents, которые использует бот: **Message Content**, **Server Members**, при необходимости **Presence**.

Docker при запуске выполняет `alembic upgrade head`, затем запускает бота.

## Следующие этапы по ТЗ

5. Мероприятия → 6. Заявки → 7. Модерация → 8. Полные логи → 9. Автоматизация → 10. RP-модули.

ТЗ требует также территории, войны семей, контракты, должности, летопись, влияние, расширенные логи, отчёты, Voice-комнаты и автоматические задачи. Эти модули добавляются отдельными миграциями, не ломая существующие данные.
