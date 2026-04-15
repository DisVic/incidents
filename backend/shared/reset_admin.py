import asyncio
from sqlalchemy import text
from shared.database import async_session
from shared.utils import hash_password

async def main():
    new_hash = hash_password("admin123")
    print(f"New hash: {new_hash}")
    async with async_session() as db:
        result = await db.execute(
            text("UPDATE users SET password_hash = :hash WHERE email = 'admin@example.com'"),
            {"hash": new_hash}
        )
        await db.commit()
        print(f"Updated {result.rowcount} rows")

asyncio.run(main())
