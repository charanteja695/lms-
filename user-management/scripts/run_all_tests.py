import asyncio
import json
import os
import sys
import httpx
from sqlalchemy import text

# Ensure app is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import Settings
from app.db.session import build_engine, build_sessionmaker

BASE_URL = "http://127.0.0.1:8001"
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "..", "var", "demo_credentials.json")

def load_credentials():
    with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

async def main():
    print("=" * 70)
    print("RUNNING EXAMLMS DEMO ACCOUNTS & PASSWORD GENERATION TEST SUITE")
    print("=" * 70)

    settings = Settings()
    engine = build_engine(settings)
    session_maker = build_sessionmaker(engine)

    creds_data = load_credentials()
    demo_accounts = creds_data if isinstance(creds_data, list) else creds_data["accounts"]

    # ---------------------------------------------------------
    # TEST 1: Run seed script idempotency
    # ---------------------------------------------------------
    print("\n[TEST 1] Testing demo account seed script idempotency...")
    from scripts.seed_demo_accounts import seed_demo_accounts
    summary = await seed_demo_accounts()
    created_count = len(summary["created"])
    skipped_count = len(summary["skipped"])
    failed_count = len(summary["failed"])
    print(f"  Seed run result: Created={created_count}, Skipped={skipped_count}, Failed={failed_count}")
    assert created_count == 0, f"Expected 0 created on second run, got {created_count}"
    assert skipped_count == 15, f"Expected 15 skipped on second run, got {skipped_count}"
    assert failed_count == 0, f"Expected 0 failed, got {failed_count}"
    print("  [PASS] TEST 1: Seed script is fully idempotent (0 created, 15 skipped, 0 duplicates).")

    # ---------------------------------------------------------
    # TEST 2: Log in using one account from each role
    # ---------------------------------------------------------
    print("\n[TEST 2] Logging in using one account from each of the 5 roles...")
    roles_to_test = ["SUPER_ADMIN", "ADMIN", "INSTITUTION_HEAD", "STAFF", "STUDENT"]
    tokens = {}
    async with httpx.AsyncClient(timeout=30.0) as client:
        for role in roles_to_test:
            acc = next(a for a in demo_accounts if a["role"].upper() == role)
            payload = {
                "identifier": acc["email"],
                "password": acc["password"],
            }
            res = await client.post(f"{BASE_URL}/api/v1/auth/login", json=payload)
            assert res.status_code == 200, f"Login failed for {role} ({acc['email']}): {res.status_code} {res.text}"
            data = res.json()
            access_token = data.get("token", {}).get("access_token") or data.get("session", {}).get("access_token")
            assert access_token is not None, f"No access token for {role}: {data}"
            tokens[role] = access_token
            print(f"  [OK] {role:<16} ({acc['email']}) logged in successfully -> Token received.")
    print("  [PASS] TEST 2: All 5 roles authenticated successfully.")

    # ---------------------------------------------------------
    # TEST 3: Confirm all 15 demo accounts exist and have correct roles in DB
    # ---------------------------------------------------------
    print("\n[TEST 3] Confirming all 15 demo accounts exist in database with correct roles...")
    async with session_maker() as session:
        result = await session.execute(text("""
            SELECT id, public_id, email, username, role, institution_id, first_name, last_name
            FROM users
            WHERE email LIKE 'demo.%@example.com'
            ORDER BY email
        """))
        rows = [dict(r._mapping) for r in result.fetchall()]
        print(f"  Found {len(rows)} demo accounts in database.")
        assert len(rows) == 15, f"Expected 15 accounts in DB, found {len(rows)}"
        
        role_counts = {}
        for r in rows:
            role = r["role"].upper()
            role_counts[role] = role_counts.get(role, 0) + 1
            print(f"  - {r['email']:<32} Role: {r['role']:<18} Inst: {r['institution_id']}")
        
        for expected_role in ["SUPER_ADMIN", "ADMIN", "INSTITUTION_HEAD", "STAFF", "STUDENT"]:
            count = role_counts.get(expected_role, 0)
            assert count == 3, f"Expected 3 of {expected_role}, got {count}"
    print("  [PASS] TEST 3: All 15 demo accounts exist with exactly 3 per role.")

    # ---------------------------------------------------------
    # TEST 4 & 5 & 6: Create new user with auto-generated temporary password
    # ---------------------------------------------------------
    print("\n[TEST 4, 5, 6] Creating new student without email -> verify temporary password generation & response...")
    head_token = tokens["INSTITUTION_HEAD"]
    headers = {"Authorization": f"Bearer {head_token}"}
    
    async with session_maker() as session:
        # Check all institutions
        all_insts = await session.execute(text("SELECT id, public_id, code, name, org_type FROM institutions"))
        for row in all_insts.fetchall():
            print(f"  Inst in DB: code={row.code}, name={row.name}, org_type={row.org_type}, id={row.id}, public_id={row.public_id}")

        # Ensure demo institution is org_type = 'institution'
        await session.execute(text("UPDATE institutions SET org_type = 'institution' WHERE code LIKE 'DEMO%' OR name LIKE '%Demo%'"))
        await session.commit()

        inst_res = await session.execute(text("""
            SELECT i.public_id, i.name, i.org_type 
            FROM institutions i
            WHERE i.org_type = 'institution'
            ORDER BY i.id
            LIMIT 1
        """))
        head_inst = inst_res.fetchone()
        org_id = head_inst.public_id
        print(f"  Using Institution with org_type='institution': {head_inst.name} ({org_id})")

        # Also ensure demo.head1 belongs to this institution
        await session.execute(text("""
            UPDATE users SET institution_id = (SELECT id FROM institutions WHERE public_id = :pid)
            WHERE email = 'demo.head1@example.com'
        """), {"pid": org_id})
        await session.commit()

        await session.execute(text("DELETE FROM users WHERE username = 'test.tempuser.01'"))
        await session.commit()

    # Refresh head token to include updated institution
    acc_head = next(a for a in demo_accounts if a["role"].upper() == "INSTITUTION_HEAD")
    async with httpx.AsyncClient(timeout=60.0) as client:
        res_login = await client.post(f"{BASE_URL}/api/v1/auth/login", json={
            "identifier": acc_head["email"],
            "password": acc_head["password"],
        })
        h_data = res_login.json()
        head_token = h_data.get("token", {}).get("access_token") or h_data.get("session", {}).get("access_token")
        headers = {"Authorization": f"Bearer {head_token}"}

    new_user_payload = {
        "role": "student",
        "organization_id": str(org_id),
        "account": {
            "username": "test.tempuser.01",
            "email": None,
            "generate_password": True
        },
        "personal_info": {
            "first_name": "Temporary",
            "last_name": "Student",
            "date_of_birth": "2002-05-15",
            "phone": "+919876543299"
        },
        "student": {
            "admission_number": "ADM/TEMP/001",
            "program": "B.Tech",
            "branch": "Computer Science"
        }
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.post(f"{BASE_URL}/api/v1/users", json=new_user_payload, headers=headers)
        assert res.status_code == 201, f"Failed to create user: {res.status_code} {res.text}"
        user_res = res.json()
        print("  User created successfully:")
        print(f"  User ID: {user_res['user']['user_id']}")
        print(f"  Full Name: {user_res['user']['personal_info']['full_name']}")
        print(f"  Credentials Delivery: {user_res['credentials']['delivery']}")
        print(f"  Generated Temporary Password: {user_res['credentials']['temporary_password']}")

        assert user_res["credentials"]["delivery"] == "temporary_password"
        assert user_res["credentials"]["temporary_password"] is not None
        assert len(user_res["credentials"]["temporary_password"]) >= 12
        generated_pwd = user_res["credentials"]["temporary_password"]
        print("  [PASS] TEST 4, 5, 6: User saved and backend generated temporary password successfully.")

        # ---------------------------------------------------------
        # TEST 7: Log in using the generated temporary password
        # ---------------------------------------------------------
        print("\n[TEST 7] Logging in using the newly generated temporary password...")
        await asyncio.sleep(2)
        login_res = await client.post(f"{BASE_URL}/api/v1/auth/login", json={
            "identifier": "test.tempuser.01",
            "password": generated_pwd,
        })
        assert login_res.status_code == 200, f"Login with temporary password failed: {login_res.status_code} {login_res.text}"
        login_data = login_res.json()
        user_info = login_data.get("user", {})
        print(f"  Login succeeded: Access token received. Must change password: {user_info.get('must_change_password')}")
        assert user_info.get("must_change_password") is True
        print("  [PASS] TEST 7: Temporary password successfully authenticated.")

        # ---------------------------------------------------------
        # TEST 8 & 9: Create user with email (invitation & console fallback)
        # ---------------------------------------------------------
        print("\n[TEST 8 & 9] Creating user with email -> verify invitation workflow & console mode fallback...")
        async with session_maker() as session:
            await session.execute(text("DELETE FROM users WHERE username = 'test.emailuser.01' OR email = 'test.emailuser.01@example.com'"))
            await session.commit()

        email_user_payload = {
            "role": "staff",
            "organization_id": str(org_id),
            "account": {
                "username": "test.emailuser.01",
                "email": "test.emailuser.01@example.com",
                "generate_password": False
            },
            "personal_info": {
                "first_name": "Email",
                "last_name": "Teacher",
                "phone": "+919876543288"
            },
            "employment": {
                "employee_code": "EMP-EMAIL-01",
                "department": "Physics"
            }
        }

        res_email = await client.post(f"{BASE_URL}/api/v1/users", json=email_user_payload, headers=headers)
        assert res_email.status_code == 201, f"Failed to create user with email: {res_email.status_code} {res_email.text}"
        email_user_res = res_email.json()
        creds = email_user_res["credentials"]
        print(f"  Delivery: {creds['delivery']}")
        print(f"  Email Sent: {creds['email_sent']}")
        print(f"  Setup Link: {creds['setup_link']}")
        print(f"  Message: {creds['message']}")

        assert creds["delivery"] == "email_link"
        assert creds["email_sent"] is False  # console email backend in local dev!
        assert creds["setup_link"] is not None and "/set-password?token=" in creds["setup_link"]
        assert "console" in creds["message"].lower() or "development" in creds["message"].lower()
        print("  [PASS] TEST 8 & 9: Email setup workflow handled correctly with console recovery link.")

    # ---------------------------------------------------------
    # TEST 10: Verify passwords are stored only as Argon2 hashes
    # ---------------------------------------------------------
    print("\n[TEST 10] Verifying passwords are stored ONLY as secure hashes...")
    async with session_maker() as session:
        p_res = await session.execute(text("SELECT email, username, password_hash FROM users WHERE password_hash IS NOT NULL"))
        all_creds = [dict(r._mapping) for r in p_res.fetchall()]
        for row in all_creds:
            phash = row["password_hash"]
            assert phash is not None, f"Null password hash for {row['username']}"
            # Passwords with active credentials are Argon2id; pending email invitations have unusable password prefix '!'
            assert phash.startswith("$argon2id$") or phash.startswith("!"), f"Password for {row['username']} is not a valid hash: {phash[:10]}..."
            assert "password" not in phash.lower()
            assert "temp" not in phash.lower()

        # Specifically verify all 15 demo accounts have Argon2id hashes
        demo_creds = [c for c in all_creds if c["email"] and c["email"].startswith("demo.")]
        assert len(demo_creds) == 15, f"Expected 15 demo accounts in DB, found {len(demo_creds)}"
        for dc in demo_creds:
            assert dc["password_hash"].startswith("$argon2id$"), f"Demo account {dc['email']} does not have argon2id hash"
    print(f"  Verified {len(all_creds)} stored passwords in database. All are secure hashes ($argon2id$ or unusable token).")
    print("  [PASS] TEST 10: No plaintext passwords exist in the database.")

    # ---------------------------------------------------------
    # TEST 11: Verify Role-Based Access Control
    # ---------------------------------------------------------
    print("\n[TEST 11] Verifying RBAC restrictions across roles...")
    student_token = tokens["STUDENT"]
    staff_token = tokens["STAFF"]
    head_token = tokens["INSTITUTION_HEAD"]
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. Student trying to access /api/v1/admins
        s_res = await client.get(f"{BASE_URL}/api/v1/admins", headers={"Authorization": f"Bearer {student_token}"})
        print(f"  Student accessing /admins: status = {s_res.status_code}")
        assert s_res.status_code == 403, f"Expected 403 for student accessing /admins, got {s_res.status_code}"

        # 2. Student trying to access /api/v1/users
        s_res2 = await client.get(f"{BASE_URL}/api/v1/users", headers={"Authorization": f"Bearer {student_token}"})
        print(f"  Student accessing /users: status = {s_res2.status_code}")
        assert s_res2.status_code == 403, f"Expected 403 for student accessing /users, got {s_res2.status_code}"

        # 3. Staff trying to access /api/v1/admins
        staff_res = await client.get(f"{BASE_URL}/api/v1/admins", headers={"Authorization": f"Bearer {staff_token}"})
        print(f"  Staff accessing /admins: status = {staff_res.status_code}")
        assert staff_res.status_code == 403, f"Expected 403 for staff accessing /admins, got {staff_res.status_code}"

        # 4. Institution isolation: Head 1 query users
        async with session_maker() as session:
            o_res = await session.execute(text("SELECT public_id, code FROM institutions ORDER BY id LIMIT 3"))
            i_rows = o_res.fetchall()
            org_id_1 = str(i_rows[0].public_id)
            org_id_2 = str(i_rows[1].public_id)
        
        head1_res = await client.get(
            f"{BASE_URL}/api/v1/users",
            params={"organization_id": org_id_2},
            headers={"Authorization": f"Bearer {head_token}"}
        )
        assert head1_res.status_code in [200, 403]
        if head1_res.status_code == 200:
            head_data = head1_res.json()
            items = head_data.get("items", [])
            for item in items:
                assert str(item.get("organization_id")) == org_id_1, "Head 1 leaked data from Inst 2!"
        print("  Institution Head tenant isolation confirmed.")
    print("  [PASS] TEST 11: Strict RBAC and tenant boundaries verified.")

    print("\n" + "=" * 70)
    print("ALL 11 VERIFICATION TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 70)

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
