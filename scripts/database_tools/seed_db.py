import json
import os

def main():
    json_path = "devices_list.json"
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found")
        return

    with open(json_path, "r") as f:
        devices = json.load(f)

    sql_statements = []
    
    # 1. Clear existing devices to prevent conflict, but only if they are not in use
    sql_statements.append("TRUNCATE TABLE devices CASCADE;")
    sql_statements.append("TRUNCATE TABLE fleet_devices CASCADE;")
    sql_statements.append("TRUNCATE TABLE incidents CASCADE;")
    sql_statements.append("TRUNCATE TABLE fleet_incidents CASCADE;")

    for d in devices:
        name = d["name"]
        ip = d["ip"]
        layer = d["layer"]
        location = d["location"]
        status = d["status"]
        metadata_str = json.dumps(d.get("metadata", {}))
        
        # Escape quotes for SQL
        metadata_escaped = metadata_str.replace("'", "''")
        name_escaped = name.replace("'", "''")
        location_escaped = location.replace("'", "''")
        status_escaped = status.replace("'", "''")
        
        # Insert into devices
        sql_statements.append(
            f"INSERT INTO devices (name, ip, layer, location, status, metadata) "
            f"VALUES ('{name_escaped}', '{ip}', {layer}, '{location_escaped}', '{status_escaped}', '{metadata_escaped}');"
        )
        
        # Insert into fleet_devices
        site_id = "jateng3" # default fallback
        if "Jateng" in location or "jateng" in location:
            site_id = "jateng3"
        elif "PKL" in location or "Pekalongan" in location:
            site_id = "pkl"
        elif "PML" in location or "Pemalang" in location:
            site_id = "pml"
        elif "IDM" in location or "Indramayu" in location:
            site_id = "idm"
        elif "Local" in location or "Lab" in location:
            site_id = "lab_local"
        elif "Cabang" in location or "Cab" in location:
            site_id = "kantor_cabang"
            
        hw_info = {
            "anydesk_id": d.get("metadata", {}).get("serial", "123456789"),
            "rustdesk_id": d.get("metadata", {}).get("serial", "123456789"),
            "os_version": d.get("metadata", {}).get("os_version", "Windows 10 Pro")
        }
        hw_info_str = json.dumps(hw_info).replace("'", "''")
        
        sql_statements.append(
            f"INSERT INTO fleet_devices (pc_name, site_id, status, is_approved, hardware_info, rustdesk_id, rustdesk_running) "
            f"VALUES ('{name_escaped}', '{site_id}', 'ONLINE', TRUE, '{hw_info_str}', '{hw_info['rustdesk_id']}', TRUE);"
        )

    # 2. Add some initial synthetic incidents
    synthetic_incidents = [
        {
            "device_name": "Switch-Core-01",
            "layer": 1,
            "flag": "HIGH_LATENCY",
            "evidence": "Ping latency to 192.168.1.1 is 145ms",
            "confidence": 88.5,
            "status": "OPEN"
        },
        {
            "device_name": "Unknown-Device-885D",
            "layer": 2,
            "flag": "PACKET_LOSS",
            "evidence": "Packet loss rate is 25%",
            "confidence": 75.0,
            "status": "OPEN"
        },
        {
            "device_name": "AuditAgent",
            "layer": 7,
            "flag": "PORT_CLOSED",
            "evidence": "SSH port 22 is closed",
            "confidence": 92.0,
            "status": "RESOLVED"
        }
    ]

    for inc in synthetic_incidents:
        dev_escaped = inc["device_name"].replace("'", "''")
        flag_escaped = inc["flag"].replace("'", "''")
        ev_escaped = inc["evidence"].replace("'", "''")
        status_escaped = inc["status"].replace("'", "''")
        
        # Insert into incidents
        sql_statements.append(
            f"INSERT INTO incidents (device_name, layer, flag, evidence, confidence, rag_status) "
            f"VALUES ('{dev_escaped}', {inc['layer']}, '{flag_escaped}', '{ev_escaped}', {inc['confidence']}, 'GREEN') "
            f"RETURNING incident_id;"
        )

    # Write SQL statements to a file
    with open("seed_devices.sql", "w") as f:
        f.write("\n".join(sql_statements))
    
    print("Successfully generated seed_devices.sql")

if __name__ == "__main__":
    main()
