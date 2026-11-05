-- Reset database to production clean slate
-- SAFETY GUARD (Finding S-08 / WS-11):
-- This script performs destructive TRUNCATE operations.
-- To execute, the operator must explicitly set the confirmation variable first:
--   SET app.confirm_production_reset = 'CONFIRM_DESTRUCTIVE_RESET_YES';

BEGIN;

DO $$
BEGIN
    IF current_setting('app.confirm_production_reset', true) IS DISTINCT FROM 'CONFIRM_DESTRUCTIVE_RESET_YES' THEN
        RAISE EXCEPTION 'CRITICAL SAFETY GUARD (S-08): reset_production.sql cannot be executed without explicit session confirmation. Run "SET app.confirm_production_reset = ''CONFIRM_DESTRUCTIVE_RESET_YES'';" prior to execution.';
    END IF;
END $$;

TRUNCATE TABLE devices CASCADE;
TRUNCATE TABLE fleet_devices CASCADE;
TRUNCATE TABLE fleet_incidents CASCADE;
TRUNCATE TABLE fleet_evidence CASCADE;
TRUNCATE TABLE fleet_usbs CASCADE;
TRUNCATE TABLE fleet_services CASCADE;
TRUNCATE TABLE fleet_processes CASCADE;
TRUNCATE TABLE fleet_networks CASCADE;
TRUNCATE TABLE fleet_printers CASCADE;
TRUNCATE TABLE incidents CASCADE;
TRUNCATE TABLE incident_feedback CASCADE;
TRUNCATE TABLE pending_remediations CASCADE;
TRUNCATE TABLE remote_sessions CASCADE;
TRUNCATE TABLE fleet_sites CASCADE;

COMMIT;
