import { formatValueWithUnit } from './format.js';

export class MeasurementPanel {
  constructor() {
    this.container = document.getElementById('measurement-panel');
    this.stage = new Konva.Stage({
      container: this.container,
      width: this.container.clientWidth || 600,
      height: this.container.clientHeight || 64,
    });
    this.layer = new Konva.Layer();
    this.stage.add(this.layer);

    // Define measurement fields and create text nodes
    this.fields = [
      { key: 'freq', label: 'Freq' },
      { key: 'period', label: 'Period' },
      { key: 'v_pp', label: 'Vpp' },
      { key: 'v_max', label: 'Vmax' },
      { key: 'v_min', label: 'Vmin' },
      { key: 'v_avg', label: 'Vavg' },
    ];

    this.items = this.fields.map(() => ({ labelText: null, valueText: null }));
    this._createTexts();
    this._layout();

    // Observe container resize to keep Konva stage in sync
    this._resizeObserver = new ResizeObserver(() => this._resize());
    this._resizeObserver.observe(this.container);
  }

  _createTexts() {
    const fontFamily = 'system-ui, -apple-system, Segoe UI, Roboto, Arial';
    this.fields.forEach((f, i) => {
      const label = new Konva.Text({
        text: f.label,
        fontSize: 12,
        fill: '#bbb',
        fontFamily,
        align: 'center',
      });
      const value = new Konva.Text({
        text: '-',
        fontSize: 16,
        fill: '#fff',
        fontStyle: 'bold',
        fontFamily,
        align: 'center',
      });
      this.items[i].labelText = label;
      this.items[i].valueText = value;
      this.layer.add(label);
      this.layer.add(value);
    });
    this.layer.draw();
  }

  _layout() {
    const paddingX = 8;
    const colCount = this.items.length;
    const w = this.stage.width();
    const h = this.stage.height();
    const colW = Math.max(60, (w - paddingX * 2) / colCount);
    const labelY = Math.max(2, h * 0.18);
    const valueY = Math.min(h - 4, h * 0.56);

    this.items.forEach((item, idx) => {
      const x = paddingX + idx * colW + colW / 2;
      item.labelText.position({ x, y: labelY });
      item.labelText.offsetX(item.labelText.width() / 2);
      item.valueText.position({ x, y: valueY });
      item.valueText.offsetX(item.valueText.width() / 2);
    });
    this.layer.batchDraw();
  }

  _resize() {
    const w = this.container.clientWidth || 600;
    const h = this.container.clientHeight || 64;
    if (this.stage.width() !== w || this.stage.height() !== h) {
      this.stage.size({ width: w, height: h });
      this._layout();
    }
  }

  displayMeasurements(measurements) {
    if (!measurements) {
      this.clearMeasurements();
      return;
    }
    this.fields.forEach((f, i) => {
      const m = measurements[f.key];
      const txt = m ? formatValueWithUnit(m) : '-';
      this.items[i].valueText.text(txt);
    });
    this._layout();
  }

  clearMeasurements() {
    this.items.forEach((it) => it.valueText.text('-'));
    this._layout();
  }

  // formatting delegated to format.js
}