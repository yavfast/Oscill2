import { createButton, createLabel, setButtonActive } from './uiHelpers.js';

const DEFAULT_MODE = 'NORMAL';

export class ProcessingControl {
  constructor({ layer, onConfigChange, modeGap = 12 }) {
    this.layer = layer;
    this.onConfigChange = onConfigChange;
    this.modeGap = modeGap;
    this.swMode = DEFAULT_MODE;
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
    return nextY;
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
    if (!config || !config.sw_mode) return;
    const normalized = (config.sw_mode || DEFAULT_MODE).toUpperCase();
    if (normalized !== this.swMode) {
      this.swMode = normalized;
      this.applyState();
      this.layer.batchDraw();
    }
  }
}
