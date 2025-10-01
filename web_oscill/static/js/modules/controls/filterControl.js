import { createButton, createLabel, setButtonActive } from './uiHelpers.js';

export class FilterControl {
  constructor({ layer, onConfigChange, modeGap = 12 }) {
    this.layer = layer;
    this.onConfigChange = onConfigChange;
    this.modeGap = modeGap;
    this.filters = { high: false, low: false };
    this.ui = {};
  }

  build({ padX, y, colWidth }) {
    let nextY = y;
    this.ui.label = createLabel({ x: padX, y: nextY, text: 'Filters', fontSize: 16, color: '#ccc' });
    nextY += 22;

    const filterBtnW = (colWidth - this.modeGap) / 2;
    this.ui.filterHigh = createButton(this.layer, {
      x: padX,
      y: nextY,
      width: filterBtnW,
      height: 32,
      label: 'High 3MHz',
      onClick: () => this.toggleFilter('high'),
      active: this.filters.high,
    });
    this.ui.filterLow = createButton(this.layer, {
      x: padX + filterBtnW + this.modeGap,
      y: nextY,
      width: filterBtnW,
      height: 32,
      label: 'Low 3kHz',
      onClick: () => this.toggleFilter('low'),
      active: this.filters.low,
    });
    nextY += 40;

    this.layer.add(this.ui.label, this.ui.filterHigh.group, this.ui.filterLow.group);
    return nextY;
  }

  toggleFilter(name, explicitValue = null) {
    if (!(name in this.filters)) return;
    const nextValue = explicitValue === null ? !this.filters[name] : !!explicitValue;
    this.filters[name] = nextValue;
    this.applyState();
    this.layer.batchDraw();
    this.onConfigChange && this.onConfigChange({ filter_high: this.filters.high, filter_low: this.filters.low });
  }

  applyState() {
    setButtonActive(this.ui.filterHigh, !!this.filters.high);
    setButtonActive(this.ui.filterLow, !!this.filters.low);
  }

  updateFromConfig(config) {
    if (!config || !config.filters) return;
    const { high, low } = config.filters;
    const changedHigh = typeof high === 'boolean' && high !== this.filters.high;
    const changedLow = typeof low === 'boolean' && low !== this.filters.low;
    if (changedHigh || changedLow) {
      if (typeof high === 'boolean') this.filters.high = high;
      if (typeof low === 'boolean') this.filters.low = low;
      this.applyState();
      this.layer.batchDraw();
    }
  }
}
