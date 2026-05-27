from typing import Callable, Awaitable, Any
from aiogram import BaseMiddleware
from app.database import AsyncSessionFactory


class DbSessionMiddleware(BaseMiddleware):
    """
    Создаёт AsyncSession на каждый апдейт.

    Паттерн: хендлер сам вызывает session.commit() там, где нужно.
    Middleware делает auto-commit в конце, если хендлер забыл (flush-only операции),
    и rollback при любом исключении.

    НЕ используем `async with session.begin()` — он запрещает session.commit() внутри
    и бросает InvalidRequestError при попытке использовать сессию после коммита.
    """

    async def __call__(
        self,
        handler: Callable[[Any, dict], Awaitable[Any]],
        event: Any,
        data: dict,
    ) -> Any:
        async with AsyncSessionFactory() as session:
            data["session"] = session
            try:
                result = await handler(event, data)
                # Если хендлер делал flush() без commit() — коммитим за него
                if session.in_transaction():
                    await session.commit()
                return result
            except Exception:
                # Откатываем при любой ошибке
                if session.in_transaction():
                    await session.rollback()
                raise
