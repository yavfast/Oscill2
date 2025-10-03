import { createButton, createLabel, createSlider } from './uiHelpers.js';

const TDIV_VALUES_MS = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500];
const DEFAULT_INDEX = 5; // 5 ms
const HDIVS = 10;
const DEFAULT_SAMPLES_PER_DIV = 32;

export class HorizontalControl {
  constructor({ layer, onConfigChange, formatTime, onAutoTScale }) {
    this.layer = layer;
    this.onConfigChange = onConfigChange;
    this.formatTime = formatTime;
    this.onAutoTScale = onAutoTScale;

  this.currentTIndex = DEFAULT_INDEX;
  this.samplesPerDiv = DEFAULT_SAMPLES_PER_DIV;
  this.totalSamples = this.samplesPerDiv * HDIVS;
  this.tOffsetMax = Math.max(0, this.totalSamples - 1);
  this.tOffsetRaw = Math.min(128, this.tOffsetMax);

    this.ui = {};
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
      text: this.formatTime(TDIV_VALUES_MS[this.currentTIndex]),
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
    const nextIndex = Math.max(0, Math.min(TDIV_VALUES_MS.length - 1, this.currentTIndex + delta));
    this.currentTIndex = nextIndex;
    if (this.ui.tdivValue) {
      this.ui.tdivValue.text(this.formatTime(TDIV_VALUES_MS[this.currentTIndex]));
    }
    this.layer.batchDraw();
    this.onConfigChange && this.onConfigChange({ t_div: { v: TDIV_VALUES_MS[this.currentTIndex], u: 'ms' } });
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
      const idx = TDIV_VALUES_MS.indexOf(tValue);
      if (idx !== -1) this.currentTIndex = idx;
      if (this.ui.tdivValue) {
        this.ui.tdivValue.text(this.formatTime(TDIV_VALUES_MS[this.currentTIndex]));
      }
    }

    if (typeof config.samples_per_div === 'number') {
      this.samplesPerDiv = config.samples_per_div;
    }

    const reportedTotal = typeof config.samples_total === 'number'
      ? Math.max(0, Math.round(config.samples_total))
      : null;
    this.totalSamples = reportedTotal !== null ? reportedTotal : (this.samplesPerDiv * HDIVS);
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
