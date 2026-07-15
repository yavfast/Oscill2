import { createButton, createLabel, createSlider } from './uiHelpers.js';

// [PL_AUDIT_WEB_06] Hardcoded lists kept ONLY as offline fallback defaults; the
// live values are fetched from GET /api/config/options during init.
const TDIV_VALUES_MS = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500];
const DEFAULT_INDEX = 5; // 5 ms
const HDIVS = 8; // [PL_AUDIT_WEB_08] device captures 8 horizontal divisions (H_DIVS=8)
const DEFAULT_SAMPLES_PER_DIV = 32;

export class HorizontalControl {
  constructor({ layer, onConfigChange, formatTime, onAutoTScale }) {
    this.layer = layer;
    this.onConfigChange = onConfigChange;
    this.formatTime = formatTime;
    this.onAutoTScale = onAutoTScale;

  // [PL_AUDIT_WEB_06] Instance copies so backend-provided options can override the fallback defaults.
  this.tdivValues = TDIV_VALUES_MS;
  this.hDivs = HDIVS; // [PL_AUDIT_WEB_08]
  this.currentTIndex = DEFAULT_INDEX;
  this.samplesPerDiv = DEFAULT_SAMPLES_PER_DIV;
  this.totalSamples = this.samplesPerDiv * this.hDivs;
  this.tOffsetMax = Math.max(0, this.totalSamples - 1);
  this.tOffsetRaw = Math.min(128, this.tOffsetMax);

    this.ui = {};
  }

  // [PL_AUDIT_WEB_06] Apply options fetched from GET /api/config/options (or leave fallback defaults if absent).
  applyConfigOptions(opts) {
    if (!opts) return;
    if (Array.isArray(opts.t_div_values_ms) && opts.t_div_values_ms.length > 0) {
      this.tdivValues = opts.t_div_values_ms;
      this.currentTIndex = Math.max(0, Math.min(this.tdivValues.length - 1, this.currentTIndex));
      if (this.ui.tdivValue) {
        this.ui.tdivValue.text(this.formatTime(this.tdivValues[this.currentTIndex]));
      }
    }
    if (typeof opts.h_divs === 'number' && opts.h_divs > 0) this.hDivs = opts.h_divs; // [PL_AUDIT_WEB_08]
    if (typeof opts.samples_per_div === 'number' && opts.samples_per_div > 0) this.samplesPerDiv = opts.samples_per_div;
    this.totalSamples = this.samplesPerDiv * this.hDivs;
    this.tOffsetMax = Math.max(0, this.totalSamples - 1);
    if (this.ui.hposSlider) {
      this.ui.hposSlider.setRange(0, this.tOffsetMax);
      const adjusted = this.ui.hposSlider.clamp(this.tOffsetRaw);
      this.tOffsetRaw = adjusted;
      this.ui.hposSlider.render(adjusted);
    }
    if (this.layer) this.layer.batchDraw();
  }

  build({ padX, y, colWidth }) {
    let nextY = y;
    this.ui.label = createLabel({ x: padX, y: nextY, text: 'Horizontal', fontSize: 16, color: '#ccc' });
    nextY += 22;

    this.ui.tdivMinus = createButton(this.layer, {
      x: padX,
      y: nextY,
      width: 36,
      height: 28,
      label: '−',
      onClick: () => this.changeTDiv(-1),
    });

    this.ui.tdivValue = createLabel({
      x: padX + 44,
      y: nextY + 6,
      text: this.formatTime(this.tdivValues[this.currentTIndex]), // [PL_AUDIT_WEB_06]
      fontSize: 14,
      color: '#fff',
    });

    this.ui.tdivPlus = createButton(this.layer, {
      x: padX + 180,
      y: nextY,
      width: 36,
      height: 28,
      label: '+',
      onClick: () => this.changeTDiv(1),
    });

    this.ui.tdivAuto = createButton(this.layer, {
      x: padX + 224,
      y: nextY,
      width: 48,
      height: 28,
      label: 'Auto',
      onClick: () => this.onAutoTScale && this.onAutoTScale(),
    });
    nextY += 36;

    this.ui.hposLabel = createLabel({ x: padX, y: nextY, text: 'Position' });
    this.ui.hposSlider = createSlider(this.layer, {
      x: padX + 80,
      y: nextY - 6,
      width: colWidth - 160,
      min: 0,
      max: this.tOffsetMax,
      value: this.tOffsetRaw,
      onChange: (val) => this.previewTPosition(val),
      onCommit: (val) => this.changeTPosition(val),
      format: (v) => `${Math.round(v)}`,
    });
    nextY += 46;

    this.layer.add(
      this.ui.label,
      this.ui.tdivMinus.group,
      this.ui.tdivValue,
      this.ui.tdivPlus.group,
      this.ui.tdivAuto.group,
      this.ui.hposLabel,
      this.ui.hposSlider.group,
    );
    return nextY;
  }

  changeTDiv(delta) {
    const nextIndex = Math.max(0, Math.min(this.tdivValues.length - 1, this.currentTIndex + delta)); // [PL_AUDIT_WEB_06]
    this.currentTIndex = nextIndex;
    if (this.ui.tdivValue) {
      this.ui.tdivValue.text(this.formatTime(this.tdivValues[this.currentTIndex]));
    }
    this.layer.batchDraw();
    this.onConfigChange && this.onConfigChange({ t_div: { v: this.tdivValues[this.currentTIndex], u: 'ms' } });
  }

  changeTPosition(value) {
    const slider = this.ui.hposSlider;
    const raw = Math.round(value);
    const clamped = slider ? slider.clamp(raw) : Math.max(0, raw);
    this.tOffsetRaw = clamped;
    if (slider) slider.render(clamped);
    this.onConfigChange && this.onConfigChange({ t_offset: this.tOffsetRaw });
    this.layer.batchDraw();
  }

  previewTPosition(value) {
    const slider = this.ui.hposSlider;
    const raw = Math.round(value);
    this.tOffsetRaw = slider ? slider.clamp(raw) : Math.max(0, raw);
  }

  layout(colWidth) {
    if (this.ui.hposSlider) {
      this.ui.hposSlider.setWidth(colWidth - 160);
    }
  }

  updateFromConfig(config) {
    if (!config) return;

    if (config.t_div) {
      const tValue = config.t_div.v;
      const idx = this.tdivValues.indexOf(tValue); // [PL_AUDIT_WEB_06]
      if (idx !== -1) this.currentTIndex = idx;
      if (this.ui.tdivValue) {
        this.ui.tdivValue.text(this.formatTime(this.tdivValues[this.currentTIndex]));
      }
    }

    // [PL_AUDIT_WEB_08] Prefer device truth for horizontal divisions from the frame config (default 8).
    if (typeof config.h_divs === 'number' && config.h_divs > 0) {
      this.hDivs = config.h_divs;
    }

    if (typeof config.samples_per_div === 'number') {
      this.samplesPerDiv = config.samples_per_div;
    }

    const reportedTotal = typeof config.samples_total === 'number'
      ? Math.max(0, Math.round(config.samples_total))
      : null;
    this.totalSamples = reportedTotal !== null ? reportedTotal : (this.samplesPerDiv * this.hDivs); // [PL_AUDIT_WEB_08]
    this.tOffsetMax = Math.max(0, this.totalSamples > 0 ? this.totalSamples - 1 : 0);
    if (this.ui.hposSlider) {
      this.ui.hposSlider.setRange(0, this.tOffsetMax);
      const adjusted = this.ui.hposSlider.clamp(this.tOffsetRaw);
      this.tOffsetRaw = adjusted;
      this.ui.hposSlider.render(adjusted);
    }

    const tOffsetEntry = config.t_offset;
    // Only update if slider is not being dragged
    if (!this.ui.hposSlider?.isDragging && (typeof tOffsetEntry === 'number' || (tOffsetEntry && typeof tOffsetEntry.v === 'number'))) {
      const raw = typeof tOffsetEntry === 'number' ? tOffsetEntry : tOffsetEntry.v;
      const slider = this.ui.hposSlider;
      const clamped = slider ? slider.clamp(raw) : Math.max(0, raw);
      this.tOffsetRaw = clamped;
      if (slider) slider.render(clamped);
    }
  }
}
