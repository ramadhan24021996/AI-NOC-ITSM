# PC Client Remote Actions and Notifications Integration Plan

This plan details the changes required to link the mockup **Printer Status** actions on the dashboard with the active Windows monitoring client (`agent_device.py`), enabling desktop notifications and full remote commands control down to the client device.

## User Review Required

> [!IMPORTANT]
> **PowerShell Notification Fallback**:
> Since Python lacks cross-platform notification APIs out-of-the-box, we will utilize a lightweight PowerShell command to display native Windows System Tray notifications (Balloon Tips) on the PC Client without installing third-party Python packages.
> 
> **Printer Host Agent Mapping**:
> We will write a helper `_findHostAgent(printerName)` inside `Panels.printer` in `index.html` to scan `DataService._devices` and identify which PC client currently hosts the printer, ensuring commands are sent to the correct target device.
> 
> **Agent Remote Command Expansion**:
> We will expand the commands supported by `agent_device.py` to handle the full list of dashboard commands:
> - `TEST_PRINT` (Initiates raw print job)
> - `CLEAR_SPOOLER` (Stops spooler, wipes print queues, restarts spooler)
> - `RESTART_SPOOLER` (Restarts the Windows print spooler service)
> - `RECONNECT_PRINTER` (Triggers hardware re-scan)
> - `CMD` (Executes remote cmd)
> - `POWERSHELL` (Executes remote powershell scripts)
> - `RESTART` / `SHUTDOWN` (Schedules system shutdown/restarts with a 10s grace warning)

---

## Proposed Changes

### 1. Windows PC Client Agent
#### [MODIFY] [agent_device.py](file:///d:/AI-AGEN%20DRIVEN%20INTELLIGENT%20INCIDENT%20ANALIS/CLIENT_DISTRIBUSI/agent_device.py)
- **Desktop Toast Notification**: Add `show_desktop_notification(title, message)` that spawns a PowerShell System Tray balloon tip.
- **Implement New Command Handlers**:
  - Add `CMD` and `POWERSHELL` command blocks in `execute_agent_command` to execute shell processes and return stdout/stderr, showing desktop alerts.
  - Add `RESTART` and `SHUTDOWN` commands to schedule native Windows shutdowns with warning popups.
  - Add `RESTART_SPOOLER`, `CLEAR_SPOOLER`, and `RECONNECT_PRINTER` to stop/start Windows print spooler services and perform hardware audits.
  - Connect existing `TEST_PRINT` and `PING` handlers to show desktop toasts when received.

### 2. Frontend HTML & JS
#### [MODIFY] [index.html](file:///d:/AI-AGEN%20DRIVEN%20INTELLIGENT%20INCIDENT%20ANALIS/portal/templates/index.html)
- **Host Resolution Helper**: Add `_findHostAgent(printerName)` inside `Panels.printer` to identify the host PC name.
- **Printer Status Actions**:
  - Update `clearQueue(name)` to call `DataService.sendCommand('CLEAR_SPOOLER', host, { printer_name: name })`.
  - Update `restartService(name)` to call `DataService.sendCommand('RESTART_SPOOLER', host, { printer_name: name })`.
  - Update `reconnect(name)` to call `DataService.sendCommand('RECONNECT_PRINTER', host, { printer_name: name })`.
  - Update `printTest(name)` to call `DataService.sendCommand('TEST_PRINT', host, { printer_name: name })`.

---

## Verification Plan

### Automated Tests
- Run Node.js compiler syntax check on `index.html`.
- Compile check `agent_device.py` to ensure it is error-free.

### Manual Verification
- Go to the **Printer Status** tab.
- Click **Test Print** on `Printer-Accounting-01` or `Printer-HR-01` and verify that the local Windows system tray shows the notification *"NOC Test Print"* and the printer status remains synchronized.
- Click **Restart** on a printer card and check that the Windows print spooler service is restarted and the system tray notification appears.
- Navigate to the **Model Config** panel, select the target PC client, choose **Run CMD**, execute a command (e.g. `whoami`), and verify the result returns to the dashboard output log and shows a desktop notice on the client machine.
