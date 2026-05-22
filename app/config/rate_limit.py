"""
Настройки rate-limiter для Telegram-обработчиков.
"""

# Максимальное количество запросов в окне
RATE_LIMIT_REQUESTS: int = 8
# Длина окна в секундах
RATE_LIMIT_WINDOW: int = 3
# Нарушений до бана
RATE_LIMIT_MAX_VIOLATIONS: int = 5
# Длина бана в секундах (300 = 5 минут)
RATE_LIMIT_BAN_SECONDS: int = 300
