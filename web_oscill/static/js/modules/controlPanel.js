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
    this.vPosition = 0;
    this.tPosition = 0;
  }

  init() {
    this.bindElements();
    this.setupEventListeners();
    this.updateDisplay();
    this.updateRunStopButton(); // Initialize button state
  }

  bindElements() {
    this.vdivMinus = document.getElementById('vdiv-minus');
    this.vdivPlus = document.getElementById('vdiv-plus');
    this.vdivValue = document.getElementById('vdiv-value');
    this.vPosition = document.getElementById('v-position');
    this.couplingAc = document.getElementById('coupling-ac');
    this.couplingDc = document.getElementById('coupling-dc');
    this.couplingGnd = document.getElementById('coupling-gnd');

    this.tdivMinus = document.getElementById('tdiv-minus');
    this.tdivPlus = document.getElementById('tdiv-plus');
    this.tdivValue = document.getElementById('tdiv-value');
    this.hPosition = document.getElementById('h-position');

    this.trigAuto = document.getElementById('trig-auto');
    this.trigNormal = document.getElementById('trig-normal');
    this.trigSingle = document.getElementById('trig-single');
    this.trigRise = document.getElementById('trig-rise');
    this.trigFall = document.getElementById('trig-fall');
    this.trigLevel = document.getElementById('trig-level');

    this.runStop = document.getElementById('run-stop');
    this.single = document.getElementById('single');
  }

  setupEventListeners() {
    this.vdivMinus.addEventListener('click', () => this.changeVDiv(-1));
    this.vdivPlus.addEventListener('click', () => this.changeVDiv(1));
    this.vPosition.addEventListener('input', (e) => this.changeVPosition(parseFloat(e.target.value)));

    this.couplingAc.addEventListener('click', () => this.changeCoupling('AC'));
    this.couplingDc.addEventListener('click', () => this.changeCoupling('DC'));
    this.couplingGnd.addEventListener('click', () => this.changeCoupling('GND'));

    this.tdivMinus.addEventListener('click', () => this.changeTDiv(-1));
    this.tdivPlus.addEventListener('click', () => this.changeTDiv(1));
    this.hPosition.addEventListener('input', (e) => this.changeTPosition(parseFloat(e.target.value)));

    this.trigAuto.addEventListener('click', () => this.changeTriggerMode('Auto'));
    this.trigNormal.addEventListener('click', () => this.changeTriggerMode('Normal'));
    this.trigSingle.addEventListener('click', () => this.changeTriggerMode('Single'));
    this.trigRise.addEventListener('click', () => this.changeTriggerSlope('Rising'));
    this.trigFall.addEventListener('click', () => this.changeTriggerSlope('Falling'));
    this.trigLevel.addEventListener('input', (e) => this.changeTriggerLevel(parseInt(e.target.value)));

    this.runStop.addEventListener('click', () => this.toggleRunStop());
    this.single.addEventListener('click', () => this.onAcquisitionChange('single'));
  }

  changeVDiv(delta) {
    this.currentVIndex = Math.max(0, Math.min(this.vDivValues.length - 1, this.currentVIndex + delta));
    this.updateDisplay();
    this.onConfigChange({ v_div_mV: this.vDivValues[this.currentVIndex] });
  }

  changeTDiv(delta) {
    this.currentTIndex = Math.max(0, Math.min(this.tDivValues.length - 1, this.currentTIndex + delta));
    this.updateDisplay();
    this.onConfigChange({ t_div_s: this.tDivValues[this.currentTIndex] });
  }

  changeVPosition(value) {
    this.vPositionValue = value;
    this.onConfigChange({ v_offset: value });
  }

  changeTPosition(value) {
    this.tPositionValue = value;
    this.onConfigChange({ t_offset: value });
  }

  changeCoupling(coupling) {
    this.coupling = coupling;
    this.updateCouplingButtons();
    this.onConfigChange({ coupling });
  }

  changeTriggerMode(mode) {
    this.triggerMode = mode;
    this.updateTriggerModeButtons();
    this.onConfigChange({ trigger_mode: mode.toLowerCase() });
  }

  changeTriggerSlope(slope) {
    this.triggerSlope = slope;
    this.updateTriggerSlopeButtons();
    this.onConfigChange({ trigger_slope: slope.toLowerCase() });
  }

  changeTriggerLevel(level) {
    this.triggerLevel = level;
    this.onConfigChange({ trigger_level: level });
  }

  toggleRunStop() {
    const isRunning = this.runStop.innerHTML.includes('Stop');
    if (isRunning) {
      this.runStop.innerHTML = '<i class="fas fa-play"></i> Run';
      this.onAcquisitionChange('stop');
    } else {
      this.runStop.innerHTML = '<i class="fas fa-pause"></i> Stop';
      this.onAcquisitionChange('run');
    }
  }

  updateDisplay() {
    this.vdivValue.textContent = this.formatVoltage(this.vDivValues[this.currentVIndex]);
    this.tdivValue.textContent = this.formatTime(this.tDivValues[this.currentTIndex]);
  }

  updateCouplingButtons() {
    this.couplingAc.classList.toggle('active', this.coupling === 'AC');
    this.couplingDc.classList.toggle('active', this.coupling === 'DC');
    this.couplingGnd.classList.toggle('active', this.coupling === 'GND');
  }

  updateTriggerModeButtons() {
    this.trigAuto.classList.toggle('active', this.triggerMode === 'Auto');
    this.trigNormal.classList.toggle('active', this.triggerMode === 'Normal');
    this.trigSingle.classList.toggle('active', this.triggerMode === 'Single');
  }

  updateTriggerSlopeButtons() {
    this.trigRise.classList.toggle('active', this.triggerSlope === 'Rising');
    this.trigFall.classList.toggle('active', this.triggerSlope === 'Falling');
  }

  updateControls(config) {
    if (config.v_div) {
      const vValue = config.v_div.v;
      this.currentVIndex = this.vDivValues.indexOf(vValue);
      if (this.currentVIndex === -1) this.currentVIndex = 3; // default
    }
    if (config.t_div) {
      const tValue = config.t_div.v;
      this.currentTIndex = this.tDivValues.indexOf(tValue);
      if (this.currentTIndex === -1) this.currentTIndex = 5; // default
    }
    if (config.trigger_level !== undefined) {
      this.triggerLevel = config.trigger_level;
      this.trigLevel.value = config.trigger_level;
    }
    if (config.v_offset !== undefined) {
      this.vPosition.value = config.v_offset;
    }
    if (config.t_offset !== undefined) {
      this.hPosition.value = config.t_offset;
    }
    this.updateDisplay();
  }

  updateRunStopButton() {
    // This method can be called to sync button state with app.isRunning if needed
    // For now, button starts with play icon and "Run" text by default
  }

  formatVoltage(mv) {
    if (mv >= 1000) return `${(mv / 1000).toFixed(1)} V`;
    return `${mv} mV`;
  }

  formatTime(s) {
    if (s >= 1) return `${s.toFixed(1)} s`;
    if (s >= 0.001) return `${(s * 1000).toFixed(0)} ms`;
    if (s >= 0.000001) return `${(s * 1000000).toFixed(0)} µs`;
    return `${(s * 1000000000).toFixed(0)} ns`;
  }
}