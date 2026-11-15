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
            this.audioCtx = new AudioContext({ sampleRate: 16000 });
            this._bargeInFrames = 0;
            console.debug('[JARVIS-DUPLEX] AudioContext initialized (16kHz)');
            return true;
        } catch (err) {
            console.error('[JARVIS-DUPLEX] AudioContext init failed:', err);
            this.onError('Web Audio API not supported');
            return false;
        }
    }

    float32ToPCM16(float32Array) {
        const pcm16 = new Int16Array(float32Array.length);
        for (let i = 0; i < float32Array.length; i++) {
            const s = Math.max(-1, Math.min(1, float32Array[i]));
            pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        return pcm16;
    }

    connect() {
        if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
            return;
        }

        console.debug(`[JARVIS-DUPLEX] Connecting to Full-Duplex WebSocket: ${this.wsUrl}`);
        const wsToken = sessionStorage.getItem('noc_jwt_token');
        this.socket = wsToken ? new WebSocket(this.wsUrl, ['bearer', wsToken]) : new WebSocket(this.wsUrl);

        this.socket.onopen = () => {
            console.debug('[JARVIS-DUPLEX] ⚡ Full-Duplex Voice WebSocket Connected');
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
            console.debug('[JARVIS-DUPLEX] WebSocket Disconnected');
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
        console.debug('[JARVIS-DUPLEX] ⚡ BARGE-IN TRIGGERED BY USER SPEECH! Stopping playback...');
        this.stopLocalPlayback();
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify({ action: 'barge_in' }));
        }
        this.updateState('LISTENING');
    }

    _processAudioSamples(inputData) {
        if (!this.isRecording || !inputData || inputData.length === 0) return;

        // Barge-in check: require sustained speech (>= 4 consecutive frames above RMS threshold)
        // to prevent single-spike false barge-in in noisy NOC environments [WS-J2]
        if (this.isPlaying) {
            let sum = 0;
            for (let i = 0; i < inputData.length; i++) {
                sum += inputData[i] * inputData[i];
            }
            const rms = Math.sqrt(sum / inputData.length);
            if (rms > 0.06) {
                this._bargeInFrames = (this._bargeInFrames || 0) + 1;
                if (this._bargeInFrames >= 4) {
                    this._bargeInFrames = 0;
                    this.triggerBargeIn();
                }
            } else {
                this._bargeInFrames = 0;
            }
        } else {
            this._bargeInFrames = 0;
        }

        // Send PCM 16-bit binary chunk over WebSocket
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            const pcm16 = this.float32ToPCM16(inputData);
            this.socket.send(pcm16.buffer);
        }
    }

    async startMicrophone() {
        if (this.isRecording) return;
        if (!this.audioCtx) await this.init();

        try {
            this.mediaStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,
                    channelCount: 1,
                    sampleRate: 16000
                },
                video: false
            });
            const source = this.audioCtx.createMediaStreamSource(this.mediaStream);

            // [PILAR 5] Off-main-thread AudioWorkletNode with graceful ScriptProcessorNode fallback
            let workletConnected = false;
            if (this.audioCtx.audioWorklet && typeof window.AudioWorkletNode !== 'undefined') {
                try {
                    if (!this._workletModuleLoaded) {
                        const workletCode = `
                            class JarvisPcmCaptureProcessor extends AudioWorkletProcessor {
                                constructor() {
                                    super();
                                    this._buf = new Float32Array(4096);
                                    this._offset = 0;
                                }
                                process(inputs) {
                                    const input = inputs[0];
                                    if (input && input[0]) {
                                        const ch = input[0];
                                        for (let i = 0; i < ch.length; i++) {
                                            this._buf[this._offset++] = ch[i];
                                            if (this._offset >= 4096) {
                                                this.port.postMessage(this._buf.slice(0));
                                                this._offset = 0;
                                            }
                                        }
                                    }
                                    return true;
                                }
                            }
                            registerProcessor('jarvis-pcm-capture-processor', JarvisPcmCaptureProcessor);
                        `;
                        const blob = new Blob([workletCode], { type: 'application/javascript' });
                        const url = URL.createObjectURL(blob);
                        await this.audioCtx.audioWorklet.addModule(url);
                        URL.revokeObjectURL(url);
                        this._workletModuleLoaded = true;
                    }
                    this.workletNode = new AudioWorkletNode(this.audioCtx, 'jarvis-pcm-capture-processor');
                    this.workletNode.port.onmessage = (evt) => {
                        this._processAudioSamples(evt.data);
                    };
                    source.connect(this.workletNode);
                    this.workletNode.connect(this.audioCtx.destination);
                    workletConnected = true;
                } catch (wkErr) {
                    console.debug('[JARVIS-DUPLEX] AudioWorklet fallback to ScriptProcessorNode:', wkErr);
                }
            }

            if (!workletConnected) {
                // Buffer size 4096 = ~170ms audio chunks
                this.scriptProcessor = this.audioCtx.createScriptProcessor(4096, 1, 1);
                source.connect(this.scriptProcessor);
                this.scriptProcessor.connect(this.audioCtx.destination);
                this.scriptProcessor.onaudioprocess = (e) => {
                    this._processAudioSamples(e.inputBuffer.getChannelData(0));
                };
            }

            this.isRecording = true;
            console.debug('[JARVIS-DUPLEX] Microphone recording active. Streaming PCM audio...');
        } catch (err) {
            console.error('[JARVIS-DUPLEX] Mic access error:', err);
            this.onError('Gagal mengakses mikrofon.');
        }
    }

    stopMicrophone() {
        this.isRecording = false;
        if (this.workletNode) {
            try { this.workletNode.disconnect(); } catch (e) {}
            this.workletNode = null;
        }
        if (this.scriptProcessor) {
            this.scriptProcessor.disconnect();
            this.scriptProcessor = null;
        }
        if (this.mediaStream) {
            this.mediaStream.getTracks().forEach(track => track.stop());
            this.mediaStream = null;
        }
        console.debug('[JARVIS-DUPLEX] Microphone stopped.');
    }

    playAudioChunkBase64(b64Audio) {
        if (!this.audioCtx || !b64Audio) return;
        this._audioQueue = this._audioQueue || [];
        this._audioQueue.push(b64Audio);
        if (!this._isProcessingQueue) {
            this._playNextInQueue();
        }
    }

    _playNextInQueue() {
        if (!this.audioCtx || !this._audioQueue || this._audioQueue.length === 0) {
            this._isProcessingQueue = false;
            if (this.activeSourceNodes.length === 0) {
                this.isPlaying = false;
            }
            return;
        }
        this._isProcessingQueue = true;
        const b64Audio = this._audioQueue.shift();
        const binaryStr = window.atob(b64Audio);
        const len = binaryStr.length;
        const bytes = new Uint8Array(len);
        for (let i = 0; i < len; i++) {
            bytes[i] = binaryStr.charCodeAt(i);
        }

        this.audioCtx.decodeAudioData(bytes.buffer, (audioBuffer) => {
            // Check if barge-in cleared playback while decoding
            if (!this._isProcessingQueue && (!this._audioQueue || this._audioQueue.length === 0)) {
                return;
            }
            const source = this.audioCtx.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(this.audioCtx.destination);
            source.onended = () => {
                const idx = this.activeSourceNodes.indexOf(source);
                if (idx !== -1) this.activeSourceNodes.splice(idx, 1);
                this._playNextInQueue();
            };
            this.activeSourceNodes.push(source);
            this.isPlaying = true;
            source.start(0);
        }, (err) => {
            console.warn('[JARVIS-DUPLEX] Audio decode warning:', err);
            this._playNextInQueue();
        });
    }

    stopLocalPlayback() {
        this._audioQueue = [];
        this._isProcessingQueue = false;
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

window.Services = window.Services || {};
window.Services.JarvisDuplex = window.JarvisDuplexVoiceEngine;
