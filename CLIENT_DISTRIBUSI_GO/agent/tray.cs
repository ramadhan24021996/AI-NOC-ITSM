using System;
using System.Drawing;
using System.Windows.Forms;
using System.Net.Sockets;
using System.Text;
using System.IO;
using System.Threading;
using System.Diagnostics;

namespace AgentTray
{
    public class TrayApplicationContext : ApplicationContext
    {
        private NotifyIcon notifyIcon;
        private ContextMenuStrip contextMenu;
        private ToolStripMenuItem openChatItem;
        private ToolStripMenuItem openDashboardItem;
        private ToolStripMenuItem pauseResumeItem;
        private ToolStripMenuItem testConnectionItem;
        private ToolStripMenuItem exitItem;

        private System.Windows.Forms.Timer pollTimer;
        private string currentState = "CONNECTING";
        private string serverIP = "10.20.0.163";
        private string deviceName = "";
        private string version = "";
        private IntPtr currentHicon = IntPtr.Zero;
        
        private ChatForm chatForm = null;

        [System.Runtime.InteropServices.DllImport("user32.dll", CharSet = System.Runtime.InteropServices.CharSet.Auto)]
        private static extern bool DestroyIcon(IntPtr handle);

        public TrayApplicationContext()
        {
            // Initialize Context Menu
            contextMenu = new ContextMenuStrip();

            openChatItem = new ToolStripMenuItem("Open Support Chat", null, OpenChat_Click);
            openDashboardItem = new ToolStripMenuItem("Open NOC Dashboard", null, OpenDashboard_Click);
            pauseResumeItem = new ToolStripMenuItem("Pause Monitoring", null, PauseResume_Click);
            testConnectionItem = new ToolStripMenuItem("Test Connection", null, TestConnection_Click);
            exitItem = new ToolStripMenuItem("Exit Tray", null, Exit_Click);

            contextMenu.Items.Add(openChatItem);
            contextMenu.Items.Add(new ToolStripSeparator());
            contextMenu.Items.Add(openDashboardItem);
            contextMenu.Items.Add(pauseResumeItem);
            contextMenu.Items.Add(testConnectionItem);
            contextMenu.Items.Add(new ToolStripSeparator());
            contextMenu.Items.Add(exitItem);

            // Initialize NotifyIcon
            notifyIcon = new NotifyIcon();
            notifyIcon.ContextMenuStrip = contextMenu;
            notifyIcon.Visible = true;
            notifyIcon.Text = "OSI AI Agent\nInitializing...";
            notifyIcon.DoubleClick += NotifyIcon_DoubleClick;
            notifyIcon.BalloonTipClicked += (s, e) => {
                ShowChatWindow();
            };

            UpdateStatusIcon("CONNECTING");

            // Setup polling timer
            pollTimer = new System.Windows.Forms.Timer();
            pollTimer.Interval = 2000; // 2 seconds
            pollTimer.Tick += PollTimer_Tick;
            pollTimer.Start();

            // Perform initial poll immediately
            PollStatus();

            // Initialize ChatForm in the background to listen for notifications
            if (chatForm == null)
            {
                chatForm = new ChatForm(serverIP, this);
            }
        }

        private void PollTimer_Tick(object sender, EventArgs e)
        {
            PollStatus();
        }

        private void PollStatus()
        {
            try
            {
                using (TcpClient client = new TcpClient())
                {
                    var result = client.BeginConnect("127.0.0.1", 10000, null, null);
                    var success = result.AsyncWaitHandle.WaitOne(TimeSpan.FromSeconds(1));
                    if (!success)
                    {
                        throw new SocketException();
                    }
                    client.EndConnect(result);

                    using (NetworkStream stream = client.GetStream())
                    {
                        stream.ReadTimeout = 1000;
                        stream.WriteTimeout = 1000;

                        // Send GET_STATUS command
                        byte[] cmdBytes = Encoding.UTF8.GetBytes("{\"command\":\"GET_STATUS\"}\n");
                        stream.Write(cmdBytes, 0, cmdBytes.Length);

                        // Read response
                        byte[] buffer = new byte[4096];
                        int bytesRead = stream.Read(buffer, 0, buffer.Length);
                        string response = Encoding.UTF8.GetString(buffer, 0, bytesRead).Trim();

                        ParseResponse(response);
                    }
                }
            }
            catch (Exception)
            {
                currentState = "OFFLINE";
                UpdateStatusIcon("OFFLINE");
                notifyIcon.Text = "OSI AI Agent\nStatus: Offline (Cannot reach Service)";
            }
        }

        private void ParseResponse(string json)
        {
            // Simple manual JSON parsing to avoid dependencies
            try
            {
                string state = GetJsonValue(json, "state");
                string ip = GetJsonValue(json, "server_ip");
                string dev = GetJsonValue(json, "device_name");
                string ver = GetJsonValue(json, "version");

                if (!string.IsNullOrEmpty(state)) currentState = state;
                if (!string.IsNullOrEmpty(ip))
                {
                    serverIP = ip;
                    if (chatForm != null && !chatForm.IsDisposed)
                    {
                        chatForm.serverIP = serverIP;
                    }
                }
                if (!string.IsNullOrEmpty(dev)) deviceName = dev;
                if (!string.IsNullOrEmpty(ver)) version = ver;

                UpdateStatusIcon(currentState);

                // Update context menu items based on state
                if (currentState == "PAUSED")
                {
                    pauseResumeItem.Text = "Resume Monitoring";
                }
                else
                {
                    pauseResumeItem.Text = "Pause Monitoring";
                }

                // Update tooltip text (max 63 chars in Windows Forms NotifyIcon)
                string tooltip = string.Format("OSI AI Agent\nDev: {0}\nIP: {1}\nStatus: {2}", 
                    deviceName, serverIP, currentState);
                if (tooltip.Length > 63)
                {
                    tooltip = tooltip.Substring(0, 60) + "...";
                }
                notifyIcon.Text = tooltip;
            }
            catch
            {
                // Fallback
                UpdateStatusIcon("OFFLINE");
            }
        }

        private string GetJsonValue(string json, string key)
        {
            string searchKey = "\"" + key + "\":";
            int index = json.IndexOf(searchKey);
            if (index == -1) return "";

            int start = index + searchKey.Length;
            // Find next char
            while (start < json.Length && (char.IsWhiteSpace(json[start]) || json[start] == '"' || json[start] == ':'))
            {
                start++;
            }

            int end = start;
            if (json[start - 1] == '"')
            {
                // String value: read until next quote
                while (end < json.Length && json[end] != '"')
                {
                    end++;
                }
            }
            else
            {
                // Non-string value: read until comma or bracket
                while (end < json.Length && json[end] != ',' && json[end] != '}' && json[end] != ']')
                {
                    end++;
                }
            }

            if (end > start)
            {
                return json.Substring(start, end - start).Trim();
            }
            return "";
        }

        private void UpdateStatusIcon(string status)
        {
            try
            {
                using (Bitmap bmp = new Bitmap(16, 16))
                {
                    using (Graphics g = Graphics.FromImage(bmp))
                    {
                        g.Clear(Color.Transparent);
                        Brush brush = Brushes.Gray;
                        if (status == "ONLINE") brush = Brushes.LimeGreen;
                        else if (status == "CONNECTING") brush = Brushes.Gold;
                        else if (status == "OFFLINE") brush = Brushes.Red;
                        else if (status == "UPDATING") brush = Brushes.DeepSkyBlue;
                        else if (status == "PAUSED") brush = Brushes.DarkGray;
                        else if (status == "ERROR") brush = Brushes.Orange;

                        // Antialiasing for smooth circle
                        g.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.AntiAlias;

                        // Draw background circle
                        g.FillEllipse(brush, 1, 1, 14, 14);
                        g.DrawEllipse(Pens.Black, 1, 1, 14, 14);
                    }

                    Icon oldIcon = notifyIcon.Icon;
                    IntPtr oldHicon = currentHicon;
                    currentHicon = bmp.GetHicon();
                    notifyIcon.Icon = Icon.FromHandle(currentHicon);

                    if (oldIcon != null)
                    {
                        try { oldIcon.Dispose(); } catch { }
                    }
                    if (oldHicon != IntPtr.Zero)
                    {
                        DestroyIcon(oldHicon);
                    }
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine("Error drawing icon: " + ex.Message);
            }
        }

        private void OpenDashboard_Click(object sender, EventArgs e)
        {
            try
            {
                string url = string.Format("http://{0}:8099", serverIP);
                Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });
            }
            catch (Exception ex)
            {
                MessageBox.Show("Failed to open NOC Dashboard: " + ex.Message, "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private void PauseResume_Click(object sender, EventArgs e)
        {
            string cmd = (currentState == "PAUSED") ? "RESUME_MONITORING" : "PAUSE_MONITORING";
            SendCommand(cmd);
            PollStatus();
        }

        private void TestConnection_Click(object sender, EventArgs e)
        {
            PollStatus();
            MessageBox.Show(string.Format("Connection status tested.\nState: {0}\nTarget IP: {1}", currentState, serverIP), 
                "Connection Test", MessageBoxButtons.OK, MessageBoxIcon.Information);
        }

        private void SendCommand(string command)
        {
            try
            {
                using (TcpClient client = new TcpClient("127.0.0.1", 10000))
                using (NetworkStream stream = client.GetStream())
                {
                    byte[] cmdBytes = Encoding.UTF8.GetBytes(string.Format("{{\"command\":\"{0}\"}}\n", command));
                    stream.Write(cmdBytes, 0, cmdBytes.Length);
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show("Failed to send command to service: " + ex.Message, "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private void OpenChat_Click(object sender, EventArgs e)
        {
            ShowChatWindow();
        }

        private void NotifyIcon_DoubleClick(object sender, EventArgs e)
        {
            ShowChatWindow();
        }

        private void ShowChatWindow()
        {
            if (chatForm == null || chatForm.IsDisposed)
            {
                chatForm = new ChatForm(serverIP, this);
            }
            chatForm.Show();
            chatForm.WindowState = FormWindowState.Normal;
            chatForm.Activate();
            chatForm.Focus();
        }

        public void ShowNotification(string title, string message)
        {
            if (notifyIcon != null)
            {
                notifyIcon.ShowBalloonTip(3000, title, message, ToolTipIcon.Info);
            }
        }

        private void Exit_Click(object sender, EventArgs e)
        {
            notifyIcon.Visible = false;
            if (currentHicon != IntPtr.Zero)
            {
                DestroyIcon(currentHicon);
            }
            if (chatForm != null)
            {
                try { chatForm.Dispose(); } catch { }
            }
            Application.Exit();
        }
    }

    public static class Program
    {
        [STAThread]
        public static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new TrayApplicationContext());
        }
    }
}
