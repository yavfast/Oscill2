import { decodeFrameSamples } from './hexUtils.js';

const API_BASE = '/api';

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
      console.log('[API] Decoding', data.frames.length, 'hex frames');
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

  async connect(port = 'auto', baud = 115200) {
    const response = await fetch(`${API_BASE}/connect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ port, baud })
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  }

  async disconnect() {
    const response = await fetch(`${API_BASE}/disconnect`, {
      method: 'POST'
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  }

  async startAcquisition() {
    const response = await fetch(`${API_BASE}/acquisition/start`, {
      method: 'POST'
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  }

  async stopAcquisition() {
    const response = await fetch(`${API_BASE}/acquisition/stop`, {
      method: 'POST'
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  }

  getLastSeq() {
    return this.lastSeq;
  }
}