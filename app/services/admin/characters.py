from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User


class AdminCharactersMixin:

    async def give_character(self, session: AsyncSession, user: User, char_name: str) -> dict:
        from app.data.characters import CHARACTERS
        from app.models.character import UserCharacter

        char_data = next((c for c in CHARACTERS if c["name"] == char_name), None)
        if not char_data:
            return {"ok": False, "reason": "Персонаж не найден"}

        char = UserCharacter(
            user_id=user.id,
            character_id=char_data["name"],
            rank=char_data["rank"],
            power=char_data["power"],
        )
        session.add(char)
        await session.flush()

        from app.repositories.squad_repo import squad_repo
        await squad_repo.update_user_combat_power(session, user)

        return {"ok": True, "character": char_data}

    async def give_absolute_character(self, session: AsyncSession, user: User, char_name: str) -> dict:
        from app.data.characters import CHARACTERS
        from app.models.character import UserCharacter

        char_data = next((c for c in CHARACTERS if c["name"] == char_name and c["rank"] == "absolute"), None)
        if not char_data:
            return {"ok": False, "reason": "Абсолютный персонаж не найден"}

        char = UserCharacter(
            user_id=user.id,
            character_id=char_data["name"],
            rank=char_data["rank"],
            power=char_data["power"],
        )
        session.add(char)
        await session.flush()

        from app.repositories.squad_repo import squad_repo
        await squad_repo.update_user_combat_power(session, user)
        return {"ok": True, "character": char_data}

    async def take_absolute_characters(self, session: AsyncSession, user: User) -> dict:
        from app.models.character import UserCharacter
        from sqlalchemy import delete as sa_delete

        result = await session.execute(
            sa_delete(UserCharacter).where(
                UserCharacter.user_id == user.id,
                UserCharacter.rank == "absolute",
            )
        )
        count = result.rowcount
        await session.flush()

        from app.repositories.squad_repo import squad_repo
        await squad_repo.update_user_combat_power(session, user)
        return {"ok": True, "removed": count}
