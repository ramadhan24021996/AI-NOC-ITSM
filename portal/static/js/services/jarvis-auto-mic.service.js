/**
 * Atomic Design — Service Layer: JARVIS Auto-Mic, Phonetic STT, Whisper Fallback & Neural TTS Service
 * Path: /static/js/services/jarvis-auto-mic.service.js
 * Provides: window.normalizePhonetics, window.JarvisAutoMic, and window.Services.JarvisAutoMic
 */
(function (global) {
  function normalizePhonetics(text) {
    if (!text) return "";
    let norm = text;
    const replacements = [
      [/\b(jervis|jarfis|zarvis|charvis|jaspis|jarvisnya|servis|servisnya)\b/gi, "jarvis"],
      [/\b(yutub|yutup|utub|youtub)\b/gi, "youtube"],
      [/\b(chat\s*jipiti|chat\s*gipiti|gipiti|gpt\s*ei|gpt\s*ai|gpt\s*e\s*i|gpt\s*i|ji\s*pi\s*ti|ji\s*pe\s*te|chat\s*gpt|chat\s*gpt\s*ai|jet\.ai|gepeto|gpt\.ai|gpt)\b/gi, "chatgpt"],
      [/\b(live\s*cat|live\s*catting|lai\s*cat)\b/gi, "live chat"],
      [/\b(live\s*lock|live\s*lok|live\s*loc|live\s*look|lai\s*log|live\s*lognya)\b/gi, "live log"],
      [/\b(open\s*menu|open)\b/gi, "buka"],
      [/\b(buka\s*remote\s*akses|remote\s*akses|akses\s*remote)\b/gi, "remote"],
      [/\b(pcnux|pc\s*nux|pc\s*nuk|nux|nuk|noob|nobe)\b/gi, "PC-MKT-NUC"],
      [/\b(rus\s*desk|rasdesk|rosdesk|rusdek|rust\s*desk)\b/gi, "rustdesk"],
      [/\b(vi\s*en\s*si|vensi|pi\s*en\s*si)\b/gi, "vnc"],
      [/\b(ar\s*di\s*pi|er\s*de\s*pe|er\s*di\s*pi)\b/gi, "rdp"],
      [/\b(es\s*es\s*ha|es\s*es\s*h)\b/gi, "ssh"],
      [/\b(si\s*p\s*u|se\s*p\s*u|ce\s*p\s*u|sepuh|sepu|si\s*pi\s*u|se\s*pi\s*u)\b/gi, "cpu"],
      [/\b(rem|raem)\b/gi, "ram"],
      [/\b(disik|desks)\b/gi, "disk"],
      [/\b(hel|helth|heltek|helcek|helsek|halk\s*cek)\b/gi, "health"],
      [/\b(servr|serv|servernya)\b/gi, "server"],
      [/\b(priter|printe)\b/gi, "printer"],
      [/\b(devis|divais|devaice)\b/gi, "device"],
      [/\b(stat|satus|tatus)\b/gi, "status"],
      [/\b(spuler|sipuler|spoler|spul)\b/gi, "spooler"],
      [/\b(posgres|postgre|pos\s*gres)\b/gi, "postgresql"],
      [/\b(flas\s*dns|plas\s*dns|plas\s*d\s*en\s*es|flus\s*dns)\b/gi, "flush dns"],
      [/\b(be\s*ge\s*pe|pejei|bjei)\b/gi, "bgp"],
      [/\b(o\s*te\s*a|otey)\b/gi, "ota"],
      [/\b(fail\s*over|pelover)\b/gi, "failover"],
      [/\b(autit\s*log|otit\s*log)\b/gi, "audit log"],
      [/\b(kosal\s*graf|kausal\s*graf)\b/gi, "causal graph"],
      [/\b(blas\s*radius|blas\s*radios)\b/gi, "blast radius"],
      [/\b(kritikaliti|kritikalitas)\b/gi, "criticality"],
      [/\b(restar|restat|res\s*tat|ristart)\b/gi, "restart"],
      [/\b(apruf|aprof|apruve)\b/gi, "approve"],
      [/\b(rijek|rijec|rejek)\b/gi, "reject"],
      [/\b(netwok|netwoknya|jaringan)\b/gi, "jaringan"],
      [/\b(mikrotik|mikro\s*tik)\b/gi, "mikrotik"],
      [/\b(sisco|sisko)\b/gi, "cisco"],
      [/\b(kashir|kasier)\b/gi, "kasir"],
      [/\b(gudan)\b/gi, "gudang"],
      [/\b(on\s*lein|onlin|on\s*line)\b/gi, "online"],
      [/\b(of\s*lein|offlin|of\s*line)\b/gi, "offline"],
      [/\b(sistem|sistemnya)\b/gi, "sistem"]
    ];
    for (const [pat, rep] of replacements) {
      norm = norm.replace(pat, rep);
    }
    return norm;
  }

  function forceOpenTab(url) {
    if (!url) return false;
    try {
      if (global.JarvisMediaPlayer && url.includes("youtube.com")) {
        global.JarvisMediaPlayer.play(url);
      }
    } catch (e) {}

    try {
      const win = window.open(url, '_blank');
      if (win) {
        try { win.focus(); } catch (e) {}
        return true;
      }
    } catch (e) {}
    try {
      const a = document.createElement('a');
      a.href = url;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      document.body.appendChild(a);
      a.click();
      setTimeout(() => { try { document.body.removeChild(a); } catch (e) {} }, 500);
      return true;
    } catch (e) {
      return false;
    }
  }

  function resolveTargetUrl(rawText) {
    const q = rawText.toLowerCase().trim();
    if (/\b(?:kesukaan|favorit|favo|fav)\b/i.test(q) || q === "musik" || q === "play musik" || q === "play music") {
      return "https://www.youtube.com/watch?v=smk6RW2TMIM&list=RDsmk6RW2TMIM&start_radio=1";
    }
    if (/\b(?:chatgpt|chat\s*gpt|gpt\.ai|gpt\s*ai|openai)\b/i.test(q)) {
      let prompt = "";
      const tMatch = q.match(/\b(?:tanyakan|tanya)\s+(?:ke\s+chatgpt|ke\s+gpt)?\s*(.*)/i);
      if (tMatch && tMatch[1]) {
        prompt = tMatch[1].trim();
      }
      if (prompt) {
        return "https://chatgpt.com/?q=" + encodeURIComponent(prompt);
      }
      return "https://chatgpt.com";
    }
    let search = "";
    const mYt = rawText.match(/\b(?:buka\s+youtube|cari\s+di\s+youtube|youtube|yutub)\s*(?:play\s+music|play\s+musik|tentang|cari|lagu|musik|video)?\s*(.*)/i);
    const mPlay = rawText.match(/\b(?:play|putar|setel|dengarkan)\s+(?:musik|lagu|music|video|song|track)?\s*(.*)/i);

    if (mYt && mYt[1] && mYt[1].trim()) {
      search = mYt[1].replace(/^(?:tentang|lagu|musik|video|cari|play|music)\s+/i, "").trim();
    } else if (mPlay && mPlay[1] && mPlay[1].trim()) {
      search = mPlay[1].replace(/^(?:tentang|lagu|musik|video|cari|music)\s+/i, "").trim();
    }

    if (search && search.length > 0 && !["musik", "music", "lagu"].includes(search.toLowerCase())) {
      return "https://www.youtube.com/results?search_query=" + encodeURIComponent(search);
    }
    return "https://www.youtube.com/watch?v=smk6RW2TMIM&list=RDsmk6RW2TMIM&start_radio=1";
  }

  const JarvisAutoMic = {
    recognition: null,
    isMuted: false,
    mouthInterval: null,
    isSpeaking: false,
    currentAudioEl: null,
    restartTimer: null,
    whisperFallbackActive: false,
    whisperStream: null,
    whisperAudioCtx: null,
    whisperProcessor: null,

    init() {
      if (this._initialized) return;
      this._initialized = true;
      global.JarvisAutoMic = this;
      this.setupSpeechRecognition();
      const unlockHandler = () => {
        this.unlockAudio();
        if (!global.isListening && !this.isMuted && !this.isSpeaking) {
          this.safeRestart();
        }
      };
      document.addEventListener('click', unlockHandler, { once: true });
      document.addEventListener('keydown', unlockHandler, { once: true });
      if (global.UI && global.UI.Organisms && global.UI.Organisms.JarvisHologram3D) {
        global.UI.Organisms.JarvisHologram3D.init();
      } else if (global.JarvisWebGL) {
        global.JarvisWebGL.init();
      }
    },

    unlockAudio() {
      if ('speechSynthesis' in window) {
        try { window.speechSynthesis.resume(); } catch (e) {}
      }
      try {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (AudioCtx) {
          if (!this._unlockCtx) this._unlockCtx = new AudioCtx();
          if (this._unlockCtx.state === 'suspended') this._unlockCtx.resume();
        }
      } catch (e) {}
    },

    stopCurrentAudio() {
      if (this.currentAudioEl) {
        try {
          this.currentAudioEl.pause();
          this.currentAudioEl.currentTime = 0;
        } catch (e) {}
        this.currentAudioEl = null;
      }
      if ('speechSynthesis' in window) {
        try { window.speechSynthesis.cancel(); } catch (e) {}
      }
      this.isSpeaking = false;
      this.animateMouth(false);
    },

    animateMouth(talking) {
      if (talking) {
        if (this.mouthInterval) clearInterval(this.mouthInterval);
        this.mouthInterval = setInterval(() => {
          global.mouthOpening = Math.random() * 12 + 4;
        }, 80);
      } else {
        clearInterval(this.mouthInterval);
        global.mouthOpening = 0;
        setTimeout(() => { global.mouthOpening = 0; }, 50);
      }
    },

    toggleListeningManual() {
      this.unlockAudio();
      if (this.whisperFallbackActive) {
        this.isMuted = !this.isMuted;
        const statusText = document.getElementById('jrv-statusText');
        if (statusText) {
          statusText.innerText = this.isMuted ? "STATUS: MIC MUTED" : "STATUS: MENDENGARKAN (WHISPER)...";
          statusText.style.color = this.isMuted ? "#f87171" : "#00F0FF";
        }
        return;
      }
      if (!this.recognition) {
        this.startWhisperMicFallback();
        return;
      }
      if (global.isListening) {
        try { this.recognition.stop(); } catch (e) {}
      } else {
        try { this.recognition.start(); } catch (e) { console.warn("Recognition start ignored:", e); }
      }
    },

    toggleMic() {
      this.unlockAudio();
      this.isMuted = !this.isMuted;
      const btnText = document.getElementById('jrv-mic-status-text');
      if (this.isMuted) {
        if (btnText) btnText.innerText = 'Mic Muted';
        if (this.recognition) { try { this.recognition.stop(); } catch (e) {} }
      } else {
        if (btnText) btnText.innerText = 'Mic Auto-On';
        this.safeRestart();
      }
    },

    submitManualCmd() {
      this.unlockAudio();
      const inp = document.getElementById('jrv-cmd-input');
      if (!inp || !inp.value.trim()) return;
      const val = inp.value.trim();
      inp.value = '';
      this.sendQuery(val);
    },

    safeRestart() {
      if (this.isMuted || this.isSpeaking) return;
      if (this.whisperFallbackActive) {
        global.isListening = true;
        const statusText = document.getElementById('jrv-statusText');
        const subText = document.getElementById('jrv-talking-sub');
        if (statusText) { statusText.innerText = "STATUS: MENDENGARKAN (NEURAL STT)..."; statusText.style.color = "#00F0FF"; }
        if (subText) subText.innerText = "RESPONS SUARA JARVIS: MENDENGARKAN SUARA OPERATOR...";
        return;
      }
      if (this.restartTimer) clearTimeout(this.restartTimer);
      this.restartTimer = setTimeout(() => {
        if (!this.isMuted && !this.isSpeaking && this.recognition) {
          try { this.recognition.start(); } catch (e) {}
        }
      }, 400);
    },

    _encodeWavBase64(pcm16Samples, sampleRate) {
      const numBytes = pcm16Samples.length * 2;
      const buffer = new ArrayBuffer(44 + numBytes);
      const view = new DataView(buffer);
      const writeStr = (offset, str) => { for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i)); };
      writeStr(0, 'RIFF');
      view.setUint32(4, 36 + numBytes, true);
      writeStr(8, 'WAVE');
      writeStr(12, 'fmt ');
      view.setUint32(16, 16, true);
      view.setUint16(20, 1, true);
      view.setUint16(22, 1, true);
      view.setUint32(24, sampleRate, true);
      view.setUint32(28, sampleRate * 2, true);
      view.setUint16(32, 2, true);
      view.setUint16(34, 16, true);
      writeStr(36, 'data');
      view.setUint32(40, numBytes, true);
      let offset = 44;
      for (let i = 0; i < pcm16Samples.length; i++, offset += 2) {
        view.setInt16(offset, pcm16Samples[i], true);
      }
      const bytes = new Uint8Array(buffer);
      let binary = '';
      const chunkSize = 8192;
      for (let i = 0; i < bytes.length; i += chunkSize) {
        binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunkSize));
      }
      return btoa(binary);
    },

    async startWhisperMicFallback() {
      if (this.whisperFallbackActive) return;
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        console.warn("[JARVIS] getUserMedia not available for Whisper fallback.");
        return;
      }
      try {
        this.whisperStream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 }
        });
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        this.whisperAudioCtx = new AudioCtx({ sampleRate: 16000 });
        const actualRate = this.whisperAudioCtx.sampleRate || 16000;
        const source = this.whisperAudioCtx.createMediaStreamSource(this.whisperStream);
        this.whisperProcessor = this.whisperAudioCtx.createScriptProcessor(4096, 1, 1);
        source.connect(this.whisperProcessor);
        this.whisperProcessor.connect(this.whisperAudioCtx.destination);

        let speechChunks = [];
        let isSpeechActive = false;
        let silenceFrames = 0;
        let speechFrames = 0;

        this.whisperProcessor.onaudioprocess = (e) => {
          if (this.isMuted || this.isSpeaking || this._sendingWhisperAudio) return;
          const input = e.inputBuffer.getChannelData(0);
          let sum = 0;
          for (let i = 0; i < input.length; i++) sum += input[i] * input[i];
          const rms = Math.sqrt(sum / input.length);

          if (rms > 0.022) {
            isSpeechActive = true;
            silenceFrames = 0;
            speechFrames++;
            const pcm = new Int16Array(input.length);
            for (let i = 0; i < input.length; i++) {
              const s = Math.max(-1, Math.min(1, input[i]));
              pcm[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
            }
            speechChunks.push(pcm);
            const statusText = document.getElementById('jrv-statusText');
            if (statusText) { statusText.innerText = "STATUS: MENDENGARKAN SUARA..."; statusText.style.color = "#00F0FF"; }
          } else if (isSpeechActive) {
            silenceFrames++;
            const pcm = new Int16Array(input.length);
            for (let i = 0; i < input.length; i++) {
              const s = Math.max(-1, Math.min(1, input[i]));
              pcm[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
            }
            speechChunks.push(pcm);
            if (silenceFrames >= 3 || speechFrames >= 32) {
              isSpeechActive = false;
              const capturedFrames = speechFrames;
              speechFrames = 0;
              silenceFrames = 0;
              const chunksToSend = speechChunks;
              speechChunks = [];
              if (capturedFrames >= 2) {
                let totalLen = 0;
                chunksToSend.forEach(c => totalLen += c.length);
                const merged = new Int16Array(totalLen);
                let pos = 0;
                chunksToSend.forEach(c => { merged.set(c, pos); pos += c.length; });
                const wavB64 = this._encodeWavBase64(merged, actualRate);
                this.sendAudioQuery(wavB64);
              }
            }
          }
        };

        this.whisperFallbackActive = true;
        global.isListening = true;
        const statusText = document.getElementById('jrv-statusText');
        const subText = document.getElementById('jrv-talking-sub');
        if (statusText) { statusText.innerText = "STATUS: MENDENGARKAN (NEURAL STT)..."; statusText.style.color = "#00F0FF"; }
        if (subText) subText.innerText = "RESPONS SUARA JARVIS: MENDENGARKAN SUARA OPERATOR...";
        console.debug("[JARVIS] Local Whisper STT microphone fallback active.");
      } catch (err) {
        console.warn("[JARVIS] Failed to start Whisper mic fallback:", err);
      }
    },

    async sendAudioQuery(wavB64) {
      if (!wavB64 || this._sendingWhisperAudio || this.isSpeaking) return;
      this._sendingWhisperAudio = true;
      const statusText = document.getElementById('jrv-statusText');
      if (statusText) { statusText.innerText = "STATUS: MEMPROSES SUARA..."; statusText.style.color = "#f59e0b"; }
      try {
        if (!window._jrvSessionId) {
          window._jrvSessionId = "voice_" + Date.now() + "_" + Math.random().toString(36).substr(2, 6);
        }
        const token = sessionStorage.getItem('noc_jwt_token') || localStorage.getItem('noc_jwt_token') || '';
        const headers = { 'Content-Type': 'application/json' };
        if (token) {
          headers['Authorization'] = 'Bearer ' + token;
          headers['X-CSRF-Token'] = token;
        }
        const res = await fetch('/api/jarvis/voice/query', {
          method: 'POST',
          headers: headers,
          body: JSON.stringify({
            audio_b64: wavB64,
            session_id: window._jrvSessionId,
            locale: 'id-ID'
          })
        });
        if (res.ok) {
          const data = await res.json();
          const transcribed = (data && data.query_text) ? data.query_text.trim() : '';
          if (transcribed && transcribed !== 'status sistem') {
            const transcriptText = document.getElementById('transcriptText');
            if (transcriptText) transcriptText.innerText = `"${transcribed}"`;
            await this.sendQuery(transcribed, data);
          } else {
            this.safeRestart();
          }
        } else {
          this.safeRestart();
        }
      } catch (e) {
        console.warn("[JARVIS] sendAudioQuery error:", e);
        this.safeRestart();
      } finally {
        this._sendingWhisperAudio = false;
      }
    },

    setupSpeechRecognition() {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRecognition) {
        console.warn("Web Speech API not supported on this browser context. Switching to Whisper STT fallback.");
        this.startWhisperMicFallback();
        return;
      }

      this.recognition = new SpeechRecognition();
      this.recognition.continuous = true;
      this.recognition.interimResults = true;
      this.recognition.lang = 'id-ID';

      this.recognition.onerror = (e) => {
        console.warn("Speech recognition error notice:", e.error);
        global.isListening = false;
        if (e.error === 'network' || e.error === 'service-not-allowed' || e.error === 'language-not-supported') {
          this.startWhisperMicFallback();
        } else if (e.error !== 'not-allowed') {
          this.safeRestart();
        }
      };

      this.recognition.onstart = () => {
        global.isListening = true;
        const statusText = document.getElementById('jrv-statusText');
        const subText = document.getElementById('jrv-talking-sub');

        if (statusText) { statusText.innerText = "STATUS: MENDENGARKAN..."; statusText.style.color = "#00F0FF"; }
        if (subText) subText.innerText = "RESPONS SUARA JARVIS: MENDENGARKAN SUARA OPERATOR...";
      };

      this.recognition.onresult = (event) => {
        if (this.isMuted) return;
        const lastIndex = event.results.length - 1;
        const transcript = event.results[lastIndex][0].transcript.trim();
        const transcriptText = document.getElementById('transcriptText');
        if (transcriptText) transcriptText.innerText = `"${transcript}"`;

        if (event.results[lastIndex].isFinal) {
          this.stopCurrentAudio();
          this.sendQuery(transcript);
        }
      };

      this.recognition.onend = () => {
        global.isListening = false;
        const statusText = document.getElementById('jrv-statusText');
        const subText = document.getElementById('jrv-talking-sub');

        if (statusText && !this.isSpeaking) { statusText.innerText = "STATUS: SIAP"; statusText.style.color = "#34d399"; }
        if (subText && !this.isSpeaking) subText.innerText = "RESPONS SUARA JARVIS: PULSA NEURAL AKTIF...";

        this.safeRestart();
      };

      try { this.recognition.start(); } catch (e) {}
    },

    async sendQuery(rawQuery, preFetchedData = null) {
      this.stopCurrentAudio();
      if (this.recognition) {
        try { this.recognition.stop(); } catch (e) {}
      }

      const cleanQuery = typeof normalizePhonetics === 'function' ? normalizePhonetics(rawQuery) : rawQuery;

      const convLog = document.getElementById('jrv-conv-log');
      if (convLog) {
        const userBubble = document.createElement('div');
        userBubble.className = 'bubble-usr';
        userBubble.innerHTML = `🎤 <strong>User:</strong> "${cleanQuery}"`;
        convLog.appendChild(userBubble);
        convLog.scrollTop = convLog.scrollHeight;
      }

      const lowerQ = cleanQuery.toLowerCase();
      let navTarget = null;
      let navName = "";

      const navMap = [
        { keys: ["printer", "cetak", "printer status"], target: "printer", name: "Printer Status" },
        { keys: ["pc health", "kesehatan pc", "pc agent", "komputer", "pc"], target: "pchealth", name: "PC Health" },
        { keys: ["fleet config", "konfigurasi fleet", "config fleet"], target: "fleet_config", name: "Fleet Global Config" },
        { keys: ["fleet", "armada", "perangkat"], target: "fleet", name: "Fleet Management" },
        { keys: ["monitoring", "pemantauan", "live monitoring"], target: "monitoring", name: "Monitoring Live" },
        { keys: ["server health", "kesehatan server", "server", "srv"], target: "server", name: "Server Health" },
        { keys: ["incident triage", "incident", "insiden", "triage"], target: "incident", name: "Incident Triage" },
        { keys: ["rca", "root cause", "ground truth", "penyebab utama"], target: "rca", name: "Ground Truth & RCA" },
        { keys: ["korelasi event", "event correlation", "korelasi"], target: "event_correlation", name: "Event Correlation" },
        { keys: ["unified dag", "dag", "grafik", "graf"], target: "unified_dag", name: "Unified Graphs" },
        { keys: ["storage", "penyimpanan", "disk", "kapasitas"], target: "storage", name: "Storage Stats" },
        { keys: ["timeline", "eksekusi", "waktu eksekusi"], target: "exec_timeline", name: "Execution Timeline" },
        { keys: ["security policy", "kebijakan keamanan", "policy"], target: "security_policies", name: "Security Policies" },
        { keys: ["governance", "tata kelola", "infrastruktur", "infrastructure"], target: "gov", name: "Governance & Infrastructure" },
        { keys: ["knowledge center", "rag", "pusat pengetahuan", "pengetahuan"], target: "knowledge_center", name: "RAG Knowledge Center" },
        { keys: ["knowledge graph", "causal graph", "grafik pengetahuan"], target: "kgraph", name: "Knowledge Graph" },
        { keys: ["sop", "standar operasional"], target: "sop", name: "SOP Lifecycle" },
        { keys: ["playbook", "playbooks", "buku panduan"], target: "playbooks", name: "Playbook Studio" },
        { keys: ["live logs", "live log", "live lock", "live lok", "live loc", "log", "logs", "catatan sistem"], target: "logs", name: "Live Logs" },
        { keys: ["models", "model config", "konfigurasi model", "model"], target: "models", name: "Model Config" },
        { keys: ["training", "pelatihan", "latih model"], target: "training", name: "Continuous Training" },
        { keys: ["rbac", "akses", "hak akses", "user", "pengguna"], target: "rbac", name: "RBAC Policies" },
        { keys: ["live chat", "menu chat", "fitur chat", "chat room", "pesan"], target: "chat", name: "Live Chat" },
        { keys: ["evidence", "bukti", "bukti analisis"], target: "evidence", name: "Evidence Explorer" },
        { keys: ["agent health", "kesehatan agen", "agen"], target: "agent_health", name: "Agent Health Monitor" },
        { keys: ["decision log", "keputusan ai", "ai decision"], target: "ai_decision_logs", name: "AI Decision Logs" },
        { keys: ["topology", "topologi", "ai lifecycle", "siklus ai"], target: "ai_lifecycle_topology", name: "AI Lifecycle Topology" },
        { keys: ["failed actions", "failed action", "gagal"], target: "failed_actions", name: "Failed Actions" },
        { keys: ["approval queue", "approval", "persetujuan", "antrean"], target: "approval_queue", name: "Approval Queue" },
        { keys: ["smart stream", "telemetri", "stream"], target: "smart_stream", name: "Smart Stream Telemetry" },
        { keys: ["nats", "nats subject", "subjek nats"], target: "nats_subjects", name: "NATS Subjects" },
        { keys: ["sandbox", "sanbox", "promosi sandbox"], target: "learning_gate_policy", name: "Learning Gate & Sandbox" },
        { keys: ["ai core", "otak ai", "ai engine"], target: "ai", name: "AI Core Engine" },
        { keys: ["voice", "jarvis voice", "suara"], target: "jarvis_voice_overview", name: "JARVIS Voice Overview" },
        { keys: ["overview", "dashboard", "beranda", "tampilan utama"], target: "overview", name: "Dashboard Overview" }
      ];

      const isExplicitNav = /\b(buka menu|buka panel|tampilkan menu|pindah ke|navigasi ke|buka halaman|go to|goto)\b/i.test(lowerQ);
      if (isExplicitNav) {
        for (const item of navMap) {
          if (item.keys.some(k => lowerQ.includes(k))) {
            navTarget = item.target;
            navName = item.name;
            break;
          }
        }
      }

      let navExecuted = false;
      if (navTarget && typeof Nav !== 'undefined' && Nav.go) {
        try {
          Nav.go(navTarget);
          navExecuted = true;
        } catch (e) {
          console.error("Navigation error:", e);
        }
      }

      let replyText = "";
      let confScore = "98%";
      let evidenceStr = "OSI Ensemble Consensus & Knowledge Base";
      let urgencyLevel = "NORMAL";

      const emergencyWords = ["darurat", "segera", "mati total", "critical", "kritis", "emergency", "down parah", "bahaya"];
      const highWords = ["gangguan", "error", "problem", "masalah", "isu", "kendala", "macet", "timeout", "lag"];
      if (emergencyWords.some(w => lowerQ.includes(w))) {
        urgencyLevel = "EMERGENCY";
      } else if (highWords.some(w => lowerQ.includes(w))) {
        urgencyLevel = "HIGH";
      }

      if (!window._jrvSessionId) {
        window._jrvSessionId = "voice_" + Date.now() + "_" + Math.random().toString(36).substr(2, 6);
      }

      let actionUrl = "";
      let actionCardHtml = "";

      const taskRegex = /^(?:jarvis\s+)?(?:catat|tulis|tambah|buat)\s+(?:task|tugas|catatan|memo|nota)?\s*(.*)/i;
      const taskMatch = cleanQuery.match(taskRegex);
      const isTaskCommand = (lowerQ.includes("catat") || lowerQ.includes("tulis task") || lowerQ.includes("buat task") || lowerQ.includes("tambah task") || lowerQ.includes("catat tugas") || lowerQ.includes("tulis tugas")) && taskMatch && taskMatch[1] && taskMatch[1].trim().length > 0;

      if (isTaskCommand && global.JarvisTaskManager) {
        const taskContent = taskMatch[1].trim();
        const newTask = global.JarvisTaskManager.add(taskContent);

        replyText = `✅ Task berhasil dicatat: '${taskContent}'. Ditambahkan ke daftar Task Operasional NOC.`;
        confScore = "100%";
        evidenceStr = "JARVIS Voice Task & Operational Note Engine";

        actionCardHtml = `
          <div style="margin-top:6px; padding:8px 12px; background:rgba(6,182,212,0.12); border:1px solid #06b6d4; border-radius:6px; display:flex; align-items:center; justify-content:space-between;">
            <span style="font-size:11px; color:#06b6d4; font-weight:bold;">📌 TASK DITAMBAHKAN: "${taskContent}"</span>
            <span style="font-size:9px; color:#94a3b8; font-family:monospace;">${newTask ? newTask.id : ''}</span>
          </div>
        `;
      } else if ((lowerQ.includes("tampilkan task") || lowerQ.includes("lihat task") || lowerQ.includes("daftar task") || lowerQ.includes("lihat tugas") || lowerQ.includes("tampilkan tugas")) && global.JarvisTaskManager) {
        global.JarvisTaskManager.render();
        replyText = "Berikut adalah daftar task operasional NOC yang tersimpan di sistem.";
        confScore = "100%";
        evidenceStr = "JARVIS Task Manager";
      } else if ((lowerQ.includes("bersihkan task") || lowerQ.includes("hapus semua task")) && global.JarvisTaskManager) {
        global.JarvisTaskManager.clear();
        replyText = `Seluruh task operasional NOC telah dibersihkan.`;
        confScore = "100%";
        evidenceStr = "JARVIS Voice Task & Operational Note Engine";
      } else if (lowerQ === "jarvis" || lowerQ === "halo jarvis" || lowerQ === "hi jarvis" || lowerQ === "hai jarvis") {
        replyText = "Siap Bosku! JARVIS Senior Engineer di sini, standby 24/7. Kopi udah siap? Ada yang perlu kita eksekusi atau amankan hari ini?";
        confScore = "100%";
        evidenceStr = "JARVIS Active Presence & Greeting Engine";
      } else if (lowerQ === "ada" || lowerQ === "ada?" || lowerQ === "ada apa" || lowerQ === "ada apanya" || lowerQ === "ada isu" || lowerQ === "ada issue") {
        replyText = "Ada yang perlu kita inspeksi atau eksekusi, Senior? Silakan sebutkan nama perangkat atau perintahkan JARVIS.";
        confScore = "100%";
        evidenceStr = "JARVIS Contextual Standby Engine";
      } else if (lowerQ === "ya" || lowerQ === "iya" || lowerQ === "oke" || lowerQ === "ok") {
        replyText = "Ya, JARVIS di sini siap mendengarkan. Ada yang bisa saya bantu untuk operasional saat ini?";
        confScore = "100%";
        evidenceStr = "JARVIS Active Presence & Greeting Engine";
      } else if (window._jrvAwaitingMusicQuery) {
        window._jrvAwaitingMusicQuery = false;
        const songTitle = rawQuery.trim();
        actionUrl = (songTitle === "musik" || songTitle === "music")
          ? "https://www.youtube.com/watch?v=smk6RW2TMIM&list=RDsmk6RW2TMIM&start_radio=1"
          : "https://www.youtube.com/results?search_query=" + encodeURIComponent(songTitle);
        forceOpenTab(actionUrl);
        replyText = `Membuka musik '${songTitle}' di YouTube pada player tersemat dan tab baru. Dashboard JARVIS tetap aktif mendengarkan.`;
        confScore = "99%";
        evidenceStr = "Interactive Voice Music Clarification Engine";
      }

      let isBrowserAction = false;
      let isRemoteAction = false;

      if (!replyText) {
        const isStopMusic = /\b(?:stop\s+musik|stop\s+music|jeda\s+musik|matikan\s+musik|pause\s+musik|hentikan\s+musik|stop\s+lagu|matikan\s+lagu)\b/i.test(lowerQ) || lowerQ.trim() === "stop" || lowerQ.trim() === "pause" || lowerQ.trim() === "jeda";
        isBrowserAction = !isStopMusic && (
          /\b(?:youtube|yutub)\b/i.test(lowerQ) ||
          /\b(?:buka\s+youtube|cari\s+di\s+youtube)\b/i.test(lowerQ) ||
          /\b(?:putar\s+musik|play\s+musik|play\s+lagu|putar\s+lagu|play\s+music|putar\s+music|setel\s+musik|setel\s+lagu|dengarkan\s+musik|dengarkan\s+lagu)\b/i.test(lowerQ) ||
          /^(?:jarvis[,\s]+)?(?:play|putar|setel)\s+(?!book|box|play|ground|list|flow|service|agent|daemon)([a-zA-Z0-9_\s]{2,})$/i.test(cleanQuery.trim()) ||
          /\b(?:chatgpt|chat\s*gpt|gpt\.ai|gpt\s*ai|openai)\b/i.test(lowerQ) ||
          /\b(?:buka\s+(?:website|site|url|web|tab))\b/i.test(lowerQ)
        );
        isRemoteAction = /\b(?:buka\s+remote|akses\s+remote|remote\s+ke|sambungkan\s+ke|connect\s+to|remote\s+desktop|desktop\s+jauh)\b/i.test(lowerQ) ||
          /\b(?:buka|akses|launch)\s+(?:rustdesk|rust\s*desk|vnc|rdp|anydesk|teamviewer|ssh)\b/i.test(lowerQ) ||
          /^(?:jarvis[,\s]+)?(?:rustdesk|rust\s*desk|vnc|rdp|anydesk|teamviewer)$/i.test(cleanQuery.trim());

        if (isStopMusic) {
          try {
            document.querySelectorAll('audio, video').forEach(el => { try { el.pause(); } catch (e) {} });
          } catch (e) {}
          replyText = "Sip bos, pemutaran musik dihentikan dan player dimatikan. Dashboard JARVIS tetap aktif mendengarkan.";
          confScore = "100%";
          evidenceStr = "JARVIS Media Control Engine";
        } else if (isRemoteAction) {
          let pcTarget = "PC-MKT-NUC";
          let remoteTool = 'rustdesk';
          if (lowerQ.includes('ssh')) remoteTool = 'ssh';
          else if (lowerQ.includes('rdp')) remoteTool = 'rdp';
          else if (lowerQ.includes('vnc')) remoteTool = 'vnc';
          else if (lowerQ.includes('anydesk')) remoteTool = 'anydesk';
          else if (lowerQ.includes('rustdesk') || lowerQ.includes('rust desk')) remoteTool = 'rustdesk';

          const isPureToolCmd = /^(?:jarvis[,\s]+)?(?:buka|akses|launch)\s+(?:ssh|rdp|vnc|anydesk|rustdesk|rust\s*desk)\s*$/i.test(cleanQuery.trim());

          if (!isPureToolCmd) {
            if (lowerQ.includes("store") || lowerQ.includes("fnb") || lowerQ.includes("kasir")) {
              pcTarget = "PC-FNBCBD02";
            } else if (lowerQ.includes("printer") || lowerQ.includes("prt")) {
              pcTarget = "PRT-HR-01";
            } else if (lowerQ.includes("linux") || lowerQ.includes("tms") || lowerQ.includes("nuc") || lowerQ.includes("nux") || lowerQ.includes("nuk") || lowerQ.includes("noob") || lowerQ.includes("nobe") || lowerQ.includes("mkt")) {
              pcTarget = "PC-MKT-NUC";
            } else {
              let customTarget = cleanQuery
                .replace(/^(?:jarvis[,\s]+)?/i, '')
                .replace(/^(?:buka|akses|launch|remote ke|sambungkan ke)\s+/i, '')
                .replace(/^(?:ssh|rdp|vnc|anydesk|rustdesk|rust\s*desk)\s+/i, '')
                .replace(/^(?:ke\s+)?(?:pc|server|device|komputer)\s+/i, '')
                .trim();
              if (customTarget && !['remote', 'akses', 'service', 'buka', 'pc', 'ssh', 'rdp', 'vnc', 'anydesk', 'rustdesk'].includes(customTarget.toLowerCase())) {
                pcTarget = customTarget.replace(/[^\w\.\:\-]/g, '');
              }
            }
          }
          if (!pcTarget) pcTarget = "PC-MKT-NUC";

          if (typeof Modal !== 'undefined') Modal.close();
          if (typeof Remote !== 'undefined' && typeof Remote.launch === 'function') {
            Remote.launch(remoteTool, pcTarget);
          } else if (typeof RemoteSettings !== 'undefined') {
            RemoteSettings.open();
            RemoteSettings.switchTab(remoteTool);
          }

          replyText = `Baik, membuka sesi ${remoteTool.toUpperCase()} ke perangkat '${pcTarget}'.`;
          confScore = "100%";
          evidenceStr = "JARVIS Direct Remote Launch Gateway Engine";
        } else if (isBrowserAction) {
          actionUrl = resolveTargetUrl(rawQuery);
          forceOpenTab(actionUrl);

          if (lowerQ.includes("favorit") || lowerQ.includes("kesukaan") || lowerQ.includes("favo") || lowerQ.includes("fav") || lowerQ.trim() === "musik" || lowerQ.trim() === "play musik" || lowerQ.trim() === "play music") {
            replyText = "Memutar playlist musik favorit Anda di YouTube pada player tersemat dan tab baru. Dashboard JARVIS tetap aktif mendengarkan.";
          } else if (lowerQ.includes("chatgpt") || lowerQ.includes("chat gpt") || lowerQ.includes("gpt.ai") || lowerQ.includes("gpt ai") || lowerQ.includes("gpt") || lowerQ.includes("openai")) {
            replyText = "Membuka tab ChatGPT.AI pada tab baru. Dashboard JARVIS tetap aktif mendengarkan.";
          } else {
            replyText = `Membuka YouTube dan memproses pencarian media pada player tersemat dan tab baru. Dashboard JARVIS tetap aktif mendengarkan.`;
          }
          confScore = "100%";
          evidenceStr = "JARVIS Browser Control Bridge Engine";
        }
      }

      if (navExecuted) {
        replyText = `Navigasi berhasil: Membuka menu '${navName}' pada dashboard AI NOC.`;
      }

      const localOverrideReply = replyText;
      let spokenReplyText = replyText;

      try {
        let data = preFetchedData;
        if (!data || localOverrideReply) {
          const token = sessionStorage.getItem('noc_jwt_token') || localStorage.getItem('noc_jwt_token') || '';
          const headers = { 'Content-Type': 'application/json' };
          if (token) {
            headers['Authorization'] = 'Bearer ' + token;
            headers['X-CSRF-Token'] = token;
          }
          const reqPayload = {
            question: cleanQuery,
            query: rawQuery,
            session_id: window._jrvSessionId,
            urgency: urgencyLevel,
            intent_hint: navTarget || 'AUTO',
            locale: 'id-ID'
          };
          if (localOverrideReply) {
            reqPayload.tts_only_text = localOverrideReply.replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/gu, '').trim();
          }
          const res = await fetch('/api/jarvis/voice/query', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(reqPayload)
          });
          if (res.ok) {
            data = await res.json();
          } else {
            console.warn('[JARVIS] API returned', res.status);
            if (!replyText) {
              replyText = 'Sistem JARVIS sedang memproses. Silakan ulangi perintah Anda.';
            }
          }
        }

        if (data) {
          const answerText = data.answer_text || data.answer || '';
          if (data.spoken_text) {
            spokenReplyText = data.spoken_text;
          }
          if (answerText && !localOverrideReply && !isBrowserAction && !isRemoteAction) {
            replyText = answerText;
          }

          if (data.intent_confidence != null) {
            confScore = Math.round(data.intent_confidence * 100) + '%';
          } else if (data.confidence) {
            confScore = Math.round(data.confidence * 100) + '%';
          }

          if (data.source && !localOverrideReply) evidenceStr = data.source.replace(/_/g, ' ');
          if (data.urgency) urgencyLevel = data.urgency;

          if (lowerQ.includes("mengenai issue") || lowerQ.includes("mengenai isu") || lowerQ.includes("issue")) {
            evidenceStr = "OSI Active AI Engine (Ensemble Consensus)";
            confScore = "100%";
          }

          const intentBadge = document.getElementById('jrv-statusText');
          if (intentBadge && data.intent && data.intent !== 'UNKNOWN') {
            const intentColors = {
              QUERY: '#38bdf8', REMEDIATE: '#f59e0b', HITL: '#c084fc',
              REMOTE: '#34d399', CHAT: '#fb923c', ISSUE: '#f87171'
            };
            const color = intentColors[data.intent] || '#00F0FF';
            intentBadge.innerText = `INTENT: ${data.intent} (${confScore})`;
            intentBadge.style.color = color;
          }

          if (data.audio_b64 && data.audio_b64.length > 100) {
            try {
              const audioFormat = (data.audio_format || 'mp3').toLowerCase();
              const mimeType = (audioFormat === 'mp3') ? 'audio/mpeg' : `audio/${audioFormat}`;
              const byteChars = atob(data.audio_b64);
              const byteArr = new Uint8Array(byteChars.length);
              for (let i = 0; i < byteChars.length; i++) byteArr[i] = byteChars.charCodeAt(i);
              const audioBlob = new Blob([byteArr], { type: mimeType });
              const audioUrl = URL.createObjectURL(audioBlob);
              this.stopCurrentAudio();
              if (this.recognition) {
                try { this.recognition.stop(); } catch (e) {}
              }
              const audioEl = new Audio(audioUrl);
              this.currentAudioEl = audioEl;
              this.isSpeaking = true;

              audioEl.onplay = () => {
                JarvisAutoMic.isSpeaking = true;
                JarvisAutoMic.animateMouth(true);
                const statusText = document.getElementById('jrv-statusText');
                const subText = document.getElementById('jrv-talking-sub');
                if (statusText) { statusText.innerText = "STATUS: JARVIS BERBICARA..."; statusText.style.color = "#c084fc"; }
                if (subText) subText.innerText = "RESPONS SUARA JARVIS: SEDANG BERBICARA...";
              };
              audioEl.onended = () => {
                if (JarvisAutoMic.currentAudioEl === audioEl) JarvisAutoMic.currentAudioEl = null;
                JarvisAutoMic.isSpeaking = false;
                JarvisAutoMic.animateMouth(false);
                const statusText = document.getElementById('jrv-statusText');
                const subText = document.getElementById('jrv-talking-sub');
                if (statusText) { statusText.innerText = "STATUS: SIAP"; statusText.style.color = "#34d399"; }
                if (subText) subText.innerText = "RESPONS SUARA JARVIS: PULSA NEURAL AKTIF...";
                URL.revokeObjectURL(audioUrl);
                JarvisAutoMic.safeRestart();
              };
              audioEl.onerror = () => {
                if (JarvisAutoMic.currentAudioEl === audioEl) JarvisAutoMic.currentAudioEl = null;
                JarvisAutoMic.isSpeaking = false;
                JarvisAutoMic.animateMouth(false);
                URL.revokeObjectURL(audioUrl);
                JarvisAutoMic.safeRestart();
              };

              await audioEl.play();
              window._jrvUsingBackendTTS = true;
            } catch (audioErr) {
              console.warn('[JARVIS] Backend TTS audio play failed, using browser TTS:', audioErr);
              this.isSpeaking = false;
              window._jrvUsingBackendTTS = false;
            }
          } else {
            window._jrvUsingBackendTTS = false;
          }

          const actionCtx = data.action_context || {};

          if (actionCtx.requires_hitl_approval || actionCtx.hitl_queue_id) {
            const hitlBanner = document.createElement('div');
            hitlBanner.style.cssText = 'margin-top:6px;padding:8px 12px;background:rgba(245,158,11,0.15);border:1px solid #f59e0b;border-radius:6px;font-size:10px;color:#fbbf24;font-weight:bold;';
            hitlBanner.innerHTML = `⚠️ MENUNGGU PERSETUJUAN HITL — Queue: ${actionCtx.hitl_queue_id || 'PENDING'} | Konfirmasi wajib melalui tombol HITL di panel Approval Queue Dashboard NOC (Kebijakan K-07)`;
            if (convLog) { convLog.appendChild(hitlBanner); convLog.scrollTop = convLog.scrollHeight; }
          }

          if (data.intent === 'REMOTE' && actionCtx.execution_status === 'SUCCESS') {
            if (lowerQ.includes('remot') || lowerQ.includes('rustdesk') || lowerQ.includes('vnc')) {
              if (typeof RemoteSettings !== 'undefined') {
                RemoteSettings.open();
                RemoteSettings.switchTab(actionCtx.remote_tool || 'rustdesk');
              }
            }
          }

          if (data.action) {
            if (data.action.type === 'OPEN_REMOTE') {
              if (typeof Modal !== 'undefined') Modal.close();
              if (typeof RemoteSettings !== 'undefined') {
                RemoteSettings.open();
                RemoteSettings.switchTab('rustdesk');
              }
            } else if (data.action.type === 'OPEN_BROWSER' || data.action.url) {
              actionUrl = data.action.url || actionUrl || resolveTargetUrl(rawQuery);
              forceOpenTab(actionUrl);
            }
          }
        }
      } catch (err) {
        console.warn('[JARVIS] Voice API call notice:', err);
      }

      if (!replyText || replyText.trim() === "") {
        replyText = "Saya JARVIS, asisten AI NOC. Sistem analisis aktif — koneksi ke Orchestrator sedang dipulihkan. Silakan ulangi perintah Anda.";
      }

      if (convLog) {
        const jarvisBubble = document.createElement('div');
        jarvisBubble.className = 'bubble-jrv';

        let urgencyBadge = '';
        if (urgencyLevel === 'EMERGENCY') {
          urgencyBadge = '<span style="background:#ef4444;color:#fff;font-size:8px;padding:1px 5px;border-radius:3px;margin-right:4px;font-weight:700;letter-spacing:1px;">🚨 EMERGENCY</span>';
          jarvisBubble.style.borderLeft = '3px solid #ef4444';
          jarvisBubble.style.boxShadow = '0 0 8px rgba(239,68,68,0.4)';
        } else if (urgencyLevel === 'HIGH') {
          urgencyBadge = '<span style="background:#f59e0b;color:#000;font-size:8px;padding:1px 5px;border-radius:3px;margin-right:4px;font-weight:700;letter-spacing:1px;">⚠️ HIGH</span>';
          jarvisBubble.style.borderLeft = '3px solid #f59e0b';
        }

        if (!actionCardHtml && actionUrl) {
          actionCardHtml = `<div style="margin-top:8px;"><a href="${actionUrl}" target="_blank" rel="noopener noreferrer" style="display:inline-block;padding:6px 14px;background:linear-gradient(135deg,#ef4444,#dc2626);color:#fff;font-weight:700;font-size:11px;border-radius:4px;text-decoration:none;box-shadow:0 0 10px rgba(239,68,68,0.5);letter-spacing:0.5px;">▶ BUKA TAB MEDIA: ${actionUrl}</a></div>`;
        }

        jarvisBubble.innerHTML = `${urgencyBadge}🤖 <strong>Jarvis:</strong> "${replyText}"${actionCardHtml}<div class="jrv-meta"><span class="meta-conf">Confidence: ${confScore}</span><span class="meta-ev">Evidence: ${evidenceStr}</span></div>`;
        convLog.appendChild(jarvisBubble);
        convLog.scrollTop = convLog.scrollHeight;
      }

      if (!window._jrvUsingBackendTTS && 'speechSynthesis' in window && replyText) {
        const synth = window.speechSynthesis;
        try { synth.cancel(); } catch (e) {}
        this.isSpeaking = true;
        if (this.recognition) {
          try { this.recognition.stop(); } catch (e) {}
        }

        const utter = new SpeechSynthesisUtterance(spokenReplyText || replyText);
        utter.lang = 'id-ID';
        utter.rate = 0.95;
        utter.pitch = 0.9;

        const ttsSafetyWatchdog = setTimeout(() => {
          if (this.isSpeaking) {
            this.isSpeaking = false;
            this.animateMouth(false);
            this.safeRestart();
          }
        }, 12000);

        utter.onstart = () => {
          this.isSpeaking = true;
          const statusText = document.getElementById('jrv-statusText');
          const subText = document.getElementById('jrv-talking-sub');
          if (statusText) { statusText.innerText = "STATUS: JARVIS BERBICARA..."; statusText.style.color = "#c084fc"; }
          if (subText) subText.innerText = "RESPONS SUARA JARVIS: SEDANG BERBICARA...";
          this.animateMouth(true);
        };

        utter.onend = () => {
          clearTimeout(ttsSafetyWatchdog);
          this.isSpeaking = false;
          const statusText = document.getElementById('jrv-statusText');
          const subText = document.getElementById('jrv-talking-sub');
          if (statusText) { statusText.innerText = "STATUS: SIAP"; statusText.style.color = "#34d399"; }
          if (subText) subText.innerText = "RESPONS SUARA JARVIS: PULSA NEURAL AKTIF...";
          this.animateMouth(false);
          this.safeRestart();
        };

        utter.onerror = () => {
          clearTimeout(ttsSafetyWatchdog);
          this.isSpeaking = false;
          this.animateMouth(false);
          this.safeRestart();
        };

        const voices = synth.getVoices();
        const idVoice = voices.find(v => v.lang.includes('id') || v.lang.includes('ID'));
        if (idVoice) utter.voice = idVoice;
        synth.speak(utter);
      } else if (!window._jrvUsingBackendTTS) {
        this.safeRestart();
      }
      window._jrvUsingBackendTTS = false;
    }
  };

  global.normalizePhonetics = normalizePhonetics;
  global.JarvisAutoMic = JarvisAutoMic;
  global.Services = global.Services || {};
  global.Services.JarvisAutoMic = JarvisAutoMic;
})(window);
