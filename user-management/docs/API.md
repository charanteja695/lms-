# LMS User Management API

Authentication, users, admins, institutions, employers, permissions, audit log, bulk import, exports, background jobs and
events for the LMS. Base URL `https://<host>/api/v1` (local `http://localhost:8001/api/v1`). Interactive docs: `/docs`.
Machine-readable: [openapi.json](openapi.json) · Postman: [postman/lms-user-management.postman_collection.json](postman/lms-user-management.postman_collection.json)

---

## 1. Conventions

| Topic | Rule |
| --- | --- |
| Auth | `Authorization: Bearer <access_token>` |
| IDs | `user_id`, `organization_id` (institutions **and** employers), `session_id`, `job_id`, `audit_log_id`: 64-bit numbers sent **as strings**, e.g. `"358672738860850316"`. Internal database keys are never exposed. Malformed or unknown IDs return `404`. |
| Names | `snake_case` fields, lowercase enum values |
| Time | UTC ISO 8601 `2026-09-16T17:57:24Z`, fields named `*_time`; dates `YYYY-MM-DD` |
| Phones | Returned in E.164 `+919876543210`; input without `+` is read as `DEFAULT_COUNTRY_CODE` (IN) |
| Updates | `PUT` is partial: only sent fields change; `null` clears an optional value |
| Strictness | Unknown body fields and query parameters are rejected (`UNKNOWN_FIELD`) |
| Rules live here | Clients render from `allowed_actions`, `GET /users/me/permissions` and `GET /users/form-options`; they never re-implement rules. Every request is still checked. |
| Configuration | Every setting comes from the env file (`.env.example` lists all of them) |

### Response envelope

```json
{ "status": "success", "code": "SUCCESS", "message": "User retrieved successfully.", "user": { } }
```

Lists add `page_context`:

```json
"page_context": { "page": 1, "per_page": 20, "total_records": 57, "total_is_exact": true,
                  "total_pages": 3, "has_more_page": true, "sort_column": "created_time", "sort_order": "desc" }
```

Counts stop at 10,000 (`total_is_exact: false`), and `page x per_page` may not exceed 10,000: use export for more.

### Errors

```json
{
  "status": "error",
  "code": "INVALID_DATA",
  "message": "Some fields are missing or invalid.",
  "details": [ { "field": "personal_info.phone", "code": "INVALID_PHONE", "message": "Enter a valid phone number, e.g. +919876543210" } ],
  "request_id": "5f0c2b9ad4e84d6c9d1f3a7e2b8c4d10"
}
```

| HTTP | Codes |
| --- | --- |
| 400 | `INVALID_OTP`, `INVALID_RESET_TOKEN`, `INVALID_CURRENT_PASSWORD`, `INVALID_MFA_CODE`, `MFA_SETUP_NOT_STARTED`, `MFA_NOT_ENABLED`, `FILE_TOO_LARGE`, `INVALID_FILE_ENCODING`, `EMPTY_FILE`, `TOO_MANY_ROWS` |
| 401 | `NOT_AUTHENTICATED`, `INVALID_TOKEN`, `TOKEN_REVOKED`, `SESSION_REVOKED`, `INVALID_CREDENTIALS`, `ACCOUNT_LOCKED`, `INVALID_REFRESH_TOKEN`, `INVALID_MFA_TOKEN`, `INVALID_MFA_CODE` |
| 403 | `PERMISSION_DENIED`, `SELF_ACTION_NOT_ALLOWED`, `ACCOUNT_INACTIVE`, `INSTITUTION_INACTIVE`, `PASSWORD_CHANGE_REQUIRED`, `MFA_SETUP_REQUIRED`, `MFA_REQUIRED_FOR_ROLE` |
| 404 | `USER_NOT_FOUND`, `INSTITUTION_NOT_FOUND`, `EMPLOYER_NOT_FOUND`, `SESSION_NOT_FOUND`, `JOB_NOT_FOUND`, `URL_NOT_FOUND` |
| 409 | `DUPLICATE_DATA` (see `details`), `INSTITUTION_INACTIVE`, `ADMIN_HAS_INSTITUTIONS`, `ADMIN_OWNS_ORGANIZATIONS`, `MFA_ALREADY_ENABLED`, `JOB_NOT_READY`, `IMPORT_CONFLICT` |
| 422 | `INVALID_DATA`, `WEAK_PASSWORD`, `PASSWORD_REUSED`, `ROLE_CHANGE_NOT_ALLOWED`, `INVALID_COLUMNS`, `ORGANIZATION_TYPE_MISMATCH`, `ADMIN_SCOPE_REQUIRED` |
| 429 | `TOO_MANY_REQUESTS` (`Retry-After` header) |
| 500 | `INTERNAL_ERROR` (quote `request_id`) |

---

## 2. Roles, scopes and permissions

```
Super Admin (CLI only) ─ Admin ─┬─ Institution (organization_id) ─ Institution Head ─ Staff ─ Student
                                └─ Employer    (organization_id) ─ Employer Admin ─ Recruiter
```

| Actor | Can manage | Actions | Scope |
| --- | --- | --- | --- |
| Super admin | admin, head, staff, student, employer admin, recruiter | all | whole system |
| Admin | members of organisations they own | all | institutions (scope `accounts.manage`), employers (scope `careers.manage`) |
| Institution head | staff, student | all | own institution |
| Staff | student | view, create, update, set password, import | own institution |
| Employer admin | recruiter | all | own employer |
| Student, recruiter | – | – | own profile (`/users/me`) |

"All" = view, create, update, suspend/activate, delete, revoke, reset MFA, set password, import, export. Nobody acts on
their own account through management endpoints. Records outside the caller's scope return `404`.

**Admin scopes** (in access tokens as `scopes`, super admins hold all): `accounts.manage`, `careers.manage`,
`content.author`, `content.review`, `exams.manage`, `support.manage`, `ai.manage`, `analytics.view`, `billing.manage`. New admins get `accounts.manage`
unless `scopes` is sent. A scope that lets an admin own organisations cannot be removed while they own any
(`ADMIN_OWNS_ORGANIZATIONS`); changing scopes signs the admin out so new tokens carry them.

Every request checks, in order: token valid → not revoked → session live → user active → organisation active →
password changed → two-factor enrolled (if mandatory for the role) → role allowed → target in scope.

| Action | Can log in after? | Tokens | Record |
| --- | --- | --- | --- |
| Suspend | No | Ended now | Kept, reversible |
| Revoke | Yes | Ended now | Unchanged |
| Set password | Yes, must change it | Ended now | Temporary password |
| Delete | No | Ended now | Hidden; email/username reusable; employee codes and admission numbers never reused |

### What the client shows comes from the server

| Endpoint / field | Use it for |
| --- | --- |
| `allowed_actions` on every user, admin, institution and employer | Which buttons and menu items to show for that record: `update`, `suspend`, `activate`, `revoke_sessions`, `reset_mfa`, `set_password`, `delete` (users); `update`, `suspend`, `activate`, `revoke_sessions`, `delete`, `add_member`, `view_members` (organisations) |
| `GET /users/me/permissions` | Menu `sections`, `organization_type`, `scopes`, viewable/creatable roles, import/export rights, list filter options, admin scopes you can assign |
| `GET /users/form-options?role=staff` (`&user_id=` when editing) | Roles to offer (when only one is returned, use it), whether the organisation/manager/scopes/employment/student sections show, required fields, whether email is optional, default scopes and values |

```json
GET /users/me/permissions   (institution head)
{
  "status": "success", "code": "SUCCESS", "message": "Permissions retrieved successfully.",
  "permissions": {
    "role": "institution_head", "organization_type": "institution", "scopes": [],
    "sections": ["dashboard", "my_organization", "users", "downloads", "audit_logs", "profile", "security"],
    "users": { "view_roles": ["staff", "student"], "create_roles": ["staff", "student"], "can_import": true, "can_export": true,
               "filter_statuses": ["active", "suspended"], "filter_by_institution": false },
    "admins": { "view": false, "create": false },
    "institutions": { "create": false, "filter_statuses": ["active", "suspended"], "filter_by_admin": false, "reassign_admin": false },
    "employers": { "create": false, "filter_statuses": ["active", "suspended"], "filter_by_admin": false, "reassign_admin": false },
    "admin_scopes": [], "audit_logs": { "view": true }
  }
}
```

```json
GET /users/form-options?role=student   (institution head)
{
  "form_options": {
    "roles": ["staff", "student"], "role_editable": true,
    "organization": { "shown": true, "type": "institution", "required": true, "selectable": false, "fixed": true },
    "scopes": { "shown": false, "options": ["accounts.manage", "careers.manage", "..."], "default": ["accounts.manage"] },
    "manager": { "shown": true, "role": "staff", "defaults_to_you": false },
    "sections": { "address": true, "employment": false, "student": true, "guardians": true },
    "guardians": { "max": 4, "required_below_age": 18 },
    "initial_password": { "allowed": true, "min_length": 12, "generated_without_email": true },
    "email_optional": true,
    "required_fields": ["role", "personal_info.first_name", "personal_info.last_name", "personal_info.date_of_birth", "student.admission_number", "organization_id"],
    "defaults": { "language": "en", "timezone": "Asia/Kolkata", "country": "IN" }
  }
}
```

---

## 3. Data collected and validation

| Section | Field | Required | Rules |
| --- | --- | --- | --- |
| account | `email` | everyone except students | valid, ≤254, lower-cased, unique |
| | `username` | no | 3–30, starts with a letter, `a-z 0-9 . _ -`, reserved names refused; generated from the name if omitted |
| | `password` | no | 12–128, upper/lower/digit/symbol, not containing name/email. Omit to email a set-up link (recommended); students without email get a generated temporary password |
| — | `scopes` | admins only | list of admin scopes (§2) |
| personal_info | `first_name`, `last_name` | yes | 1–50, letters of any script, space `' - .` |
| | `middle_name`, `gender` | no | gender: `male`, `female`, `other`, `prefer_not_to_say` |
| | `date_of_birth` | students | not future, age ≤120 |
| | `phone` | admin, head, staff, employer admin, recruiter | valid, stored E.164 |
| | `alternate_phone`, `preferred_language`, `timezone` | no | phone ≠ `phone`; `en`, `te`, `en-IN`; IANA zone |
| address | `line1`, `city`, `state`, `postal_code`, `country` (+ `line2`) | if sent | PIN 6 digits for IN, ZIP for US; ISO country |
| employment | `employee_code` | head, staff | `A-Z 0-9 - _ /`, unique per organisation |
| | `designation`, `department`, `employment_type`, `date_of_joining` | no | type: `full_time`, `part_time`, `contract`, `visiting`, `intern` |
| student | `admission_number` | students | unique per institution |
| | `admission_date` | no | not future |
| | `program`, `branch`, `section` | no | ≤100 / ≤100 / ≤20, e.g. `B.Tech`, `Computer Science`, `A` |
| | `year_of_study` | no | 1–10 |
| | `graduation_year` | no | 1950–2100 |
| | `cgpa` | no | 0–10, two decimals (string or number) |
| | `guardians[]` | under 18 | 1–4; `full_name`, `relationship` (`father`, `mother`, `legal_guardian`, `grandparent`, `sibling`, `other`), `phone` required; one primary (a single guardian is primary automatically) |

Role rules: admins have no `organization_id` and no `student`; institution members need an institution, employer members
need an employer (`ORGANIZATION_TYPE_MISMATCH`); heads/staff need `phone` and `employee_code`, age ≥18; students need
`date_of_birth`, `admission_number`, age ≥3, and a guardian under 18. All problems are reported together.
Updates never add a new problem, but existing gaps in older records do not block unrelated edits.

---

## 4. Authentication

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| POST | `/auth/login` | – | Email or username + password |
| POST | `/auth/mfa/verify` | – | Second step when `code` is `MFA_REQUIRED` |
| POST | `/auth/refresh-token` | – | New access + refresh token (refresh tokens are single-use) |
| POST | `/auth/logout` | bearer | `{ "all_sessions": true }` for every device |
| GET | `/auth/sessions` | bearer | My devices |
| DELETE | `/auth/sessions/{session_id}` | bearer | Log out one device |
| POST | `/auth/forgot-password` | – | Emails a 6-digit code and link; always `202`. Accounts without email: ask a manager to set a temporary password |
| POST | `/auth/verify-otp` | – | Code → 15-minute `reset_token` |
| POST | `/auth/reset-password` | – | `reset_token` (or link token) + `new_password` + `confirm_password`; also completes account set-up |
| POST | `/auth/change-password` | bearer | `current_password`, `new_password`, `confirm_password`; ends all sessions |
| GET | `/auth/mfa` | bearer | Two-factor status |
| POST | `/auth/mfa/setup` | bearer | `{ "password" }` → `secret` + `otpauth_uri` (show as QR) |
| POST | `/auth/mfa/enable` | bearer | `{ "code" }` → 10 recovery codes (shown once) |
| POST | `/auth/mfa/disable` | bearer | `{ "password", "code" }`; refused if mandatory for the role |
| POST | `/auth/mfa/recovery-codes` | bearer | `{ "password", "code" }` → new codes |

### Login

```json
{ "identifier": "platform.owner", "password": "Str0ng!Passphrase#1" }
```

```json
{
  "status": "success", "code": "SUCCESS", "message": "Logged in successfully.",
  "token": { "access_token": "eyJ...", "refresh_token": "zJb...", "token_type": "Bearer", "expires_in": 900, "refresh_expires_in": 604800 },
  "user": {
    "user_id": "358672737539181121", "full_name": "Platform Owner", "email": "owner@example.com",
    "username": "platform.owner", "role": "super_admin", "institution": null, "scopes": ["accounts.manage", "careers.manage", "..."],
    "must_change_password": false, "mfa_enabled": false, "mfa_setup_required": false
  },
  "mfa_challenge": null
}
```

With two-factor authentication on, the same call returns `code: "MFA_REQUIRED"`, `token: null`, `user: null` and
`"mfa_challenge": { "mfa_token": "...", "expires_in": 300, "methods": ["totp", "recovery_code"] }`. Then:

```json
POST /auth/mfa/verify
{ "mfa_token": "...", "code": "492817" }        // or { "mfa_token": "...", "recovery_code": "k7m2p-9xq4r" }
```

returns the normal login body. Challenges allow 5 attempts in 5 minutes; a code or recovery code works once.
If `user.must_change_password` or `user.mfa_setup_required` is `true`, only `/users/me`, `/auth/logout`,
`/auth/sessions`, `/auth/change-password` and `/auth/mfa/*` work until that step is done.

### Browser sessions (httpOnly cookie)

Browsers send `X-Session-Transport: cookie` on login, `/auth/mfa/verify`, `/auth/refresh-token`, logout and
change-password. The refresh token is then set as an `httpOnly`, `SameSite=Strict`, `Secure` cookie scoped to
`/api/v1/auth`, and `token.refresh_token` in the body is `null`. Refresh with **no body** and the same header. The header
is required for the cookie to be read (CSRF protection). Mobile apps and services keep using the body.

### Tokens for other services

Access token claims: `sub`=`user_id`, `sid`=`session_id`, `role`, `org`=`organization_id`, `org_type`
(`institution`/`employer`), `scopes`, `ver`, `iss`, `aud`, `iat`, `exp`, `kid` header. Verify with
`GET /.well-known/jwks.json` (RS256, required outside local/test). During key rotation both the current and the
previous key are published.

Revocations reach other services within seconds through Redis (prefix `ACCESS_STATE_KEY_PREFIX`, default `lms:access`):

| Key | Reject the token when |
| --- | --- |
| `lms:access:session:{sid}` | the key exists (that device signed out) |
| `lms:access:user:{sub}` | `ver` < stored value (suspended, deleted, password changed, role/scopes changed, signed out everywhere) |
| `lms:access:org:{org}` | `iat` ≤ stored unix time (organisation suspended, deleted or signed out) |

Keys expire after the longest access-token lifetime. Reference implementation: `app/core/access_state.py`.

---

## 5. Users

| Method | Path | Purpose |
| --- | --- | --- |
| GET / PUT | `/users/me` | My profile; self-service phone, language, time zone, address |
| GET | `/users/me/permissions` | What I can do (§2) |
| GET | `/users/form-options` | Create/edit form description (§2) |
| POST | `/users` | Create |
| GET | `/users` | List with filters |
| GET | `/users/export` | Stream CSV now (up to 500,000 rows) |
| POST | `/users/export-jobs` | Queue a background export; email when ready |
| GET | `/users/import/template` | CSV template |
| POST | `/users/import` | Bulk import now (multipart, up to 5,000 rows) |
| POST | `/users/import-jobs` | Bulk import in the background (up to 50,000 rows) |
| GET / PUT / DELETE | `/users/{user_id}` | Get, partial update, soft delete |
| PATCH | `/users/{user_id}/status` | `{ "status": "active" \| "suspended", "reason": "..." }` |
| POST | `/users/{user_id}/password` | `{ "new_password" }`: temporary password, must change at next sign-in, all sessions end |
| POST | `/users/{user_id}/revoke` | Sign out everywhere |
| POST | `/users/{user_id}/mfa/reset` | Lost phone: clear two-factor enrolment and sign out |

### Create (student)

```json
{
  "role": "student",
  "organization_id": "358672738414054064",
  "account": { "email": "aarav.reddy@example.com" },
  "personal_info": { "first_name": "Aarav", "last_name": "Reddy", "gender": "male", "date_of_birth": "2012-04-15" },
  "address": { "line1": "Plot 42, Road No. 5", "line2": "Jubilee Hills", "city": "Hyderabad", "state": "Telangana", "postal_code": "500033", "country": "IN" },
  "student": {
    "admission_number": "ADM/2024/0457", "admission_date": "2024-06-01",
    "program": "Class 8", "section": "B", "year_of_study": 8, "graduation_year": 2029,
    "guardians": [ { "full_name": "Suresh Reddy", "relationship": "father", "phone": "+919876543210", "email": "suresh.reddy@example.com", "occupation": "Engineer" } ]
  }
}
```

A staff member sends `employment` (with `employee_code`) instead of `student`; members may omit `organization_id`.
A student may be created **without** `account.email`: sign-in is by username.

`201` (GET, PUT and PATCH status return the same `user` without `credentials`):

```json
{
  "status": "success", "code": "SUCCESS", "message": "User created successfully.",
  "user": {
    "user_id": "358672738860850316", "role": "student", "status": "active", "status_reason": null,
    "account": { "email": "aarav.reddy@example.com", "username": "aarav.reddy", "email_verified": false, "must_change_password": true, "last_login_time": null, "password_changed_time": "2026-09-16T17:57:24Z" },
    "personal_info": { "first_name": "Aarav", "middle_name": null, "last_name": "Reddy", "full_name": "Aarav Reddy", "gender": "male", "date_of_birth": "2012-04-15", "phone": null, "alternate_phone": null, "preferred_language": "en", "timezone": "Asia/Kolkata" },
    "address": { "line1": "Plot 42, Road No. 5", "line2": "Jubilee Hills", "city": "Hyderabad", "state": "Telangana", "postal_code": "500033", "country": "IN" },
    "employment": null,
    "student": { "admission_number": "ADM/2024/0457", "admission_date": "2024-06-01", "program": "Class 8", "branch": null, "year_of_study": 8, "section": "B", "graduation_year": 2029, "cgpa": null,
                 "guardians": [ { "full_name": "Suresh Reddy", "relationship": "father", "phone": "+919876543210", "email": "suresh.reddy@example.com", "occupation": "Engineer", "is_primary": true } ] },
    "institution": { "organization_id": "358672738414054064", "name": "Springfield High School", "code": "SPH-HYD", "organization_type": "institution" },
    "manager": { "user_id": "358672738684233908", "full_name": "Priya Sharma", "role": "staff", "email": "priya.sharma@example.com" },
    "created_by": { "user_id": "358672738684233908", "full_name": "Priya Sharma", "role": "staff", "email": "priya.sharma@example.com" },
    "scopes": [],
    "created_time": "2026-09-16T17:57:24Z", "modified_time": "2026-09-16T17:57:24Z", "deleted_time": null,
    "allowed_actions": ["update", "set_password"]
  },
  "credentials": { "delivery": "email_link", "temporary_password": null }
}
```

`credentials.delivery`: `email_link` (set-up link emailed), `initial_password` (the password you sent) or
`temporary_password` (student without email: `temporary_password` is returned **only in this response**; share it securely).

### List filters (also used by `/users/export` and `/users/export-jobs`)

| Parameter | Example | Notes |
| --- | --- | --- |
| `page`, `per_page` | `1`, `20` | `per_page` ≤ 100 (lists only) |
| `search_text` | `reddy` | ≥2 chars: name, email, username, phone, employee code, admission number |
| `role`, `status` | `student`, `active` | `status=deleted` for super admins |
| `organization_id`, `manager_user_id`, `created_by_user_id` | ids | |
| `gender`, `department`, `employment_type`, `email_verified` | `female`, `Mathematics`, `full_time`, `true` | |
| `program`, `branch`, `section`, `year_of_study`, `graduation_year` | `B.Tech`, `computer science`, `A`, `3`, `2027` | students; text is exact and case-insensitive |
| `created_from`, `created_to` | `2026-06-01` | inclusive UTC dates |
| `sort_column`, `sort_order` | `first_name`, `asc` | `created_time`, `first_name`, `last_name`, `email`, `last_login_time` |

List items: `user_id, role, status, full_name, email, username, phone, employee_code, admission_number, branch,
year_of_study, section, graduation_year, institution, last_login_time, created_time, allowed_actions`.

### Update

```json
PUT /users/358672738860850316
{ "personal_info": { "phone": "+919812300000" }, "employment": { "designation": "Senior Mathematics Teacher" } }
```

Sections: `account` (students may clear `email` with `null`), `personal_info`, `address` (whole, or `null`), `employment`,
`student` (academic fields individually; `guardians` replaces the list), plus `organization_id`, `manager_user_id`,
`role` (only `institution_head` ↔ `staff`) and `scopes` (admins). Role, organisation or scope changes sign the user out.

### Export

`GET /users/export?role=student` streams `users-YYYYMMDD-HHMMSS.csv` (UTF-8 with BOM, formula-safe) with columns:
`user_id, role, status, first_name, middle_name, last_name, email, email_verified, username, phone, alternate_phone, gender,
date_of_birth, preferred_language, timezone, address_line1, address_line2, city, state, postal_code, country, organization_id,
institution_name, institution_code, manager_user_id, manager_name, employee_code, designation, department, employment_type,
date_of_joining, admission_number, admission_date, program, branch, year_of_study, section, graduation_year, cgpa,
primary_guardian_name, primary_guardian_relationship, primary_guardian_phone, created_by_user_id, last_login_time,
created_time, modified_time`.

For very large exports use `POST /users/export-jobs?role=student` → `202` with a `job` (see §10).

### Bulk import

1. `GET /users/import/template` → CSV with columns
   `role, organization_id, manager_user_id, email, username, first_name, middle_name, last_name, gender, date_of_birth, phone,
   alternate_phone, preferred_language, timezone, address_line1, address_line2, city, state, postal_code, country, employee_code,
   designation, department, employment_type, date_of_joining, admission_number, admission_date, program, branch, year_of_study,
   section, graduation_year, cgpa, guardian_name, guardian_relationship, guardian_phone, guardian_email, guardian_occupation`
   (required columns: `role, email, first_name, last_name`; `email` may be blank for students).
2. `POST /users/import` (multipart): `file`, `dry_run` (`true` to validate only), `mode` (`all_or_nothing` default, or `skip_invalid`).
   Up to 5,000 rows / 5 MB. No passwords in files: imported users get an account set-up email, or (students without email)
   a temporary password returned in `created_users[].temporary_password`.
3. Larger files: `POST /users/import-jobs` with the same form fields → `202` with a `job` of type `user_import`
   (up to 50,000 rows / 50 MB). When it completes, `job.import_summary` holds the counts and the download is a report with
   one line per created user and per problem: `row, result, user_id, username, email, temporary_password, column, code, message`.

```json
{
  "status": "success", "code": "SUCCESS", "message": "Import finished: 2 created, 1 failed.",
  "import_result": {
    "dry_run": false, "mode": "skip_invalid", "total_rows": 3, "valid_rows": 2, "invalid_rows": 1, "created": 2,
    "created_users": [ { "row": 2, "user_id": "358672738860850316", "email": null, "username": "bulk.kid", "temporary_password": "Kp7m-X3qd-9Hwt" } ],
    "errors": [ { "row": 4, "column": "guardian_phone", "code": "INVALID_PHONE", "message": "Enter a valid phone number, e.g. +919876543210" } ]
  }
}
```

Rows are checked with exactly the rules of `POST /users`, plus `DUPLICATE_IN_FILE` for repeated emails, usernames,
employee codes and admission numbers.

---

## 6. Admins (super admin only)

| Method | Path | Purpose |
| --- | --- | --- |
| POST / GET | `/admins` | Create (`scopes`, `account`, `personal_info`, `address`, `employment`; the response carries `credentials` like `POST /users`) / list (`search_text`, `status`, `scope`, `email_verified`, dates, sort) |
| GET | `/admins/export` · POST `/admins/export-jobs` | CSV now / background |
| GET / PUT / DELETE | `/admins/{user_id}` | `PUT { "scopes": [...] }` replaces scopes. Delete refused with `ADMIN_HAS_INSTITUTIONS` while they own organisations |
| PATCH | `/admins/{user_id}/status` | Activate / suspend |
| POST | `/admins/{user_id}/revoke` · `/admins/{user_id}/mfa/reset` | Sign out · reset two-factor |

Admin objects are user objects plus `institution_count` and `employer_count` (list items also carry `scopes`).

---

## 7. Institutions

| Method | Path | Who |
| --- | --- | --- |
| POST | `/institutions` | super admin (sets `admin_user_id`, an admin with `accounts.manage`), admin with `accounts.manage` (owns it) |
| GET | `/institutions` · `/institutions/export` · POST `/institutions/export-jobs` | everyone, scoped |
| GET | `/institutions/{organization_id}` | everyone, scoped |
| PUT | `/institutions/{organization_id}` | super admin, owning admin (only super admin changes `admin_user_id`) |
| PATCH | `/institutions/{organization_id}/status` | suspending blocks every member |
| DELETE | `/institutions/{organization_id}` | soft delete; members lose access |
| POST | `/institutions/{organization_id}/revoke` | sign out every member |

```json
POST /institutions
{
  "name": "Springfield High School", "code": "SPH-HYD", "type": "school", "admin_user_id": "358672738043308256",
  "contact": { "email": "office@springfieldhigh.edu.in", "phone": "+914023456789", "website": "https://www.springfieldhigh.edu.in" },
  "address": { "line1": "Plot 42, Road No. 5", "line2": "Jubilee Hills", "city": "Hyderabad", "state": "Telangana", "postal_code": "500033", "country": "IN" },
  "timezone": "Asia/Kolkata", "registration_number": "TS-SCH-2004-1187", "affiliation": "CBSE", "established_year": 2004
}
```

Response `institution`: `organization_id, name, code, type, status, status_reason, contact, address, timezone,
registration_number, affiliation, established_year, admin, member_counts {institution_heads, staff, students, total},
created_by, created_time, modified_time, deleted_time, allowed_actions`.

Filters: `search_text` (name, code, city), `status`, `type` (`school`, `college`, `university`, `coaching_center`,
`training_institute`, `other`), `admin_user_id`, `country`, `state`, `city`, `affiliation`, `created_from`, `created_to`,
`sort_column` (`created_time`, `name`, `code`), `sort_order`.

---

## 8. Employers

Hiring companies for the job portal. They share `organization_id` with institutions but are separate records: an
institution id never works under `/employers` and the reverse.

| Method | Path | Who |
| --- | --- | --- |
| POST | `/employers` | super admin (sets `admin_user_id`, an admin with `careers.manage`), admin with `careers.manage` (owns it) |
| GET | `/employers` · `/employers/export` · POST `/employers/export-jobs` | everyone, scoped |
| GET / PUT / DELETE | `/employers/{organization_id}` | as institutions |
| PATCH | `/employers/{organization_id}/status` | suspending blocks every employer admin and recruiter |
| POST | `/employers/{organization_id}/revoke` | sign out every member |

```json
POST /employers
{
  "name": "Acme Technologies Pvt Ltd", "code": "ACME-HYD", "industry": "Information Technology",
  "contact": { "email": "talent@acme.example", "phone": "+914045678901", "website": "https://acme.example" },
  "address": { "line1": "Tower B, Hitec City", "city": "Hyderabad", "state": "Telangana", "postal_code": "500081", "country": "IN" },
  "registration_number": "U72900TG2015PTC098765", "established_year": 2015
}
```

Response `employer`: `organization_id, name, code, industry, status, status_reason, contact, address, timezone,
registration_number, established_year, admin, member_counts {employer_admins, recruiters, total}, created_by,
created_time, modified_time, deleted_time, allowed_actions`. Filters: `search_text`, `status`, `industry`,
`admin_user_id`, `country`, `state`, `city`, dates, `sort_column`, `sort_order`.

Members are created with `POST /users` using `role: "employer_admin"` (by the owning admin) or `role: "recruiter"`
(by the employer admin, who becomes the default manager).

---

## 9. Audit log

`GET /audit-logs`: who did what and when, newest first. Super admins see everything, admins see their organisations
and their own actions, institution heads and employer admins see their organisation.

| Parameter | Example |
| --- | --- |
| `category` | `auth`, `user`, `institution`, `employer`, `job` |
| `action` | `user.status_changed` |
| `user_id` | one person's history (as actor or subject) |
| `actor_user_id`, `organization_id` | ids |
| `created_from`, `created_to`, `page`, `per_page`, `sort_order` | |

```json
{
  "audit_log_id": "359031755840136992", "time": "2026-09-17T17:44:01Z",
  "action": "user.status_changed", "category": "user",
  "actor": { "user_id": "358672738684233900", "full_name": "Head One", "role": "institution_head", "email": "head1@example.com" },
  "target": { "type": "user", "id": "358672738860850316", "name": "Aarav Reddy" },
  "institution": { "organization_id": "358672738414054064", "name": "Springfield High School", "code": "SPH-HYD", "organization_type": "institution" },
  "ip_address": "10.0.0.12", "user_agent": "Mozilla/5.0 ...", "request_id": "5f0c2b9ad4e84d6c9d1f3a7e2b8c4d10",
  "details": { "from": "active", "to": "suspended", "reason": "Fee dues" }
}
```

---

## 10. Background jobs

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/jobs` | My jobs (exports and imports), newest first |
| GET | `/jobs/{job_id}` | Status |
| GET | `/jobs/{job_id}/download` | Export CSV or import report (requester only, until `expires_time`) |

```json
{
  "status": "success", "code": "SUCCESS", "message": "Job retrieved successfully.",
  "job": {
    "job_id": "358690112233445566", "type": "user_import", "status": "completed", "row_count": 48210,
    "file_name": "user-import-report-358690112233445566.csv", "file_size_bytes": 1284031, "error_message": null,
    "download_url": "/api/v1/jobs/358690112233445566/download",
    "import_summary": { "dry_run": false, "mode": "skip_invalid", "total_rows": 48210, "valid_rows": 48190, "invalid_rows": 20, "created": 48190 },
    "created_time": "2026-09-17T10:14:58Z", "started_time": "2026-09-17T10:15:00Z",
    "finished_time": "2026-09-17T10:21:29Z", "expires_time": "2026-09-20T10:21:29Z"
  }
}
```

Types: `user_export`, `admin_export`, `institution_export`, `employer_export`, `user_import`. Statuses: `queued` →
`running` → `completed` (or `failed`), then `expired` after 72 hours. Permissions are checked again when the job runs.
Imports never retry automatically (a second run could repeat writes); `error_message` explains a failure.

---

## 11. Events for other microservices

Every change writes an event in the same transaction; the worker publishes it to the Redis Stream `lms:events`.

| Field | Example |
| --- | --- |
| `event_id` | `01a0ab52aedc73ad9239a1ab16cf4c43` (use to de-duplicate: delivery is at-least-once) |
| `event_type` | `user.created`, `user.updated`, `user.suspended`, `user.activated`, `user.deleted`, `user.access_revoked`, `institution.*` and `employer.*` (`created`, `updated`, `suspended`, `activated`, `deleted`, `access_revoked`), `access.session_revoked`, `access.user_revoked`, `access.organization_revoked` |
| `aggregate_type` | `user` / `institution` / `session` |
| `occurred_time` | `2026-09-17T10:15:29Z` |
| `payload` | JSON, public ids only, e.g. `{"user_id":"...","role":"student","status":"active","organization_id":"..."}`; organisation events include `organization_type` |

Consume with `XGROUP CREATE lms:events <service> $ MKSTREAM` and `XREADGROUP GROUP <service> <consumer> STREAMS lms:events >`.
The `access.*` events are also applied to the Redis access-state keys (§4) by the worker.

---

## 12. Operations, performance and security

| Item | Value |
| --- | --- |
| Processes | API (`uvicorn app.main:app`) and worker (`python -m app.worker`), both stateless and horizontally scalable |
| Configuration | Env files only: `.env.example` (local) and `.env.docker.example` (compose), generated from `app/core/config.py` |
| Housekeeping | The worker runs it hourly: expired files, sessions, tokens, reset requests, MFA challenges, old events |
| Measured latency (1,000,000 users, 10,000 institutions) | reads 7–45 ms, super admin list of all users 18 ms, update 21 ms, login 68–200 ms (deliberate Argon2id cost) |
| Passwords | Argon2id, lockout after 5 failures, identical responses for unknown accounts |
| Tokens | 15-min RS256 JWT with key rotation, single-use rotating refresh tokens with reuse detection, httpOnly cookie for browsers, revocation shared with every service in seconds |
| Two-factor | TOTP with replay protection, encrypted secrets, hashed recovery codes; mandatory for `MFA_REQUIRED_ROLES` |
| Data | internal keys never exposed; exports scoped, audited and formula-safe; every change audited and queryable |
