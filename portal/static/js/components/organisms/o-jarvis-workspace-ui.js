/**
 * Atomic Design — Organism Layer: JARVIS Voice Workspace UI, Media Player & Task Manager
 * Path: /static/js/components/organisms/o-jarvis-workspace-ui.js
 * Provides:
 *   - window.UI.Organisms.JarvisWorkspaceUI
 *   - window.UI.Organisms.JarvisMediaPlayer (and window.JarvisMediaPlayer)
 *   - window.UI.Organisms.JarvisTaskManager (and window.JarvisTaskManager)
 */
(function (global) {
  const JarvisMediaPlayer = {
    play(mediaUrl) {
      if (!mediaUrl) return;
      let embedUrl = mediaUrl;
      if (mediaUrl.includes('youtube.com/watch?v=')) {
        const vId = mediaUrl.split('v=')[1].split('&')[0];
        const listId = mediaUrl.includes('list=') ? mediaUrl.split('list=')[1].split('&')[0] : '';
        embedUrl = `https://www.youtube.com/embed/${vId}?autoplay=1${listId ? '&list=' + listId : ''}`;
      } else if (mediaUrl.includes('youtube.com/results?search_query=')) {
        const query = mediaUrl.split('search_query=')[1];
        embedUrl = `https://www.youtube.com/embed?listType=search&list=${query}&autoplay=1`;
      }

      let overlay = document.getElementById('jrv-media-player-container');
      if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'jrv-media-player-container';
        overlay.style.cssText = 'position:fixed; bottom:20px; right:20px; width:450px; height:280px; background:rgba(15,23,42,0.95); backdrop-filter:blur(12px); border:1px solid #06b6d4; border-radius:12px; z-index:99999; box-shadow:0 10px 30px rgba(0,0,0,0.8); overflow:hidden; display:flex; flex-direction:column;';
        overlay.innerHTML = `
          <div style="display:flex; align-items:center; justify-content:space-between; padding:8px 12px; background:rgba(6,182,212,0.15); border-bottom:1px solid rgba(6,182,212,0.3);">
            <div style="display:flex; align-items:center; gap:8px;">
              <span style="color:#ef4444; font-size:11px; font-weight:bold; letter-spacing:0.5px;">🎵 JARVIS MEDIA PLAYER</span>
              <span style="background:#059669; color:#fff; font-size:9px; padding:2px 6px; border-radius:4px; font-weight:bold;">LIVE PLAYBACK</span>
            </div>
            <div style="display:flex; gap:8px;">
              <button onclick="JarvisMediaPlayer.minimize()" style="background:none; border:none; color:#94a3b8; cursor:pointer; font-size:14px;">−</button>
              <button onclick="JarvisMediaPlayer.close()" style="background:none; border:none; color:#f87171; cursor:pointer; font-size:14px; font-weight:bold;">✕</button>
            </div>
          </div>
          <iframe id="jrv-media-iframe" src="about:blank" style="width:100%; height:calc(100% - 35px); border:none;" allow="autoplay; encrypted-media" allowfullscreen></iframe>
        `;
        document.body.appendChild(overlay);
      }
      const iframe = document.getElementById('jrv-media-iframe');
      if (iframe) iframe.src = embedUrl;
      overlay.style.display = 'flex';
    },

    close() {
      const overlay = document.getElementById('jrv-media-player-container');
      const iframe = document.getElementById('jrv-media-iframe');
      if (overlay && iframe) {
        iframe.src = 'about:blank';
        overlay.style.display = 'none';
      }
    },

    minimize() {
      const overlay = document.getElementById('jrv-media-player-container');
      if (overlay) {
        overlay.style.height = overlay.style.height === '35px' ? '280px' : '35px';
      }
    }
  };

  const JarvisTaskManager = {
    tasks: JSON.parse(localStorage.getItem('jrv_tasks') || '[]'),

    save() {
      try { localStorage.setItem('jrv_tasks', JSON.stringify(this.tasks)); } catch (e) {}
      this.render();
    },

    add(text) {
      if (!text || text.trim().length === 0) return null;
      const newTask = {
        id: 'TSK-' + Math.floor(Math.random() * 9000 + 1000),
        text: text.trim(),
        status: 'PENDING',
        time: new Date().toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' })
      };
      this.tasks.unshift(newTask);
      this.save();
      return newTask;
    },

    toggle(id) {
      const t = this.tasks.find(x => x.id === id);
      if (t) {
        t.status = t.status === 'COMPLETED' ? 'PENDING' : 'COMPLETED';
        this.save();
      }
    },

    deleteTask(id) {
      this.tasks = this.tasks.filter(x => x.id !== id);
      this.save();
    },

    clear() {
      this.tasks = [];
      this.save();
    },

    render() {
      const el = document.getElementById('jrv-task-list-container');
      if (!el) return;
      if (this.tasks.length === 0) {
        el.innerHTML = `<div style="color:#64748b; font-size:10px; text-align:center; padding:10px; font-style:italic;">Belum ada task operasional. Ucapkan "Jarvis catat task [isi tugas]" untuk menambahkan task baru.</div>`;
        return;
      }
      const cards = (global.UI && global.UI.Molecules && global.UI.Molecules.JarvisCards) || null;
      let html = '';
      this.tasks.forEach(t => {
        if (cards && cards.renderTaskItem) {
          html += cards.renderTaskItem(t);
        }
      });
      el.innerHTML = html;
    }
  };

  const JarvisWorkspaceUI = {
    setStatus(text, color) {
      const statusText = document.getElementById('jrv-statusText');
      if (statusText) {
        statusText.innerText = text;
        if (color) statusText.style.color = color;
      }
    },

    setSubStatus(text) {
      const subText = document.getElementById('jrv-talking-sub');
      if (subText) subText.innerText = text;
    },

    setMicButtonLabel(text) {
      const btnText = document.getElementById('jrv-mic-status-text');
      if (btnText) btnText.innerText = text;
    },

    setTranscript(text) {
      const transcriptText = document.getElementById('transcriptText');
      if (transcriptText) transcriptText.innerText = `"${text}"`;
    },

    consumeManualInput() {
      const inp = document.getElementById('jrv-cmd-input');
      if (!inp || !inp.value.trim()) return '';
      const val = inp.value.trim();
      inp.value = '';
      return val;
    },

    updateIntentBadge(intent, confScore) {
      if (!intent || intent === 'UNKNOWN') return;
      const badges = (global.UI && global.UI.Atoms && global.UI.Atoms.JarvisBadges) || null;
      if (badges && badges.getIntentStatusStyle) {
        const st = badges.getIntentStatusStyle(intent, confScore);
        this.setStatus(st.text, st.color);
      }
    },

    appendUserTurn(cleanQuery) {
      const convLog = document.getElementById('jrv-conv-log');
      if (!convLog) return;
      const cards = (global.UI && global.UI.Molecules && global.UI.Molecules.JarvisCards) || null;
      const bubble = cards ? cards.createUserBubble(cleanQuery) : null;
      if (bubble) {
        convLog.appendChild(bubble);
        convLog.scrollTop = convLog.scrollHeight;
      }
    },

    appendJarvisTurn(opts) {
      const convLog = document.getElementById('jrv-conv-log');
      if (!convLog) return;
      const cards = (global.UI && global.UI.Molecules && global.UI.Molecules.JarvisCards) || null;
      const bubble = cards ? cards.createJarvisBubble(opts) : null;
      if (bubble) {
        convLog.appendChild(bubble);
        convLog.scrollTop = convLog.scrollHeight;
      }
    },

    appendProactiveTurn(data) {
      const convLog = document.getElementById('jrv-conv-log');
      if (!convLog) return;
      const cards = (global.UI && global.UI.Molecules && global.UI.Molecules.JarvisCards) || null;
      const bubble = cards ? cards.createProactiveBubble(data) : null;
      if (bubble) {
        convLog.appendChild(bubble);
        convLog.scrollTop = convLog.scrollHeight;
      }
    },

    appendHitlBanner(hitlQueueId) {
      const convLog = document.getElementById('jrv-conv-log');
      if (!convLog) return;
      const cards = (global.UI && global.UI.Molecules && global.UI.Molecules.JarvisCards) || null;
      const banner = cards ? cards.createHitlBanner(hitlQueueId) : null;
      if (banner) {
        convLog.appendChild(banner);
        convLog.scrollTop = convLog.scrollHeight;
      }
    }
  };

  global.JarvisMediaPlayer = JarvisMediaPlayer;
  global.JarvisTaskManager = JarvisTaskManager;
  global.JarvisWorkspaceUI = JarvisWorkspaceUI;
  global.UI = global.UI || {};
  global.UI.Organisms = global.UI.Organisms || {};
  global.UI.Organisms.JarvisMediaPlayer = JarvisMediaPlayer;
  global.UI.Organisms.JarvisTaskManager = JarvisTaskManager;
  global.UI.Organisms.JarvisWorkspaceUI = JarvisWorkspaceUI;
})(window);
