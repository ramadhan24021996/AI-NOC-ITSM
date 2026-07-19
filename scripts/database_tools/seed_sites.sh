#!/bin/sh
PGPASSWORD=osi_password psql -U postgres -d osi_system -c "SELECT site_id, site_name, router_ip FROM fleet_sites LIMIT 10;"
echo "---INSERT---"
PGPASSWORD=osi_password psql -U postgres -d osi_system -c "INSERT INTO fleet_sites (site_id, site_name, router_ip, router_port, dns_primary, dns_secondary, default_remote_tool) VALUES ('jateng3', 'Jateng 3', '192.168.1.1', 10001, '8.8.8.8', '1.1.1.1', 'rustdesk'), ('pkl', 'PKL', '192.168.4.1', 10001, '8.8.8.8', '1.1.1.1', 'rustdesk'), ('pml', 'PML', '192.168.10.1', 10001, '8.8.8.8', '1.1.1.1', 'rustdesk'), ('idm', 'IDM', '192.168.20.1', 10001, '8.8.8.8', '1.1.1.1', 'rustdesk'), ('lab_local', 'Lab_Local', '127.0.0.1', 10001, '8.8.8.8', '1.1.1.1', 'rustdesk'), ('kantor_cabang', 'Kantor Cabang', '10.20.0.1', 10001, '8.8.8.8', '1.1.1.1', 'rustdesk') ON CONFLICT (site_id) DO UPDATE SET router_ip = EXCLUDED.router_ip, site_name = EXCLUDED.site_name;"
echo "---AFTER INSERT---"
PGPASSWORD=osi_password psql -U postgres -d osi_system -c "SELECT site_id, site_name, router_ip FROM fleet_sites;"
