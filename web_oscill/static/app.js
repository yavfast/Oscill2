const $ = (sel) => document.querySelector(sel);

const statusEl = $('#status');
const deviceInfoEl = $('#deviceInfo');
const connectBtn = $('#btnConnect');
const disconnectBtn = $('#btnDisconnect');
const acquireBtn = $('#btnAcquire');
const verifyBtn = $('#btnVerify');
const applyBtn = $('#btnApply');
const vDivSel = $('#vDiv');
const tDivSel = $('#tDiv');
const trigLevelInput = $('#trigLevel');
const offsetInput = $('#offsetV');
const canvas = $('#scope');
const ctx = canvas.getContext('2d');

function setStatus(msg, kind = 'info') {
  statusEl.textContent = msg;
  statusEl.dataset.kind = kind;
}

let pollTimer = null;
let isConnected = false;

function setConnected(connected) {
  isConnected = connected;
  connectBtn.disabled = connected;
  disconnectBtn.disabled = !connected;
  acquireBtn.disabled = !connected;
  applyBtn.disabled = !connected;
  if (verifyBtn) verifyBtn.disabled = !connected;
  if (!connected && pollTimer) { clearInterval(pollTimer); pollTimer = null; }
}

async function connect() {
  const port = $('#port').value.trim() || 'auto';
  const baud = parseInt($('#baud').value, 10) || 115200;
  setStatus('Connecting...');
  try {
    const res = await fetch('/api/connect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ port, baud })
    });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    if (data.status !== 'ok') throw new Error(data.message || 'Failed to connect');
    setConnected(true);
    setStatus('Connected');
    renderDeviceInfo(data.properties || {});
    syncControlsFromStatus(data);
    startAutoUpdate();
  } catch (err) {
    console.error(err);
    setStatus('Connect error: ' + err.message, 'error');
  }
}

async function disconnect() {
  setStatus('Disconnecting...');
  try {
    const res = await fetch('/api/disconnect', { method: 'POST' });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    if (data.status !== 'ok') throw new Error(data.message || 'Failed to disconnect');
    setConnected(false);
    setStatus('Disconnected');
  } catch (err) {
    console.error(err);
    setStatus('Disconnect error: ' + err.message, 'error');
  }
}

async function acquireSingle() {
  setStatus('Acquiring...');
  try {
    const res = await fetch('/api/acquire/single');
    if (!res.ok) throw new Error('HTTP ' + res.status);
  const data = await res.json();
    if (data.status !== 'ok') throw new Error(data.message || 'Failed to acquire');
  const samples = (data.samples_mV && data.samples_mV.length) ? data.samples_mV : (data.samples || []);
  drawWaveform(samples, Boolean(data.samples_mV), data);
    const range = (typeof data.min_mV === 'number' && typeof data.max_mV === 'number') ? `, range: ${data.min_mV.toFixed(1)}..${data.max_mV.toFixed(1)} mV` : '';
    setStatus(`Acquired ${samples.length} samples${range}`);
  } catch (err) {
    console.error(err);
    setStatus('Acquire error: ' + err.message, 'error');
  }
}

function renderDeviceInfo(props) {
  const entries = Object.entries(props).map(([k, v]) => `<strong>${k}</strong>: ${v}`).join(' · ');
  deviceInfoEl.innerHTML = entries || '';
}

function drawWaveform(samples, isMilliVolts = false, meta = null) {
  const W = canvas.width;
  const H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  // Layout
  const padLeft = 54;   // space for Y labels
  const padRight = 12;
  const padTop = 12;
  const padBottom = 28; // space for X labels
  const plotW = W - padLeft - padRight;
  const plotH = H - padTop - padBottom;

  // Frame metadata
  const vDivSelVal = parseFloat(vDivSel.value);
  const tDivSelVal = parseFloat(tDivSel.value);
  const tDiv = (meta && typeof meta.t_div_s === 'number') ? meta.t_div_s : (Number.isFinite(tDivSelVal) ? tDivSelVal : 1e-3);
  const divCountX = 10; // horizontal divisions
  const divCountY = 8;  // vertical divisions
  const totalTime = tDiv * divCountX;
  const samplesPerDiv = meta?.config?.samples_per_div ?? 32;
  const tOffsetSamples = meta?.config?.t_offset_samples ?? 0;
  const tOffsetSeconds = (typeof tOffsetSamples === 'number' && samples && samples.length > 0)
    ? (tOffsetSamples * (tDiv / samplesPerDiv))
    : 0;

  if (!samples || samples.length === 0) return;

  // Voltage axis range based on device scale: offset_V ± (V/div * divCountY)
  const offsetV = meta?.config?.offset_V ?? 0;
  const vDiv_mV = (meta?.config?.v_div_mV ?? (Number.isFinite(vDivSelVal) ? vDivSelVal : undefined)) || 200;
  const vDiv_V = vDiv_mV / 1000.0;
  // UI shows 8 vertical divisions total; full-scale = vDiv * 8
  let min = - (vDiv_V * (divCountY / 2)) + offsetV;
  let max = + (vDiv_V * (divCountY / 2)) + offsetV;
  if (!isMilliVolts) {
    // If samples are raw, fallback to data range to avoid flat lines
    min = Infinity; max = -Infinity;
    for (const v of samples) { if (v < min) min = v; if (v > max) max = v; }
    if (min === max) { min = 0; max = 255; }
  } else {
    // samples already in mV; convert min/max to mV for rendering
    min *= 1000.0; max *= 1000.0;
  }

  // Axes grid aligned to ticks
  const yTicks = 8;
  const xTicks = 10;
  ctx.strokeStyle = '#e5e7eb';
  ctx.lineWidth = 1;
  // Draw grid and labels
  ctx.fillStyle = '#64748b';
  ctx.font = '12px system-ui';
  // Y-axis ticks and labels (min..max)
  for (let i = 0; i <= yTicks; i++) {
    const t = i / yTicks; // 0..1
    const y = padTop + plotH - t * plotH + 0.5;
    ctx.beginPath(); ctx.moveTo(padLeft, y); ctx.lineTo(W - padRight, y); ctx.stroke();
    const val = min + t * (max - min);
    ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
    ctx.fillText(formatVoltage(val, isMilliVolts), padLeft - 6, y);
  }
  // X-axis ticks and labels (centered by time offset)
  for (let i = 0; i <= xTicks; i++) {
    const t = i / xTicks;
    const x = padLeft + t * plotW + 0.5;
    ctx.beginPath(); ctx.moveTo(x, padTop); ctx.lineTo(x, padTop + plotH); ctx.stroke();
    const tv = -totalTime/2 + t * totalTime + tOffsetSeconds; // center + offset
    ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    ctx.fillText(formatSeconds(tv), x, padTop + plotH + 6);
  }

  // Drawing waveform within plot rect
  const toX = (i) => padLeft + (i / (samples.length - 1)) * plotW;
  const toY = (v) => padTop + plotH - ((v - min) / (max - min)) * plotH;

  ctx.strokeStyle = '#2563eb';
  ctx.lineWidth = 2;
  ctx.beginPath();
  const step = Math.max(1, Math.floor(samples.length / plotW));
  for (let i = 0; i < samples.length; i += step) {
    const x = toX(i);
    const y = toY(samples[i]);
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.stroke();

  // Axes captions
  const vDivHuman = vDivSelVal >= 1000 ? `${(vDivSelVal/1000).toFixed(2)} V/div` : `${vDivSelVal} mV/div`;
  ctx.fillStyle = '#475569';
  ctx.textAlign = 'left'; ctx.textBaseline = 'top';
  ctx.fillText(`${vDivHuman} | ${formatSeconds(tDiv)} / div`, padLeft, 2);
  if (meta && meta.time_iso) { ctx.fillText(`t: ${meta.time_iso}`, padLeft + 220, 2); }
}

function formatSeconds(s) {
  if (s < 1e-6) return `${(s*1e9).toFixed(0)} ns`;
  if (s < 1e-3) return `${(s*1e6).toFixed(0)} µs`;
  if (s < 1) return `${(s*1e3).toFixed(0)} ms`;
  return `${s.toFixed(2)} s`;
}

function formatVoltage(v, isMilliVolts) {
  // If inputs are already mV, isMilliVolts=true → prefer mV. Otherwise format smartly.
  const abs = Math.abs(v);
  if (isMilliVolts) {
    if (abs >= 1000) return (v/1000).toFixed(2) + ' V';
    return v.toFixed(1) + ' mV';
  }
  // raw samples path — show as counts
  return v.toFixed(0);
}

function syncControlsFromStatus(status) {
  if (status?.config) {
    const mv = status.config.v_div_mV;
    if (typeof mv === 'number') setSelectClosestByNumber(vDivSel, mv);
    if (typeof status.config.t_div_s === 'number') setSelectClosestByNumber(tDivSel, status.config.t_div_s);
    if (typeof status.config.trigger_level === 'number') trigLevelInput.value = String(status.config.trigger_level);
    if (typeof status.config.offset_V === 'number') offsetInput.value = String(status.config.offset_V.toFixed(2));
  }
}

function setSelectClosestByNumber(selectEl, target) {
  let bestIdx = -1;
  let bestDiff = Infinity;
  for (let i = 0; i < selectEl.options.length; i++) {
    const v = parseFloat(selectEl.options[i].value);
    if (!Number.isFinite(v)) continue;
    const d = Math.abs(v - target);
    if (d < bestDiff) { bestDiff = d; bestIdx = i; }
  }
  if (bestIdx >= 0) {
    selectEl.selectedIndex = bestIdx;
  } else {
    // fallback: set raw value if nothing matched
    selectEl.value = String(target);
  }
}

async function applyConfig() {
  const body = {};
  const vDiv = parseInt(vDivSel.value, 10);
  if (!Number.isNaN(vDiv)) body.v_div_mV = vDiv;
  const tDiv = parseFloat(tDivSel.value);
  if (!Number.isNaN(tDiv)) body.t_div_s = tDiv;
  const trig = parseInt(trigLevelInput.value, 10);
  if (!Number.isNaN(trig)) body.trigger_level = trig;
  const off = parseFloat(offsetInput.value);
  if (!Number.isNaN(off)) body.offset_V = off;
  try {
    const res = await fetch('/api/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const data = await res.json();
    if (data.status !== 'ok') throw new Error(data.message || 'Config failed');
    syncControlsFromStatus(data);
  } catch (e) {
    console.error(e);
    setStatus('Config error: ' + e.message, 'error');
  }
}

async function pollStatusOnce() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    if (data.status === 'ok') {
      setConnected(true);
      renderDeviceInfo(data.properties || {});
      syncControlsFromStatus(data);
      return true;
    }
    setConnected(false);
    setStatus('Disconnected');
    return false;
  } catch {
    setConnected(false);
    return false;
  }
}

function startAutoUpdate() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    try {
      if (!isConnected) {
        const ok = await pollStatusOnce();
        if (!ok) return; // still disconnected
      }
      const res = await fetch('/api/acquire/single');
      const data = await res.json();
      if (data.status === 'ok') {
        const samples = (data.samples_mV && data.samples_mV.length) ? data.samples_mV : (data.samples || []);
        drawWaveform(samples, Boolean(data.samples_mV), data);
      } else if (data.status === 'disconnected') {
        setConnected(false);
      }
    } catch {}
  }, 200);
}

connectBtn.addEventListener('click', connect);
disconnectBtn.addEventListener('click', disconnect);
acquireBtn.addEventListener('click', acquireSingle);
applyBtn.addEventListener('click', applyConfig);
verifyBtn?.addEventListener('click', async () => {
  try {
    await fetch('/api/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ v_div_mV: 20, t_div_s: 1e-3 }) });
    const res = await fetch('/api/acquire/single');
    const data = await res.json();
    if (data.status === 'ok') {
      const minMv = data.min_mV, maxMv = data.max_mV;
      setStatus(`Verify: V/div=20mV, t/div=1ms, range=${minMv?.toFixed?.(1)}..${maxMv?.toFixed?.(1)} mV`);
      const samples = (data.samples_mV && data.samples_mV.length) ? data.samples_mV : (data.samples || []);
      drawWaveform(samples, Boolean(data.samples_mV), data);
      console.log('Verify payload', data);
    } else {
      setStatus('Verify failed: ' + (data.message || data.status), 'error');
    }
  } catch (e) {
    console.error(e);
    setStatus('Verify error: ' + e.message, 'error');
  }
});

// Autoconnect and initial status
(async () => {
  const ok = await pollStatusOnce();
  if (ok) startAutoUpdate();
})();
