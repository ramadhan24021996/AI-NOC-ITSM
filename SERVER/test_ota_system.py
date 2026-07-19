#!/usr/bin/env python
"""
OTA System Test Script - Tests all OTA endpoints and flows
Verifies Dashboard, Ingestion Server, and PC Agent OTA capabilities
"""

import json
import hashlib
import urllib.request
import os
import sys
from datetime import datetime

# Configuration
DASHBOARD_IP = "10.20.0.163"
DASHBOARD_PORT = 9999
INGESTION_IP = "10.20.0.163"
INGESTION_PORT = 8800
AGENT_PATH = r"d:\AI-AGEN DRIVEN INTELLIGENT INCIDENT ANALIS\client\05_SIAP_DISTRIBUSI\PC_HEALTH_AGENT.py"

class OTATestSuite:
    def __init__(self):
        self.results = []
        self.current_hash = None
        self.original_hash = None
        self.server_hash = None
        
    def log_test(self, name, status, details=""):
        """Log test result"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        result = f"[{timestamp}] {name}: {'✅ PASS' if status else '❌ FAIL'}"
        if details:
            result += f" - {details}"
        self.results.append(result)
        print(result)
        
    def test_agent_file_exists(self):
        """Test 1: Verify agent file exists"""
        exists = os.path.exists(AGENT_PATH)
        self.log_test("Agent File Exists", exists, AGENT_PATH)
        return exists
    
    def test_calculate_current_hash(self):
        """Test 2: Calculate current file hash"""
        try:
            with open(AGENT_PATH, "rb") as f:
                hash_val = hashlib.sha256(f.read()).hexdigest()
            if self.original_hash is None:
                self.original_hash = hash_val
            self.current_hash = hash_val
            self.log_test("Calculate Current Hash", True, self.current_hash[:16] + "...")
            return True
        except Exception as e:
            self.log_test("Calculate Current Hash", False, str(e))
            return False
    
    def test_dashboard_push_ota(self):
        """Test 3: Trigger OTA push from dashboard"""
        try:
            import base64
            url = f"http://{DASHBOARD_IP}:{DASHBOARD_PORT}/api/push_ota"
            req = urllib.request.Request(url, method="POST")
            auth_str = base64.b64encode(b"mkt:mkt123").decode("utf-8")
            req.add_header("Authorization", f"Basic {auth_str}")
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                success = response.status == 200 and data.get("status") == "success"
                self.log_test("Dashboard Push OTA", success, data.get("message", "No message"))
                return success
        except Exception as e:
            self.log_test("Dashboard Push OTA", False, str(e))
            return False
    
    def test_ingestion_version_endpoint(self):
        """Test 4: Check ingestion server version endpoint"""
        try:
            url = f"http://{INGESTION_IP}:{INGESTION_PORT}/api/agent_version"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                self.server_hash = data.get("version", "")
                success = response.status == 200 and self.server_hash
                self.log_test("Ingestion Version Endpoint", success, self.server_hash[:16] + "..." if self.server_hash else "No hash")
                return success
        except Exception as e:
            self.log_test("Ingestion Version Endpoint", False, str(e))
            return False
    
    def test_hash_comparison(self):
        """Test 5: Compare hashes (should be different after push_ota)"""
        if not self.original_hash or not self.server_hash:
            self.log_test("Hash Comparison", False, "Missing hash data")
            return False
        
        # After push_ota, they should be different
        different = self.original_hash != self.server_hash
        self.log_test("Hash Comparison", different, 
                     f"Original: {self.original_hash[:8]}... vs Server: {self.server_hash[:8]}...")
        return different
    
    def test_ingestion_download_endpoint(self):
        """Test 6: Download agent file from ingestion server"""
        try:
            url = f"http://{INGESTION_IP}:{INGESTION_PORT}/download/PC_HEALTH_AGENT.py"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=10) as response:
                file_data = response.read()
                success = response.status == 200 and len(file_data) > 0
                # Verify hash of downloaded file
                download_hash = hashlib.sha256(file_data).hexdigest()
                hash_match = download_hash == self.server_hash
                self.log_test("Ingestion Download Endpoint", success and hash_match, 
                             f"Downloaded {len(file_data)} bytes, hash match: {hash_match}")
                return success and hash_match
        except Exception as e:
            self.log_test("Ingestion Download Endpoint", False, str(e))
            return False
    
    def test_network_dashboard(self):
        """Test 7: Network connectivity to dashboard"""
        try:
            url = f"http://{DASHBOARD_IP}:{DASHBOARD_PORT}/health"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=2) as response:
                data = json.loads(response.read().decode())
                success = response.status == 200 and data.get("status") == "UP"
                self.log_test("Network: Dashboard Health", success, f"Status: {data.get('status')}")
                return success
        except Exception as e:
            self.log_test("Network: Dashboard Health", False, str(e))
            return False
    
    def test_network_ingestion(self):
        """Test 8: Network connectivity to ingestion server"""
        try:
            url = f"http://{INGESTION_IP}:{INGESTION_PORT}/api/agent_version"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=2) as response:
                success = response.status == 200
                self.log_test("Network: Ingestion Server", success, "Port 8800 accessible")
                return success
        except Exception as e:
            self.log_test("Network: Ingestion Server", False, str(e))
            return False
    
    def run_all_tests(self):
        """Run all tests in sequence"""
        print("=" * 70)
        print("OTA SYSTEM VERIFICATION TEST SUITE")
        print("=" * 70)
        print()
        
        tests = [
            ("File System", self.test_agent_file_exists),
            ("Hash Calculation", self.test_calculate_current_hash),
            ("Network & Dashboard", self.test_network_dashboard),
            ("OTA Push Trigger", self.test_dashboard_push_ota),
            ("Hash Recalculation", lambda: self.test_calculate_current_hash()),
            ("Ingestion Version", self.test_ingestion_version_endpoint),
            ("Hash Comparison", self.test_hash_comparison),
            ("Ingestion Download", self.test_ingestion_download_endpoint),
            ("Network & Ingestion", self.test_network_ingestion),
        ]
        
        results = {}
        for name, test_func in tests:
            try:
                print(f"\n📋 Testing: {name}")
                results[name] = test_func()
            except Exception as e:
                print(f"❌ Test Exception: {e}")
                results[name] = False
        
        # Summary
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        passed = sum(1 for v in results.values() if v)
        total = len(results)
        
        for test_name, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status} - {test_name}")
        
        print()
        print(f"Total: {passed}/{total} tests passed")
        
        if passed == total:
            print("\n🎉 ALL TESTS PASSED - OTA SYSTEM IS READY!")
        elif passed >= total * 0.8:
            print(f"\n⚠️  {total - passed} TESTS FAILED - Check network connectivity")
        else:
            print(f"\n❌ MULTIPLE FAILURES - OTA system needs investigation")
        
        return results

if __name__ == "__main__":
    print("Starting OTA System Tests...")
    print(f"Dashboard: {DASHBOARD_IP}:{DASHBOARD_PORT}")
    print(f"Ingestion: {INGESTION_IP}:{INGESTION_PORT}")
    print(f"Agent: {AGENT_PATH}")
    print()
    
    tester = OTATestSuite()
    results = tester.run_all_tests()
    
    # Exit code based on results
    passed = sum(1 for v in results.values() if v)
    sys.exit(0 if passed == len(results) else 1)
