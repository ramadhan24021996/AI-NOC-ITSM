#!/usr/bin/env python3
"""
H-02 API Authentication Test Suite
Tests JWT token generation, verification, and endpoint protection
"""

import os
import sys
import json
import requests
from datetime import datetime, timedelta

# Test configuration
BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:9999")
TIMEOUT = 5

print("\n" + "="*80)
print("H-02 API AUTHENTICATION TEST SUITE")
print("="*80)

# =====================================================================
# TEST 1: Health Check (No Auth Required)
# =====================================================================
def test_health_endpoint():
    """Test health check endpoint (public)"""
    print("\n[TEST 1] Health Check Endpoint (Public)")
    print("-" * 80)
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=TIMEOUT)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check passed")
            print(f"   Status: {data.get('status')}")
            print(f"   Service: {data.get('service')}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

# =====================================================================
# TEST 2: Login Endpoint
# =====================================================================
def test_login():
    """Test login endpoint to get JWT token"""
    print("\n[TEST 2] Login Endpoint (Get JWT Token)")
    print("-" * 80)
    
    # Default test credentials
    credentials = {
        "user_id": "test-agent-001",
        "api_key": os.environ.get('API_KEY_AGENT', 'agent-key-67890')
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json=credentials,
            timeout=TIMEOUT
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Login successful")
            print(f"   User: {data.get('user_id')}")
            print(f"   Role: {data.get('role')}")
            print(f"   Token Type: {data.get('token_type')}")
            print(f"   Expires In: {data.get('expires_in')} seconds")
            
            # Return token for next tests
            return data.get('token')
        else:
            print(f"❌ Login failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

# =====================================================================
# TEST 3: Token Verification
# =====================================================================
def test_verify_token(token):
    """Test token verification endpoint"""
    print("\n[TEST 3] Token Verification Endpoint")
    print("-" * 80)
    
    if not token:
        print("❌ No token provided - skipping test")
        return False
    
    try:
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.get(
            f"{BASE_URL}/api/auth/verify",
            headers=headers,
            timeout=TIMEOUT
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Token verification successful")
            print(f"   Valid: {data.get('valid')}")
            print(f"   User ID: {data.get('user_id')}")
            print(f"   Role: {data.get('role')}")
            return True
        else:
            print(f"❌ Token verification failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

# =====================================================================
# TEST 4: Protected Endpoint with Token
# =====================================================================
def test_protected_endpoint_with_token(token):
    """Test accessing protected endpoint with valid token"""
    print("\n[TEST 4] Protected Endpoint with Bearer Token")
    print("-" * 80)
    
    if not token:
        print("❌ No token provided - skipping test")
        return False
    
    try:
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.get(
            f"{BASE_URL}/api/devices",
            headers=headers,
            timeout=TIMEOUT
        )
        
        if response.status_code == 200:
            print(f"✅ Protected endpoint accessed with valid token")
            print(f"   Response status: {response.status_code}")
            # Note: Actual data depends on database content
            return True
        elif response.status_code == 401:
            print(f"❌ Token rejected: Unauthorized")
            return False
        else:
            print(f"✅ Token accepted (endpoint returned {response.status_code})")
            return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

# =====================================================================
# TEST 5: Protected Endpoint without Token (Should Fail)
# =====================================================================
def test_protected_endpoint_without_token():
    """Test that protected endpoint rejects requests without token"""
    print("\n[TEST 5] Protected Endpoint Without Token (Should Fail)")
    print("-" * 80)
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/devices",
            timeout=TIMEOUT
        )
        
        if response.status_code == 401:
            print(f"✅ Endpoint correctly rejected request without token")
            try:
                msg = response.json().get('message')
            except Exception:
                msg = response.text
            print(f"   Response: {msg}")
            return True
        else:
            print(f"❌ Endpoint did not require authentication (status: {response.status_code})")
            return False
    except Exception as e:
        print(f"⚠️  Error: {e}")
        return False

# =====================================================================
# TEST 6: API Key Authentication
# =====================================================================
def test_api_key_auth():
    """Test API key authentication"""
    print("\n[TEST 6] API Key Authentication")
    print("-" * 80)
    
    api_key = os.environ.get('API_KEY_AGENT', 'agent-key-67890')
    
    try:
        headers = {'X-API-Key': api_key}
        response = requests.get(
            f"{BASE_URL}/api/devices",
            headers=headers,
            timeout=TIMEOUT
        )
        
        if response.status_code == 200:
            print(f"✅ API key authentication successful")
            print(f"   Response status: {response.status_code}")
            return True
        elif response.status_code == 401:
            print(f"❌ API key rejected")
            return False
        else:
            print(f"✅ API key accepted (endpoint returned {response.status_code})")
            return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

# =====================================================================
# TEST 7: Invalid Token (Should Fail)
# =====================================================================
def test_invalid_token():
    """Test that invalid token is rejected"""
    print("\n[TEST 7] Invalid Token (Should Fail)")
    print("-" * 80)
    
    try:
        headers = {'Authorization': 'Bearer invalid.token.here'}
        response = requests.get(
            f"{BASE_URL}/api/devices",
            headers=headers,
            timeout=TIMEOUT
        )
        
        if response.status_code == 401:
            print(f"✅ Invalid token correctly rejected")
            print(f"   Response: {response.json().get('message')}")
            return True
        else:
            print(f"❌ Invalid token was not rejected (status: {response.status_code})")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

# =====================================================================
# MAIN TEST RUNNER
# =====================================================================
def main():
    results = {}
    
    # Run tests
    results['health'] = test_health_endpoint()
    
    token = test_login()
    results['login'] = token is not None
    results['verify_token'] = test_verify_token(token) if token else False
    results['protected_with_token'] = test_protected_endpoint_with_token(token) if token else False
    results['protected_without_token'] = test_protected_endpoint_without_token()
    results['api_key_auth'] = test_api_key_auth()
    results['invalid_token'] = test_invalid_token()
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED - H-02 Authentication is working!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
