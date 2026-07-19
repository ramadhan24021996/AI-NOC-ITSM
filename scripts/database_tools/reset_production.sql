-- Reset database to production clean slate
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
