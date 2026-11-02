import asyncio
import sys
import os
from pathlib import Path

current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from sqlalchemy import select
from app.core.config import get_settings
from app.core.security import hash_password, verify_password
from app.db.session import build_engine, build_sessionmaker
from app.models import User
from scripts.seed_demo_accounts import DEMO_ACCOUNTS_DATA

async def reset_passwords():
    settings = get_settings()
    engine = build_engine(settings)
    session_factory = build_sessionmaker(engine)
    
    async with session_factory() as db:
        for acc in DEMO_ACCOUNTS_DATA:
            result = await db.execute(select(User).where(User.email == acc["email"]))
            user = result.scalars().first()
            if user:
                valid, _ = await verify_password(user.password_hash, acc["password"])
                print(f"User {acc['email']}: valid password? {valid}")
                if not valid:
                    user.password_hash = await hash_password(acc["password"])
                    user.is_active = True
                    user.must_change_password = False
                    print(f"  --> Updated password for {acc['email']} to {acc['password']}")
        await db.commit()
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(reset_passwords())
