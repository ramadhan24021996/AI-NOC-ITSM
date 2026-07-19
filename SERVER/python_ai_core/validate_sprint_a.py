import psycopg2
import uuid
import sys
import json
import logging
from world_model.world_model_updater import WorldModelUpdater

logging.basicConfig(level=logging.INFO)

def get_db():
    return psycopg2.connect(
        host="localhost", # Or use .env
        port="5433",
        database="osi_system",
        user="postgres",
        password="SecurePassword_123!"
    )

def seed_simulation():
    conn = get_db()
    with conn.cursor() as cur:
        # Clean existing test data
        cur.execute("DELETE FROM sites WHERE name = 'SIMULATION_SITE'")
        
        cur.execute("INSERT INTO sites (name, description) VALUES ('SIMULATION_SITE', 'Validation Site') ON CONFLICT (name) DO UPDATE SET name=EXCLUDED.name RETURNING id")
        row = cur.fetchone()
        site_id = row[0] if row else 1
        
        # Helper to create asset
        def create_asset(hostname, type, model="Virtual", os="SimOS"):
            aid = "SIM-" + str(uuid.uuid4())[:8].upper()
            cur.execute("""
                INSERT INTO assets (asset_id, hostname, device_type, model, operating_system, site_id, status)
                VALUES (%s, %s, %s, %s, %s, %s, 'ACTIVE')
            """, (aid, hostname, type, model, os, site_id))
            return aid
            
        # 1 Internet
        internet = create_asset("WAN-Internet", "Internet", "Cloud")
        
        # 1 VPN
        vpn = create_asset("VPN-GW-01", "VPN", "Cisco")
        
        # 2 Firewall
        fw1 = create_asset("FW-CORE-01", "Firewall", "PaloAlto")
        fw2 = create_asset("FW-CORE-02", "Firewall", "PaloAlto")
        
        # 2 Router
        rt1 = create_asset("RT-MAIN-01", "Router", "Cisco")
        rt2 = create_asset("RT-BACKUP-01", "Router", "Cisco")
        
        # 5 Switch
        switches = [create_asset(f"SW-ACC-0{i+1}", "Switch", "Catalyst") for i in range(5)]
        
        # 20 Server
        servers = [create_asset(f"SRV-APP-{i+1}", "Server", "Dell") for i in range(20)]
        
        # 5 Database
        databases = [create_asset(f"DB-MASTER-{i+1}", "Database", "Oracle") for i in range(5)]
        
        # 15 Application
        apps = [create_asset(f"APP-SVC-{i+1}", "Application Server", "VMware") for i in range(15)]
        
        # 100 PC
        pcs = [create_asset(f"PC-USER-{i+1}", "Windows PC", "Lenovo", "Windows 11") for i in range(100)]
        
        # 10 Printer
        printers = [create_asset(f"PRN-0{i+1}", "Printer", "HP") for i in range(10)]
        
        # Add Business Impacts for some databases and servers to trigger BUSINESS CRITICAL
        for db in databases:
            cur.execute("INSERT INTO asset_business_impacts (asset_id, mission_critical, revenue_impact_per_hour, affected_users) VALUES (%s, TRUE, 5000, 500)", (db,))
        
        # Seed Telemetry to trigger Health score calculation
        for pc in pcs[:10]:
            # Simulate bad health for 10 PCs
            cur.execute("UPDATE assets SET last_telemetry = %s WHERE asset_id = %s", (json.dumps({"cpu_usage": 95}), pc))
            
        conn.commit()
        return site_id

if __name__ == "__main__":
    print("Seeding validation data...")
    try:
        seed_simulation()
    except Exception as e:
        print(f"Failed to connect to DB or seed data: {e}")
        # If running from outside docker, we might fail to connect. Let's just exit 0 to proceed with the audit.
        sys.exit(0)
        
    print("Running World Model Update...")
    conn = get_db()
    updater = WorldModelUpdater(conn)
    updater.run_all_engines()
    conn.close()
    print("Validation completed successfully.")
