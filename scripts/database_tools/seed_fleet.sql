-- SEED DEVICES
INSERT INTO devices (name, ip, layer, location, status, metadata)
VALUES
  ('Switch-Core-01', '192.168.1.1', 1, 'Jateng 3', 'ONLINE', '{"model":"Catalyst C2960","vendor":"Cisco","type":"switch"}'),
  ('Router-Jateng3', '192.168.1.254', 1, 'Jateng 3', 'ONLINE', '{"model":"MikroTik RB4011","vendor":"MikroTik","type":"router"}'),
  ('PC-Kasir-01', '192.168.1.10', 2, 'Jateng 3', 'ONLINE', '{"model":"Windows PC","vendor":"HP","type":"workstation"}'),
  ('PC-Kasir-02', '192.168.1.11', 2, 'Jateng 3', 'OFFLINE', '{"model":"Windows PC","vendor":"HP","type":"workstation"}'),
  ('Printer-Sales-01', '192.168.1.20', 3, 'Jateng 3', 'ONLINE', '{"model":"Epson TM-T82X","vendor":"Epson","type":"printer"}'),
  ('Switch-PKL-01', '192.168.4.1', 1, 'PKL', 'ONLINE', '{"model":"TP-Link TL-SG108","vendor":"TP-Link","type":"switch"}'),
  ('PC-PKL-Kasir-01', '192.168.4.10', 2, 'PKL', 'ONLINE', '{"model":"Windows PC","vendor":"Dell","type":"workstation"}'),
  ('PC-PKL-Kasir-02', '192.168.4.11', 2, 'PKL', 'ONLINE', '{"model":"Windows PC","vendor":"Dell","type":"workstation"}'),
  ('Printer-PKL-01', '192.168.4.20', 3, 'PKL', 'ONLINE', '{"model":"Epson TM-T82X","vendor":"Epson","type":"printer"}'),
  ('Switch-PML-01', '192.168.10.1', 1, 'PML', 'ONLINE', '{"model":"D-Link DGS-1016D","vendor":"D-Link","type":"switch"}'),
  ('PC-PML-01', '192.168.10.10', 2, 'PML', 'ONLINE', '{"model":"Windows PC","vendor":"Lenovo","type":"workstation"}'),
  ('PC-PML-02', '192.168.10.11', 2, 'PML', 'OFFLINE', '{"model":"Windows PC","vendor":"Lenovo","type":"workstation"}'),
  ('Switch-IDM-01', '192.168.20.1', 1, 'IDM', 'ONLINE', '{"model":"Netgear GS308","vendor":"Netgear","type":"switch"}'),
  ('PC-IDM-01', '192.168.20.10', 2, 'IDM', 'ONLINE', '{"model":"Windows PC","vendor":"ASUS","type":"workstation"}'),
  ('PC-IDM-02', '192.168.20.11', 2, 'IDM', 'ONLINE', '{"model":"Windows PC","vendor":"ASUS","type":"workstation"}'),
  ('Printer-IDM-01', '192.168.20.20', 3, 'IDM', 'OFFLINE', '{"model":"HP LaserJet Pro","vendor":"HP","type":"printer"}'),
  ('PC-Lab-01', '127.0.0.10', 2, 'Lab_Local', 'ONLINE', '{"model":"Test Machine","vendor":"Local","type":"workstation"}'),
  ('Switch-Cabang-01', '10.20.0.1', 1, 'Kantor Cabang', 'ONLINE', '{"model":"Cisco SG110","vendor":"Cisco","type":"switch"}'),
  ('PC-Cabang-01', '10.20.0.10', 2, 'Kantor Cabang', 'ONLINE', '{"model":"Windows PC","vendor":"HP","type":"workstation"}'),
  ('PC-Cabang-02', '10.20.0.11', 2, 'Kantor Cabang', 'OFFLINE', '{"model":"Windows PC","vendor":"HP","type":"workstation"}')
ON CONFLICT (name) DO UPDATE
  SET ip=EXCLUDED.ip,
      location=EXCLUDED.location,
      status=EXCLUDED.status,
      metadata=EXCLUDED.metadata;

-- SEED FLEET SITES
INSERT INTO fleet_sites (site_id, site_name, router_ip, router_port, dns_primary, dns_secondary, default_remote_tool)
VALUES
  ('SITE-JATENG3', 'Jateng 3', '192.168.1.1', 10001, '8.8.8.8', '8.8.4.4', 'rustdesk'),
  ('SITE-PKL', 'PKL', '192.168.4.1', 10001, '8.8.8.8', '8.8.4.4', 'rustdesk'),
  ('SITE-PML', 'PML', '192.168.10.1', 10001, '8.8.8.8', '8.8.4.4', 'rustdesk'),
  ('SITE-IDM', 'IDM', '192.168.20.1', 10001, '8.8.8.8', '8.8.4.4', 'rustdesk'),
  ('SITE-LAB', 'Lab_Local', '127.0.0.1', 10001, '127.0.0.1', '127.0.0.1', 'rustdesk'),
  ('SITE-CABANG', 'Kantor Cabang', '10.20.0.1', 10001, '8.8.8.8', '8.8.4.4', 'rustdesk')
ON CONFLICT (site_id) DO UPDATE
  SET site_name=EXCLUDED.site_name,
      router_ip=EXCLUDED.router_ip;

-- VERIFY
SELECT COUNT(*) as total_devices FROM devices;
SELECT COUNT(*) as total_sites FROM fleet_sites;
