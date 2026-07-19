-- ============================================================
-- 1. Drop the FK constraint on fleet_devices.site_id
--    so devices can exist WITHOUT a site assignment
-- ============================================================
ALTER TABLE fleet_devices DROP CONSTRAINT IF EXISTS fleet_devices_site_id_fkey;
ALTER TABLE fleet_usbs     DROP CONSTRAINT IF EXISTS fleet_usbs_site_id_fkey;
ALTER TABLE cmdb_assets    DROP CONSTRAINT IF EXISTS cmdb_assets_site_id_fkey;
ALTER TABLE health_scores  DROP CONSTRAINT IF EXISTS health_scores_site_id_fkey;
ALTER TABLE fleet_incidents DROP CONSTRAINT IF EXISTS fleet_incidents_site_id_fkey;

-- ============================================================
-- 2. Remove all SITE-* rows from fleet_sites
-- ============================================================
DELETE FROM fleet_sites WHERE site_id IN (
  'SITE-JATENG3','SITE-PKL','SITE-PML','SITE-IDM','SITE-LAB','SITE-CABANG'
);

-- ============================================================
-- 3. Clear fleet_devices (safe: FK removed above)
-- ============================================================
TRUNCATE TABLE fleet_devices CASCADE;

-- ============================================================
-- 4. Re-seed devices table (safe upsert - no site FK needed)
-- ============================================================
INSERT INTO devices (name, ip, layer, location, status, metadata)
VALUES
  ('Switch-Core-01',   '192.168.1.1',   1, 'Jateng 3',      'ONLINE',  '{"model":"Catalyst C2960","vendor":"Cisco","type":"switch"}'),
  ('Router-Jateng3',   '192.168.1.254', 1, 'Jateng 3',      'ONLINE',  '{"model":"MikroTik RB4011","vendor":"MikroTik","type":"router"}'),
  ('PC-Kasir-01',      '192.168.1.10',  1, 'Jateng 3',      'ONLINE',  '{"model":"Windows PC","vendor":"HP","type":"workstation","hostname":"KASIR-01"}'),
  ('PC-Kasir-02',      '192.168.1.11',  1, 'Jateng 3',      'OFFLINE', '{"model":"Windows PC","vendor":"HP","type":"workstation","hostname":"KASIR-02"}'),
  ('Printer-Sales-01', '192.168.1.20',  2, 'Jateng 3',      'ONLINE',  '{"model":"Epson TM-T82X","vendor":"Epson","type":"printer"}'),
  ('Switch-PKL-01',    '192.168.4.1',   1, 'PKL',           'ONLINE',  '{"model":"TP-Link TL-SG108","vendor":"TP-Link","type":"switch"}'),
  ('PC-PKL-Kasir-01',  '192.168.4.10',  1, 'PKL',           'ONLINE',  '{"model":"Windows PC","vendor":"Dell","type":"workstation","hostname":"PKL-K01"}'),
  ('PC-PKL-Kasir-02',  '192.168.4.11',  1, 'PKL',           'ONLINE',  '{"model":"Windows PC","vendor":"Dell","type":"workstation","hostname":"PKL-K02"}'),
  ('Printer-PKL-01',   '192.168.4.20',  2, 'PKL',           'ONLINE',  '{"model":"Epson TM-T82X","vendor":"Epson","type":"printer"}'),
  ('Switch-PML-01',    '192.168.10.1',  1, 'PML',           'ONLINE',  '{"model":"D-Link DGS-1016D","vendor":"D-Link","type":"switch"}'),
  ('PC-PML-01',        '192.168.10.10', 1, 'PML',           'ONLINE',  '{"model":"Windows PC","vendor":"Lenovo","type":"workstation","hostname":"PML-01"}'),
  ('PC-PML-02',        '192.168.10.11', 1, 'PML',           'OFFLINE', '{"model":"Windows PC","vendor":"Lenovo","type":"workstation","hostname":"PML-02"}'),
  ('Switch-IDM-01',    '192.168.20.1',  1, 'IDM',           'ONLINE',  '{"model":"Netgear GS308","vendor":"Netgear","type":"switch"}'),
  ('PC-IDM-01',        '192.168.20.10', 1, 'IDM',           'ONLINE',  '{"model":"Windows PC","vendor":"ASUS","type":"workstation","hostname":"IDM-01"}'),
  ('PC-IDM-02',        '192.168.20.11', 1, 'IDM',           'ONLINE',  '{"model":"Windows PC","vendor":"ASUS","type":"workstation","hostname":"IDM-02"}'),
  ('Printer-IDM-01',   '192.168.20.20', 2, 'IDM',           'OFFLINE', '{"model":"HP LaserJet Pro","vendor":"HP","type":"printer"}'),
  ('PC-Lab-01',        '127.0.0.10',    1, 'Lab_Local',     'ONLINE',  '{"model":"Test Machine","vendor":"Local","type":"workstation","hostname":"LAB-01"}'),
  ('Switch-Cabang-01', '10.20.0.1',     1, 'Kantor Cabang', 'ONLINE',  '{"model":"Cisco SG110","vendor":"Cisco","type":"switch"}'),
  ('PC-Cabang-01',     '10.20.0.10',    1, 'Kantor Cabang', 'ONLINE',  '{"model":"Windows PC","vendor":"HP","type":"workstation","hostname":"CABANG-01"}'),
  ('PC-Cabang-02',     '10.20.0.11',    1, 'Kantor Cabang', 'OFFLINE', '{"model":"Windows PC","vendor":"HP","type":"workstation","hostname":"CABANG-02"}')
ON CONFLICT (name) DO UPDATE
  SET ip=EXCLUDED.ip, location=EXCLUDED.location,
      status=EXCLUDED.status, metadata=EXCLUDED.metadata;

-- ============================================================
-- 5. Re-seed fleet_devices WITHOUT site_id (NULL is fine now)
-- ============================================================
INSERT INTO fleet_devices (pc_name, site_id, status, is_approved, hardware_info, rustdesk_id, rustdesk_running)
VALUES
  ('PC-Kasir-01',     NULL, 'ONLINE',  TRUE, '{"anydesk_id":"881290345","rustdesk_id":"881290345","os_version":"Windows 10 Pro"}',      '881290345', TRUE),
  ('PC-Kasir-02',     NULL, 'OFFLINE', TRUE, '{"anydesk_id":"881290346","rustdesk_id":"881290346","os_version":"Windows 10 Pro"}',      '881290346', FALSE),
  ('PC-PKL-Kasir-01', NULL, 'ONLINE',  TRUE, '{"anydesk_id":"334812093","rustdesk_id":"334812093","os_version":"Windows 11 Pro"}',     '334812093', TRUE),
  ('PC-PKL-Kasir-02', NULL, 'ONLINE',  TRUE, '{"anydesk_id":"334812094","rustdesk_id":"334812094","os_version":"Windows 11 Pro"}',     '334812094', TRUE),
  ('PC-PML-01',       NULL, 'ONLINE',  TRUE, '{"anydesk_id":"445812903","rustdesk_id":"445812903","os_version":"Windows 10 Enterprise"}','445812903', TRUE),
  ('PC-PML-02',       NULL, 'OFFLINE', TRUE, '{"anydesk_id":"445812904","rustdesk_id":"445812904","os_version":"Windows 10 Enterprise"}','445812904', FALSE),
  ('PC-IDM-01',       NULL, 'ONLINE',  TRUE, '{"anydesk_id":"556812903","rustdesk_id":"556812903","os_version":"Windows 10 Home"}',     '556812903', TRUE),
  ('PC-IDM-02',       NULL, 'ONLINE',  TRUE, '{"anydesk_id":"556812904","rustdesk_id":"556812904","os_version":"Windows 10 Home"}',     '556812904', TRUE),
  ('PC-Lab-01',       NULL, 'ONLINE',  TRUE, '{"anydesk_id":"999812903","rustdesk_id":"999812903","os_version":"Windows 11 Pro"}',      '999812903', TRUE),
  ('PC-Cabang-01',    NULL, 'ONLINE',  TRUE, '{"anydesk_id":"112812903","rustdesk_id":"112812903","os_version":"Windows 10 Pro"}',      '112812903', TRUE),
  ('PC-Cabang-02',    NULL, 'OFFLINE', TRUE, '{"anydesk_id":"112812904","rustdesk_id":"112812904","os_version":"Windows 10 Pro"}',      '112812904', FALSE);

-- ============================================================
-- 6. Verify result
-- ============================================================
SELECT COUNT(*) AS total_devices FROM devices;
SELECT COUNT(*) AS total_pc_fleet FROM fleet_devices;
SELECT COUNT(*) AS total_sites FROM fleet_sites;
