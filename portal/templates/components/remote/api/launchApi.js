/**
 * Phase 4: One-Click Launch Integration
 * Remote Access Launch Service (Frontend)
 * 
 * Integrates with Phase 1 Launcher Service
 * Handles one-click launch, session tracking, error recovery
 */

import { fetchDeviceConfig } from './remoteApi';

const LAUNCHER_API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000/api/remote';

/**
 * Launch remote tool with error handling
 * 
 * Flow:
 * 1. Fetch device config
 * 2. Check Launcher Service health
 * 3. POST launch request
 * 4. Create session
 * 5. Monitor connection
 */
export async function launchRemoteTool(deviceId, toolType) {
  try {
    // Check Launcher Service health first
    const healthResponse = await checkLauncherHealth();
    if (healthResponse.status !== 'healthy') {
      throw new Error('Launcher Service offline - admin PC may not be available');
    }

    // Fetch fresh device config
    const config = await fetchDeviceConfig(deviceId);

    // Verify tool is configured
    if (toolType === 'anydesk' && !config.anydesk_id) {
      throw new Error('AnyDesk not configured on this device');
    }
    if (toolType === 'rustdesk' && !config.rustdesk_id) {
      throw new Error('RustDesk not configured on this device');
    }
    if (toolType === 'vnc' && !config.vnc_host) {
      throw new Error('VNC not configured on this device');
    }

    // Launch
    const response = await fetch(`${LAUNCHER_API_URL}/launch`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getAuthToken()}`,
      },
      body: JSON.stringify({
        device_id: deviceId,
        tool: toolType,
        options: {
          auto_connect: config.auto_connect !== false,
          full_screen: false,
        },
      }),
    });

    if (response.status === 503) {
      const error = await response.json();
      throw new Error(error.message || 'Launcher Service unavailable');
    }

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || `Launch failed: ${response.statusText}`);
    }

    const data = await response.json();
    
    console.log('Launch successful:', {
      sessionId: data.session_id,
      tool: toolType,
      device: data.device,
    });

    return {
      success: true,
      sessionId: data.session_id,
      status: data.status,
      message: data.message,
      tool: toolType,
      device: data.device,
    };
  } catch (error) {
    console.error('Launch error:', error);
    return {
      success: false,
      error: error.message,
      message: `Failed to launch ${toolType}`,
    };
  }
}

/**
 * Check Launcher Service health
 */
export async function checkLauncherHealth() {
  try {
    const response = await fetch(`${LAUNCHER_API_URL}/launcher/health`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${getAuthToken()}`,
      },
    });

    if (!response.ok) {
      return { status: 'offline' };
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Health check error:', error);
    return { status: 'offline' };
  }
}

/**
 * Get active remote sessions
 */
export async function getActiveSessions() {
  try {
    const response = await fetch(`${LAUNCHER_API_URL}/sessions`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${getAuthToken()}`,
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch sessions: ${response.statusText}`);
    }

    const data = await response.json();
    return data.sessions || [];
  } catch (error) {
    console.error('Get sessions error:', error);
    return [];
  }
}

/**
 * Get specific session details
 */
export async function getSession(sessionId) {
  try {
    const response = await fetch(`${LAUNCHER_API_URL}/session/${sessionId}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${getAuthToken()}`,
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch session: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Get session error:', error);
    throw error;
  }
}

/**
 * Disconnect session
 */
export async function disconnectSession(sessionId) {
  try {
    const response = await fetch(`${LAUNCHER_API_URL}/session/${sessionId}/disconnect`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getAuthToken()}`,
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to disconnect: ${response.statusText}`);
    }

    const data = await response.json();
    console.log('Session disconnected:', data);
    return data;
  } catch (error) {
    console.error('Disconnect error:', error);
    throw error;
  }
}

/**
 * Retry failed launch
 */
export async function retryLaunch(sessionId) {
  try {
    const response = await fetch(`${LAUNCHER_API_URL}/launch/retry`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getAuthToken()}`,
      },
      body: JSON.stringify({
        session_id: sessionId,
      }),
    });

    if (!response.ok) {
      throw new Error(`Retry failed: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Retry error:', error);
    throw error;
  }
}

/**
 * Monitor session with polling
 * Returns unsubscribe function
 */
export function monitorSession(sessionId, onUpdate, onError, pollInterval = 2000) {
  let isMonitoring = true;

  const poll = async () => {
    if (!isMonitoring) return;

    try {
      const session = await getSession(sessionId);
      onUpdate?.(session);

      // Stop polling if session ended
      if (['disconnected', 'failed', 'closed'].includes(session.status)) {
        isMonitoring = false;
        return;
      }

      // Continue polling
      setTimeout(poll, pollInterval);
    } catch (error) {
      onError?.(error);
      // Retry on error
      setTimeout(poll, pollInterval * 2);
    }
  };

  // Start polling
  poll();

  // Return unsubscribe function
  return () => {
    isMonitoring = false;
  };
}

/**
 * Get auth token from storage
 */
function getAuthToken() {
  let token = localStorage.getItem('auth_token');
  if (!token) {
    token = sessionStorage.getItem('auth_token');
  }
  if (!token) {
    token = process.env.REACT_APP_AUTH_TOKEN;
  }
  return token || '';
}
