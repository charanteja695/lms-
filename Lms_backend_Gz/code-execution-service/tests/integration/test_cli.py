import httpx
import respx
from cryptography.fernet import Fernet
from sqlalchemy import select

from app.cli import commands
from app.core.crypto import SecretCipher
from app.engines.judge0 import Judge0Engine
from app.models.language import Language
from app.models.problem import Problem
from app.models.test_case import TestCase
from tests.conftest import LANGUAGES_FILE, ProblemFactory, _settings


async def test_sync_languages_is_idempotent_and_the_file_is_the_source_of_truth(sessionmaker) -> None:
    settings = _settings(LANGUAGES_FILE=str(LANGUAGES_FILE))
    created, updated = await commands.sync_languages(sessionmaker, settings)
    assert (created, updated) == (0, 18)  # the test harness already loaded the catalogue; nothing new, all refreshed

    async with sessionmaker() as db:
        python = (await db.execute(select(Language).where(Language.code == "python3"))).scalar_one()
        python.time_multiplier = 99.0  # somebody's manual change...
        await db.commit()
    await commands.sync_languages(sessionmaker, settings)
    async with sessionmaker() as db:
        assert (await db.execute(select(Language.time_multiplier).where(Language.code == "python3"))).scalar_one() == 3.0  # ...is reset by a deploy


async def test_sync_creates_languages_on_an_empty_database(sessionmaker) -> None:
    async with sessionmaker() as db:
        for language in (await db.execute(select(Language))).scalars():
            await db.delete(language)
        await db.commit()
    created, updated = await commands.sync_languages(sessionmaker, _settings(LANGUAGES_FILE=str(LANGUAGES_FILE)))
    assert (created, updated) == (18, 0)


async def test_verify_languages_flags_ids_the_engine_does_not_have(sessionmaker) -> None:
    settings = _settings(JUDGE0_URL="http://judge0.test")
    engine_languages = [{"id": 71, "name": "Python (3.8.1)"}, {"id": 54, "name": "C++ (GCC 9.2.0)"}, {"id": 62, "name": "Java (OpenJDK 13.0.1)"}]
    with respx.mock(base_url="http://judge0.test") as router:
        router.get("/languages").mock(return_value=httpx.Response(200, json=engine_languages))
        checks = await commands.verify_languages(sessionmaker, settings, engine=Judge0Engine(settings))

    by_code = {check.code: check for check in checks}
    assert (by_code["python3"].ok, by_code["python3"].engine_name) == (True, "Python (3.8.1)")
    assert by_code["cpp20"].ok and by_code["cpp17"].ok  # both standards share one engine id, told apart by compiler options
    assert not by_code["go"].ok and by_code["go"].engine_name is None  # id 60 does not exist on this engine
    assert "sqlite" not in by_code  # SQL dialects run on this service's own engines and have no engine id


async def test_rotating_keys_re_encrypts_everything_so_the_old_key_can_be_retired(sessionmaker, make_problem: ProblemFactory, settings) -> None:
    problem_id = await make_problem(problem_type="sql", setup_sql="CREATE TABLE t (x INT)", allowed_languages=["sqlite"], cases=[{"input": "seed", "expected": "x\n1"}])
    old_key = settings.encryption_keys[0]
    new_key = Fernet.generate_key().decode()
    rotating = _settings(TEST_CASE_ENCRYPTION_KEYS=f"{new_key},{old_key}")  # the new key first, the old one still readable

    assert await commands.rotate_keys(sessionmaker, rotating) == 3  # input, expected and the setup script
    only_new = SecretCipher([new_key])
    async with sessionmaker() as db:
        case = (await db.execute(select(TestCase))).scalar_one()
        problem = (await db.execute(select(Problem).where(Problem.public_id == problem_id))).scalar_one()
    assert (only_new.decrypt(case.input_encrypted), only_new.decrypt(case.expected_encrypted)) == ("seed", "x\n1")
    assert only_new.decrypt(problem.setup_sql_encrypted) == "CREATE TABLE t (x INT)"
    assert await commands.rotate_keys(sessionmaker, _settings(TEST_CASE_ENCRYPTION_KEYS=new_key)) == 3  # repeatable with only the new key
