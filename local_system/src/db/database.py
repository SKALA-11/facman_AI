from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncAttrs
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# MARIA_DB = "mysql+aiomysql://manager:SqlDba-1@127.0.0.1:3306/facman?charset=utf8mb4"

# MARIA_DB = "mysql+aiomysql://root:1234@localhost:3306/facman"

MARIA_DB = "mysql+aiomysql://root:skcc12345@facman.duckdns.org:3306/facman?charset=utf8"

async_engine = create_async_engine(MARIA_DB, echo=True)

AsyncSessionLocal = sessionmaker(
    bind=async_engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base(cls=AsyncAttrs)


async def get_db():
    session = AsyncSessionLocal()
    try:
        yield session
    finally:
        await session.close()
