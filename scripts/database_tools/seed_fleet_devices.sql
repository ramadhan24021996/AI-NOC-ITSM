TRUNCATE TABLE fleet_devices CASCADE;

INSERT INTO fleet_devices (pc_name, site_id, status, is_approved, hardware_info, rustdesk_id, rustdesk_running)
VALUES
  ('PC-Kasir-01', 'SITE-JATENG3', 'ONLINE', TRUE, '{"anydesk_id": "881290345", "rustdesk_id": "881290345", "os_version": "Windows 10 Pro"}', '881290345', TRUE),
  ('PC-Kasir-02', 'SITE-JATENG3', 'OFFLINE', TRUE, '{"anydesk_id": "881290346", "rustdesk_id": "881290346", "os_version": "Windows 10 Pro"}', '881290346', FALSE),
  ('PC-PKL-Kasir-01', 'SITE-PKL', 'ONLINE', TRUE, '{"anydesk_id": "334812093", "rustdesk_id": "334812093", "os_version": "Windows 11 Pro"}', '334812093', TRUE),
  ('PC-PKL-Kasir-02', 'SITE-PKL', 'ONLINE', TRUE, '{"anydesk_id": "334812094", "rustdesk_id": "334812094", "os_version": "Windows 11 Pro"}', '334812094', TRUE),
  ('PC-PML-01', 'SITE-PML', 'ONLINE', TRUE, '{"anydesk_id": "445812903", "rustdesk_id": "445812903", "os_version": "Windows 10 Enterprise"}', '445812903', TRUE),
  ('PC-PML-02', 'SITE-PML', 'OFFLINE', TRUE, '{"anydesk_id": "445812904", "rustdesk_id": "445812904", "os_version": "Windows 10 Enterprise"}', '445812904', FALSE),
  ('PC-IDM-01', 'SITE-IDM', 'ONLINE', TRUE, '{"anydesk_id": "556812903", "rustdesk_id": "556812903", "os_version": "Windows 10 Home"}', '556812903', TRUE),
  ('PC-IDM-02', 'SITE-IDM', 'ONLINE', TRUE, '{"anydesk_id": "556812904", "rustdesk_id": "556812904", "os_version": "Windows 10 Home"}', '556812904', TRUE),
  ('PC-Lab-01', 'SITE-LAB', 'ONLINE', TRUE, '{"anydesk_id": "999812903", "rustdesk_id": "999812903", "os_version": "Windows 11 Pro"}', '999812903', TRUE),
  ('PC-Cabang-01', 'SITE-CABANG', 'ONLINE', TRUE, '{"anydesk_id": "112812903", "rustdesk_id": "112812903", "os_version": "Windows 10 Pro"}', '112812903', TRUE),
  ('PC-Cabang-02', 'SITE-CABANG', 'OFFLINE', TRUE, '{"anydesk_id": "112812904", "rustdesk_id": "112812904", "os_version": "Windows 10 Pro"}', '112812904', FALSE);
