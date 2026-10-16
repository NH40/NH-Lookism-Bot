"""Публичное API домена training (сервис)."""
from bot.services.training.personal import PersonalTrainResult, personal_cooldown_left, train_personal  # noqa: F401
from bot.services.training.training import TrainingOnCooldownError, TrainResult, train_extras  # noqa: F401
