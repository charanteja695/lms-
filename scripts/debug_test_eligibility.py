import asyncio
import asyncpg

async def check():
    conn_cat = await asyncpg.connect('postgresql://lms:lms@127.0.0.1:5432/lms_catalog')
    tables = await conn_cat.fetch("""
        SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'
    """)
    print('Catalog Tables:', [t['table_name'] for t in tables])

    if 'course_version_rules' in [t['table_name'] for t in tables]:
        r = await conn_cat.fetch('SELECT * FROM course_version_rules LIMIT 5')
        print('Sample rules:', [dict(x) for x in r])
    await conn_cat.close()

asyncio.run(check())
