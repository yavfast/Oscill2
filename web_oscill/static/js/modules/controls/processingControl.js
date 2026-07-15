import { createButton, createLabel, setButtonActive, createSlider } from './uiHelpers.js';

const DEFAULT_MODE = 'NORMAL';

export class ProcessingControl {
  constructor({ layer, onConfigChange, modeGap = 12 }) {
    this.layer = layer;
    this.onConfigChange = onConfigChange;
    this.modeGap = modeGap;
    this.swMode = DEFAULT_MODE;
    // [SP_RES_01_01] Resolution-enhancement controls (defaults mirror EnhancementSettings).
    this.enhEnabled = false;
    this.enhDepth = 16;
    this.enhWindow = 1;
    // Bounds default to the structural limits (SP_RES_01_04); overwritten from
    // config.limits when available (SingleSourceForSharedConstants — not hardcoded UI copy).
    this.enhDepthLimit = { min: 2, max: 64 };
    this.enhWindowLimit = { min: 1, max: 63 };
    this.ui = {};
  }

  build({ padX, y, colWidth }) {
    let nextY = y;
    this.ui.label = createLabel({ x: padX, y: nextY, text: 'Processing', fontSize: 16, color: '#ccc' });
    nextY += 22;

    const modeRow1Count = 3;
    const modeBtnW1 = (colWidth - this.modeGap * (modeRow1Count - 1)) / modeRow1Count;
    this.ui.modeNormal = createButton(this.layer, {
      x: padX,
      y: nextY,
      width: modeBtnW1,
      height: 32,
      label: 'Normal',
      onClick: () => this.setMode('NORMAL'),
      active: this.swMode === 'NORMAL',
    });
    this.ui.modePeak = createButton(this.layer, {
      x: padX + (modeBtnW1 + this.modeGap),
      y: nextY,
      width: modeBtnW1,
      height: 32,
      label: 'Peak',
      onClick: () => this.setMode('PEAK'),
      active: this.swMode === 'PEAK',
    });
    this.ui.modePeakHi = createButton(this.layer, {
      x: padX + 2 * (modeBtnW1 + this.modeGap),
      y: nextY,
      width: modeBtnW1,
      height: 32,
      label: 'Peak Hi',
      onClick: () => this.setMode('PEAK_HI'),
      active: this.swMode === 'PEAK_HI',
    });
    nextY += 40;

    const modeRow2Count = 2;
    const modeBtnW2 = (colWidth - this.modeGap * (modeRow2Count - 1)) / modeRow2Count;
    this.ui.modeAvg = createButton(this.layer, {
      x: padX,
      y: nextY,
      width: modeBtnW2,
      height: 32,
      label: 'Avg',
      onClick: () => this.setMode('AVG'),
      active: this.swMode === 'AVG',
    });
    this.ui.modeAvgHi = createButton(this.layer, {
      x: padX + (modeBtnW2 + this.modeGap),
      y: nextY,
      width: modeBtnW2,
      height: 32,
      label: 'Avg Hi-Res',
      onClick: () => this.setMode('AVG_HIRES'),
      active: this.swMode === 'AVG_HIRES',
    });
    nextY += 40;

    this.layer.add(
      this.ui.label,
      this.ui.modeNormal.group,
      this.ui.modePeak.group,
      this.ui.modePeakHi.group,
      this.ui.modeAvg.group,
      this.ui.modeAvgHi.group,
    );

    // [SP_RES_02_06] Resolution enhancement (periodic-signal effective-resolution boost).
    nextY += 10;
    this.ui.enhLabel = createLabel({ x: padX, y: nextY, text: 'Resolution (periodic)', fontSize: 16, color: '#ccc' });
    nextY += 22;
    this.ui.enhToggle = createButton(this.layer, {
      x: padX, y: nextY, width: colWidth, height: 32,
      label: this._enhToggleLabel(),
      onClick: () => this.toggleEnh(),
      active: this.enhEnabled,
    });
    nextY += 40;

    const sliderW = Math.max(60, colWidth - 44);
    this.ui.enhDepthLabel = createLabel({ x: padX, y: nextY, text: 'Depth N', fontSize: 12, color: '#aaa' });
    nextY += 16;
    this.ui.enhDepthSlider = createSlider(this.layer, {
      x: padX, y: nextY, width: sliderW,
      min: this.enhDepthLimit.min, max: this.enhDepthLimit.max, value: this.enhDepth,
      onCommit: (v) => this.setEnhDepth(v),
      format: (v) => `${Math.round(v)}`,
    });
    nextY += 30;

    this.ui.enhWinLabel = createLabel({ x: padX, y: nextY, text: 'SMA window W', fontSize: 12, color: '#aaa' });
    nextY += 16;
    this.ui.enhWinSlider = createSlider(this.layer, {
      x: padX, y: nextY, width: sliderW,
      min: this.enhWindowLimit.min, max: this.enhWindowLimit.max, value: this.enhWindow,
      onCommit: (v) => this.setEnhWindow(v),
      format: (v) => `${Math.round(v)}`,
    });
    nextY += 34;

    this.layer.add(
      this.ui.enhLabel,
      this.ui.enhToggle.group,
      this.ui.enhDepthLabel,
      this.ui.enhDepthSlider.group,
      this.ui.enhWinLabel,
      this.ui.enhWinSlider.group,
    );
    return nextY;
  }

  _enhToggleLabel() {
    return this.enhEnabled ? 'Enhance: ON' : 'Enhance: OFF';
  }

  toggleEnh() {
    this.enhEnabled = !this.enhEnabled;
    setButtonActive(this.ui.enhToggle, this.enhEnabled);
    if (this.ui.enhToggle) this.ui.enhToggle.text.text(this._enhToggleLabel());
    this.layer.batchDraw();
    this.onConfigChange && this.onConfigChange({ enh_enabled: this.enhEnabled });
  }

  setEnhDepth(value) {
    const n = Math.round(value);
    if (n === this.enhDepth) return;
    this.enhDepth = n;
    this.onConfigChange && this.onConfigChange({ enh_depth: n });
  }

  setEnhWindow(value) {
    // W must be odd (backend forces it); snap locally for immediate feedback.
    let n = Math.round(value);
    if (n % 2 === 0) n -= 1;
    if (n < 1) n = 1;
    if (this.ui.enhWinSlider) this.ui.enhWinSlider.setValue(n, { silent: true });
    if (n === this.enhWindow) return;
    this.enhWindow = n;
    this.onConfigChange && this.onConfigChange({ enh_sma_window: n });
  }

  _updateEnhFromConfig(config) {
    // Adopt server-authoritative bounds (SingleSourceForSharedConstants).
    const lim = config.limits;
    if (lim) {
      if (lim.enh_depth && this.ui.enhDepthSlider) {
        this.enhDepthLimit = { min: lim.enh_depth.min, max: lim.enh_depth.max };
        this.ui.enhDepthSlider.setRange(lim.enh_depth.min, lim.enh_depth.max);
      }
      if (lim.enh_sma_window && this.ui.enhWinSlider) {
        this.enhWindowLimit = { min: lim.enh_sma_window.min, max: lim.enh_sma_window.max };
        this.ui.enhWinSlider.setRange(lim.enh_sma_window.min, lim.enh_sma_window.max);
      }
    }
    if (typeof config.enh_enabled === 'boolean' && config.enh_enabled !== this.enhEnabled) {
      this.enhEnabled = config.enh_enabled;
      setButtonActive(this.ui.enhToggle, this.enhEnabled);
      if (this.ui.enhToggle) this.ui.enhToggle.text.text(this._enhToggleLabel());
      this.layer.batchDraw();
    }
    if (typeof config.enh_depth === 'number' && config.enh_depth !== this.enhDepth) {
      this.enhDepth = config.enh_depth;
      if (this.ui.enhDepthSlider) this.ui.enhDepthSlider.setValue(config.enh_depth, { silent: true });
    }
    if (typeof config.enh_sma_window === 'number' && config.enh_sma_window !== this.enhWindow) {
      this.enhWindow = config.enh_sma_window;
      if (this.ui.enhWinSlider) this.ui.enhWinSlider.setValue(config.enh_sma_window, { silent: true });
    }
  }

  setMode(mode) {
    const normalized = (mode || DEFAULT_MODE).toUpperCase();
    this.swMode = normalized;
    this.applyState();
    this.layer.batchDraw();
    this.onConfigChange && this.onConfigChange({ sw_mode: this.swMode });
  }

  applyState() {
    setButtonActive(this.ui.modeNormal, this.swMode === 'NORMAL');
    setButtonActive(this.ui.modePeak, this.swMode === 'PEAK');
    if (this.ui.modePeakHi) setButtonActive(this.ui.modePeakHi, this.swMode === 'PEAK_HI');
    setButtonActive(this.ui.modeAvg, this.swMode === 'AVG');
    setButtonActive(this.ui.modeAvgHi, this.swMode === 'AVG_HIRES');
  }

  updateFromConfig(config) {
    if (!config) return;
    if (config.sw_mode) {
      const normalized = (config.sw_mode || DEFAULT_MODE).toUpperCase();
      if (normalized !== this.swMode) {
        this.swMode = normalized;
        this.applyState();
        this.layer.batchDraw();
      }
    }
    this._updateEnhFromConfig(config);
  }
}
