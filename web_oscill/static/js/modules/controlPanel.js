import { formatUniversal, Quantity, FormatType } from './format.js';

export class ControlPanel {
  constructor(onConfigChange, onAcquisitionChange) {
    this.onConfigChange = onConfigChange;
    this.onAcquisitionChange = onAcquisitionChange;
    this.vDivValues = [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000]; // mV
    this.tDivValues = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500]; // ms
    this.currentVIndex = 3; // 200 mV
    this.currentTIndex = 5; // 5 ms
    this.coupling = 'DC';
    this.triggerMode = 'Auto';
    this.triggerSlope = 'Rising';
    this.triggerLevel = 128;
    this.vPositionValue = 0; // in DIVS (-4..4)
    this.tPositionValue = 0;
    this.onTriggerLevelChange = null;
    this._isAcquiring = false;
    this.swMode = 'NORMAL';
    this.filters = { high: false, low: false };
    this.syncType = 'AUTO';
    this.syncFront = true;
    this.syncBack = false;

    this._ui = {}; // store Konva nodes
  }

  init() {
    this.container = document.getElementById('control-panel');
    // Clear existing DOM controls and mount canvas UI
    this.container.innerHTML = '';
    const width = this.container.clientWidth || 320;
    const height = this.container.clientHeight || window.innerHeight - 60;
    this.stage = new Konva.Stage({ container: this.container, width, height });
    this.layer = new Konva.Layer();
    this.stage.add(this.layer);

    this._buildUI();
    this._layoutUI();

    this._resizeObserver = new ResizeObserver(() => this._resize());
    this._resizeObserver.observe(this.container);
  }

  _resize() {
    const w = this.container.clientWidth || 320;
    const h = this.container.clientHeight || window.innerHeight - 60;
    this.stage.size({ width: w, height: h });
    this._layoutUI();
  }

  _button(x, y, w, h, label, onClick, opts = {}) {
    const group = new Konva.Group({ x, y });
    const rect = new Konva.Rect({ width: w, height: h, cornerRadius: 6, fill: opts.active ? '#007acc' : '#3c3c3c', stroke: opts.active ? '#007acc' : '#555', strokeWidth: 1 });
    const text = new Konva.Text({ x: 0, y: 0, width: w, height: h, align: 'center', verticalAlign: 'middle', text: label, fontSize: 14, fill: '#fff' });
    group.add(rect, text);
    group.on('mouseenter', () => { document.body.style.cursor = 'pointer'; rect.fill(opts.active ? '#1286d8' : '#4c4c4c'); this.layer.draw(); });
    group.on('mouseleave', () => { document.body.style.cursor = 'default'; rect.fill(opts.active ? '#007acc' : '#3c3c3c'); this.layer.draw(); });
    group.on('click', () => onClick && onClick());
    return { group, rect, text };
  }

  _label(x, y, textStr, size = 14, color = '#ccc') {
    const t = new Konva.Text({ x, y, text: textStr, fontSize: size, fill: color });
    return t;
  }

  _slider(x, y, w, min, max, value, onChange, onCommit, opts = {}) {
    const group = new Konva.Group({ x, y });
    const track = new Konva.Rect({ x: 0, y: 10, width: w, height: 4, fill: '#555', cornerRadius: 2 });
    const range = max - min;
    const toX = (val) => ((val - min) / range) * w;
    const toVal = (px) => min + (px / w) * range;
    const handle = new Konva.Circle({ x: toX(value), y: 12, radius: 8, fill: '#999', stroke: '#ddd', strokeWidth: 1, draggable: true });
    const valueText = new Konva.Text({ x: w + 8, y: 4, text: opts.format ? opts.format(value) : String(value), fontSize: 12, fill: '#ddd' });
    handle.on('dragmove', () => {
      const nx = Math.max(0, Math.min(w, handle.x()));
      handle.x(nx);
      const val = toVal(nx);
      valueText.text(opts.format ? opts.format(val) : val.toFixed(2));
      onChange && onChange(val);
      this.layer.batchDraw();
    });
    handle.on('dragend', () => {
      const val = toVal(handle.x());
      onCommit && onCommit(val);
    });
    group.add(track, handle, valueText);
    return { group, handle, valueText, toX, toVal };
  }

  _buildUI() {
    const padX = 12;
    const colW = (this.stage.width() - padX * 2);
    let y = 8;

    // Acquisition controls
  const buttonW = (colW - 12) / 2;
  this._ui.runStop = this._button(padX, y, buttonW, 36, '▶ Run', () => this._toggleRunStop());
  this._ui.single = this._button(padX + buttonW + 12, y, buttonW, 36, '⏺ Single', () => this.onAcquisitionChange('single'));
  y += 46;

  // Processing modes
  const modeGap = 12;
  this._ui.procLabel = this._label(padX, y, 'Processing', 16, '#ccc');
  y += 22;
  const modeBtnW = (colW - modeGap * 3) / 4;
  this._ui.modeNormal = this._button(padX, y, modeBtnW, 32, 'Normal', () => this.setSwMode('NORMAL'), { active: this.swMode === 'NORMAL' });
  this._ui.modePeak = this._button(padX + (modeBtnW + modeGap), y, modeBtnW, 32, 'Peak', () => this.setSwMode('PEAK'), { active: this.swMode === 'PEAK' || this.swMode === 'PEAK_HI' });
  this._ui.modeAvg = this._button(padX + 2 * (modeBtnW + modeGap), y, modeBtnW, 32, 'Avg', () => this.setSwMode('AVG'), { active: this.swMode === 'AVG' });
  this._ui.modeAvgHi = this._button(padX + 3 * (modeBtnW + modeGap), y, modeBtnW, 32, 'Avg Hi-Res', () => this.setSwMode('AVG_HIRES'), { active: this.swMode === 'AVG_HIRES' });
  y += 40;

  // Hardware filters
  this._ui.filterLabel = this._label(padX, y, 'Filters', 16, '#ccc');
  y += 22;
  const filterBtnW = (colW - modeGap) / 2;
  this._ui.filterHigh = this._button(padX, y, filterBtnW, 32, 'High 3MHz', () => this.toggleFilter('high'), { active: this.filters.high });
  this._ui.filterLow = this._button(padX + filterBtnW + modeGap, y, filterBtnW, 32, 'Low 3kHz', () => this.toggleFilter('low'), { active: this.filters.low });
  y += 40;

    // Vertical group
    this._ui.vertLabel = this._label(padX, y, 'Vertical', 16, '#ccc');
    y += 22;
    this._ui.vdivMinus = this._button(padX, y, 36, 28, '−', () => this.changeVDiv(-1));
    this._ui.vdivValue = this._label(
      padX + 44,
      y + 6,
      formatUniversal(this.vDivValues[this.currentVIndex], 'm', 'auto', Quantity.V, FormatType.std),
      14,
      '#fff'
    );
    this._ui.vdivPlus = this._button(padX + 180, y, 36, 28, '+', () => this.changeVDiv(1));
    y += 36;
    this._ui.vposLabel = this._label(padX, y, 'Position');
    this._ui.vposSlider = this._slider(padX + 80, y - 6, colW - 160, -4, 4, this.vPositionValue,
      (val) => { // onChange preview
        this.previewVPosition(val);
      },
      (val) => { // onCommit
        this.changeVPosition(val);
      },
      { format: (v) => `${v.toFixed(1)} div` }
    );
    y += 40;
    this._ui.cplLabel = this._label(padX, y, 'Coupling');
    this._ui.cplAc = this._button(padX + 80, y - 6, 60, 28, 'AC', () => this.changeCoupling('AC'), { active: this.coupling === 'AC' });
    this._ui.cplDc = this._button(padX + 146, y - 6, 60, 28, 'DC', () => this.changeCoupling('DC'), { active: this.coupling === 'DC' });
    this._ui.cplGnd = this._button(padX + 212, y - 6, 60, 28, 'GND', () => this.changeCoupling('GND'), { active: this.coupling === 'GND' });
    y += 46;

    // Horizontal group
    this._ui.horzLabel = this._label(padX, y, 'Horizontal', 16, '#ccc');
    y += 22;
    this._ui.tdivMinus = this._button(padX, y, 36, 28, '−', () => this.changeTDiv(-1));
    this._ui.tdivValue = this._label(
      padX + 44,
      y + 6,
      formatUniversal(this.tDivValues[this.currentTIndex], 'm', 'auto', Quantity.s, FormatType.std),
      14,
      '#fff'
    );
    this._ui.tdivPlus = this._button(padX + 180, y, 36, 28, '+', () => this.changeTDiv(1));
    y += 36;
    this._ui.hposLabel = this._label(padX, y, 'Position');
    this._ui.hposSlider = this._slider(padX + 80, y - 6, colW - 160, -5, 5, this.tPositionValue,
      (val) => { this.previewTPosition(val); },
      (val) => { this.changeTPosition(val); },
      { format: (v) => `${v.toFixed(1)} div` }
    );
    y += 46;

    // Trigger group
    this._ui.trigLabel = this._label(padX, y, 'Trigger', 16, '#ccc');
    y += 22;
  const trigBtnW = (colW - modeGap * 3) / 4;
  this._ui.trigAuto = this._button(padX, y, trigBtnW, 28, 'Auto', () => this.setSyncType('AUTO'), { active: this.syncType === 'AUTO' });
  this._ui.trigTimeout = this._button(padX + (trigBtnW + modeGap), y, trigBtnW, 28, 'Timeout', () => this.setSyncType('WAIT_TIMEOUT'), { active: this.syncType === 'WAIT_TIMEOUT' });
  this._ui.trigWait = this._button(padX + 2 * (trigBtnW + modeGap), y, trigBtnW, 28, 'Wait', () => this.setSyncType('WAIT'), { active: this.syncType === 'WAIT' });
  this._ui.trigFree = this._button(padX + 3 * (trigBtnW + modeGap), y, trigBtnW, 28, 'Free', () => this.setSyncType('FREE'), { active: this.syncType === 'FREE' });
  y += 36;
  this._ui.edgeLabel = this._label(padX, y, 'Sync Edges');
  y += 22;
  const edgeBtnW = (colW - modeGap) / 2;
  this._ui.trigFront = this._button(padX, y, edgeBtnW, 28, 'Front', () => this.toggleSyncEdge('front'), { active: this.syncFront });
  this._ui.trigBack = this._button(padX + edgeBtnW + modeGap, y, edgeBtnW, 28, 'Back', () => this.toggleSyncEdge('back'), { active: this.syncBack });
  y += 36;
    this._ui.levelLabel = this._label(padX, y, 'Level');
    this._ui.levelSlider = this._slider(padX + 80, y - 6, colW - 160, 0, 255, this.triggerLevel,
      (val) => this.previewTriggerLevel(Math.round(val)),
      (val) => this.changeTriggerLevel(Math.round(val)),
      { format: (v) => `${Math.round(v)}` }
    );
    y += 60;

    // Add all to layer
    this.layer.add(
      this._ui.runStop.group,
      this._ui.single.group,
  this._ui.procLabel,
  this._ui.modeNormal.group,
  this._ui.modePeak.group,
  this._ui.modeAvg.group,
  this._ui.modeAvgHi.group,
  this._ui.filterLabel,
  this._ui.filterHigh.group,
  this._ui.filterLow.group,
      this._ui.vertLabel,
      this._ui.vdivMinus.group,
      this._ui.vdivValue,
      this._ui.vdivPlus.group,
      this._ui.vposLabel,
      this._ui.vposSlider.group,
      this._ui.cplLabel,
      this._ui.cplAc.group,
      this._ui.cplDc.group,
      this._ui.cplGnd.group,
      this._ui.horzLabel,
      this._ui.tdivMinus.group,
      this._ui.tdivValue,
      this._ui.tdivPlus.group,
      this._ui.hposLabel,
      this._ui.hposSlider.group,
      this._ui.trigLabel,
      this._ui.trigAuto.group,
      this._ui.trigTimeout.group,
      this._ui.trigWait.group,
      this._ui.trigFree.group,
      this._ui.edgeLabel,
      this._ui.trigFront.group,
      this._ui.trigBack.group,
      this._ui.levelLabel,
      this._ui.levelSlider.group,
    );

    this.layer.draw();
    this.setSingleEnabled(true);
  }

  _layoutUI() {
    // Reposition width-dependent elements like slider widths and labels
    const padX = 12;
    const colW = (this.stage.width() - padX * 2);
    // Update widths of elements that depend on colW
    // VDiv section: value label stays at padX + 44; plus button at padX+180 is acceptable baseline
    // Sliders: adjust width and value text x
    const setSliderWidth = (slider, w) => {
      slider.group.findOne('Rect').width(w);
      const val = slider.toVal(slider.handle.x());
      slider.group.findOne('Text').x(w + 8);
    };
    setSliderWidth(this._ui.vposSlider, colW - 160);
    setSliderWidth(this._ui.hposSlider, colW - 160);
    setSliderWidth(this._ui.levelSlider, colW - 160);
    this.layer.batchDraw();
  }

  _toggleRunStop() {
    const willStart = !this._isAcquiring;
    if (willStart) {
      this._isAcquiring = true;
      this._setRunButtonLabel();
      this.setSingleEnabled(false);
      this.onAcquisitionChange('run');
    } else {
      this._isAcquiring = false;
      this._setRunButtonLabel();
      this.setSingleEnabled(true);
      this.onAcquisitionChange('stop');
    }
    this.layer.batchDraw();
  }

  changeVDiv(delta) {
    this.currentVIndex = Math.max(0, Math.min(this.vDivValues.length - 1, this.currentVIndex + delta));
    this._ui.vdivValue.text(
      formatUniversal(this.vDivValues[this.currentVIndex], 'm', 'auto', Quantity.V, FormatType.std)
    );
    this.layer.batchDraw();
    this.onConfigChange({ v_div: { v: this.vDivValues[this.currentVIndex], u: "mV" } });
  }

  changeTDiv(delta) {
    this.currentTIndex = Math.max(0, Math.min(this.tDivValues.length - 1, this.currentTIndex + delta));
    this._ui.tdivValue.text(
      formatUniversal(this.tDivValues[this.currentTIndex], 'm', 'auto', Quantity.s, FormatType.std)
    );
    this.layer.batchDraw();
    this.onConfigChange({ t_div: { v: this.tDivValues[this.currentTIndex], u: "ms" } });
  }

  changeVPosition(value) {
    this.vPositionValue = value;
    const vDivV = (this.vDivValues[this.currentVIndex] || 200) / 1000.0;
    const volts = value * vDivV;
    this.onConfigChange({ v_offset: { v: volts, u: "V" } });
  }

  changeTPosition(value) {
    this.tPositionValue = value;
    // Optional: backend currently expects t_offset_samples; this UI preview is informational only
    this.onConfigChange({ t_offset: value });
  }

  previewTPosition(value) {
    this.tPositionValue = value;
  }

  changeCoupling(coupling) {
    this.coupling = coupling;
    this._setButtonActive(this._ui.cplAc, coupling === 'AC');
    this._setButtonActive(this._ui.cplDc, coupling === 'DC');
    this._setButtonActive(this._ui.cplGnd, coupling === 'GND');
    this.layer.batchDraw();
    this.onConfigChange({ coupling });
  }

  _applySwModeState(mode) {
    const normalized = (mode || 'NORMAL').toUpperCase();
    this.swMode = normalized;
    const isPeak = normalized.startsWith('PEAK');
    this._setButtonActive(this._ui.modeNormal, normalized === 'NORMAL');
    this._setButtonActive(this._ui.modePeak, isPeak);
    this._setButtonActive(this._ui.modeAvg, normalized === 'AVG');
    this._setButtonActive(this._ui.modeAvgHi, normalized === 'AVG_HIRES');
  }

  setSwMode(mode) {
    this._applySwModeState(mode);
    this.layer.batchDraw();
    this.onConfigChange({ sw_mode: this.swMode });
  }

  _applyFilterState() {
    this._setButtonActive(this._ui.filterHigh, !!this.filters.high);
    this._setButtonActive(this._ui.filterLow, !!this.filters.low);
  }

  toggleFilter(name, explicitValue = null) {
    if (!(name in this.filters)) return;
    const nextValue = explicitValue === null ? !this.filters[name] : !!explicitValue;
    this.filters[name] = nextValue;
    this._applyFilterState();
    this.layer.batchDraw();
    this.onConfigChange({ filter_high: this.filters.high, filter_low: this.filters.low });
  }

  _applySyncTypeState(type) {
    const normalized = (type || 'AUTO').toUpperCase();
    this.syncType = normalized;
    if (this._ui.trigAuto) this._setButtonActive(this._ui.trigAuto, normalized === 'AUTO');
    if (this._ui.trigTimeout) this._setButtonActive(this._ui.trigTimeout, normalized === 'WAIT_TIMEOUT');
    if (this._ui.trigWait) this._setButtonActive(this._ui.trigWait, normalized === 'WAIT');
    if (this._ui.trigFree) this._setButtonActive(this._ui.trigFree, normalized === 'FREE');
  }

  setSyncType(type) {
    this._applySyncTypeState(type);
    this.layer.batchDraw();
    this.onConfigChange({ sync_type: this.syncType });
  }

  _applySyncEdgesState(front = this.syncFront, back = this.syncBack) {
    this.syncFront = typeof front === 'boolean' ? front : this.syncFront;
    this.syncBack = typeof back === 'boolean' ? back : this.syncBack;
    if (this._ui.trigFront) this._setButtonActive(this._ui.trigFront, this.syncFront);
    if (this._ui.trigBack) this._setButtonActive(this._ui.trigBack, this.syncBack);
  }

  toggleSyncEdge(edge, explicitValue = null) {
    if (edge === 'front') {
      const next = explicitValue === null ? !this.syncFront : !!explicitValue;
      this._applySyncEdgesState(next, this.syncBack);
    } else if (edge === 'back') {
      const next = explicitValue === null ? !this.syncBack : !!explicitValue;
      this._applySyncEdgesState(this.syncFront, next);
    } else {
      return;
    }
    this.layer.batchDraw();
    this.onConfigChange({ sync_front: this.syncFront, sync_back: this.syncBack });
  }

  changeTriggerMode(mode) {
    this.setSyncType(mode);
  }

  changeTriggerLevel(level) {
    this.triggerLevel = level;
    this.onConfigChange({ trigger_level: level });
    if (this.onTriggerLevelChange) this.onTriggerLevelChange(level);
  }

  previewTriggerLevel(level) {
    this.triggerLevel = level;
    if (this.onTriggerLevelChange) this.onTriggerLevelChange(level);
  }

  updateControls(config) {
    if (config.v_div) {
      let vValue = config.v_div.v;
      if (config.v_div.u === 'V') vValue *= 1000; // Convert to mV for comparison
      const idx = this.vDivValues.indexOf(vValue);
      this.currentVIndex = idx !== -1 ? idx : this.currentVIndex;
      if (this._ui.vdivValue) this._ui.vdivValue.text(this.formatVoltage(this.vDivValues[this.currentVIndex]));
    }
    if (config.t_div) {
      let tValue = config.t_div.v;
      const idx = this.tDivValues.indexOf(tValue);
      this.currentTIndex = idx !== -1 ? idx : this.currentTIndex;
      if (this._ui.tdivValue) this._ui.tdivValue.text(this.formatTime(this.tDivValues[this.currentTIndex]));
    }
    if (typeof config.trigger_level === 'number' && this._ui.levelSlider) {
      this.triggerLevel = config.trigger_level;
      const x = this._ui.levelSlider.toX(this.triggerLevel);
      this._ui.levelSlider.handle.x(x);
      this._ui.levelSlider.valueText.text(`${Math.round(this.triggerLevel)}`);
    }
    if (config.coupling) {
      this.coupling = config.coupling;
      this._setButtonActive(this._ui.cplAc, this.coupling === 'AC');
      this._setButtonActive(this._ui.cplDc, this.coupling === 'DC');
      this._setButtonActive(this._ui.cplGnd, this.coupling === 'GND');
    }
    if (config.filters) {
      this.filters.high = !!config.filters.high;
      this.filters.low = !!config.filters.low;
      this._applyFilterState();
    }
    if (config.sw_mode) {
      this._applySwModeState(config.sw_mode);
    }
    if (config.sync_type) {
      this._applySyncTypeState(config.sync_type);
    }
    if (typeof config.sync_front === 'boolean' || typeof config.sync_back === 'boolean') {
      const front = typeof config.sync_front === 'boolean' ? config.sync_front : this.syncFront;
      const back = typeof config.sync_back === 'boolean' ? config.sync_back : this.syncBack;
      this._applySyncEdgesState(front, back);
    }
    // t_offset is represented in samples in config; the UI slider is in divs; keep as-is for now.
    this.layer && this.layer.batchDraw();
  }

  setAcquisitionState(state) {
    if (!this._ui.runStop) return;
    if (state === 'run') {
      this._isAcquiring = true;
      this.setSingleEnabled(false);
    } else if (state === 'stop') {
      this._isAcquiring = false;
      this.setSingleEnabled(true);
    }
    this._setRunButtonLabel();
    this.layer.batchDraw();
  }

  setSingleEnabled(enabled) {
    if (!this._ui.single) return;
    this._ui.singleEnabled = enabled;
    const { group, rect, text } = this._ui.single;
    group.listening(enabled);
    rect.listening(enabled);
    text.listening(enabled);
    const fill = enabled ? '#3c3c3c' : '#1f1f1f';
    const stroke = enabled ? '#555' : '#2a2a2a';
    const labelColor = enabled ? '#fff' : '#777';
    rect.fill(fill);
    rect.stroke(stroke);
    text.fill(labelColor);
    group.opacity(enabled ? 1 : 0.5);
    this.layer && this.layer.batchDraw();
  }

  _setButtonActive(buttonRef, active) {
    if (!buttonRef) return;
    buttonRef.rect.fill(active ? '#007acc' : '#3c3c3c');
    buttonRef.rect.stroke(active ? '#007acc' : '#555');
  }

  _setRunButtonLabel() {
    if (!this._ui.runStop) return;
    const iconLabel = this._isAcquiring ? '⏹ Stop' : '▶ Run';
    this._ui.runStop.text.text(iconLabel);
  }

  setTriggerLevelChangeCallback(callback) { this.onTriggerLevelChange = callback; }

  formatVoltage(valueMV) {
    return formatUniversal(valueMV, 'm', 'auto', Quantity.V, FormatType.std);
  }

  formatTime(valueMS) {
    return formatUniversal(valueMS, 'm', 'auto', Quantity.s, FormatType.std);
  }

  // Formatting delegated to format.js (formatUniversal)
}