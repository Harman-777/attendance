-- ====================================================================
-- ULTRA PORTAL — SUPABASE ROW LEVEL SECURITY (RLS) HARDENING SCRIPT
-- ====================================================================
-- This script hardens all database tables used by db_client.py and sync_worker.py:
--   1. portal_users  (User credentials, encrypted vault, profile snapshots)
--   2. login_logs    (Security audit trails, IP addresses, browser agents)
--   3. app_feedback  (Student feedback tickets, admin announcements, developer replies)
--
-- Instructions: Run this script inside the Supabase SQL Editor for your project.
-- ====================================================================

-- --------------------------------------------------------------------
-- 1. ENABLE ROW LEVEL SECURITY (RLS) ACROSS ALL TABLES
-- --------------------------------------------------------------------
ALTER TABLE IF EXISTS portal_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS login_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS app_feedback ENABLE ROW LEVEL SECURITY;

-- --------------------------------------------------------------------
-- 2. SERVICE_ROLE FULL PRIVILEGES (Backend Flask API & Sync Worker)
-- --------------------------------------------------------------------
-- The service_role key is used server-side in db_client.py and sync_worker.py.
-- These explicit policies guarantee unhindered serverless read/write operations.

DROP POLICY IF EXISTS "Service role full access on portal_users" ON portal_users;
CREATE POLICY "Service role full access on portal_users"
    ON portal_users
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

DROP POLICY IF EXISTS "Service role full access on login_logs" ON login_logs;
CREATE POLICY "Service role full access on login_logs"
    ON login_logs
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

DROP POLICY IF EXISTS "Service role full access on app_feedback" ON app_feedback;
CREATE POLICY "Service role full access on app_feedback"
    ON app_feedback
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- --------------------------------------------------------------------
-- 3. RESTRICT PUBLIC (ANON) ROLE ACCESS
-- --------------------------------------------------------------------
-- By default, public / anon HTTP clients without backend authentication
-- should NOT be permitted to read raw encrypted vault passwords or tamper
-- with logs and admin announcements.

-- Disallow public anon SELECT / UPDATE / DELETE on portal_users
DROP POLICY IF EXISTS "Deny anon access on portal_users" ON portal_users;
-- (With RLS enabled and no anon policies granted, anon requests are denied by default)

-- Disallow public anon access on login_logs
DROP POLICY IF EXISTS "Deny anon access on login_logs" ON login_logs;
-- (With RLS enabled and no anon policies granted, anon requests are denied by default)

-- Optional: Allow anon to insert feedback if submitted through direct client (if desired),
-- otherwise all feedback routing is strictly brokered by Flask API backend.
REVOKE ALL ON portal_users FROM anon;
REVOKE ALL ON login_logs FROM anon;
REVOKE ALL ON app_feedback FROM anon;

-- Grant required permissions to service_role and postgres
GRANT ALL ON portal_users TO service_role, postgres;
GRANT ALL ON login_logs TO service_role, postgres;
GRANT ALL ON app_feedback TO service_role, postgres;

-- Verification Query: Check that RLS is active on all 3 tables
SELECT 
    schemaname,
    tablename,
    rowsecurity AS rls_enabled
FROM pg_tables 
WHERE tablename IN ('portal_users', 'login_logs', 'app_feedback');
