from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class ClanRegionBuilding(Base):
    """Здание, построенное кланом в захваченном регионе Кореи."""
    __tablename__ = "clan_region_buildings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clan_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    building_type: Mapped[str] = mapped_column(String(32), nullable=False)
    level: Mapped[int] = mapped_column(Integer, default=1)
