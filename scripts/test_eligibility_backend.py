import asyncio
import sys
import os
import datetime

sys.path.insert(0, os.path.abspath('Lms_backend_Gz/assessment-service'))

from app.core.config import get_settings
from app.services.eligibility_service import EligibilityService
from app.models.test import Test
from app.core.security import AccessTokenClaims
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

async def main():
    settings = get_settings()
    engine = create_async_engine(str(settings.DATABASE_URL))
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    
    async with sessionmaker() as session:
        tests = (await session.execute(select(Test).where(Test.kind == 'final'))).scalars().all()
        print(f"Found {len(tests)} final tests")
        
        auth = AccessTokenClaims(
            user_id=3,
            session_id=1,
            role="student",
            organization_id=1,
            organization_type="institution",
            scopes=(),
            token_version=1,
            token_id="tok-123",
            issued_at=int(datetime.datetime.now(datetime.timezone.utc).timestamp()),
            expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)
        )
        
        service = EligibilityService(session, settings)
        for t in tests[:5]:
            print(f"\nChecking test {t.public_id} '{t.title}' target_id={t.target_id}:")
            try:
                el = await service.check(t, auth)
                print(f"Result: can_start={el.can_start}, reason={el.reason}, message={el.message}")
            except Exception as e:
                print(f"Exception during check: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(main())
