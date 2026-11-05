/**
 * portal/static/js/core/jarvis-duplex-voice.js
 * =============================================
 * Real-time Full-Duplex Voice Engine for JARVIS AI (<300ms Latency).
 *
 * Features:
 *   - Continuous PCM audio chunk streaming via WebSocket (/api/jarvis/voice/duplex)
 *   - Low-latency AudioContext Chunk Queue Player
 *   - Barge-in (Interruption Handling): Stops local TTS playback and notifies JARVIS instantly when user speaks mid-response.
 */

class JarvisDuplexVoiceEngine {
    constructor(options = {}) {
        this.wsUrl = options.wsUrl || `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/jarvis/voice/duplex`;
        this.socket = null;
        this.audioCtx = null;
        this.mediaStream = null;
        this.scriptProcessor = null;
        this.activeSourceNodes = [];
        this.isRecording = false;
        this.isPlaying = false;
        this.avatarState = 'IDLE';

        // Callbacks
        this.onAvatarStateChange = options.onAvatarStateChange || (() => {});
        this.onAnswerText = options.onAnswerText || (() => {});
        this.onError = options.onError || (() => {});
    }

    async init() {
        try {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            this.audioCtx = new AudioContext({ sampleRate: 24000 });
            console.log('[JARVIS-DUPLEX] AudioContext initialized (24kHz)');
            return true;
        } catch (err) {
            console.error('[JARVIS-DUPLEX] AudioContext init failed:', err);
            this.onError('Web Audio API not supported');
            return false;
        }
    }

    connect() {
        if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
            return;
        }

        console.log(`[JARVIS-DUPLEX] Connecting to Full-Duplex WebSocket: ${this.wsUrl}`);
        const wsToken = sessionStorage.getItem('noc_jwt_token');
        this.socket = wsToken ? new WebSocket(this.wsUrl, ['bearer', wsToken]) : new WebSocket(this.wsUrl);

        this.socket.onopen = () => {
            console.log('[JARVIS-DUPLEX] ⚡ Full-Duplex Voice WebSocket Connected');
            this.updateState('LISTENING');
        };

        this.socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleServerEvent(data);
            } catch (e) {
                console.warn('[JARVIS-DUPLEX] Binary frame or unparseable text frame received');
            }
        };

        this.socket.onerror = (err) => {
            console.error('[JARVIS-DUPLEX] WebSocket Error:', err);
            this.onError('WebSocket connection error');
        };

        this.socket.onclose = () => {
            console.log('[JARVIS-DUPLEX] WebSocket Disconnected');
            this.updateState('IDLE');
        };
    }

    handleServerEvent(data) {
        if (data.avatar_state) {
            this.updateState(data.avatar_state);
        }

        if (data.answer_text) {
            this.onAnswerText(data.answer_text, data.intent);
        }

        if (data.audio_chunk_b64) {
            this.playAudioChunkBase64(data.audio_chunk_b64);
        }

        if (data.avatar_state === 'INTERRUPTED') {
            this.stopLocalPlayback();
        }
    }

    sendTextQuery(text) {
        if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
            this.connect();
        }
        const payload = JSON.stringify({ question: text });
        this.socket.send(payload);
        this.updateState('THINKING');
    }

    triggerBargeIn() {
        console.log('[JARVIS-DUPLEX] ⚡ BARGE-IN TRIGGERED BY USER SPEECH! Stopping playback...');
        this.stopLocalPlayback();
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify({ action: 'barge_in' }));
        }
        this.updateState('LISTENING');
    }

    async startMicrophone() {
        if (this.isRecording) return;
        if (!this.audioCtx) await this.init();

        try {
            this.mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
            const source = this.audioCtx.createMediaStreamSource(this.mediaStream);

            // Buffer size 4096 = ~170ms audio chunks
            this.scriptProcessor = this.audioCtx.createScriptProcessor(4096, 1, 1);
            source.connect(this.scriptProcessor);
            this.scriptProcessor.connect(this.audioCtx.destination);

            this.scriptProcessor.onaudioprocess = (e) => {
                if (!this.isRecording) return;
                const inputData = e.inputBuffer.getChannelData(0);

                // Barge-in check: if JARVIS is playing audio and user speaks loudly
                if (this.isPlaying) {
                    let sum = 0;
                    for (let i = 0; i < inputData.length; i++) {
                        sum += inputData[i] * inputData[i];
                    }
                    const rms = Math.sqrt(sum / inputData.length);
                    if (rms > 0.05) { // Energy threshold for speech detection
                        this.triggerBargeIn();
                    }
                }

                // Send PCM 16-bit binary chunk over WebSocket
                if (this.socket && this.socket.readyState === WebSocket.OPEN) {
                    const pcm16 = this.float32ToPCM16(inputData);
                    this.socket.send(pcm16.buffer);
                }
            };

            this.isRecording = true;
            console.log('[JARVIS-DUPLEX] Microphone recording active. Streaming PCM audio...');
        } catch (err) {
            console.error('[JARVIS-DUPLEX] Mic access error:', err);
            this.onError('Gagal mengakses mikrofon.');
        }
    }

    stopMicrophone() {
        this.isRecording = false;
        if (this.scriptProcessor) {
            this.scriptProcessor.disconnect();
            this.scriptProcessor = null;
        }
        if (this.mediaStream) {
            this.mediaStream.getTracks().forEach(track => track.stop());
            this.mediaStream = null;
        }
        console.log('[JARVIS-DUPLEX] Microphone stopped.');
    }

    playAudioChunkBase64(b64Audio) {
        if (!this.audioCtx) return;
        const binaryStr = window.atob(b64Audio);
        const len = binaryStr.length;
        const bytes = new Uint8Array(len);
        for (let i = 0; i < len; i++) {
            bytes[i] = binaryStr.charCodeAt(i);
        }

        this.audioCtx.decodeAudioData(bytes.buffer, (audioBuffer) => {
            const source = this.audioCtx.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(this.audioCtx.destination);
            source.onended = () => {
                const idx = this.activeSourceNodes.indexOf(source);
                if (idx !== -1) this.activeSourceNodes.splice(idx, 1);
                if (this.activeSourceNodes.length === 0) {
                    this.isPlaying = false;
                }
            };
            this.activeSourceNodes.push(source);
            this.isPlaying = true;
            source.start(0);
        }, (err) => {
            console.warn('[JARVIS-DUPLEX] Audio decode warning:', err);
        });
    }

    stopLocalPlayback() {
        this.activeSourceNodes.forEach(node => {
            try { node.stop(); } catch (e) {}
        });
        this.activeSourceNodes = [];
        this.isPlaying = false;
    }

    updateState(newState) {
        this.avatarState = newState;
        this.onAvatarStateChange(newState);
    }

    disconnect() {
        this.stopMicrophone();
        this.stopLocalPlayback();
        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
    }
}

// Global Export
window.JarvisDuplexVoiceEngine = JarvisDuplexVoiceEngine;
