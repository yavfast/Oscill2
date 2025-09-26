import { formatUniversal, Quantity, FormatType } from './format.js';

export class ControlPanel {
  constructor(onConfigChange, onAcquisitionChange) {
    this.onConfigChange = onConfigChange;
    this.onAcquisitionChange = onAcquisitionChange;
    this.vDivValues = [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000]; // mV
    this.tDivValues = [0.0001, 0.0002, 0.0005, 0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5]; // s
    this.currentVIndex = 3; // 200 mV
    this.currentTIndex = 5; // 5 ms
    this.coupling = 'DC';
    this.triggerMode = 'Auto';
    this.triggerSlope = 'Rising';
    this.triggerLevel = 128;
    this.vPositionValue = 0; // in DIVS (-4..4)
    this.tPositionValue = 0;
    this.onTriggerLevelChange = null;

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
    this._ui.acqLabel = this._label(padX, y, 'Acquisition', 16, '#ccc');
    y += 22;
    this._ui.runStop = this._button(padX, y, colW * 0.55, 36, 'Run', () => this._toggleRunStop());
    this._ui.single = this._button(padX + colW * 0.6, y, colW * 0.4, 36, 'Single', () => this.onAcquisitionChange('single'));
    y += 48;

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
      formatUniversal(this.tDivValues[this.currentTIndex], '_', 'auto', Quantity.s, FormatType.std),
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
    this._ui.trigAuto = this._button(padX, y, 70, 28, 'Auto', () => this.changeTriggerMode('Auto'), { active: this.triggerMode === 'Auto' });
    this._ui.trigNormal = this._button(padX + 76, y, 80, 28, 'Normal', () => this.changeTriggerMode('Normal'), { active: this.triggerMode === 'Normal' });
    this._ui.trigSingle = this._button(padX + 162, y, 80, 28, 'Single', () => this.changeTriggerMode('Single'), { active: this.triggerMode === 'Single' });
    y += 36;
    this._ui.slopeLabel = this._label(padX, y, 'Slope');
    this._ui.trigRise = this._button(padX + 80, y - 6, 80, 28, 'Rising', () => this.changeTriggerSlope('Rising'), { active: this.triggerSlope === 'Rising' });
    this._ui.trigFall = this._button(padX + 166, y - 6, 80, 28, 'Falling', () => this.changeTriggerSlope('Falling'), { active: this.triggerSlope === 'Falling' });
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
      this._ui.acqLabel,
      this._ui.runStop.group,
      this._ui.single.group,
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
      this._ui.trigNormal.group,
      this._ui.trigSingle.group,
      this._ui.slopeLabel,
      this._ui.trigRise.group,
      this._ui.trigFall.group,
      this._ui.levelLabel,
      this._ui.levelSlider.group,
    );

    this.layer.draw();
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
    const isRun = this._ui.runStop.text.text() === 'Run' ? false : true;
    if (isRun) {
      this._ui.runStop.text.text('Run');
      this.onAcquisitionChange('stop');
    } else {
      this._ui.runStop.text.text('Stop');
      this.onAcquisitionChange('run');
    }
    this.layer.batchDraw();
  }

  changeVDiv(delta) {
    this.currentVIndex = Math.max(0, Math.min(this.vDivValues.length - 1, this.currentVIndex + delta));
    this._ui.vdivValue.text(
      formatUniversal(this.vDivValues[this.currentVIndex], 'm', 'auto', Quantity.V, FormatType.std)
    );
    this.layer.batchDraw();
    this.onConfigChange({ v_div_mV: this.vDivValues[this.currentVIndex] });
  }

  changeTDiv(delta) {
    this.currentTIndex = Math.max(0, Math.min(this.tDivValues.length - 1, this.currentTIndex + delta));
    this._ui.tdivValue.text(
      formatUniversal(this.tDivValues[this.currentTIndex], '_', 'auto', Quantity.s, FormatType.std)
    );
    this.layer.batchDraw();
    this.onConfigChange({ t_div_s: this.tDivValues[this.currentTIndex] });
  }

  changeVPosition(value) {
    this.vPositionValue = value;
    const vDivV = (this.vDivValues[this.currentVIndex] || 200) / 1000.0;
    const volts = value * vDivV;
    this.onConfigChange({ offset_V: volts });
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
    const setActive = (btn, active) => { btn.rect.fill(active ? '#007acc' : '#3c3c3c'); btn.rect.stroke(active ? '#007acc' : '#555'); };
    setActive(this._ui.cplAc, coupling === 'AC');
    setActive(this._ui.cplDc, coupling === 'DC');
    setActive(this._ui.cplGnd, coupling === 'GND');
    this.layer.batchDraw();
    this.onConfigChange({ coupling });
  }

  changeTriggerMode(mode) {
    this.triggerMode = mode;
    const setActive = (btn, active) => { btn.rect.fill(active ? '#007acc' : '#3c3c3c'); btn.rect.stroke(active ? '#007acc' : '#555'); };
    setActive(this._ui.trigAuto, mode === 'Auto');
    setActive(this._ui.trigNormal, mode === 'Normal');
    setActive(this._ui.trigSingle, mode === 'Single');
    this.layer.batchDraw();
    this.onConfigChange({ trigger_mode: mode.toLowerCase() });
  }

  changeTriggerSlope(slope) {
    this.triggerSlope = slope;
    const setActive = (btn, active) => { btn.rect.fill(active ? '#007acc' : '#3c3c3c'); btn.rect.stroke(active ? '#007acc' : '#555'); };
    setActive(this._ui.trigRise, slope === 'Rising');
    setActive(this._ui.trigFall, slope === 'Falling');
    this.layer.batchDraw();
    this.onConfigChange({ trigger_slope: slope.toLowerCase() });
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
      const vValue = config.v_div.v;
      const idx = this.vDivValues.indexOf(vValue);
      this.currentVIndex = idx !== -1 ? idx : this.currentVIndex;
      if (this._ui.vdivValue) this._ui.vdivValue.text(this.formatVoltage(this.vDivValues[this.currentVIndex]));
    }
    if (config.t_div) {
      const tValue = config.t_div.v;
      const idx = this.tDivValues.indexOf(tValue);
      this.currentTIndex = idx !== -1 ? idx : this.currentTIndex;
      if (this._ui.tdivValue) this._ui.tdivValue.text(this.formatTime(this.tDivValues[this.currentTIndex]));
    }
    if (config.trigger_level !== undefined && this._ui.levelSlider) {
      this.triggerLevel = config.trigger_level;
      const x = this._ui.levelSlider.toX(this.triggerLevel);
      this._ui.levelSlider.handle.x(x);
      this._ui.levelSlider.valueText.text(`${Math.round(this.triggerLevel)}`);
    }
    // t_offset is represented in samples in config; the UI slider is in divs; keep as-is for now.
    this.layer && this.layer.batchDraw();
  }

  setAcquisitionState(state) {
    if (!this._ui.runStop) return;
    if (state === 'run') this._ui.runStop.text.text('Stop');
    else if (state === 'stop') this._ui.runStop.text.text('Run');
    this.layer.batchDraw();
  }

  setTriggerLevelChangeCallback(callback) { this.onTriggerLevelChange = callback; }

  // Formatting delegated to format.js (formatUniversal)
}