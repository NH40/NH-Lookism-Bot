import json
from datetime import datetime
from sqlalchemy import Integer, String, BigInteger, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class ActiveBoss(Base):
    __tablename__ = "active_bosses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    boss_id: Mapped[str] = mapped_column(String(32), nullable=False)

    # Текущее HP (у Братьев может уходить в минус)
    hp: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Оригинальный макс HP при спавне (неизменен)
    base_max_hp: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Текущий эффективный макс HP (растёт у Никиты при шкале отчаяния)
    current_max_hp: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # active / defeated / expired
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Когда появится следующий босс (заполняется при завершении текущего)
    next_spawn_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    defeated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # JSON-блоб для специфичного состояния босса:
    # Никита:    {"despair_scale": 0.0, "nikita_base": <hp>, "heal_count": 0}
    # Архангел:  {"shield_hp": 0, "debuff_attacks": 0}
    # Менеджер:  {"healed": false}
    # Братья:    {}
    state_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    def get_state(self) -> dict:
        try:
            return json.loads(self.state_json or "{}")
        except Exception:
            return {}

    def set_state(self, state: dict) -> None:
        self.state_json = json.dumps(state, ensure_ascii=False)
