"""
Интервалы фоновых задач APScheduler.
Все значения в минутах/секундах.
"""

# Тик дохода зданий
INCOME_TICK_MINUTES: int = 1

# Тик Ultra Instinct (авто-действия)
UI_TICK_MINUTES: int = 1

# Тик раундов аукциона (проверка завершения раунда)
AUCTION_ROUND_TICK_SECONDS: int = 10

# Тик запуска нового аукциона (проверяем — не пора ли запустить)
AUCTION_START_TICK_MINUTES: int = 2

# Тик пересчёта бонуса реферальной мощи
REFERRAL_POWER_TICK_MINUTES: int = 30

# Тик войн кланов (завершение просроченных)
CLAN_WAR_TICK_MINUTES: int = 5

# Тик аукционов кланов
CLAN_AUCTION_TICK_MINUTES: int = 1

# Тик завершения походов (проверяем каждые 2 минуты)
CAMPAIGN_TICK_MINUTES: int = 2

# Тик боссов (спавн/завершение, каждую минуту)
BOSS_TICK_SECONDS: int = 60

# Тик войн за регионы Кореи (завершение истёкших, каждые 5 минут)
REGION_WAR_TICK_MINUTES: int = 5
