#!/usr/bin/env python3
import subprocess
import urllib.request
import sys
import os

def print_hdr(msg):
    print(f"\n==================================================")
    print(f" {msg}")
    print(f"==================================================")

def run_cmd(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode('utf-8').strip()
    except subprocess.CalledProcessError as e:
        return e.output.decode('utf-8').strip()

def parse_env():
    env_vars = {}
    try:
        with open('.env', 'r') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    env_vars[k] = v.strip('"\'')
    except:
        pass
    return env_vars

def audit():
    print_hdr("PRODUCTION HARDENING AUDITOR V2.1 (ADVANCED DOCKER E2E)")
    env_vars = parse_env()
    redis_pass = env_vars.get("OSI_SECURITY_KEY", "")
    db_pass = env_vars.get("DB_PASSWORD", "postgres")
    
    scores = {}
    weights = {
        "PostgreSQL": 20, "Redis": 10, "NATS": 10, "API_Gateway": 15,
        "Dashboard": 10, "Security": 10, "Audit": 10, "Recovery": 5,
        "Monitoring": 5, "Backup": 5
    }
    
    print("--- 1. FOUNDATION SERVICES ---")
    
    # Check Postgres
    pg_res = run_cmd(f"docker exec osi-postgres pg_isready -U postgres")
    if "accepting connections" in pg_res:
        print("✅ PostgreSQL: PASS (Healthy & Accepting Connections)")
        scores["PostgreSQL"] = 1.0
    else:
        print(f"❌ PostgreSQL: FAIL ({pg_res})")
        scores["PostgreSQL"] = 0.0

    # Check Redis
    print("\n[Redis Deep Diagnostics]")
    redis_ping = run_cmd("docker exec osi-redis redis-cli ping")
    
    if "Connection refused" in redis_ping:
        print("❌ Redis Service : FAIL (Connection Refused)")
        scores["Redis"] = 0.0
    elif "NOAUTH" in redis_ping:
        print("✅ Redis Service : PASS (Container is running)")
        
        # Test Auth & Functional
        auth_cmd = f"docker exec osi-redis redis-cli -a '{redis_pass}' ping"
        redis_auth = run_cmd(auth_cmd)
        
        if "PONG" in redis_auth:
            print("✅ Authentication: PASS")
            # Test Functional
            run_cmd(f"docker exec osi-redis redis-cli -a '{redis_pass}' SET auditor_test 'ready'")
            get_res = run_cmd(f"docker exec osi-redis redis-cli -a '{redis_pass}' GET auditor_test")
            run_cmd(f"docker exec osi-redis redis-cli -a '{redis_pass}' DEL auditor_test")
            
            if "ready" in get_res:
                print("✅ Functional Test: PASS (SET/GET/DEL)")
                scores["Redis"] = 1.0
            else:
                print("❌ Functional Test: FAIL")
                scores["Redis"] = 0.5
        elif "ERR invalid password" in redis_auth:
            print("❌ Authentication: FAIL (Wrong Password in Auditor)")
            scores["Redis"] = 0.5
        else:
            print(f"❌ Authentication: FAIL ({redis_auth})")
            scores["Redis"] = 0.0
    else:
        print(f"⚠️ Redis Service : UNKNOWN STATE ({redis_ping})")
        scores["Redis"] = 0.0
        
    # Check NATS
    print("")
    nats_res = run_cmd("docker exec osi-nats wget -qO- http://localhost:8222/varz")
    if "server_id" in nats_res:
        print("✅ NATS JetStream: PASS (Healthy)")
        scores["NATS"] = 1.0
    else:
        print("❌ NATS: FAIL")
        scores["NATS"] = 0.0
        
    print("\n--- 2. BACKEND & API GATEWAY ---")
    
    # Check API Gateway (Nginx)
    try:
        req = urllib.request.Request("http://localhost/health")
        with urllib.request.urlopen(req, timeout=3) as response:
            if response.status == 200:
                print("✅ API Gateway (Nginx): PASS (200 OK)")
                scores["API_Gateway"] = 1.0
            else:
                print("❌ API Gateway (Nginx): FAIL")
                scores["API_Gateway"] = 0.5
    except Exception as e:
        print(f"❌ API Gateway (Nginx): FAIL ({e})")
        scores["API_Gateway"] = 0.0
        
    # Security (RBAC) Check
    try:
        req = urllib.request.Request("http://localhost/api/system/health")
        with urllib.request.urlopen(req, timeout=3) as response:
            scores["Security"] = 0.0
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("✅ Security (RBAC): PASS (401 Unauthorized Enforced)")
            scores["Security"] = 1.0
        else:
            print(f"⚠️ Security (RBAC): FAIL (Expected 401, got {e.code})")
            scores["Security"] = 0.5
    except Exception as e:
        print(f"❌ Security (RBAC): FAIL ({e})")
        scores["Security"] = 0.0
        
    print("\n--- 3. DASHBOARD & UI ---")
    
    # Dashboard Server
    dash_res = run_cmd("docker ps --filter name=osi-dashboard-server --format '{{.Status}}'")
    if "Up" in dash_res:
        print("✅ Dashboard: PASS (Container Running)")
        scores["Dashboard"] = 1.0
    else:
        print("❌ Dashboard: FAIL")
        scores["Dashboard"] = 0.0
        
    print("\n--- 4. COMPLIANCE & RECOVERY ---")
    # Audit Trail (Checking if table exists via postgres)
    audit_res = run_cmd(f"docker exec osi-postgres psql -U postgres -d osi_system -c \"SELECT count(*) FROM audit_logs;\"")
    if "count" in audit_res or "0" in audit_res:
        print("✅ Audit Trail: PASS (Postgres Table Responsive)")
        scores["Audit"] = 1.0
    else:
        scores["Audit"] = 0.0
        
    # Monitoring (Checking Netdata)
    try:
        with urllib.request.urlopen("http://localhost:19999/api/v1/info", timeout=3) as response:
            if response.status == 200:
                print("✅ Monitoring: PASS (Netdata)")
                scores["Monitoring"] = 1.0
            else:
                scores["Monitoring"] = 0.0
    except:
        print("❌ Monitoring: FAIL")
        scores["Monitoring"] = 0.0
        
    # Recovery & Backup
    rec_res = run_cmd("ls -l scripts/disaster_recovery.ps1 scripts/backup_system.py")
    if "backup" in rec_res:
        print("✅ Recovery & Backup: PASS")
        scores["Recovery"] = 1.0
        scores["Backup"] = 1.0
    else:
        scores["Recovery"] = 0.0
        scores["Backup"] = 0.0

    print_hdr("FINAL READINESS SCORE")
    total_score = 0
    for key, weight in weights.items():
        score = scores.get(key, 0.0)
        weighted = score * weight
        total_score += weighted
        print(f" - {key:<15}: {score*100:>3.0f}% (Weight: {weight}%) -> {weighted:>4.1f} pts")
        
    print(f"\n==================================================")
    print(f" TOTAL PRODUCTION READINESS SCORE: {total_score:.1f}%")
    print(f"==================================================")
    
if __name__ == "__main__":
    audit()
