import asyncio
from .db.database import Base, async_engine


async def initialize_database():
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    finally:
        await async_engine.dispose()


def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(initialize_database())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
