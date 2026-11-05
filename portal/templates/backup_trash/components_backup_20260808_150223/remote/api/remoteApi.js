/**
 * Remote Access API Service
 * 
 * Connects React components to backend Phase 2 APIs
 * - Fetch device configuration
 * - Update device configuration
 * - Store/retrieve credentials
 * - Test connectivity
 * - Launch remote access tools
 */

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000/api/remote';

/**
 * Fetch device configuration from backend
 * GET /api/remote/device/<device_id>
 */
export async function fetchDeviceConfig(deviceId) {
  try {
    const response = await fetch(`${API_BASE_URL}/device/${deviceId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getAuthToken()}`,
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch device config: ${response.statusText}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('fetchDeviceConfig error:', error);
    throw error;
  }
}

/**
 * Update device configuration
 * PUT /api/remote/device/<device_id>/config
 */
export async function updateDeviceConfig(deviceId, updates) {
  try {
    const response = await fetch(`${API_BASE_URL}/device/${deviceId}/config`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getAuthToken()}`,
      },
      body: JSON.stringify(updates),
    });

    if (!response.ok) {
      throw new Error(`Failed to update device config: ${response.statusText}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('updateDeviceConfig error:', error);
    throw error;
  }
}

/**
 * Store encrypted credential
 * POST /api/remote/device/<device_id>/credentials
 */
export async function storeCredential(deviceId, toolType, credentialData) {
  try {
    const response = await fetch(`${API_BASE_URL}/device/${deviceId}/credentials`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getAuthToken()}`,
      },
      body: JSON.stringify({
        tool_type: toolType,
        ...credentialData,
      }),
    });

    if (!response.ok) {
      throw new Error(`Failed to store credential: ${response.statusText}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('storeCredential error:', error);
    throw error;
  }
}

/**
 * Retrieve credential (decrypted)
 * GET /api/remote/device/<device_id>/credentials/<tool_type>
 */
export async function getCredential(deviceId, toolType) {
  try {
    const response = await fetch(
      `${API_BASE_URL}/device/${deviceId}/credentials/${toolType}`,
      {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${getAuthToken()}`,
        },
      }
    );

    if (!response.ok) {
      throw new Error(`Failed to retrieve credential: ${response.statusText}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('getCredential error:', error);
    throw error;
  }
}

/**
 * List all devices
 * GET /api/remote/devices
 */
export async function listDevices() {
  try {
    const response = await fetch(`${API_BASE_URL}/devices`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getAuthToken()}`,
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to list devices: ${response.statusText}`);
    }

    const data = await response.json();
    return data.devices || [];
  } catch (error) {
    console.error('listDevices error:', error);
    throw error;
  }
}

/**
 * Test connectivity to device
 * POST /api/remote/device/<device_id>/test
 */
export async function testConnection(deviceId) {
  try {
    const response = await fetch(`${API_BASE_URL}/device/${deviceId}/test`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getAuthToken()}`,
      },
    });

    if (!response.ok) {
      throw new Error(`Connection test failed: ${response.statusText}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('testConnection error:', error);
    throw error;
  }
}

/**
 * Launch remote access tool
 * POST /api/remote/launch
 */
export async function launchRemoteTool(deviceId, toolType) {
  try {
    const response = await fetch(`${API_BASE_URL}/launch`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getAuthToken()}`,
      },
      body: JSON.stringify({
        device_id: deviceId,
        tool: toolType,
      }),
    });

    if (!response.ok) {
      throw new Error(`Failed to launch tool: ${response.statusText}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('launchRemoteTool error:', error);
    throw error;
  }
}

/**
 * List active sessions
 * GET /api/remote/sessions
 */
export async function listActiveSessions() {
  try {
    const response = await fetch(`${API_BASE_URL}/sessions`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getAuthToken()}`,
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to list sessions: ${response.statusText}`);
    }

    const data = await response.json();
    return data.sessions || [];
  } catch (error) {
    console.error('listActiveSessions error:', error);
    throw error;
  }
}

/**
 * Get JWT auth token from localStorage or sessionStorage
 * Components should set this after login
 */
function getAuthToken() {
  // Try to get from localStorage first (persistent)
  let token = localStorage.getItem('auth_token');
  
  // Fallback to sessionStorage
  if (!token) {
    token = sessionStorage.getItem('auth_token');
  }
  
  // Fallback to environment variable (for testing)
  if (!token) {
    token = process.env.REACT_APP_AUTH_TOKEN;
  }
  
  return token || '';
}

/**
 * Set auth token (call after login)
 */
export function setAuthToken(token, persist = true) {
  if (persist) {
    localStorage.setItem('auth_token', token);
  } else {
    sessionStorage.setItem('auth_token', token);
  }
}

/**
 * Clear auth token (call on logout)
 */
export function clearAuthToken() {
  localStorage.removeItem('auth_token');
  sessionStorage.removeItem('auth_token');
}
