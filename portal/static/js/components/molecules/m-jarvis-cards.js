/**
 * Atomic Design — Molecule Layer: JARVIS Conversation Bubbles, HITL Banners & Task Cards
 * Path: /static/js/components/molecules/m-jarvis-cards.js
 * Provides: window.UI.Molecules.JarvisCards
 */
(function (global) {
  const JarvisCards = {
    createUserBubble(cleanQuery) {
      const userBubble = document.createElement('div');
      userBubble.className = 'bubble-usr';
      userBubble.innerHTML = `🎤 <strong>User:</strong> "${cleanQuery}"`;
      return userBubble;
    },

    createJarvisBubble(opts) {
      const {
        replyText = '',
        urgencyLevel = 'NORMAL',
        actionCardHtml = '',
        actionUrl = '',
        confScore = '98%',
        evidenceStr = 'OSI Ensemble Consensus & Knowledge Base'
      } = opts || {};

      const jarvisBubble = document.createElement('div');
      jarvisBubble.className = 'bubble-jrv';

      const badges = (global.UI && global.UI.Atoms && global.UI.Atoms.JarvisBadges) || null;
      const urgencyBadge = badges ? badges.renderUrgencyBadge(urgencyLevel) : '';

      if (urgencyLevel === 'EMERGENCY') {
        jarvisBubble.style.borderLeft = '3px solid #ef4444';
        jarvisBubble.style.boxShadow = '0 0 8px rgba(239,68,68,0.4)';
      } else if (urgencyLevel === 'HIGH') {
        jarvisBubble.style.borderLeft = '3px solid #f59e0b';
      }

      const finalCardHtml = actionCardHtml || (badges && actionUrl ? badges.renderMediaLinkButton(actionUrl) : '');
      jarvisBubble.innerHTML = `${urgencyBadge}🤖 <strong>Jarvis:</strong> "${replyText}"${finalCardHtml}<div class="jrv-meta"><span class="meta-conf">Confidence: ${confScore}</span><span class="meta-ev">Evidence: ${evidenceStr}</span></div>`;
      return jarvisBubble;
    },

    createProactiveBubble(data) {
      const jrvBubble = document.createElement('div');
      jrvBubble.className = 'bubble-jrv';
      jrvBubble.innerHTML = `📢 <strong>Jarvis (Proaktif):</strong> "${data.text}"<div class="jrv-meta"><span class="meta-conf">Severity: ${data.severity || 'INFO'}</span><span class="meta-ev">Device: ${data.device || 'System'}</span></div>`;
      return jrvBubble;
    },

    createHitlBanner(hitlQueueId) {
      const hitlBanner = document.createElement('div');
      hitlBanner.style.cssText = 'margin-top:6px;padding:8px 12px;background:rgba(245,158,11,0.15);border:1px solid #f59e0b;border-radius:6px;font-size:10px;color:#fbbf24;font-weight:bold;';
      hitlBanner.innerHTML = `⚠️ MENUNGGU PERSETUJUAN HITL — Queue: ${hitlQueueId || 'PENDING'} | Konfirmasi wajib melalui tombol HITL di panel Approval Queue Dashboard NOC (Kebijakan K-07)`;
      return hitlBanner;
    },

    renderTaskItem(t) {
      const isDone = t.status === 'COMPLETED';
      return `
        <div style="display:flex; align-items:center; justify-content:space-between; padding:5px 8px; background:rgba(3,10,20,0.8); border:1px solid ${isDone ? '#059669' : 'rgba(0,240,255,0.25)'}; border-radius:6px; font-size:10px;">
          <div style="display:flex; align-items:center; gap:8px;">
            <input type="checkbox" ${isDone ? 'checked' : ''} onchange="JarvisTaskManager.toggle('${t.id}')" style="cursor:pointer; accent-color:#00F0FF;">
            <span style="color:${isDone ? '#64748b' : '#e2e8f0'}; text-decoration:${isDone ? 'line-through' : 'none'}; font-weight:${isDone ? 'normal' : '600'};">${t.text}</span>
          </div>
          <div style="display:flex; align-items:center; gap:6px;">
            <span style="color:#64748b; font-size:9px; font-family:monospace;">${t.time}</span>
            <button onclick="JarvisTaskManager.deleteTask('${t.id}')" style="background:none; border:none; color:#f87171; cursor:pointer; font-size:11px;">✕</button>
          </div>
        </div>
      `;
    },

    buildSandboxTestModalBody(opts) {
      const {
        incId = 'SYS',
        devName = 'SYSTEM',
        desc = 'Anomali telemetri terdeteksi',
        actionCode = 'ACT_AUTO_REMEDIATE',
        rcaSummary = 'Anomali layanan terdeteksi dari telemetri perangkat.',
        dryRunMs = 48,
        scorePct = '99.2%'
      } = opts || {};

      return `
        <div style="padding:10px; font-size:12px; color:var(--txt);">
          <div style="background:rgba(139,92,246,0.1); border:1px solid rgba(139,92,246,0.3); padding:12px; border-radius:8px; margin-bottom:16px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
              <strong style="color:var(--purple); font-size:14px;"><i class="fa-solid fa-flask-vial"></i> AI Sandbox Pipeline Test (6-Stage Isolation)</strong>
              <span class="tag tag-purple" style="font-weight:700;">SANDBOX_DRAFT → VALIDATED</span>
            </div>
            <div style="color:var(--txt2); font-size:11px;">
              Target Perangkat: <strong style="color:#fff;">${devName}</strong> | ID Insiden: <strong style="color:var(--cyan);">${incId}</strong>
            </div>
            <div style="color:var(--txt3); font-size:10.5px; margin-top:4px;">
              Deskripsi: <em>${desc}</em>
            </div>
          </div>

          <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:10px; margin-bottom:16px;">
            <div style="background:rgba(15,23,42,0.8); border:1px solid rgba(34,197,94,0.3); padding:10px; border-radius:6px;">
              <div style="color:var(--green); font-size:10.5px; font-weight:700;"><i class="fa-solid fa-check-circle"></i> Stage 0 & 1: Intake & Staging</div>
              <div style="color:var(--txt3); font-size:10px; margin-top:4px;">Karantina UUID dibuat. Lingkungan virtual terisolasi aktif.</div>
            </div>
            <div style="background:rgba(15,23,42,0.8); border:1px solid rgba(6,182,212,0.3); padding:10px; border-radius:6px;">
              <div style="color:var(--cyan); font-size:10.5px; font-weight:700;"><i class="fa-solid fa-shield-halved"></i> Stage 2 & 3: Threat Scan & Dry Run</div>
              <div style="color:var(--txt3); font-size:10px; margin-top:4px;">0 Vulnerabilities. Simulasi <code>${actionCode}</code> aman tanpa efek samping.</div>
            </div>
            <div style="background:rgba(15,23,42,0.8); border:1px solid rgba(139,92,246,0.3); padding:10px; border-radius:6px;">
              <div style="color:var(--purple); font-size:10.5px; font-weight:700;"><i class="fa-solid fa-award"></i> Stage 4 & 5: Golden & Rule #6</div>
              <div style="color:var(--txt3); font-size:10px; margin-top:4px;">Skor Verifikasi Simulasi: ${scorePct} PASS (${dryRunMs}ms).</div>
            </div>
          </div>

          <div style="background:rgba(0,0,0,0.4); border:1px solid rgba(255,255,255,0.1); border-radius:8px; padding:14px;">
            <div style="font-size:12px; font-weight:700; color:#fff; margin-bottom:8px; display:flex; align-items:center; justify-content:space-between;">
              <span>📊 Hasil Analisis Root Cause & Remedi Sandbox:</span>
              <span class="tag tag-green">✅ SANDBOX VERIFIED</span>
            </div>
            <ul style="margin:0; padding-left:18px; color:var(--txt2); line-height:1.7; font-size:11px;">
              <li><strong>Akar Masalah (RCA)</strong>: ${rcaSummary}</li>
              <li><strong>Verifikasi Simulasi Dry-Run</strong>: Prosedur <code>${actionCode}</code> diuji dalam <strong>${dryRunMs}ms</strong> di sandbox terisolasi tanpa dampak downtime pada <strong>${devName}</strong>.</li>
              <li><strong>Governance Rule #6 (Dual-Evidence Gate)</strong>: Saat dieksekusi, status insiden dikunci pada <code>PENDING_VERIFICATION</code> hingga <code>execution_evidence</code> (ACK Agent) dan <code>post_remediation_evidence</code> (T_post &ge; T_exec) terverifikasi.</li>
            </ul>
          </div>
        </div>
      `;
    },

    buildLearningGateDetailModal(log, meta) {
      const { conf, ts, confColor, isBlocked, eventTitle, reasoningText } = meta;
      const safeJson = JSON.stringify(log).replace(/"/g, '&quot;');
      return `
        <div id="learning-log-modal-overlay" style="position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.75);backdrop-filter:blur(4px);z-index:99999;display:flex;align-items:center;justify-content:center;padding:20px;animation:fadeIn .2s ease">
          <div style="background:var(--bg2,#121824);border:1px solid var(--border,#1e293b);border-radius:12px;width:100%;max-width:760px;max-height:90vh;overflow-y:auto;box-shadow:0 25px 50px -12px rgba(0,0,0,0.5);color:var(--txt1,#f8fafc)">
            <div style="padding:16px 20px;border-bottom:1px solid var(--border,#1e293b);display:flex;align-items:center;justify-content:space-between;background:rgba(16,185,129,0.08)">
              <div style="display:flex;align-items:center;gap:10px">
                <div style="width:36px;height:36px;border-radius:8px;background:rgba(16,185,129,0.2);display:flex;align-items:center;justify-content:center;color:#10b981;font-size:18px">
                  <i class="fa-solid fa-graduation-cap"></i>
                </div>
                <div>
                  <h3 style="margin:0;font-size:16px;font-weight:700;color:#f8fafc">Audit Gerbang Pembelajaran Kontinu AI #${log.id}</h3>
                  <div style="font-size:11px;color:var(--txt2,#94a3b8);margin-top:2px">Incident ID: INC-${log.incident_id || 'SYS'} · ${ts}</div>
                </div>
              </div>
              <button onclick="document.getElementById('learning-log-modal-overlay').remove()" style="background:transparent;border:none;color:var(--txt2,#94a3b8);font-size:20px;cursor:pointer;padding:4px 8px"><i class="fa-solid fa-xmark"></i></button>
            </div>
            <div style="padding:20px;display:flex;flex-direction:column;gap:16px">
              <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:12px">
                <div style="background:rgba(255,255,255,0.03);border:1px solid var(--border,#1e293b);border-radius:8px;padding:12px">
                  <div style="font-size:11px;color:var(--txt2,#94a3b8);margin-bottom:4px"><i class="fa-solid fa-shield-cat" style="color:#10b981;margin-right:4px"></i>Status Keputusan Governance</div>
                  <div style="font-size:15px;font-weight:800;color:${isBlocked ? '#ef4444' : '#10b981'};margin-top:4px">
                    ${isBlocked ? '🛡️ DITOLAK FILTER KEAMANAN' : '✅ DISETUJUI UNTUK PEMBELAJARAN'}
                  </div>
                  <div style="font-size:10px;color:var(--txt3,#64748b);margin-top:2px">Cognitive Safety & Guardrail Filter (Rule #6 Compliant)</div>
                </div>
                <div style="background:rgba(255,255,255,0.03);border:1px solid var(--border,#1e293b);border-radius:8px;padding:12px">
                  <div style="font-size:11px;color:var(--txt2,#94a3b8);margin-bottom:4px"><i class="fa-solid fa-chart-line" style="color:#38bdf8;margin-right:4px"></i>Tingkat Kepercayaan Pembelajaran</div>
                  <div style="font-size:20px;font-weight:800;color:${confColor}">${conf}%</div>
                  <div style="font-size:10px;color:var(--txt3,#64748b);margin-top:2px">Evaluasi Konsensus Multi-LLM</div>
                </div>
              </div>
              <div style="background:rgba(56,189,248,0.05);border:1px solid rgba(56,189,248,0.2);border-radius:8px;padding:14px">
                <div style="font-size:12px;font-weight:700;color:#38bdf8;margin-bottom:6px;display:flex;align-items:center;gap:6px">
                  <i class="fa-solid fa-bell"></i> Peristiwa / Anomali Terdeteksi (Detected Event)
                </div>
                <div style="font-size:13px;font-weight:600;color:#f8fafc">${eventTitle}</div>
              </div>
              <div style="background:rgba(255,255,255,0.02);border:1px solid var(--border,#1e293b);border-radius:8px;padding:14px">
                <div style="font-size:12px;font-weight:700;color:#f59e0b;margin-bottom:6px;display:flex;align-items:center;gap:6px">
                  <i class="fa-solid fa-diagram-project"></i> Alasan & Evaluasi Gerbang Kognitif (Learning Gate Reasoning)
                </div>
                <div style="font-size:12.5px;line-height:1.6;color:var(--txt1,#f8fafc);background:rgba(0,0,0,0.25);padding:12px;border-radius:6px;border-left:3px solid #f59e0b">${reasoningText}</div>
              </div>
            </div>
            <div style="padding:14px 20px;border-top:1px solid var(--border,#1e293b);display:flex;justify-content:space-between;align-items:center;background:rgba(0,0,0,0.2)">
              <button class="btn btn-secondary btn-sm" onclick="navigator.clipboard.writeText(JSON.stringify(${safeJson}));Notify.toast('📋 Copied','Log audit disalin ke clipboard','ok')" style="padding:6px 14px">
                <i class="fa-solid fa-copy" style="margin-right:4px"></i> Salin JSON Audit
              </button>
              <button class="btn btn-primary btn-sm" onclick="document.getElementById('learning-log-modal-overlay').remove()" style="padding:6px 18px">Tutup</button>
            </div>
          </div>
        </div>
      `;
    }
  };

  global.UI = global.UI || {};
  global.UI.Molecules = global.UI.Molecules || {};
  global.UI.Molecules.JarvisCards = JarvisCards;
})(window);
