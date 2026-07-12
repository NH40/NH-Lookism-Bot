from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class ClanLandBuilding(Base):
    """Здание, построенное кланом на клановой земле (патч 4)."""
    __tablename__ = "clan_land_buildings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clan_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    building_type: Mapped[str] = mapped_column(String(32), nullable=False)
