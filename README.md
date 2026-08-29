# Family Bot — Этапы 1–2

Discord-бот для семьи STIFFLER (Majestic RP). Реализованы **Этап 1** (база)
и **Этап 2** (профили, XP, уровни, репутация) из ТЗ.

## Что уже реализовано

### Этап 1 — База
- Подключение бота к Discord (discord.py 2.4, slash-команды).
- Асинхронное подключение к PostgreSQL (SQLAlchemy 2.0 + asyncpg).
- Миграции через Alembic (таблицы создаются автоматически при деплое).
- Таблицы: `users`, `ranks`, `rank_permissions`, `settings`, `bot_logs`, `audit_logs`.
- Система рангов и прав доступа (`/rank create|list|delete|assign`,
  `/rank permission set`), с автоматической синхронизацией Discord-роли,
  если она привязана к рангу.
- Настройки сервера (`/settings view|admin_role|log_channel|timezone`).
- Базовое логирование: старт бота, вход/выход участников, административные
  действия (audit log) — пишется в БД и опционально дублируется в канал логов.
- Graceful shutdown, автопереподключение к БД (`pool_pre_ping`), health-check.

### Этап 2 — Семья: профили, XP, уровни, репутация
- Таблицы: `profiles`, `xp_history`, `levels`, `reputation_history`.
- `/profile [участник]` — интерактивная карточка (раздел 3 ТЗ) со всеми
  полями: Discord ID/username, игровой ник, ранг, уровень, XP и прогресс
  до следующего уровня, репутация, дата вступления, дней в семье, серия
  активности, voice-время, титул. Кнопки: 🏆 Достижения, 📊 Статистика,
  🎯 Задания, 💰 Инвентарь, 📜 История, ⬅ Назад (Достижения/Задания/
  Инвентарь — заглушки до Этапов 3–4, Статистика и История работают уже сейчас).
- Автоматическое начисление XP за сообщения и Voice, с защитой от фарма:
  cooldown между сообщениями, дневной лимит XP, отключение XP по каналам,
  исключение ботов.
- Автоматический расчёт уровня по формуле `level = floor(sqrt(xp / 100))`,
  уведомление в лог-канал при повышении, опциональная выдача Discord-роли
  за уровень (`/level reward`).
- Репутация с историей изменений (`/reputation add`).
- Ручная корректировка XP администрацией (`/xp add`, может быть отрицательным).
- Настройка XP-системы: `/xp settings_view`, `/xp settings_set`,
  `/xp toggle_channel`.

## Локальный запуск

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# заполните DISCORD_TOKEN, DATABASE_URL, GUILD_ID

alembic upgrade head
python -m bot.main
```

## Деплой на Railway

1. Создайте проект на Railway, подключите этот GitHub-репозиторий.
2. Добавьте плагин **PostgreSQL** — Railway создаст переменную `DATABASE_URL`
   автоматически (её нужно будет продублировать/связать с сервисом бота).
3. В **Variables** сервиса бота задайте:
   - `DISCORD_TOKEN` — токен бота (**никогда не коммитьте его в GitHub**);
   - `GUILD_ID` — ID вашего сервера (для мгновенной синхронизации slash-команд);
   - `DATABASE_URL` — обычно подставляется автоматически при связке с Postgres.
4. Railway соберёт образ по `Dockerfile` и при каждом деплое выполнит
   `alembic upgrade head` перед запуском бота (см. CMD в Dockerfile).

## Права бота при инвайте

Минимально необходимые права для Этапа 1:
- `Manage Roles` (для синхронизации ранг → Discord-роль);
- `View Channels`, `Send Messages`, `Embed Links` (для логов и ответов);
- `Use Application Commands`.

Роль бота в иерархии сервера должна стоять **выше** ролей, которые связаны
с рангами семьи — иначе Discord не позволит боту их выдавать.

## Структура проекта

```
├── bot/
│   ├── main.py            # точка входа, загрузка cogs, graceful shutdown
│   ├── cogs/
│   │   ├── events.py       # on_ready, on_member_join/remove, базовые логи
│   │   ├── admin.py        # /settings — настройки сервера
│   │   └── ranks.py        # /rank — ранги и права доступа
│   ├── models/             # SQLAlchemy-модели (users, ranks, settings, logs)
│   ├── services/           # бизнес-логика и работа с БД
│   └── utils/              # проверка прав, embed-хелперы
├── migrations/              # Alembic (initial revision — таблицы Этапа 1)
├── requirements.txt
├── Dockerfile
├── railway.toml
└── .env.example
```

## Доступные команды

| Команда | Описание | Требуемое право |
|---|---|---|
| `/settings view` | Показать настройки сервера | — |
| `/settings admin_role` | Задать роль администрации | `manage_settings` |
| `/settings log_channel` | Задать канал логов | `manage_settings` |
| `/settings timezone` | Задать часовой пояс | `manage_settings` |
| `/rank create` | Создать ранг (+ привязка к роли) | `manage_ranks` |
| `/rank list` | Список рангов | — |
| `/rank delete` | Удалить ранг | `manage_ranks` |
| `/rank assign` | Назначить ранг участнику | `manage_ranks` |
| `/rank permission set` | Выдать/забрать право рангу | `manage_permissions` |
| `/profile [участник]` | Показать карточку профиля | — |
| `/xp add` | Начислить/списать XP вручную | `manage_xp` |
| `/xp settings_view` | Показать настройки XP | — |
| `/xp settings_set` | Изменить настройки XP (cooldown, диапазон, лимит) | `manage_xp` |
| `/xp toggle_channel` | Включить/отключить XP в канале | `manage_xp` |
| `/reputation add` | Изменить репутацию участника | `manage_reputation` |
| `/level reward` | Назначить роль-награду за уровень | `manage_xp` |

Права проверяются в таком порядке: администратор сервера / владелец →
роль администрации из `/settings` → право, выданное рангу пользователя
через `/rank permission set`.

## Что дальше (Этап 3 и далее)

Согласно приоритету разработки из ТЗ (раздел 38):
- **Этап 3** — задания, достижения, рейтинги, сезоны, Family Pass;
- **Этап 4** — экономика, магазин, кейсы, инвентарь, семейный банк;
- далее — мероприятия, заявки, модерация, полное логирование, автоматизация,
  RP-механики (территории, войны семей, летопись).

Каждый следующий этап будет добавлять новые таблицы/модели без изменения
уже созданной структуры Этапа 1.
