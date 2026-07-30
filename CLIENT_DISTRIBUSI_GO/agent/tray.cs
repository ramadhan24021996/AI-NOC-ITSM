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
        private ToolStripMenuItem pauseResumeItem;
        private ToolStripMenuItem testConnectionItem;
        private ToolStripMenuItem exitItem;

        private System.Windows.Forms.Timer pollTimer;
        private string currentState = "CONNECTING";
        private string serverIP = "10.20.0.154";
        private string deviceName = "";
        private string version = "";
        private IntPtr currentHicon = IntPtr.Zero;
        private SynchronizationContext syncContext;
        
        private ChatForm chatForm = null;

        [System.Runtime.InteropServices.DllImport("user32.dll", CharSet = System.Runtime.InteropServices.CharSet.Auto)]
        private static extern bool DestroyIcon(IntPtr handle);

        public TrayApplicationContext()
        {
            syncContext = SynchronizationContext.Current ?? new SynchronizationContext();

            // Initialize Context Menu
            contextMenu = new ContextMenuStrip();

            openChatItem = new ToolStripMenuItem("Open Support Chat", null, OpenChat_Click);
            pauseResumeItem = new ToolStripMenuItem("Pause Monitoring", null, PauseResume_Click);
            testConnectionItem = new ToolStripMenuItem("Test Connection", null, TestConnection_Click);
            exitItem = new ToolStripMenuItem("Exit Tray", null, Exit_Click);

            contextMenu.Items.Add(openChatItem);
            contextMenu.Items.Add(new ToolStripSeparator());
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

            // Setup polling timer (3s)
            pollTimer = new System.Windows.Forms.Timer();
            pollTimer.Interval = 3000;
            pollTimer.Tick += PollTimer_Tick;
            pollTimer.Start();

            // Perform initial poll asynchronously in background thread
            ThreadPool.QueueUserWorkItem(_ => PollStatus());

            // Initialize ChatForm in the background to listen for notifications
            if (chatForm == null)
            {
                chatForm = new ChatForm(serverIP, this);
            }

            // Start local listener for UI Commands (port 10001)
            Thread listenerThread = new Thread(new ThreadStart(StartLocalServer));
            listenerThread.IsBackground = true;
            listenerThread.Start();
        }

        private void StartLocalServer()
        {
            try
            {
                TcpListener listener = new TcpListener(System.Net.IPAddress.Parse("127.0.0.1"), 10001);
                listener.Start();
                while (true)
                {
                    TcpClient client = listener.AcceptTcpClient();
                    ThreadPool.QueueUserWorkItem(HandleLocalClient, client);
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine("Local UI listener failed: " + ex.Message);
            }
        }

        private void HandleLocalClient(object obj)
        {
            TcpClient client = (TcpClient)obj;
            try
            {
                using (NetworkStream stream = client.GetStream())
                {
                    byte[] buffer = new byte[4096];
                    int bytesRead = stream.Read(buffer, 0, buffer.Length);
                    if (bytesRead > 0)
                    {
                        string json = Encoding.UTF8.GetString(buffer, 0, bytesRead).Trim();
                        string cmd = GetJsonValue(json, "command");

                        if (cmd == "SHOW_NOTIFICATION")
                        {
                            string title = GetJsonValue(json, "title");
                            string msg = GetJsonValue(json, "message");
                            if (string.IsNullOrEmpty(title)) title = "OSI AI Alert";
                            if (string.IsNullOrEmpty(msg)) msg = "A new alert was triggered.";

                            // Invoke on UI Thread
                            if (notifyIcon != null && notifyIcon.Visible)
                            {
                                // We can't use Control.Invoke here easily without a Form, but NotifyIcon is COM object
                                // However, it's safer to invoke it via a hidden dummy form or the ChatForm if it exists
                                if (chatForm != null && chatForm.IsHandleCreated)
                                {
                                    chatForm.Invoke(new Action(() => {
                                        notifyIcon.ShowBalloonTip(5000, title, msg, ToolTipIcon.Warning);
                                    }));
                                }
                                else
                                {
                                    notifyIcon.ShowBalloonTip(5000, title, msg, ToolTipIcon.Warning);
                                }
                            }
                        }
                        else if (cmd == "SHOW_CHAT")
                        {
                            string ip = GetJsonValue(json, "server_ip");
                            if (!string.IsNullOrEmpty(ip))
                            {
                                serverIP = ip;
                                if (chatForm != null) chatForm.serverIP = serverIP;
                            }
                            if (chatForm != null && chatForm.IsHandleCreated)
                            {
                                chatForm.Invoke(new Action(() => { ShowChatWindow(); }));
                            }
                            else
                            {
                                // It might fail if no message loop, but TrayApplicationContext runs a message loop
                                ShowChatWindow();
                            }
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine("Error handling local command: " + ex.Message);
            }
            finally
            {
                client.Close();
            }
        }

        private void PollTimer_Tick(object sender, EventArgs e)
        {
            ThreadPool.QueueUserWorkItem(_ => PollStatus());
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
                syncContext.Post(_ => {
                    UpdateStatusIcon("OFFLINE");
                    notifyIcon.Text = "OSI AI Agent\nStatus: Offline (Cannot reach Service)";
                }, null);
            }
        }

        private void ParseResponse(string json)
        {
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

                syncContext.Post(_ => {
                    UpdateStatusIcon(currentState);

                    if (currentState == "PAUSED")
                    {
                        pauseResumeItem.Text = "Resume Monitoring";
                    }
                    else
                    {
                        pauseResumeItem.Text = "Pause Monitoring";
                    }

                    string tooltip = string.Format("OSI AI Agent\nDev: {0}\nIP: {1}\nStatus: {2}", 
                        deviceName, serverIP, currentState);
                    if (tooltip.Length > 63)
                    {
                        tooltip = tooltip.Substring(0, 60) + "...";
                    }
                    notifyIcon.Text = tooltip;
                }, null);
            }
            catch
            {
                syncContext.Post(_ => UpdateStatusIcon("OFFLINE"), null);
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
                int size = 32;
                using (Bitmap bmp = new Bitmap(size, size))
                {
                    using (Graphics g = Graphics.FromImage(bmp))
                    {
                        g.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.AntiAlias;
                        g.TextRenderingHint = System.Drawing.Text.TextRenderingHint.ClearTypeGridFit;

                        // 1. Draw rounded shield/badge background
                        using (Brush bgBrush = new SolidBrush(Color.FromArgb(15, 23, 42))) // Dark Slate #0f172a
                        {
                            g.FillRectangle(bgBrush, 0, 0, size, size);
                        }
                        using (Pen borderPen = new Pen(Color.FromArgb(6, 182, 212), 2.0f)) // Cyan border #06b6d4
                        {
                            g.DrawRectangle(borderPen, 1, 1, size - 2, size - 2);
                        }

                        // 2. Draw "OSI" emblem text in center
                        using (Font font = new Font("Segoe UI", 9, FontStyle.Bold))
                        {
                            using (Brush textBrush = new SolidBrush(Color.FromArgb(248, 250, 252)))
                            {
                                StringFormat sf = new StringFormat
                                {
                                    Alignment = StringAlignment.Center,
                                    LineAlignment = StringAlignment.Center
                                };
                                g.DrawString("OSI", font, textBrush, new RectangleF(0, 0, size, size - 2), sf);
                            }
                        }

                        // 3. Status LED Indicator dot at bottom right
                        Brush dotBrush = Brushes.LimeGreen;
                        if (status == "ONLINE") dotBrush = Brushes.LimeGreen;
                        else if (status == "CONNECTING") dotBrush = Brushes.Gold;
                        else if (status == "OFFLINE") dotBrush = Brushes.Red;
                        else if (status == "UPDATING") dotBrush = Brushes.DeepSkyBlue;
                        else if (status == "PAUSED") dotBrush = Brushes.DarkGray;
                        else if (status == "ERROR") dotBrush = Brushes.Orange;

                        int dotSize = 8;
                        g.FillEllipse(dotBrush, size - dotSize - 2, size - dotSize - 2, dotSize, dotSize);
                        g.DrawEllipse(Pens.Black, size - dotSize - 2, size - dotSize - 2, dotSize, dotSize);
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
