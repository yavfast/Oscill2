import { formatSecondsStd, formatUniversal, Quantity, FormatType } from './format.js';

export class StatusBar {
  constructor() {
    this.container = document.getElementById('status-canvas');
    const width = this.container?.clientWidth || window.innerWidth;
    const height = 40;
    this.stage = new Konva.Stage({ container: this.container, width, height });
    this.layer = new Konva.Layer();
    this.stage.add(this.layer);

    const fontFamily = 'system-ui, -apple-system, Segoe UI, Roboto, Arial';
    this.connCircle = new Konva.Circle({ x: 16, y: height / 2, radius: 6, fill: '#d33' });
    this.connText = new Konva.Text({ x: 28, y: height / 2 - 8, text: 'Disconnected', fontSize: 14, fill: '#fff', fontFamily });
    this.timeText = new Konva.Text({ x: 160, y: height / 2 - 8, text: '—/div', fontSize: 14, fill: '#ddd', fontFamily });
    this.voltText = new Konva.Text({ x: 300, y: height / 2 - 8, text: '—/div', fontSize: 14, fill: '#ddd', fontFamily });
    this.trigText = new Konva.Text({ x: 440, y: height / 2 - 8, text: '—', fontSize: 14, fill: '#ddd', fontFamily });
    this.layer.add(this.connCircle, this.connText, this.timeText, this.voltText, this.trigText);

    this._resizeObserver = new ResizeObserver(() => this._resize());
    if (this.container) this._resizeObserver.observe(this.container);
  }

  _resize() {
    const w = this.container.clientWidth || window.innerWidth;
    const h = 40;
    this.stage.size({ width: w, height: h });
    // Reposition Y centers
    const cy = h / 2;
    this.connCircle.y(cy);
    [this.connText, this.timeText, this.voltText, this.trigText].forEach(t => t.y(cy - 8));
    this.layer.batchDraw();
  }

  updateStatus(status, config) {
    const isConnected = (status && status.status === 'ok') || (status && status.status === 'error') || !!config;
    this.connCircle.fill(isConnected ? '#2ecc71' : '#d33');
    this.connText.text(isConnected ? 'Connected' : 'Disconnected');

    if (config) {
      // Time division
      if (config.t_div) {
        const tCurrentDim = config.t_div.u === 's' ? '_' : 'm';
        this.timeText.text(`${formatUniversal(config.t_div.v, tCurrentDim, 'auto', Quantity.s, FormatType.std)}/div`);
      }
      // Voltage division
      if (config.v_div) {
        const vCurrentDim = config.v_div.u === 'V' ? '_' : 'm';
        this.voltText.text(`${formatUniversal(config.v_div.v, vCurrentDim, 'auto', Quantity.V, FormatType.std)}/div`);
      }
      // Trigger
      const mode = config.trigger_mode?.v || '—';
      const slope = config.trigger_slope?.v || '';
      this.trigText.text(`${mode}${slope ? ', ' + slope : ''}`);
    }
    this.layer.batchDraw();
  }

  // formatting delegated to format.js
}