import asyncio
from db.session import engine
from db.models import Base

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables successfully created.")

if __name__ == "__main__":
    asyncio.run(init_db())
