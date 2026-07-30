using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Windows.Forms;
using System.IO;
using System.Net;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Collections.Generic;
using System.Web.Script.Serialization;
using System.Management;
using System.Diagnostics;

namespace AgentTray
{
    public class ChatMessageModel
    {
        public uint ID { get; set; }
        public string ClientID { get; set; }
        public string Sender { get; set; }
        public string Message { get; set; }
        public string AttachmentPath { get; set; }
        public string ReadStatus { get; set; } // SENT, DELIVERED, READ, PENDING
        public DateTime CreatedAt { get; set; }
        public string LocalGuid { get; set; }
    }

    public class MessageBubble : Control
    {
        public ChatMessageModel Model { get; private set; }
        public string MessageText { get { return Model.Message; } }
        public string AttachmentPath { get { return Model.AttachmentPath; } }
        
        private Image attachmentImage = null;
        private bool imageLoaded = false;
        private string serverIP;
        private ChatForm parentForm;
        private Button btnResolve = null;
        private Button btnEscalate = null;
        private LinkLabel lnkExpand = null;
        private bool isExpanded = false;
        private int computedHeight = 55;
        private string CleanHtmlMessage(string input)
        {
            if (string.IsNullOrEmpty(input)) return "";
            return input.Replace("<b>", "").Replace("</b>", "")
                        .Replace("<i>", "").Replace("</i>", "")
                        .Replace("<strong>", "").Replace("</strong>", "")
                        .Replace("<br>", "\n").Replace("<br/>", "\n").Replace("<br />", "\n");
        }

        public MessageBubble(ChatMessageModel model, string serverIP, ChatForm parentForm)
        {
            this.Model = model;
            this.serverIP = serverIP;
            this.parentForm = parentForm;
            this.DoubleBuffered = true;
            this.BackColor = Color.FromArgb(18, 18, 20); // match messagePanel background
            this.Width = 310;

            // Create interactive controls if this is an Incident Card
            if (model.Sender == "SYSTEM" && model.Message.Contains("🚨 INCIDENT TERDETEKSI"))
            {
                uint incidentID = 0;
                try
                {
                    string idSearch = "<b>Incident ID:</b> ";
                    int idx = model.Message.IndexOf(idSearch);
                    if (idx != -1)
                    {
                        int start = idx + idSearch.Length;
                        int end = model.Message.IndexOf("\n", start);
                        if (end != -1)
                        {
                            string idStr = model.Message.Substring(start, end - start).Trim();
                            uint.TryParse(idStr, out incidentID);
                        }
                    }
                }
                catch {}

                lnkExpand = new LinkLabel();
                lnkExpand.Text = "▽ Lihat Detail Analisa";
                lnkExpand.LinkColor = Color.FromArgb(129, 140, 248);
                lnkExpand.ActiveLinkColor = Color.FromArgb(99, 102, 241);
                lnkExpand.VisitedLinkColor = Color.FromArgb(129, 140, 248);
                lnkExpand.Font = new Font("Segoe UI", 8f, FontStyle.Regular);
                lnkExpand.Size = new Size(120, 16);
                lnkExpand.Cursor = Cursors.Hand;
                lnkExpand.LinkClicked += (s, ev) => {
                    isExpanded = !isExpanded;
                    lnkExpand.Text = isExpanded ? "△ Sembunyikan Detail" : "▽ Lihat Detail Analisa";
                    CalculateHeight();
                    this.Height = computedHeight;
                    this.parentForm.ScrollToBottom();
                };
                this.Controls.Add(lnkExpand);

                btnResolve = new Button();
                btnResolve.Text = "✔ Saya Sudah Memperbaiki";
                btnResolve.FlatStyle = FlatStyle.Flat;
                btnResolve.FlatAppearance.BorderSize = 0;
                btnResolve.BackColor = Color.FromArgb(16, 185, 129); // green-500
                btnResolve.ForeColor = Color.White;
                btnResolve.Font = new Font("Segoe UI", 8f, FontStyle.Bold);
                btnResolve.Size = new Size(130, 26);
                btnResolve.Cursor = Cursors.Hand;
                btnResolve.Click += (s, ev) => {
                    DisableButtons();
                    var evMsg = new Dictionary<string, object>();
                    evMsg["type"] = "resolve_incident";
                    evMsg["client_id"] = parentForm.clientUUID;
                    var data = new Dictionary<string, object>();
                    data["incident_id"] = incidentID;
                    evMsg["data"] = data;
                    parentForm.SendWSMessage(new JavaScriptSerializer().Serialize(evMsg));
                };
                this.Controls.Add(btnResolve);

                btnEscalate = new Button();
                btnEscalate.Text = "💬 Hubungi NOC";
                btnEscalate.FlatStyle = FlatStyle.Flat;
                btnEscalate.FlatAppearance.BorderSize = 0;
                btnEscalate.BackColor = Color.FromArgb(239, 68, 68); // red-500
                btnEscalate.ForeColor = Color.White;
                btnEscalate.Font = new Font("Segoe UI", 8f, FontStyle.Bold);
                btnEscalate.Size = new Size(130, 26);
                btnEscalate.Cursor = Cursors.Hand;
                btnEscalate.Click += (s, ev) => {
                    DisableButtons();
                    var evMsg = new Dictionary<string, object>();
                    evMsg["type"] = "escalate_incident";
                    evMsg["client_id"] = parentForm.clientUUID;
                    var data = new Dictionary<string, object>();
                    data["incident_id"] = incidentID;
                    evMsg["data"] = data;
                    parentForm.SendWSMessage(new JavaScriptSerializer().Serialize(evMsg));
                };
                this.Controls.Add(btnEscalate);

                UpdateCardState();
            }

            CalculateHeight();
            
            if (!string.IsNullOrEmpty(model.AttachmentPath))
            {
                LoadAttachment();
            }
        }

        public void UpdateModel(Dictionary<string, object> data)
        {
            if (data.ContainsKey("message"))
                this.Model.Message = data["message"].ToString();
            if (data.ContainsKey("attachment_path"))
                this.Model.AttachmentPath = data["attachment_path"].ToString();
            if (data.ContainsKey("read_status"))
                this.Model.ReadStatus = data["read_status"].ToString();

            CalculateHeight();
            
            if (!string.IsNullOrEmpty(Model.AttachmentPath))
            {
                LoadAttachment();
            }

            UpdateCardState();

            this.Invalidate();
        }

        private void UpdateCardState()
        {
            string msgText = Model.Message;
            string status = "OPEN";
            if (msgText.Contains("<b>Status:</b> RESOLVED")) status = "RESOLVED";
            else if (msgText.Contains("<b>Status:</b> WAITING NOC")) status = "WAITING NOC";

            if (status == "RESOLVED" || status == "WAITING NOC")
            {
                if (btnResolve != null)
                {
                    btnResolve.Enabled = false;
                    btnResolve.BackColor = Color.FromArgb(75, 85, 99);
                    btnResolve.Text = status == "RESOLVED" ? "✔ Teratasi" : "✔ Saya Sudah Memperbaiki";
                }
                if (btnEscalate != null)
                {
                    btnEscalate.Enabled = false;
                    btnEscalate.BackColor = Color.FromArgb(75, 85, 99);
                    btnEscalate.Text = status == "WAITING NOC" ? "💬 NOC Dihubungi" : "💬 Hubungi NOC";
                }
            }
            else
            {
                if (btnResolve != null)
                {
                    btnResolve.Enabled = true;
                    btnResolve.BackColor = Color.FromArgb(16, 185, 129);
                    btnResolve.Text = "✔ Saya Sudah Memperbaiki";
                }
                if (btnEscalate != null)
                {
                    btnEscalate.Enabled = true;
                    btnEscalate.BackColor = Color.FromArgb(239, 68, 68);
                    btnEscalate.Text = "💬 Hubungi NOC";
                }
            }
        }

        private void DisableButtons()
        {
            if (btnResolve != null) { btnResolve.Enabled = false; btnResolve.BackColor = Color.Gray; }
            if (btnEscalate != null) { btnEscalate.Enabled = false; btnEscalate.BackColor = Color.Gray; }
        }

        protected override void OnLayout(LayoutEventArgs levent)
        {
            base.OnLayout(levent);
            if (btnResolve != null && btnEscalate != null)
            {
                int leftMargin = 30 + 8 + 4; // 42
                int bubbleWidth = this.Width - leftMargin - 20;
                int bubbleX     = leftMargin;

                int textHeight = 0;
                using (Graphics g = this.CreateGraphics())
                {
                    Font font = new Font("Segoe UI", 9.5f);
                    SizeF size = g.MeasureString(string.IsNullOrEmpty(Model.Message) ? " " : Model.Message, font, bubbleWidth - 20);
                    textHeight = (int)Math.Ceiling(size.Height);
                }

                int nameOffset = 16;
                int attachHeight = 0;
                if (!string.IsNullOrEmpty(Model.AttachmentPath))
                {
                    attachHeight = IsImagePath(Model.AttachmentPath) ? 130 : 50;
                }

                int contentBottom = 6 + nameOffset + textHeight + attachHeight + 12;

                if (lnkExpand != null)
                {
                    lnkExpand.Location = new Point(bubbleX + 10, contentBottom + 5);
                }

                btnResolve.Location = new Point(bubbleX + 10, this.Height - 38);
                btnResolve.Width = (bubbleWidth - 30) / 2;

                btnEscalate.Location = new Point(bubbleX + 10 + btnResolve.Width + 10, this.Height - 38);
                btnEscalate.Width = (bubbleWidth - 30) / 2;
            }
        }

        private void CalculateHeight()
        {
            int height = 8; // Top padding
            bool isClient = Model.Sender == "CLIENT";
            bool isSystem = Model.Sender == "SYSTEM" || Model.Sender == "AI_HYPOTHESIS";

            // Sender name label (for non-client)
            if (!isClient)
                height += 16;

            string cleanMsg = CleanHtmlMessage(Model.Message);

            int bubbleWidth = isClient ? 240 : (isSystem ? (this.Width - 42 - 20) : 240);
            if (bubbleWidth < 120) bubbleWidth = 240;

            using (Graphics g = this.CreateGraphics())
            {
                Font font = new Font("Segoe UI", 9.5f);
                SizeF size = g.MeasureString(string.IsNullOrEmpty(cleanMsg) ? " " : cleanMsg, font, bubbleWidth - 20);
                height += (int)Math.Ceiling(size.Height) + 8; // Extra padding for text lines
            }

            if (!string.IsNullOrEmpty(Model.AttachmentPath))
            {
                height += IsImagePath(Model.AttachmentPath) ? 130 : 50;
            }

            height += 22; // Timestamp & status
            
            if (Model.Sender == "SYSTEM" && Model.Message.Contains("🚨 INCIDENT TERDETEKSI"))
            {
                height += 25; // Extra space for lnkExpand
                height += 40; // Space for Timeline
                if (isExpanded)
                {
                    height += 80; // Space for details
                }
                height += 36; // Extra space for buttons
            }

            height += 12;  // Bottom padding

            this.Height = computedHeight = Math.Max(height, 55);
        }

        private string CleanHtmlMessage(string input)
        {
            if (string.IsNullOrEmpty(input)) return "";
            string cleaned = input.Replace("<b>", "").Replace("</b>", "")
                                  .Replace("<i>", "").Replace("</i>", "")
                                  .Replace("<strong>", "").Replace("</strong>", "")
                                  .Replace("<em>", "").Replace("</em>", "")
                                  .Replace("<br>", "\n").Replace("<br/>", "\n").Replace("<br />", "\n");

            // Replace unsupported UTF-32 Emojis with clean WinForms compatible symbols
            cleaned = cleaned.Replace("🤖", "[AI]")
                             .Replace("💡", "[Tip]")
                             .Replace("⚙", "[Sys]")
                             .Replace("🚨", "[Alert]")
                             .Replace("🟢", "●")
                             .Replace("🔴", "●")
                             .Replace("⚠️", "[!]");
            return cleaned;
        }

        private bool IsImagePath(string path)
        {
            string ext = Path.GetExtension(path).ToLower();
            return ext == ".png" || ext == ".jpg" || ext == ".jpeg" || ext == ".gif" || ext == ".bmp";
        }

        private void SafeInvoke(Action action)
        {
            if (this.IsDisposed || !this.IsHandleCreated) return;
            try {
                if (this.InvokeRequired) {
                    this.Invoke((MethodInvoker)delegate { action(); });
                } else {
                    action();
                }
            } catch { }
        }

        private void LoadAttachment()
        {
            if (IsImagePath(Model.AttachmentPath))
            {
                Task.Run(() => {
                    try
                    {
                        string url = string.Format("http://{0}/{1}", serverIP, Model.AttachmentPath.Replace('\\', '/'));
                        using (WebClient client = new WebClient())
                        {
                            byte[] data = client.DownloadData(url);
                            using (MemoryStream ms = new MemoryStream(data))
                            {
                                Image img = Image.FromStream(ms);
                                Image thumb = img.GetThumbnailImage(180, 100, null, IntPtr.Zero);
                                SafeInvoke(() => {
                                    attachmentImage = thumb;
                                    imageLoaded = true;
                                    this.Invalidate();
                                });
                            }
                        }
                    }
                    catch { }
                });
            }
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            base.OnPaint(e);
            Graphics g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.TextRenderingHint = System.Drawing.Text.TextRenderingHint.ClearTypeGridFit;

            // Fill background solid to eliminate white artifact borders
            using (SolidBrush bgBrush = new SolidBrush(Color.FromArgb(18, 18, 20)))
            {
                g.FillRectangle(bgBrush, this.ClientRectangle);
            }

            bool isClient = Model.Sender == "CLIENT";
            bool isSystem = Model.Sender == "SYSTEM" || Model.Sender == "AI_HYPOTHESIS";

            Font font     = new Font("Segoe UI", 9.5f);
            Font timeFont = new Font("Segoe UI", 7.5f);
            Font nameFont = new Font("Segoe UI", 8f, FontStyle.Bold);

            int avatarSize = 30;
            int avatarX    = 8;
            int leftMargin = isClient ? 0 : (avatarSize + avatarX + 4); // space for avatar on left

            int bubbleWidth = isClient ? 245 : (isSystem ? (this.Width - leftMargin - 20) : 245);
            if (bubbleWidth < 120) bubbleWidth = 245;
            int bubbleX     = isClient ? (this.Width - bubbleWidth - 10) : leftMargin;

            // Current Y offset (accumulates top-down)
            int yOff = 6;
            int nameOffset = 0;

            // Draw sender name for non-client
            if (!isClient)
            {
                string senderName = isSystem
                    ? (Model.Sender == "AI_HYPOTHESIS" ? "[AI] AI Analysis" : "[Sys] System")
                    : "Teknisi IT";
                Color nameColor = isSystem
                    ? Color.FromArgb(129, 140, 248)
                    : Color.FromArgb(52, 211, 153);
                using (SolidBrush nb = new SolidBrush(nameColor))
                    g.DrawString(senderName, nameFont, nb, bubbleX + 8, yOff);
                yOff += 16;
                nameOffset = 16;
            }

            string displayMessage = CleanHtmlMessage(Model.Message);

            // Measure clean text height with linebreaks
            SizeF textSize   = g.MeasureString(string.IsNullOrEmpty(displayMessage) ? " " : displayMessage, font, bubbleWidth - 20);
            int textHeight   = (int)Math.Ceiling(textSize.Height);
            int bubbleHeight = this.Height - yOff - 6;
            int attachOffset = textHeight + 12;

            // Colors
            Color bubbleColor = isClient
                ? Color.FromArgb(37, 99, 235)
                : (Model.Sender == "AI_HYPOTHESIS"
                    ? Color.FromArgb(30, 27, 75)
                    : (Model.Sender == "SYSTEM"
                        ? Color.FromArgb(28, 28, 32)
                        : Color.FromArgb(39, 39, 46)));

            // Draw avatar circle (non-client only)
            if (!isClient)
            {
                int avatarY = yOff + (bubbleHeight / 2) - (avatarSize / 2);
                if (avatarY < yOff) avatarY = yOff;
                using (SolidBrush ab = new SolidBrush(isSystem
                    ? Color.FromArgb(79, 70, 229)
                    : Color.FromArgb(5, 150, 105)))
                {
                    g.FillEllipse(ab, avatarX, avatarY, avatarSize, avatarSize);
                }
                string initials = isSystem ? (Model.Sender == "AI_HYPOTHESIS" ? "AI" : "SY") : "IT";
                using (SolidBrush wb = new SolidBrush(Color.White))
                {
                    Font initFont = new Font("Segoe UI", 8f, FontStyle.Bold);
                    SizeF iSize   = g.MeasureString(initials, initFont);
                    g.DrawString(initials, initFont, wb,
                        avatarX + (avatarSize - iSize.Width) / 2,
                        avatarY + (avatarSize - iSize.Height) / 2);
                }
            }

            // Draw bubble
            using (GraphicsPath path = GetRoundedRectPath(bubbleX, yOff, bubbleWidth, bubbleHeight, 10))
            {
                using (SolidBrush brush = new SolidBrush(bubbleColor))
                    g.FillPath(brush, path);

                if (Model.Sender == "AI_HYPOTHESIS")
                {
                    using (Pen pen = new Pen(Color.FromArgb(129, 140, 248), 1.5f))
                        g.DrawPath(pen, path);
                }
                else if (Model.Sender == "SYSTEM")
                {
                    using (Pen pen = new Pen(Color.FromArgb(63, 63, 70), 1f))
                        g.DrawPath(pen, path);
                }
            }

            // Draw message text
            using (SolidBrush brush = new SolidBrush(Color.White))
                g.DrawString(displayMessage, font, brush,
                    new RectangleF(bubbleX + 10, yOff + 6, bubbleWidth - 20, textHeight + 6));

            int attachHeight = 0;
            // Draw attachment
            if (!string.IsNullOrEmpty(Model.AttachmentPath))
            {
                int attachY = yOff + attachOffset;
                attachHeight = IsImagePath(Model.AttachmentPath) ? 130 : 50;
                if (IsImagePath(Model.AttachmentPath))
                {
                    if (imageLoaded && attachmentImage != null)
                        g.DrawImage(attachmentImage, bubbleX + 8, attachY, 190, 110);
                    else
                    {
                        using (SolidBrush pb = new SolidBrush(Color.FromArgb(55, 55, 65)))
                            g.FillRectangle(pb, bubbleX + 8, attachY, 190, 110);
                        using (SolidBrush tb = new SolidBrush(Color.Gray))
                            g.DrawString("Loading...", font, tb, bubbleX + 60, attachY + 45);
                    }
                }
                else
                {
                    string filename = Path.GetFileName(Model.AttachmentPath);
                    string fileext  = Path.GetExtension(filename).ToUpper().Replace(".", "");
                    using (SolidBrush fb = new SolidBrush(Color.FromArgb(55, 55, 65)))
                        g.FillRectangle(fb, bubbleX + 8, attachY, bubbleWidth - 16, 42);
                    using (SolidBrush ib = new SolidBrush(Color.FromArgb(100, 100, 115)))
                        g.FillRectangle(ib, bubbleX + 12, attachY + 6, 30, 30);
                    using (SolidBrush wb = new SolidBrush(Color.White))
                    {
                        Font ef = new Font("Segoe UI", 7f, FontStyle.Bold);
                        g.DrawString(fileext.Length > 3 ? fileext.Substring(0, 3) : fileext, ef, wb, bubbleX + 14, attachY + 13);
                        Font nf = new Font("Segoe UI", 8f);
                        string dn = filename.Length > 22 ? filename.Substring(0, 19) + "..." : filename;
                        g.DrawString(dn, nf, wb, bubbleX + 48, attachY + 14);
                    }
                }
            }

            // Draw details & timeline if Incident Card
            if (Model.Sender == "SYSTEM" && Model.Message.Contains("🚨 INCIDENT TERDETEKSI"))
            {
                string msgText = Model.Message;
                string status = "OPEN";
                if (msgText.Contains("<b>Status:</b> RESOLVED")) status = "RESOLVED";
                else if (msgText.Contains("<b>Status:</b> WAITING NOC")) status = "WAITING NOC";

                int contentBottom = yOff + nameOffset + textHeight + attachHeight + 12;
                int detailsY = contentBottom + 25;

                if (isExpanded)
                {
                    using (SolidBrush db = new SolidBrush(Color.FromArgb(20, 20, 25)))
                    {
                        g.FillRectangle(db, bubbleX + 10, detailsY, bubbleWidth - 20, 75);
                    }
                    using (Pen dp = new Pen(Color.FromArgb(63, 63, 70), 1f))
                    {
                        g.DrawRectangle(dp, bubbleX + 10, detailsY, bubbleWidth - 20, 75);
                    }

                    string detailsText = string.Format(
                        "Device: {0}\nTime: {1:yyyy-MM-dd HH:mm:ss}\nRef: {2}\nClient ID: {3}",
                        parentForm.pcName, Model.CreatedAt, Model.LocalGuid ?? "N/A", Model.ClientID
                    );
                    using (SolidBrush brush = new SolidBrush(Color.LightGray))
                    {
                        Font detFont = new Font("Segoe UI", 7.5f);
                        g.DrawString(detailsText, detFont, brush, new RectangleF(bubbleX + 15, detailsY + 5, bubbleWidth - 30, 65));
                    }
                }

                int timelineY = isExpanded ? (detailsY + 80) : detailsY;
                int stepWidth = (bubbleWidth - 30) / 4;
                int startX = bubbleX + 15;
                int centerY = timelineY + 10;

                bool step1 = true; 
                bool step2 = true; 
                bool step3 = !string.IsNullOrEmpty(Model.AttachmentPath); 
                bool step4 = (status == "WAITING NOC" || status == "RESOLVED"); 
                bool step5 = (status == "RESOLVED"); 

                using (Pen pGreen = new Pen(Color.FromArgb(16, 185, 129), 2f))
                using (Pen pGray = new Pen(Color.FromArgb(75, 85, 99), 2f))
                {
                    g.DrawLine(step2 ? pGreen : pGray, startX, centerY, startX + stepWidth, centerY);
                    g.DrawLine(step3 ? pGreen : pGray, startX + stepWidth, centerY, startX + stepWidth * 2, centerY);
                    g.DrawLine(step4 ? pGreen : pGray, startX + stepWidth * 2, centerY, startX + stepWidth * 3, centerY);
                    g.DrawLine(step5 ? pGreen : pGray, startX + stepWidth * 3, centerY, startX + stepWidth * 4, centerY);
                }

                string[] labels = { "DET", "AI", "SCR", "NOC", "OK" };
                bool[] steps = { step1, step2, step3, step4, step5 };
                Font labelFont = new Font("Segoe UI", 6.5f);

                for (int i = 0; i < 5; i++)
                {
                    int x = startX + (i * stepWidth);
                    Color circleColor = steps[i] ? Color.FromArgb(16, 185, 129) : Color.FromArgb(75, 85, 99);
                    using (SolidBrush cb = new SolidBrush(circleColor))
                    {
                        g.FillEllipse(cb, x - 4, centerY - 4, 8, 8);
                    }
                    if (steps[i])
                    {
                        using (Pen cp = new Pen(Color.White, 1f))
                            g.DrawEllipse(cp, x - 4, centerY - 4, 8, 8);
                    }

                    using (SolidBrush tb = new SolidBrush(steps[i] ? Color.White : Color.Gray))
                    {
                        SizeF lSize = g.MeasureString(labels[i], labelFont);
                        g.DrawString(labels[i], labelFont, tb, x - (lSize.Width / 2), centerY + 6);
                    }
                }
            }

            // Timestamp & read status
            string timeStr = Model.CreatedAt.ToString("HH:mm");
            if (isClient)
            {
                string statusStr  = "✓✓";
                Color statusColor = Color.FromArgb(147, 197, 253); // blue-300
                if (Model.ReadStatus == "PENDING")
                { statusStr = "⏳"; statusColor = Color.FromArgb(251, 191, 36); }
                else if (Model.ReadStatus == "SENT")
                { statusStr = "✓"; statusColor = Color.FromArgb(161, 161, 170); }
                else if (Model.ReadStatus == "READ")
                { statusStr = "✓✓"; statusColor = Color.FromArgb(56, 189, 248); }

                using (SolidBrush tb = new SolidBrush(Color.FromArgb(199, 210, 254)))
                    g.DrawString(timeStr, timeFont, tb, bubbleX + bubbleWidth - 88, yOff + bubbleHeight - 16);
                using (SolidBrush sb = new SolidBrush(statusColor))
                    g.DrawString(statusStr, timeFont, sb, bubbleX + bubbleWidth - 46, yOff + bubbleHeight - 16);
            }
            else
            {
                using (SolidBrush tb = new SolidBrush(Color.FromArgb(161, 161, 170)))
                    g.DrawString(timeStr, timeFont, tb, bubbleX + bubbleWidth - 38, yOff + bubbleHeight - 16);
            }
        }

        private GraphicsPath GetRoundedRectPath(float x, float y, float width, float height, float radius)
        {
            GraphicsPath path = new GraphicsPath();
            float d = radius * 2;
            path.AddArc(x, y, d, d, 180, 90);
            path.AddArc(x + width - d, y, d, d, 270, 90);
            path.AddArc(x + width - d, y + height - d, d, d, 0, 90);
            path.AddArc(x, y + height - d, d, d, 90, 90);
            path.CloseAllFigures();
            return path;
        }
    }

    public class AttachmentPreviewControl : Panel
    {
        public string FilePath { get; private set; }
        public event EventHandler OnRemove;

        public AttachmentPreviewControl(string filePath)
        {
            this.FilePath = filePath;
            this.Size = new Size(80, 50);
            this.BackColor = Color.FromArgb(39, 39, 42); // zinc-800
            
            PictureBox pb = new PictureBox();
            pb.Size = new Size(50, 40);
            pb.Location = new Point(5, 5);
            pb.SizeMode = PictureBoxSizeMode.Zoom;
            
            string ext = Path.GetExtension(filePath).ToLower();
            if (ext == ".png" || ext == ".jpg" || ext == ".jpeg" || ext == ".gif" || ext == ".bmp")
            {
                try
                {
                    pb.Image = Image.FromFile(filePath);
                }
                catch { }
            }
            else
            {
                Bitmap bmp = new Bitmap(50, 40);
                using (Graphics g = Graphics.FromImage(bmp))
                {
                    g.Clear(Color.FromArgb(113, 113, 122));
                    using (SolidBrush b = new SolidBrush(Color.White))
                    {
                        string displayExt = ext.Replace(".", "").ToUpper();
                        g.DrawString(displayExt.Length > 4 ? displayExt.Substring(0, 3) : displayExt, new Font("Segoe UI", 7f, FontStyle.Bold), b, 10, 15);
                    }
                }
                pb.Image = bmp;
            }
            this.Controls.Add(pb);

            Button btnClose = new Button();
            btnClose.Size = new Size(16, 16);
            btnClose.Location = new Point(60, 2);
            btnClose.Text = "×";
            btnClose.FlatStyle = FlatStyle.Flat;
            btnClose.FlatAppearance.BorderSize = 0;
            btnClose.ForeColor = Color.Red;
            btnClose.BackColor = Color.Transparent;
            btnClose.Font = new Font("Segoe UI", 8f, FontStyle.Bold);
            btnClose.Click += (s, e) => {
                if (OnRemove != null) OnRemove(this, EventArgs.Empty);
            };
            this.Controls.Add(btnClose);
        }
    }

    public class ChatForm : Form
    {
        // Hotkey APIs
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern bool RegisterHotKey(IntPtr hWnd, int id, int fsModifiers, int vlc);
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern bool UnregisterHotKey(IntPtr hWnd, int id);

        private const int HOTKEY_ID = 9001;
        private const int MOD_CONTROL = 0x0002;
        private const int MOD_SHIFT = 0x0004;
        private const int VK_S = 0x53;

        private ClientWebSocket ws;
        public string serverIP;
        public string clientUUID;
        public string pcName;
        private TrayApplicationContext context;
        
        private List<string> selectedFiles = new List<string>();
        private List<ChatMessageModel> offlineQueue = new List<ChatMessageModel>();
        private bool isConnecting = false;
        private bool isTyping = false;
        private DateTime lastSentTypingTime = DateTime.MinValue;
        private uint lastMessageID = 0;

        private System.Windows.Forms.Timer reconnectTimer;
        private System.Windows.Forms.Timer pollFallbackTimer;
        private System.Windows.Forms.Timer typingTimer;

        // UI Controls
        private Panel headerPanel;
        private Label lblTitle;
        private Button btnMinimize;
        private Button btnClose;
        
        private Panel connectionStrip;
        private Label lblConnectionState;
        
        private Panel presencePanel;
        private Label lblPresence;
        private Label lblTypingIndicator;
        
        private Panel searchPanel;
        private TextBox txtSearch;
        
        private FlowLayoutPanel messagePanel;
        private FlowLayoutPanel attachmentPanel;
        
        private Panel inputPanel;
        private TextBox txtMessage;
        private Button btnAttach;
        private Button btnScreenshot;
        private Button btnSend;
        
        private Panel welcomePanel;
        private Label lblWelcomeTitle;
        private Label lblWelcomeDesc;
        private Button btnStartChat;

        // Window drag variables
        private bool drag = false;
        private Point startPoint = new Point(0, 0);

        public ChatForm(string initialServerIP, TrayApplicationContext context = null)
        {
            this.serverIP = initialServerIP;
            this.context = context;
            this.clientUUID = GetClientUUID();
            this.pcName = Environment.MachineName;

            this.Size = new Size(400, 640);
            this.FormBorderStyle = FormBorderStyle.None;
            this.StartPosition = FormStartPosition.CenterScreen;
            this.BackColor = Color.FromArgb(18, 18, 20);
            this.MinimumSize = new Size(380, 500);

            InitializeUI();
            var forceHandle = this.Handle; // Force window handle creation to allow background timers to Invoke
            SetupTimers();

            this.Load += ChatForm_Load;
            this.FormClosing += ChatForm_FormClosing;
        }

        private string GetClientUUID()
        {
            try
            {
                string programData = Environment.GetEnvironmentVariable("PROGRAMDATA");
                if (string.IsNullOrEmpty(programData)) programData = @"C:\ProgramData";
                string path = Path.Combine(programData, @"Company\PC Health Agent\client_uuid.txt");
                if (File.Exists(path))
                {
                    return File.ReadAllText(path).Trim();
                }
            }
            catch { }
            return Guid.NewGuid().ToString();
        }

        private void InitializeUI()
        {
            // 1. Header Panel
            headerPanel = new Panel();
            headerPanel.Size = new Size(this.Width, 40);
            headerPanel.Location = new Point(0, 0);
            headerPanel.BackColor = Color.FromArgb(9, 9, 11); // zinc-950
            headerPanel.MouseDown += (s, e) => { drag = true; startPoint = new Point(e.X, e.Y); };
            headerPanel.MouseMove += (s, e) => {
                if (drag) {
                    Point p = PointToScreen(e.Location);
                    this.Location = new Point(p.X - startPoint.X, p.Y - startPoint.Y);
                }
            };
            headerPanel.MouseUp += (s, e) => { drag = false; };

            lblTitle = new Label();
            lblTitle.Text = "OSI AI Support Chat";
            lblTitle.Font = new Font("Segoe UI", 10f, FontStyle.Bold);
            lblTitle.ForeColor = Color.White;
            lblTitle.Location = new Point(12, 10);
            lblTitle.AutoSize = true;
            headerPanel.Controls.Add(lblTitle);

            btnClose = new Button();
            btnClose.Text = "×";
            btnClose.Size = new Size(30, 30);
            btnClose.Location = new Point(this.Width - 35, 5);
            btnClose.FlatStyle = FlatStyle.Flat;
            btnClose.FlatAppearance.BorderSize = 0;
            btnClose.ForeColor = Color.FromArgb(161, 161, 170); // zinc-400
            btnClose.Font = new Font("Segoe UI", 12f, FontStyle.Bold);
            btnClose.Click += (s, e) => { this.Hide(); };
            headerPanel.Controls.Add(btnClose);

            btnMinimize = new Button();
            btnMinimize.Text = "—";
            btnMinimize.Size = new Size(30, 30);
            btnMinimize.Location = new Point(this.Width - 65, 5);
            btnMinimize.FlatStyle = FlatStyle.Flat;
            btnMinimize.FlatAppearance.BorderSize = 0;
            btnMinimize.ForeColor = Color.FromArgb(161, 161, 170);
            btnMinimize.Font = new Font("Segoe UI", 8f, FontStyle.Bold);
            btnMinimize.Click += (s, e) => { this.WindowState = FormWindowState.Minimized; };
            headerPanel.Controls.Add(btnMinimize);

            this.Controls.Add(headerPanel);

            // 2. Connection Strip
            connectionStrip = new Panel();
            connectionStrip.Size = new Size(this.Width, 20);
            connectionStrip.Location = new Point(0, 40);
            connectionStrip.BackColor = Color.FromArgb(245, 158, 11); // orange for connecting
            
            lblConnectionState = new Label();
            lblConnectionState.Text = "Connecting...";
            lblConnectionState.Font = new Font("Segoe UI", 8f, FontStyle.Bold);
            lblConnectionState.ForeColor = Color.Black;
            lblConnectionState.Dock = DockStyle.Fill;
            lblConnectionState.TextAlign = ContentAlignment.MiddleCenter;
            connectionStrip.Controls.Add(lblConnectionState);
            
            this.Controls.Add(connectionStrip);

            // 3. Presence Panel
            presencePanel = new Panel();
            presencePanel.Size = new Size(this.Width, 28);
            presencePanel.Location = new Point(0, 60);
            presencePanel.BackColor = Color.FromArgb(39, 39, 42); // zinc-800
            
            lblPresence = new Label();
            lblPresence.Text = "🔴 Operator Offline";
            lblPresence.Font = new Font("Segoe UI", 8.5f, FontStyle.Bold);
            lblPresence.ForeColor = Color.LightGray;
            lblPresence.Location = new Point(10, 6);
            lblPresence.AutoSize = true;
            presencePanel.Controls.Add(lblPresence);

            lblTypingIndicator = new Label();
            lblTypingIndicator.Text = "Operator is typing...";
            lblTypingIndicator.Font = new Font("Segoe UI", 8f, FontStyle.Italic);
            lblTypingIndicator.ForeColor = Color.FromArgb(56, 189, 248); // sky-400
            lblTypingIndicator.Location = new Point(this.Width - 130, 6);
            lblTypingIndicator.AutoSize = true;
            lblTypingIndicator.Visible = false;
            presencePanel.Controls.Add(lblTypingIndicator);

            this.Controls.Add(presencePanel);

            // 4. Search Panel
            searchPanel = new Panel();
            searchPanel.Size = new Size(this.Width, 34);
            searchPanel.Location = new Point(0, 88);
            searchPanel.BackColor = Color.FromArgb(24, 24, 27); // zinc-900

            txtSearch = new TextBox();
            txtSearch.Size = new Size(this.Width - 24, 22);
            txtSearch.Location = new Point(12, 6);
            txtSearch.BackColor = Color.FromArgb(39, 39, 42);
            txtSearch.ForeColor = Color.White;
            txtSearch.BorderStyle = BorderStyle.FixedSingle;
            txtSearch.Text = "Search chat history...";
            txtSearch.GotFocus += (s, e) => { if (txtSearch.Text == "Search chat history...") txtSearch.Text = ""; };
            txtSearch.LostFocus += (s, e) => { if (string.IsNullOrEmpty(txtSearch.Text)) txtSearch.Text = "Search chat history..."; };
            txtSearch.TextChanged += TxtSearch_TextChanged;
            searchPanel.Controls.Add(txtSearch);

            this.Controls.Add(searchPanel);

            // 5. Message Flow Panel
            messagePanel = new FlowLayoutPanel();
            messagePanel.Size = new Size(this.Width, this.Height - 122 - 56);
            messagePanel.Location = new Point(0, 122);
            messagePanel.FlowDirection = FlowDirection.TopDown;
            messagePanel.WrapContents = false;
            messagePanel.AutoScroll = true;
            messagePanel.BackColor = Color.FromArgb(18, 18, 20); // very dark
            // Enable double buffering
            typeof(FlowLayoutPanel).InvokeMember("DoubleBuffered", 
                System.Reflection.BindingFlags.SetProperty | System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic, 
                null, messagePanel, new object[] { true });
            
            messagePanel.Resize += (s, e) => {
                messagePanel.SuspendLayout();
                foreach (Control ctrl in messagePanel.Controls) {
                    ctrl.Width = messagePanel.ClientSize.Width - 5;
                }
                messagePanel.ResumeLayout();
            };
            
            this.Controls.Add(messagePanel);

            // 6. Attachment Panel
            attachmentPanel = new FlowLayoutPanel();
            attachmentPanel.Size = new Size(this.Width, 0); // starts hidden
            attachmentPanel.Location = new Point(0, 430);
            attachmentPanel.FlowDirection = FlowDirection.LeftToRight;
            attachmentPanel.BackColor = Color.FromArgb(24, 24, 27);
            attachmentPanel.AutoScroll = true;
            
            this.Controls.Add(attachmentPanel);

            // 7. Input Panel - WhatsApp style
            inputPanel = new Panel();
            inputPanel.Size = new Size(this.Width, 56);
            inputPanel.Location = new Point(0, this.Height - 56);
            inputPanel.BackColor = Color.FromArgb(9, 9, 11);

            // Emoji button
            Button btnEmoji = new Button();
            btnEmoji.Text = "😊";
            btnEmoji.Size = new Size(32, 32);
            btnEmoji.Location = new Point(5, 12);
            btnEmoji.FlatStyle = FlatStyle.Flat;
            btnEmoji.FlatAppearance.BorderSize = 0;
            btnEmoji.ForeColor = Color.White;
            btnEmoji.Font = new Font("Segoe UI", 12f);
            btnEmoji.BackColor = Color.Transparent;
            btnEmoji.Click += (s, ev) => {
                // Quick emoji picker - simple context menu
                ContextMenuStrip menu = new ContextMenuStrip();
                menu.BackColor = Color.FromArgb(39, 39, 42);
                menu.ForeColor = Color.White;
                string[] emojis = { "😊","😂","👍","🙏","✅","❌","⚠️","🔧","💻","📋","🔴","🟢" };
                foreach (string em in emojis)
                {
                    string cap = em;
                    ToolStripMenuItem item = new ToolStripMenuItem(cap);
                    item.Font = new Font("Segoe UI", 13f);
                    item.Click += (ss, ee) => { txtMessage.AppendText(cap); txtMessage.Focus(); };
                    menu.Items.Add(item);
                }
                menu.Show(btnEmoji, new Point(0, -menu.Height - 5));
            };
            inputPanel.Controls.Add(btnEmoji);

            // Attach button
            btnAttach = new Button();
            btnAttach.Text = "📎";
            btnAttach.Size = new Size(32, 32);
            btnAttach.Location = new Point(40, 12);
            btnAttach.FlatStyle = FlatStyle.Flat;
            btnAttach.FlatAppearance.BorderSize = 0;
            btnAttach.ForeColor = Color.White;
            btnAttach.Font = new Font("Segoe UI", 11f);
            btnAttach.BackColor = Color.Transparent;
            btnAttach.Click += BtnAttach_Click;
            inputPanel.Controls.Add(btnAttach);

            // Screenshot button
            btnScreenshot = new Button();
            btnScreenshot.Text = "📷";
            btnScreenshot.Size = new Size(32, 32);
            btnScreenshot.Location = new Point(75, 12);
            btnScreenshot.FlatStyle = FlatStyle.Flat;
            btnScreenshot.FlatAppearance.BorderSize = 0;
            btnScreenshot.ForeColor = Color.White;
            btnScreenshot.Font = new Font("Segoe UI", 11f);
            btnScreenshot.BackColor = Color.Transparent;
            btnScreenshot.Click += (s, ev) => { CaptureAndSendScreenshot(); };
            inputPanel.Controls.Add(btnScreenshot);

            // Text input
            txtMessage = new TextBox();
            txtMessage.Size = new Size(this.Width - 165, 32);
            txtMessage.Location = new Point(112, 12);
            txtMessage.Multiline = true;
            txtMessage.BackColor = Color.FromArgb(39, 39, 46);
            txtMessage.ForeColor = Color.White;
            txtMessage.BorderStyle = BorderStyle.None;
            txtMessage.Font = new Font("Segoe UI", 9.5f);
            txtMessage.KeyDown += TxtMessage_KeyDown;
            txtMessage.TextChanged += TxtMessage_TextChanged;
            inputPanel.Controls.Add(txtMessage);

            // Send button (round blue)
            btnSend = new Button();
            btnSend.Text = "➤";
            btnSend.Size = new Size(40, 40);
            btnSend.Location = new Point(this.Width - 48, 8);
            btnSend.FlatStyle = FlatStyle.Flat;
            btnSend.FlatAppearance.BorderSize = 0;
            btnSend.BackColor = Color.FromArgb(37, 99, 235);
            btnSend.ForeColor = Color.White;
            btnSend.Font = new Font("Segoe UI", 13f, FontStyle.Bold);
            btnSend.Click += BtnSend_Click;
            inputPanel.Controls.Add(btnSend);

            this.Controls.Add(inputPanel);


            // 8. Welcome Panel
            welcomePanel = new Panel();
            welcomePanel.Size = new Size(this.Width, this.Height - 96);
            welcomePanel.Location = new Point(0, 40);
            welcomePanel.BackColor = Color.FromArgb(18, 18, 20);

            lblWelcomeTitle = new Label();
            lblWelcomeTitle.Text = "OSI AI Support";
            lblWelcomeTitle.Font = new Font("Segoe UI", 18f, FontStyle.Bold);
            lblWelcomeTitle.ForeColor = Color.White;
            lblWelcomeTitle.Size = new Size(this.Width, 40);
            lblWelcomeTitle.Location = new Point(0, 110);
            lblWelcomeTitle.TextAlign = ContentAlignment.MiddleCenter;
            welcomePanel.Controls.Add(lblWelcomeTitle);

            // Logo circle
            Panel logoCircle = new Panel();
            logoCircle.Size = new Size(72, 72);
            logoCircle.Location = new Point(this.Width / 2 - 36, 28);
            logoCircle.BackColor = Color.FromArgb(37, 99, 235);
            logoCircle.Paint += (s, ev) => {
                ev.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
                ev.Graphics.Clear(Color.FromArgb(37, 99, 235));
                using (GraphicsPath gp = new GraphicsPath())
                {
                    gp.AddEllipse(0, 0, 72, 72);
                    ev.Graphics.SetClip(gp);
                    ev.Graphics.FillRectangle(new SolidBrush(Color.FromArgb(37, 99, 235)), 0, 0, 72, 72);
                }
                using (SolidBrush wb = new SolidBrush(Color.White))
                    ev.Graphics.DrawString("AI", new Font("Segoe UI", 20f, FontStyle.Bold), wb, 14f, 18f);
            };
            welcomePanel.Controls.Add(logoCircle);

            lblWelcomeDesc = new Label();
            lblWelcomeDesc.Text = "Hubungkan ke tim IT Support untuk bantuan teknis.\nRiwayat chat akan tampil otomatis jika sudah ada.";
            lblWelcomeDesc.Font = new Font("Segoe UI", 9f);
            lblWelcomeDesc.ForeColor = Color.FromArgb(161, 161, 170);
            lblWelcomeDesc.Size = new Size(this.Width - 40, 70);
            lblWelcomeDesc.Location = new Point(20, 158);
            lblWelcomeDesc.TextAlign = ContentAlignment.MiddleCenter;
            welcomePanel.Controls.Add(lblWelcomeDesc);

            btnStartChat = new Button();
            btnStartChat.Text = "Mulai Chat";
            btnStartChat.Size = new Size(170, 48);
            btnStartChat.Location = new Point(this.Width / 2 - 85, 248);
            btnStartChat.FlatStyle = FlatStyle.Flat;
            btnStartChat.FlatAppearance.BorderSize = 0;
            btnStartChat.BackColor = Color.FromArgb(37, 99, 235);
            btnStartChat.ForeColor = Color.White;
            btnStartChat.Font = new Font("Segoe UI", 11f, FontStyle.Bold);
            btnStartChat.Click += BtnStartChat_Click;
            welcomePanel.Controls.Add(btnStartChat);

            this.Controls.Add(welcomePanel);
            welcomePanel.BringToFront();
        }

        private void SetupTimers()
        {
            reconnectTimer = new System.Windows.Forms.Timer();
            reconnectTimer.Interval = 3000;
            reconnectTimer.Tick += async (s, e) => {
                if (ws == null || ws.State != WebSocketState.Open)
                {
                    await ConnectWebSocket();
                }
            };
            reconnectTimer.Start();

            pollFallbackTimer = new System.Windows.Forms.Timer();
            pollFallbackTimer.Interval = 5000;
            pollFallbackTimer.Tick += (s, e) => {
                if (ws == null || ws.State != WebSocketState.Open)
                {
                    PollHistoryFallback();
                }
            };

            typingTimer = new System.Windows.Forms.Timer();
            typingTimer.Interval = 2000;
            typingTimer.Tick += (s, e) => {
                if (isTyping)
                {
                    isTyping = false;
                    SendTypingStatus(false);
                }
            };
        }

        private async void ChatForm_Load(object sender, EventArgs e)
        {
            bool success = RegisterHotKey(this.Handle, HOTKEY_ID, MOD_CONTROL | MOD_SHIFT, VK_S);
            if (!success)
            {
                Debug.WriteLine("[HOTKEY] Failed to register global Ctrl+Shift+S hotkey.");
            }

            await ConnectWebSocket();
            // Load history and auto-dismiss welcome panel if history exists
            LoadChatHistoryWithAutoShow();
        }

        private void ChatForm_FormClosing(object sender, FormClosingEventArgs e)
        {
            // Do not close agent tray application, just hide form
            if (e.CloseReason == CloseReason.UserClosing)
            {
                e.Cancel = true;
                this.Hide();
            }
            else
            {
                UnregisterHotKey(this.Handle, HOTKEY_ID);
                if (ws != null) { try { ws.Dispose(); } catch { } }
            }
        }

        protected override void WndProc(ref Message m)
        {
            const int WM_HOTKEY = 0x0312;
            if (m.Msg == WM_HOTKEY && m.WParam.ToInt32() == HOTKEY_ID)
            {
                CaptureScreenshot();
            }
            base.WndProc(ref m);
        }

        private async Task ConnectWebSocket()
        {
            if (isConnecting) return;
            isConnecting = true;
            UpdateConnectionState("CONNECTING");

            try
            {
                if (ws != null)
                {
                    try { ws.Abort(); } catch { }
                    try { ws.Dispose(); } catch { }
                }
                ws = new ClientWebSocket();
                ws.Options.KeepAliveInterval = TimeSpan.FromSeconds(10);
                
                // Enterprise Chat Engine endpoint (vs legacy /api/chat/ws)
                string wsUrl = string.Format("ws://{0}/ws/client_chat?client_id={1}&pc_name={2}",
                    serverIP, clientUUID, Uri.EscapeDataString(pcName));
                
                CancellationTokenSource cts = new CancellationTokenSource(TimeSpan.FromSeconds(4));
                await ws.ConnectAsync(new Uri(wsUrl), cts.Token);
                
                UpdateConnectionState("CONNECTED");
                pollFallbackTimer.Stop();

                var receiveTask = Task.Run(new Func<Task>(ReceiveWSLoop));
                
                SendInitContext();
                FlushOfflineQueue();
            }
            catch
            {
                UpdateConnectionState("RECONNECTING");
                pollFallbackTimer.Start();
            }
            finally
            {
                isConnecting = false;
            }
        }

        private void SafeInvoke(Action action)
        {
            if (this.IsDisposed || !this.IsHandleCreated) return;
            try {
                if (this.InvokeRequired) {
                    this.Invoke((MethodInvoker)delegate { action(); });
                } else {
                    action();
                }
            } catch { }
        }

        private void UpdateConnectionState(string state)
        {
            if (this.IsDisposed || !this.IsHandleCreated) return;
            SafeInvoke(() => {
                if (state == "CONNECTED")
                {
                    connectionStrip.BackColor = Color.FromArgb(16, 185, 129); // green
                    lblConnectionState.Text = "🟢 Connected to Support Engine";
                    lblConnectionState.ForeColor = Color.White;
                }
                else if (state == "CONNECTING")
                {
                    connectionStrip.BackColor = Color.FromArgb(245, 158, 11); // orange
                    lblConnectionState.Text = "Connecting...";
                    lblConnectionState.ForeColor = Color.Black;
                }
                else
                {
                    connectionStrip.BackColor = Color.FromArgb(239, 68, 68); // red/yellow reconnecting
                    lblConnectionState.Text = "⚠️ Reconnecting... (Offline queue active)";
                    lblConnectionState.ForeColor = Color.White;
                }
            });
        }

        private void SendInitContext()
        {
            try
            {
                var meta = new Dictionary<string, object>();
                meta["hostname"] = Environment.MachineName;
                meta["os"] = Environment.OSVersion.ToString();
                meta["cpu"] = GetCPUNameSimple();
                meta["ram"] = GetRAMSizeSimple();

                var ev = new Dictionary<string, object>();
                ev["type"] = "init_context";
                ev["client_id"] = clientUUID;
                ev["data"] = meta;

                SendWSMessage(new JavaScriptSerializer().Serialize(ev));
            }
            catch { }
        }

        private async Task ReceiveWSLoop()
        {
            byte[] buffer = new byte[8192];
            MemoryStream ms = new MemoryStream();

            while (ws != null && ws.State == WebSocketState.Open)
            {
                try
                {
                    ms.SetLength(0);
                    WebSocketReceiveResult result;
                    do
                    {
                        result = await ws.ReceiveAsync(new ArraySegment<byte>(buffer), CancellationToken.None);
                        ms.Write(buffer, 0, result.Count);
                    }
                    while (!result.EndOfMessage);

                    if (result.MessageType == WebSocketMessageType.Close)
                    {
                        await ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "", CancellationToken.None);
                        UpdateConnectionState("RECONNECTING");
                        break;
                    }

                    string json = Encoding.UTF8.GetString(ms.ToArray());
                    ProcessIncomingMessage(json);
                }
                catch
                {
                    UpdateConnectionState("RECONNECTING");
                    break;
                }
            }
        }

        private void ProcessIncomingMessage(string json)
        {
            try
            {
                JavaScriptSerializer serializer = new JavaScriptSerializer();
                var ev = serializer.Deserialize<Dictionary<string, object>>(json);
                if (ev == null || !ev.ContainsKey("type")) return;

                string type = ev["type"].ToString();

                // ── Enterprise Chat Engine event types (primary) ──────────────────
                // Normalize: RECEIVE_MESSAGE → message, START_TYPING → typing, MESSAGE_READ → read_receipt
                if (type == "RECEIVE_MESSAGE") type = "message";
                else if (type == "START_TYPING") type = "typing";
                else if (type == "STOP_TYPING") { SafeInvoke(() => { lblTypingIndicator.Visible = false; }); return; }
                else if (type == "MESSAGE_READ") type = "read_receipt";
                else if (type == "MESSAGE_DELIVERED") { /* ack only */ return; }
                else if (type == "AI_SUGGESTION" || type == "AI_ISSUE_REPORT")
                {
                    // Show AI suggestion / issue report as a system bubble
                    var aiData = ev.ContainsKey("data") ? ev["data"] as Dictionary<string, object> : null;
                    string aiText = null;
                    if (aiData != null)
                    {
                        if (aiData.ContainsKey("summary")) aiText = aiData["summary"].ToString();
                        else if (aiData.ContainsKey("ai_analysis")) aiText = aiData["ai_analysis"].ToString();
                        else if (aiData.ContainsKey("issue_name"))
                        {
                            string issue = aiData["issue_name"].ToString();
                            string analysis = aiData.ContainsKey("ai_analysis") ? aiData["ai_analysis"].ToString() : "";
                            aiText = string.IsNullOrEmpty(analysis) ? issue : string.Format("[ALERT] {0}\n{1}", issue, analysis);
                        }
                        else if (aiData.ContainsKey("message")) aiText = aiData["message"].ToString();
                    }
                    if (!string.IsNullOrEmpty(aiText))
                    {
                        var aiMsg = new ChatMessageModel();
                        aiMsg.ID = 0;
                        aiMsg.ClientID = clientUUID;
                        aiMsg.Sender = "AI_HYPOTHESIS";
                        aiMsg.Message = "[AI ASSIST] " + aiText;
                        aiMsg.ReadStatus = "READ";
                        aiMsg.CreatedAt = DateTime.Now;
                        SafeInvoke(() => AppendMessage(aiMsg));
                    }
                    return;
                }
                else if (type == "CONNECT" || type == "SESSION_ASSIGNED" || type == "SESSION_SOLVED")
                {
                    SafeInvoke(() => {
                        lblPresence.Text = "🟢 Operator Online";
                        lblPresence.ForeColor = Color.LimeGreen;
                    });
                    return;
                }
                else if (type == "DISCONNECT")
                {
                    SafeInvoke(() => {
                        lblPresence.Text = "🔴 Operator Offline";
                        lblPresence.ForeColor = Color.LightGray;
                    });
                    return;
                }
                // ── Legacy / compatibility event types ────────────────────────────
                if (type == "operator_status")
                {
                    if (ev.ContainsKey("data"))
                    {
                        var data = ev["data"] as Dictionary<string, object>;
                        if (data != null && data.ContainsKey("status"))
                        {
                            string status = data["status"].ToString();
                            SafeInvoke(() => {
                                if (status == "ONLINE" || status == "ACTIVE")
                                {
                                    lblPresence.Text = "🟢 Operator Online";
                                    lblPresence.ForeColor = Color.LimeGreen;
                                }
                                else
                                {
                                    lblPresence.Text = "🔴 Operator Offline";
                                    lblPresence.ForeColor = Color.LightGray;
                                }
                            });
                        }
                    }
                }
                else if (type == "capture_screenshot")
                {
                    Task.Run(() => { CaptureAndUploadScreenshot(); });
                }
                else if (type == "typing" || type == "START_TYPING")
                {
                    // Enterprise: sender_type, Legacy: sender
                    string senderType = ev.ContainsKey("sender_type") ? ev["sender_type"].ToString()
                                      : (ev.ContainsKey("sender") ? ev["sender"].ToString() : "");
                    if (senderType == "OPERATOR")
                    {
                        SafeInvoke(() => { lblTypingIndicator.Visible = true; });
                        // Auto-hide after 3s
                        System.Threading.Tasks.Task.Delay(3000).ContinueWith(_ =>
                            SafeInvoke(() => { lblTypingIndicator.Visible = false; }));
                    }
                }
                else if (type == "message_update")
                {
                    var data = ev["data"] as Dictionary<string, object>;
                    if (data != null)
                    {
                        uint msgID = Convert.ToUInt32(data["id"]);
                        SafeInvoke(() => {
                            foreach (Control ctrl in messagePanel.Controls)
                            {
                                var bubble = ctrl as MessageBubble;
                                if (bubble != null && bubble.Model.ID == msgID)
                                {
                                    bubble.UpdateModel(data);
                                    break;
                                }
                            }
                        });
                    }
                }
                else if (type == "read_receipt" || type == "MESSAGE_READ")
                {
                    var data = ev.ContainsKey("data") ? ev["data"] as Dictionary<string, object> : null;
                    uint msgID = 0;
                    if (data != null && data.ContainsKey("message_id"))
                        msgID = Convert.ToUInt32(data["message_id"]);
                    if (msgID > 0)
                    {
                        SafeInvoke(() => {
                            foreach (Control ctrl in messagePanel.Controls)
                            {
                                var bubble = ctrl as MessageBubble;
                                if (bubble != null && bubble.Model.ID == msgID)
                                {
                                    bubble.Model.ReadStatus = "READ";
                                    bubble.Invalidate();
                                    break;
                                }
                            }
                        });
                    }
                }
                else if (type == "message")
                {
                    // Enterprise data is in root-level fields OR in data sub-object
                    Dictionary<string, object> data;
                    if (ev.ContainsKey("data") && ev["data"] is Dictionary<string, object>)
                        data = ev["data"] as Dictionary<string, object>;
                    else
                        data = ev; // flat format from Enterprise Engine

                    if (data != null)
                    {
                        var msg = new ChatMessageModel();
                        try { msg.ID = data.ContainsKey("message_id") ? Convert.ToUInt32(data["message_id"]) : (data.ContainsKey("id") ? Convert.ToUInt32(data["id"]) : 0); } catch { }
                        msg.ClientID = data.ContainsKey("client_id") ? data["client_id"].ToString() : clientUUID;
                        // Enterprise uses sender_type, legacy uses sender
                        msg.Sender = data.ContainsKey("sender_type") ? data["sender_type"].ToString()
                                   : (data.ContainsKey("sender") ? data["sender"].ToString() : "SYSTEM");
                        msg.Message = data.ContainsKey("message") ? data["message"].ToString() : "";
                        msg.AttachmentPath = data.ContainsKey("attachment_url") ? data["attachment_url"].ToString()
                                           : (data.ContainsKey("attachment_path") ? data["attachment_path"].ToString() : "");
                        msg.ReadStatus = data.ContainsKey("read_status") ? data["read_status"].ToString() : "DELIVERED";

                        string tsStr = data.ContainsKey("timestamp") ? data["timestamp"].ToString()
                                     : (data.ContainsKey("created_at") ? data["created_at"].ToString() : "");
                        DateTime dt;
                        if (!string.IsNullOrEmpty(tsStr) && DateTime.TryParse(tsStr, out dt))
                            msg.CreatedAt = dt;
                        else
                            msg.CreatedAt = DateTime.Now;

                        if (msg.ID > lastMessageID) lastMessageID = msg.ID;

                        SafeInvoke(() => {
                            bool isFromSelf = msg.Sender == "CLIENT";
                            bool matchedOffline = false;

                            if (isFromSelf)
                            {
                                foreach (Control ctrl in messagePanel.Controls)
                                {
                                    var bubble = ctrl as MessageBubble;
                                    if (bubble != null && bubble.Model.ReadStatus == "PENDING" && bubble.Model.Message == msg.Message)
                                    {
                                        bubble.Model.ReadStatus = "SENT";
                                        bubble.Model.ID = msg.ID;
                                        bubble.Invalidate();
                                        matchedOffline = true;
                                        break;
                                    }
                                }
                            }

                            if (!matchedOffline) AppendMessage(msg);

                            if (msg.Sender == "OPERATOR" || msg.Sender == "AI_HYPOTHESIS")
                            {
                                if (!this.ContainsFocus || !this.Visible)
                                {
                                    if (context != null)
                                    {
                                        string senderName = msg.Sender == "OPERATOR" ? "NOC Operator" : "OSI AI Assist";
                                        context.ShowNotification(senderName, msg.Message);
                                    }
                                }
                            }

                            if (msg.Sender == "OPERATOR" && this.Focused) SendReadReceipt(msg.ID);
                        });
                    }
                }
            }
            catch { }
        }

        public void SendWSMessage(string json)
        {
            if (ws != null && ws.State == WebSocketState.Open)
            {
                try
                {
                    byte[] bytes = Encoding.UTF8.GetBytes(json);
                    ws.SendAsync(new ArraySegment<byte>(bytes), WebSocketMessageType.Text, true, CancellationToken.None);
                }
                catch { }
            }
        }

        private void SendReadReceipt(uint messageID)
        {
            try
            {
                var data = new Dictionary<string, object>();
                data["message_id"] = messageID;

                var ev = new Dictionary<string, object>();
                // Enterprise Engine uses MESSAGE_READ
                ev["type"] = "MESSAGE_READ";
                ev["client_id"] = clientUUID;
                ev["sender_type"] = "CLIENT";
                ev["data"] = data;

                SendWSMessage(new JavaScriptSerializer().Serialize(ev));
            }
            catch { }
        }

        private void SendTypingStatus(bool typing)
        {
            try
            {
                var data = new Dictionary<string, object>();
                data["typing"] = typing;

                var ev = new Dictionary<string, object>();
                // Enterprise Engine uses START_TYPING / STOP_TYPING
                ev["type"] = typing ? "START_TYPING" : "STOP_TYPING";
                ev["client_id"] = clientUUID;
                ev["sender_type"] = "CLIENT";
                ev["data"] = data;

                SendWSMessage(new JavaScriptSerializer().Serialize(ev));
            }
            catch { }
        }

        private void LoadChatHistory()
        {
            LoadChatHistoryWithAutoShow();
        }

        private void LoadChatHistoryWithAutoShow()
        {
            Task.Run(() =>
            {
                try
                {
                    // Enterprise Chat Engine history endpoint
                    string url = string.Format("http://{0}/api/enterprise/chat/history/{1}", serverIP, clientUUID);
                    using (WebClient client = new WebClient())
                    {
                        client.Headers[HttpRequestHeader.Accept] = "application/json";
                        string json = client.DownloadString(url);
                        JavaScriptSerializer serializer = new JavaScriptSerializer();
                        serializer.MaxJsonLength = int.MaxValue;
                        object[] rawMessages = serializer.Deserialize<object[]>(json);

                        SafeInvoke(() => {
                            messagePanel.SuspendLayout();
                            messagePanel.Controls.Clear();

                            DateTime lastDate = DateTime.MinValue;
                            foreach (var rawMsg in rawMessages)
                            {
                                var dict = rawMsg as Dictionary<string, object>;
                                if (dict == null) continue;

                                var msg = new ChatMessageModel();
                                msg.ID = Convert.ToUInt32(dict["id"]);
                                msg.ClientID = dict.ContainsKey("client_id") ? dict["client_id"].ToString() : clientUUID;
                                msg.Sender = dict.ContainsKey("sender") ? dict["sender"].ToString() : "SYSTEM";
                                msg.Message = dict.ContainsKey("message") ? dict["message"].ToString() : "";
                                msg.AttachmentPath = dict.ContainsKey("attachment_path") ? dict["attachment_path"].ToString() : "";
                                msg.ReadStatus = dict.ContainsKey("read_status") ? dict["read_status"].ToString() : "DELIVERED";

                                if (dict.ContainsKey("created_at"))
                                {
                                    DateTime dt;
                                    if (DateTime.TryParse(dict["created_at"].ToString(), out dt))
                                        msg.CreatedAt = dt;
                                    else
                                        msg.CreatedAt = DateTime.Now;
                                }
                                else
                                {
                                    msg.CreatedAt = DateTime.Now;
                                }

                                if (msg.ID > lastMessageID)
                                    lastMessageID = msg.ID;

                                // Add date separator (WhatsApp style)
                                if (msg.CreatedAt.Date != lastDate.Date)
                                {
                                    lastDate = msg.CreatedAt.Date;
                                    AddDateSeparator(msg.CreatedAt);
                                }

                                AppendMessage(msg);
                            }
                            messagePanel.ResumeLayout();

                            // Auto-dismiss welcome panel if history exists
                            if (rawMessages.Length > 0)
                            {
                                welcomePanel.Hide();
                            }

                            ScrollToBottom();
                        });
                    }
                }
                catch { }
            });
        }

        private void AddDateSeparator(DateTime date)
        {
            string label;
            if (date.Date == DateTime.Today)
                label = "Hari ini";
            else if (date.Date == DateTime.Today.AddDays(-1))
                label = "Kemarin";
            else
                label = date.ToString("dd MMMM yyyy");

            Panel sep = new Panel();
            sep.Width = messagePanel.Width - 10;
            sep.Height = 26;
            sep.BackColor = Color.Transparent;
            sep.Margin = new Padding(0, 6, 0, 6);

            Label lbl = new Label();
            lbl.Text = label;
            lbl.Font = new Font("Segoe UI", 8f, FontStyle.Bold);
            lbl.ForeColor = Color.FromArgb(113, 113, 122);
            lbl.BackColor = Color.FromArgb(39, 39, 42);
            lbl.AutoSize = true;
            lbl.Padding = new Padding(10, 3, 10, 3);

            sep.Controls.Add(lbl);
            lbl.Location = new Point((sep.Width - lbl.PreferredWidth) / 2, 2);

            messagePanel.Controls.Add(sep);
        }

        private void PollHistoryFallback()
        {
            try
            {
                // Fallback polling: use enterprise history with last_id filter
                string url = string.Format("http://{0}/api/enterprise/chat/history/{1}", serverIP, clientUUID);
                using (WebClient client = new WebClient())
                {
                    string json = client.DownloadString(url);
                    JavaScriptSerializer serializer = new JavaScriptSerializer();
                    object[] rawMessages = serializer.Deserialize<object[]>(json);
                    
                    if (rawMessages.Length > 0)
                    {
                        SafeInvoke(() => {
                            messagePanel.SuspendLayout();
                            foreach (var rawMsg in rawMessages)
                            {
                                var dict = rawMsg as Dictionary<string, object>;
                                if (dict != null)
                                {
                                    var msg = new ChatMessageModel();
                                    msg.ID = Convert.ToUInt32(dict["id"]);
                                    msg.ClientID = dict["client_id"].ToString();
                                    msg.Sender = dict["sender"].ToString();
                                    msg.Message = dict["message"].ToString();
                                    msg.AttachmentPath = dict["attachment_path"].ToString();
                                    msg.ReadStatus = dict["read_status"].ToString();
                                    
                                    if (dict.ContainsKey("created_at"))
                                    {
                                        DateTime dt;
                                        if (DateTime.TryParse(dict["created_at"].ToString(), out dt))
                                            msg.CreatedAt = dt;
                                        else
                                            msg.CreatedAt = DateTime.Now;
                                    }
                                    else
                                    {
                                        msg.CreatedAt = DateTime.Now;
                                    }

                                    if (msg.ID > lastMessageID)
                                    {
                                        lastMessageID = msg.ID;
                                    }
                                    
                                    AppendMessage(msg);
                                }
                            }
                            messagePanel.ResumeLayout();
                            ScrollToBottom();
                        });
                    }
                }
            }
            catch { }
        }

        private void AppendMessage(ChatMessageModel msg)
        {
            MessageBubble bubble = new MessageBubble(msg, serverIP, this);
            bubble.Margin = new Padding(0, 2, 0, 2);
            // Account for vertical scrollbar (approx 20px) to prevent horizontal scrolling
            bubble.Width = messagePanel.ClientSize.Width - 5; 
            messagePanel.Controls.Add(bubble);
            ScrollToBottom();
        }

        public void ScrollToBottom()
        {
            if (messagePanel.Controls.Count == 0) return;
            messagePanel.ScrollControlIntoView(messagePanel.Controls[messagePanel.Controls.Count - 1]);
        }

        private void TxtSearch_TextChanged(object sender, EventArgs e)
        {
            string query = txtSearch.Text.Trim().ToLower();
            if (query == "search chat history...") query = "";

            messagePanel.SuspendLayout();
            foreach (Control ctrl in messagePanel.Controls)
            {
                MessageBubble bubble = ctrl as MessageBubble;
                if (bubble != null)
                {
                    if (string.IsNullOrEmpty(query))
                    {
                        bubble.Visible = true;
                    }
                    else
                    {
                        bool matches = bubble.MessageText.ToLower().Contains(query) || 
                                       bubble.AttachmentPath.ToLower().Contains(query);
                        bubble.Visible = matches;
                    }
                }
            }
            messagePanel.ResumeLayout();
        }

        private void TxtMessage_TextChanged(object sender, EventArgs e)
        {
            if (ws != null && ws.State == WebSocketState.Open)
            {
                if (!isTyping)
                {
                    isTyping = true;
                    SendTypingStatus(true);
                }
                typingTimer.Stop();
                typingTimer.Start();
            }
        }

        private void TxtMessage_KeyDown(object sender, KeyEventArgs e)
        {
            if (e.Control && e.KeyCode == Keys.V)
            {
                if (Clipboard.ContainsImage())
                {
                    e.SuppressKeyPress = true;
                    try
                    {
                        Image img = Clipboard.GetImage();
                        string tempPath = Path.Combine(Path.GetTempPath(), string.Format("clipboard_{0}.png", DateTime.Now.Ticks));
                        img.Save(tempPath, System.Drawing.Imaging.ImageFormat.Png);
                        AddAttachment(tempPath);
                    }
                    catch (Exception ex)
                    {
                        MessageBox.Show("Failed to paste image: " + ex.Message, "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    }
                }
            }
            else if (e.KeyCode == Keys.Enter && !e.Shift)
            {
                e.SuppressKeyPress = true;
                btnSend.PerformClick();
            }
        }

        private void BtnAttach_Click(object sender, EventArgs e)
        {
            if (selectedFiles.Count >= 5)
            {
                MessageBox.Show("Maximum of 5 attachments allowed per message.", "Limit Exceeded", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            using (OpenFileDialog ofd = new OpenFileDialog())
            {
                ofd.Filter = "All Files (*.*)|*.*|Images (*.png;*.jpg;*.jpeg)|*.png;*.jpg;*.jpeg|Logs/Documents (*.txt;*.log;*.pdf;*.evtx;*.csv)|*.txt;*.log;*.pdf;*.evtx;*.csv|Archives (*.zip)|*.zip";
                ofd.Multiselect = true;
                if (ofd.ShowDialog() == DialogResult.OK)
                {
                    foreach (string file in ofd.FileNames)
                    {
                        if (selectedFiles.Count >= 5) break;
                        AddAttachment(file);
                    }
                }
            }
        }

        private void AddAttachment(string path)
        {
            if (!selectedFiles.Contains(path))
            {
                selectedFiles.Add(path);
                UpdateAttachmentPanel();
            }
        }

        private void UpdateAttachmentPanel()
        {
            attachmentPanel.Controls.Clear();
            if (selectedFiles.Count > 0)
            {
                attachmentPanel.Height = 60;
                messagePanel.Height = 308 - 60;
                
                foreach (string file in selectedFiles)
                {
                    AttachmentPreviewControl ctrl = new AttachmentPreviewControl(file);
                    ctrl.OnRemove += (s, e) => {
                        selectedFiles.Remove(file);
                        UpdateAttachmentPanel();
                    };
                    attachmentPanel.Controls.Add(ctrl);
                }
            }
            else
            {
                attachmentPanel.Height = 0;
                messagePanel.Height = 308;
            }
        }

        private void CaptureScreenshot()
        {
            this.Hide();
            Thread.Sleep(350); // Wait for window to minimize
            try
            {
                Rectangle bounds = Screen.PrimaryScreen.Bounds;
                using (Bitmap bitmap = new Bitmap(bounds.Width, bounds.Height))
                {
                    using (Graphics g = Graphics.FromImage(bitmap))
                    {
                        g.CopyFromScreen(Point.Empty, Point.Empty, bounds.Size);
                    }
                    string tempFile = Path.Combine(Path.GetTempPath(), string.Format("screenshot_{0}.jpg", DateTime.Now.Ticks));
                    bitmap.Save(tempFile, System.Drawing.Imaging.ImageFormat.Jpeg);
                    AddAttachment(tempFile);
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show("Failed to capture screenshot: " + ex.Message, "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
            this.Show();
            this.Focus();
        }

        private async void CaptureAndSendScreenshot()
        {
            this.Hide();
            Thread.Sleep(350); // Wait for window to minimize
            string tempFile = null;
            try
            {
                Rectangle bounds = Screen.PrimaryScreen.Bounds;
                using (Bitmap bitmap = new Bitmap(bounds.Width, bounds.Height))
                {
                    using (Graphics g = Graphics.FromImage(bitmap))
                    {
                        g.CopyFromScreen(Point.Empty, Point.Empty, bounds.Size);
                    }
                    tempFile = Path.Combine(Path.GetTempPath(), string.Format("screenshot_{0}.jpg", DateTime.Now.Ticks));
                    bitmap.Save(tempFile, System.Drawing.Imaging.ImageFormat.Jpeg);
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show("Failed to capture screenshot: " + ex.Message, "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                this.Show();
                this.Focus();
                return;
            }
            this.Show();
            this.Focus();

            if (tempFile != null)
            {
                lblConnectionState.Text = "Sending screenshot...";
                connectionStrip.BackColor = Color.FromArgb(245, 158, 11);
                
                string relPath = await Task.Run(() => UploadFile(tempFile));
                
                UpdateConnectionState((ws != null && ws.State == WebSocketState.Open) ? "CONNECTED" : "RECONNECTING");

                if (!string.IsNullOrEmpty(relPath))
                {
                    SendChatMessage("", new List<string> { relPath });
                }
            }
        }

        private void CaptureAndUploadScreenshot()
        {
            bool wasVisible = false;
            SafeInvoke(() => {
                wasVisible = this.Visible;
                if (wasVisible) this.Hide();
            });
            Thread.Sleep(300);

            string tempFile = null;
            try
            {
                Rectangle bounds = Screen.PrimaryScreen.Bounds;
                using (Bitmap bitmap = new Bitmap(bounds.Width, bounds.Height))
                {
                    using (Graphics g = Graphics.FromImage(bitmap))
                    {
                        g.CopyFromScreen(Point.Empty, Point.Empty, bounds.Size);
                    }
                    tempFile = Path.Combine(Path.GetTempPath(), string.Format("screenshot_{0}.jpg", DateTime.Now.Ticks));
                    bitmap.Save(tempFile, System.Drawing.Imaging.ImageFormat.Jpeg);
                }
            }
            catch {}

            SafeInvoke(() => {
                if (wasVisible)
                {
                    this.Show();
                    this.Focus();
                }
            });

            if (tempFile != null)
            {
                string relPath = UploadFile(tempFile);
                if (!string.IsNullOrEmpty(relPath))
                {
                    var ev = new Dictionary<string, object>();
                    ev["type"] = "screenshot_upload";
                    ev["client_id"] = clientUUID;
                    var data = new Dictionary<string, object>();
                    data["attachment_path"] = relPath;
                    ev["data"] = data;

                    SendWSMessage(new JavaScriptSerializer().Serialize(ev));
                }
            }
        }

        private void BtnSend_Click(object sender, EventArgs e)
        {
            string text = txtMessage.Text.Trim();
            if (string.IsNullOrEmpty(text) && selectedFiles.Count == 0) return;

            SendMessageWithAttachments(text);
        }

        private async void SendMessageWithAttachments(string text)
        {
            btnSend.Enabled = false;
            txtMessage.Enabled = false;
            btnAttach.Enabled = false;
            btnScreenshot.Enabled = false;

            List<string> uploadedPaths = new List<string>();
            List<string> filesToUpload = new List<string>(selectedFiles);

            selectedFiles.Clear();
            UpdateAttachmentPanel();

            if (filesToUpload.Count > 0)
            {
                lblConnectionState.Text = "Uploading file attachments...";
                connectionStrip.BackColor = Color.FromArgb(245, 158, 11); // orange
                
                await Task.Run(() => {
                    foreach (string file in filesToUpload)
                    {
                        string relPath = UploadFile(file);
                        if (!string.IsNullOrEmpty(relPath))
                        {
                            uploadedPaths.Add(relPath);
                        }
                    }
                });
                
                UpdateConnectionState((ws != null && ws.State == WebSocketState.Open) ? "CONNECTED" : "RECONNECTING");
            }

            SendChatMessage(text, uploadedPaths);

            txtMessage.Text = "";
            txtMessage.Enabled = true;
            btnSend.Enabled = true;
            btnAttach.Enabled = true;
            btnScreenshot.Enabled = true;
            txtMessage.Focus();
        }

        private string UploadFile(string filePath)
        {
            try
            {
                // Enterprise Chat Engine upload endpoint
                string uploadUrl = string.Format("http://{0}/api/enterprise/chat/upload", serverIP);
                string boundary = "---------------------------" + DateTime.Now.Ticks.ToString("x");
                byte[] boundarybytes = System.Text.Encoding.ASCII.GetBytes("\r\n--" + boundary + "\r\n");

                HttpWebRequest wr = (HttpWebRequest)WebRequest.Create(uploadUrl);
                wr.ContentType = "multipart/form-data; boundary=" + boundary;
                wr.Method = "POST";
                wr.KeepAlive = true;

                using (Stream rs = wr.GetRequestStream())
                {
                    rs.Write(boundarybytes, 0, boundarybytes.Length);

                    string header = string.Format("Content-Disposition: form-data; name=\"file\"; filename=\"{0}\"\r\nContent-Type: {1}\r\n\r\n", 
                        Path.GetFileName(filePath), GetMimeType(filePath));
                    byte[] headerbytes = System.Text.Encoding.UTF8.GetBytes(header);
                    rs.Write(headerbytes, 0, headerbytes.Length);

                    using (FileStream fileStream = new FileStream(filePath, FileMode.Open, FileAccess.Read))
                    {
                        byte[] buffer = new byte[4096];
                        int bytesRead = 0;
                        while ((bytesRead = fileStream.Read(buffer, 0, buffer.Length)) != 0)
                        {
                            rs.Write(buffer, 0, bytesRead);
                        }
                    }

                    byte[] trailer = System.Text.Encoding.ASCII.GetBytes("\r\n--" + boundary + "--\r\n");
                    rs.Write(trailer, 0, trailer.Length);
                }

                using (WebResponse wresp = wr.GetResponse())
                {
                    using (Stream stream = wresp.GetResponseStream())
                    {
                        using (StreamReader reader = new StreamReader(stream))
                        {
                            string jsonResponse = reader.ReadToEnd();
                            JavaScriptSerializer serializer = new JavaScriptSerializer();
                            Dictionary<string, object> result = serializer.Deserialize<Dictionary<string, object>>(jsonResponse);
                            if (result != null)
                            {
                                // Enterprise returns {url:"...",attachment_type:"..."}, legacy returns {attachment_path:"..."}
                                if (result.ContainsKey("url"))
                                    return result["url"].ToString();
                                if (result.ContainsKey("attachment_path"))
                                    return result["attachment_path"].ToString();
                            }
                        }
                    }
                }
            }
            catch { }
            return null;
        }

        private string GetMimeType(string filePath)
        {
            string ext = Path.GetExtension(filePath).ToLower();
            if (ext == ".png") return "image/png";
            if (ext == ".jpg" || ext == ".jpeg") return "image/jpeg";
            if (ext == ".txt") return "text/plain";
            if (ext == ".log") return "text/plain";
            if (ext == ".pdf") return "application/pdf";
            if (ext == ".zip") return "application/zip";
            return "application/octet-stream";
        }

        private void SendChatMessage(string text, List<string> attachmentPaths)
        {
            var msgData = new Dictionary<string, object>();
            msgData["message"] = text;
            msgData["attachment_url"] = string.Join(",", attachmentPaths.ToArray());

            var chatEvent = new Dictionary<string, object>();
            // Enterprise Engine uses SEND_MESSAGE, legacy uses message
            chatEvent["type"] = "SEND_MESSAGE";
            chatEvent["client_id"] = clientUUID;
            chatEvent["sender_type"] = "CLIENT";
            chatEvent["data"] = msgData;

            string json = new JavaScriptSerializer().Serialize(chatEvent);

            if (ws != null && ws.State == WebSocketState.Open)
            {
                SendWSMessage(json);
            }
            else
            {
                // Add to offline queue
                var localMsg = new ChatMessageModel();
                localMsg.ID = 0;
                localMsg.ClientID = clientUUID;
                localMsg.Sender = "CLIENT";
                localMsg.Message = text;
                localMsg.AttachmentPath = string.Join(",", attachmentPaths.ToArray());
                localMsg.ReadStatus = "PENDING";
                localMsg.CreatedAt = DateTime.Now;

                offlineQueue.Add(localMsg);
                AppendMessage(localMsg);
            }
        }

        private void FlushOfflineQueue()
        {
            if (offlineQueue.Count == 0) return;
            
            Task.Run(() => {
                try
                {
                    foreach (var msg in offlineQueue)
                    {
                        var msgData = new Dictionary<string, object>();
                        msgData["message"] = msg.Message;
                        msgData["attachment_path"] = msg.AttachmentPath;

                        var chatEvent = new Dictionary<string, object>();
                        chatEvent["type"] = "message";
                        chatEvent["client_id"] = clientUUID;
                        chatEvent["sender"] = "CLIENT";
                        chatEvent["data"] = msgData;

                        string json = new JavaScriptSerializer().Serialize(chatEvent);
                        SendWSMessage(json);
                    }
                    SafeInvoke(() => {
                        offlineQueue.Clear();
                    });
                }
                catch { }
            });
        }

        private void BtnStartChat_Click(object sender, EventArgs e)
        {
            btnStartChat.Enabled = false;
            btnStartChat.Text = "Memulai...";

            Task.Run(() =>
            {
                try
                {
                    var diagData = CollectDiagnostics();

                    SafeInvoke(() => {
                        if (ws != null && ws.State == WebSocketState.Open)
                        {
                            var diagEvent = new Dictionary<string, object>();
                            diagEvent["type"] = "diagnostic";
                            diagEvent["client_id"] = clientUUID;
                            diagEvent["data"] = diagData;
                            SendWSMessage(new JavaScriptSerializer().Serialize(diagEvent));
                        }
                        else
                        {
                            SendDiagnosticsFallback(diagData);
                        }

                        welcomePanel.Hide();
                        txtMessage.Focus();

                        // Add date separator for today when starting new chat
                        if (messagePanel.Controls.Count == 0)
                        {
                            AddDateSeparator(DateTime.Now);
                        }
                    });
                }
                catch (Exception ex)
                {
                    SafeInvoke(() => {
                        MessageBox.Show("Gagal menginisialisasi: " + ex.Message, "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                        btnStartChat.Enabled = true;
                        btnStartChat.Text = "Start Chat";
                    });
                }
            });
        }

        private void SendDiagnosticsFallback(Dictionary<string, object> diagData)
        {
            Task.Run(() => {
                try
                {
                    string url = string.Format("http://{0}/api/chat/diagnostics", serverIP);
                    HttpWebRequest request = (HttpWebRequest)WebRequest.Create(url);
                    request.Method = "POST";
                    request.ContentType = "application/json";

                    var payload = new Dictionary<string, object>();
                    payload["client_id"] = clientUUID;
                    payload["pc_name"] = pcName;
                    payload["data"] = diagData;

                    string json = new JavaScriptSerializer().Serialize(payload);
                    byte[] data = Encoding.UTF8.GetBytes(json);
                    request.ContentLength = data.Length;

                    using (Stream stream = request.GetRequestStream())
                    {
                        stream.Write(data, 0, data.Length);
                    }

                    using (WebResponse response = request.GetResponse()) { }
                }
                catch { }
            });
        }

        private Dictionary<string, object> CollectDiagnostics()
        {
            var diag = new Dictionary<string, object>();
            
            // 1. CPU
            string cpuInfo = "Unknown CPU";
            try
            {
                using (var searcher = new ManagementObjectSearcher("SELECT Name, LoadPercentage FROM Win32_Processor"))
                {
                    foreach (ManagementObject obj in searcher.Get())
                    {
                        cpuInfo = string.Format("{0}% Load ({1})", obj["LoadPercentage"], obj["Name"]);
                        break;
                    }
                }
            }
            catch { cpuInfo = "CPU: Load unknown"; }
            diag["cpu"] = cpuInfo;

            // 2. RAM
            string ramInfo = "Unknown RAM";
            try
            {
                using (var searcher = new ManagementObjectSearcher("SELECT TotalVisibleMemorySize, FreePhysicalMemory FROM Win32_OperatingSystem"))
                {
                    foreach (ManagementObject obj in searcher.Get())
                    {
                        double total = Convert.ToDouble(obj["TotalVisibleMemorySize"]) / 1024.0 / 1024.0;
                        double free = Convert.ToDouble(obj["FreePhysicalMemory"]) / 1024.0 / 1024.0;
                        double used = total - free;
                        ramInfo = string.Format("{0:F1} GB / {1:F1} GB Used ({2:F1}% Used)", used, total, (used / total) * 100.0);
                        break;
                    }
                }
            }
            catch { ramInfo = "RAM: Usage unknown"; }
            diag["ram"] = ramInfo;

            // 3. Disk
            List<string> diskDrives = new List<string>();
            try
            {
                foreach (var drive in DriveInfo.GetDrives())
                {
                    if (drive.IsReady && drive.DriveType == DriveType.Fixed)
                    {
                        double free = drive.TotalFreeSpace / 1024.0 / 1024.0 / 1024.0;
                        double total = drive.TotalSize / 1024.0 / 1024.0 / 1024.0;
                        double used = total - free;
                        diskDrives.Add(string.Format("{0} Free {1:F1}GB/{2:F1}GB ({3:F1}% Used)", 
                            drive.Name, free, total, (used / total) * 100.0));
                    }
                }
            }
            catch { }
            diag["disk"] = string.Join("; ", diskDrives.ToArray());

            // 4. SMART
            string smartStatus = "SMART OK";
            try
            {
                using (var searcher = new ManagementObjectSearcher("root\\WMI", "SELECT PredictFailure FROM MSStorageDriver_FailurePredictStatus"))
                {
                    foreach (ManagementObject obj in searcher.Get())
                    {
                        bool failure = Convert.ToBoolean(obj["PredictFailure"]);
                        if (failure)
                        {
                            smartStatus = "SMART FAILURE PREDICTED";
                            break;
                        }
                    }
                }
            }
            catch { smartStatus = "SMART OK (Status check skipped)"; }
            diag["smart"] = smartStatus;

            // 5. Services
            List<string> servicesList = new List<string>();
            try
            {
                using (var searcher = new ManagementObjectSearcher("SELECT Name, State FROM Win32_Service WHERE Name IN ('Spooler', 'wuauserv')"))
                {
                    foreach (ManagementObject obj in searcher.Get())
                    {
                        servicesList.Add(string.Format("{0}={1}", obj["Name"], obj["State"]));
                    }
                }
            }
            catch { }
            diag["services"] = string.Join(", ", servicesList.ToArray());

            // 6. Network
            List<string> ips = new List<string>();
            try
            {
                foreach (var ni in System.Net.NetworkInformation.NetworkInterface.GetAllNetworkInterfaces())
                {
                    if (ni.OperationalStatus == System.Net.NetworkInformation.OperationalStatus.Up && 
                        ni.NetworkInterfaceType != System.Net.NetworkInformation.NetworkInterfaceType.Loopback)
                    {
                        foreach (var ip in ni.GetIPProperties().UnicastAddresses)
                        {
                            if (ip.Address.AddressFamily == System.Net.Sockets.AddressFamily.InterNetwork)
                            {
                                ips.Add(ip.Address.ToString());
                            }
                        }
                    }
                }
            }
            catch { }
            diag["network"] = string.Join(", ", ips.ToArray());

            // 7. Active Processes
            List<string> processes = new List<string>();
            try
            {
                foreach (var p in Process.GetProcesses())
                {
                    string name = p.ProcessName.ToLower();
                    if (name == "chrome" || name == "msedge" || name == "firefox" || name == "explorer" || name == "rustdesk" || name == "anydesk")
                    {
                        if (!processes.Contains(name))
                        {
                            processes.Add(name);
                        }
                    }
                }
            }
            catch { }
            diag["processes"] = string.Join(", ", processes.ToArray());

            // 8. Event Log
            List<string> errors = new List<string>();
            try
            {
                using (EventLog log = new EventLog("System"))
                {
                    int count = 0;
                    for (int i = log.Entries.Count - 1; i >= 0 && count < 5; i--)
                    {
                        var entry = log.Entries[i];
                        if (entry.EntryType == EventLogEntryType.Error)
                        {
                            string rawMsg = entry.Message;
                            string shortMsg = rawMsg.Length > 80 ? rawMsg.Substring(0, 80) + "..." : rawMsg;
                            errors.Add(string.Format("[{0}] {1}", entry.Source, shortMsg));
                            count++;
                        }
                    }
                }
            }
            catch { }
            diag["event_log"] = string.Join(" | ", errors.ToArray());

            diag["hostname"] = Environment.MachineName;
            diag["os_version"] = Environment.OSVersion.ToString();
            diag["agent_version"] = "2.0.0-Tray";
            
            return diag;
        }

        private string GetCPUNameSimple()
        {
            try
            {
                using (var searcher = new ManagementObjectSearcher("SELECT Name FROM Win32_Processor"))
                {
                    foreach (ManagementObject obj in searcher.Get())
                    {
                        return obj["Name"].ToString();
                    }
                }
            }
            catch { }
            return "Unknown CPU";
        }

        private string GetRAMSizeSimple()
        {
            try
            {
                using (var searcher = new ManagementObjectSearcher("SELECT TotalVisibleMemorySize FROM Win32_OperatingSystem"))
                {
                    foreach (ManagementObject obj in searcher.Get())
                    {
                        double total = Convert.ToDouble(obj["TotalVisibleMemorySize"]) / 1024.0 / 1024.0;
                        return string.Format("{0:F1} GB", total);
                    }
                }
            }
            catch { }
            return "Unknown RAM";
        }
    }
}
