import { decodeFrameSamples } from './hexUtils.js';

const API_BASE = '/api';
// [PL_AUDIT_WEB_B10] Gate verbose per-frame logging; defaults to off so the
// console isn't spammed on every poll (~10 Hz).
const DEBUG = false;

export class ApiService {
  constructor() {
    this.lastSeq = null;
    this.useHexFormat = true; // Use hex encoding for better performance
  }

  async getStatus() {
    const response = await fetch(`${API_BASE}/status`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  }

  async applyConfig(changes) {
    const response = await fetch(`${API_BASE}/config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(changes)
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  }

  async setSwMode(mode) {
    return this.applyConfig({ sw_mode: mode });
  }

  async setFilters({ high, low }) {
    const payload = {};
    if (typeof high === 'boolean') payload.filter_high = high;
    if (typeof low === 'boolean') payload.filter_low = low;
    if (Object.keys(payload).length === 0) return { status: 'noop' };
    return this.applyConfig(payload);
  }

  async setSyncType(type) {
    return this.applyConfig({ sync_type: type });
  }

  async setSyncEdges({ front, back }) {
    const payload = {};
    if (typeof front === 'boolean') payload.sync_front = front;
    if (typeof back === 'boolean') payload.sync_back = back;
    if (Object.keys(payload).length === 0) return { status: 'noop' };
    return this.applyConfig(payload);
  }

  async getFrames(since = null) {
    const params = new URLSearchParams();
    if (since !== null) params.set('since', since);
    if (this.useHexFormat) params.set('format', 'hex');
    
    const queryString = params.toString();
    const url = queryString ? `${API_BASE}/frames?${queryString}` : `${API_BASE}/frames`;
    
    const response = await fetch(url);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    
    // Decode hex-encoded samples back to arrays
    if (data.format === 'hex' && data.frames) {
      if (DEBUG) console.log('[API] Decoding', data.frames.length, 'hex frames'); // [PL_AUDIT_WEB_B10]
      data.frames = data.frames.map(frame => {
        const decoded = decodeFrameSamples(frame);
        if (!decoded.samples && frame.samples_hex) {
          console.error('[API] Failed to decode frame:', frame);
        }
        return decoded;
      });
    }
    
    if (data.frames && data.frames.length > 0) {
      this.lastSeq = data.newest_seq;
    }
    return data;
  }

  // [SP_BTT_02_10] Connect over a chosen transport. `opts` may carry
  // { transport: 'auto'|'serial'|'bluetooth', port, baud, address, channel }.
  // Back-compat: connect() or connect('auto') behave as before (auto-connect).
  async connect(opts = {}) {
    // Legacy call shape connect(port, baud) — keep it working.
    if (typeof opts === 'string') opts = opts === 'auto' ? {} : { transport: 'serial', port: opts };
    const body = {};
    if (opts.transport && opts.transport !== 'auto') body.transport = opts.transport;
    if (opts.port) body.port = opts.port;
    if (opts.baud) body.baud = opts.baud;
    if (opts.address) body.address = opts.address;
    if (opts.channel != null) body.channel = opts.channel;
    const response = await fetch(`${API_BASE}/connect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    if (!response.ok) {
      // Surface the backend's actionable detail (DeviceNotFound / BluetoothUnreachable / …).
      let detail = `HTTP ${response.status}`;
      try { const j = await response.json(); if (j && j.detail) detail = j.detail; } catch (_) {}
      throw new Error(detail);
    }
    return await response.json();
  }

  async ensureConnected() {
    // Alias for connect() without parameters - auto-connects if needed
    return this.connect();
  }

  async disconnect() {
    const response = await fetch(`${API_BASE}/disconnect`, {
      method: 'POST'
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  }

  async start() {
    const response = await fetch(`${API_BASE}/start`, {
      method: 'POST'
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  }

  async stop() {
    const response = await fetch(`${API_BASE}/stop`, {
      method: 'POST'
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  }

  getLastSeq() {
    return this.lastSeq;
  }
}