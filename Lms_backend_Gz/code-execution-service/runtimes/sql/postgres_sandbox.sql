-- Sandbox role and database for the PostgreSQL SQL dialect (app/engines/sql_postgres.py).
--
-- Run ONCE, as a superuser, on a DEDICATED cluster that holds no real data: a student's query runs here,
-- so nothing on this cluster may matter. Never point SQL_POSTGRES_DSN at the service's own database.
-- Replace CHANGE-ME, then set  SQL_POSTGRES_DSN=postgresql://lms_sandbox:<password>@<host>:5432/lms_sandbox
--
-- The engine adds the rest of the containment per run: one transaction that is always rolled back, and a
-- search_path of pg_temp, so everything a run creates is session-local and disappears with it.
--
-- Part 1: connected to the default database.

CREATE ROLE lms_sandbox LOGIN PASSWORD 'CHANGE-ME'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS
    CONNECTION LIMIT 200;

CREATE DATABASE lms_sandbox;
REVOKE ALL ON DATABASE lms_sandbox FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE lms_sandbox TO lms_sandbox;

-- Limits a session cannot raise for itself. The engine also sets statement_timeout per run from the problem's
-- time limit; this is the ceiling if that ever fails.
ALTER ROLE lms_sandbox SET statement_timeout = '15s';
ALTER ROLE lms_sandbox SET idle_in_transaction_session_timeout = '30s';
ALTER ROLE lms_sandbox SET temp_file_limit = '64MB';
ALTER ROLE lms_sandbox SET work_mem = '16MB';
ALTER ROLE lms_sandbox SET temp_buffers = '8MB';
ALTER ROLE lms_sandbox SET search_path = pg_temp;

-- @@ part 2: connected to the lms_sandbox database.

REVOKE ALL ON SCHEMA public FROM PUBLIC;
