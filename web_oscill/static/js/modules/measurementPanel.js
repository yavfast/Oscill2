export class MeasurementPanel {
  constructor() {
    this.freq = document.getElementById('freq');
    this.period = document.getElementById('period');
    this.vpp = document.getElementById('vpp');
    this.vmax = document.getElementById('vmax');
    this.vmin = document.getElementById('vmin');
    this.vavg = document.getElementById('vavg');
  }

  displayMeasurements(measurements) {
    if (!measurements) {
      this.clearMeasurements();
      return;
    }

    this.freq.textContent = measurements.freq ? this.formatValue(measurements.freq) : '-';
    this.period.textContent = measurements.period ? this.formatValue(measurements.period) : '-';
    this.vpp.textContent = measurements.v_pp ? this.formatValue(measurements.v_pp) : '-';
    this.vmax.textContent = measurements.v_max ? this.formatValue(measurements.v_max) : '-';
    this.vmin.textContent = measurements.v_min ? this.formatValue(measurements.v_min) : '-';
    this.vavg.textContent = measurements.v_avg ? this.formatValue(measurements.v_avg) : '-';
  }

  clearMeasurements() {
    this.freq.textContent = '-';
    this.period.textContent = '-';
    this.vpp.textContent = '-';
    this.vmax.textContent = '-';
    this.vmin.textContent = '-';
    this.vavg.textContent = '-';
  }

  formatValue(valueObj) {
    const { v, u } = valueObj;
    if (u === 'Hz') {
      if (v >= 1000000) return `${(v / 1000000).toFixed(2)} MHz`;
      if (v >= 1000) return `${(v / 1000).toFixed(2)} kHz`;
      return `${v.toFixed(2)} Hz`;
    }
    if (u === 's') {
      if (v >= 1) return `${v.toFixed(2)} s`;
      if (v >= 0.001) return `${(v * 1000).toFixed(2)} ms`;
      if (v >= 0.000001) return `${(v * 1000000).toFixed(2)} µs`;
      return `${(v * 1000000000).toFixed(2)} ns`;
    }
    if (u === 'V') {
      if (Math.abs(v) >= 1) return `${v.toFixed(2)} V`;
      return `${(v * 1000).toFixed(2)} mV`;
    }
    return `${v.toFixed(2)} ${u}`;
  }
}