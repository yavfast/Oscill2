export class StatusBar {
  constructor() {
    this.connectionStatus = document.getElementById('connection-status');
    this.timeDiv = document.getElementById('time-div');
    this.voltsDiv = document.getElementById('volts-div');
    this.triggerMode = document.getElementById('trigger-mode');
  }

  updateStatus(status, config) {
    // Connection status - consider connected if status is ok OR if we have config data (frames are coming through)
    const isConnected = (status && status.status === 'ok') || (status && status.status === 'error') || !!config;
    this.connectionStatus.textContent = isConnected ? 'Connected' : 'Disconnected';
    this.connectionStatus.classList.toggle('connected', isConnected);

    // Core params
    if (config) {
      if (config.t_div) {
        this.timeDiv.textContent = this.formatTime(config.t_div.v) + '/div';
      }
      if (config.v_div) {
        this.voltsDiv.textContent = this.formatVoltage(config.v_div.v) + '/div';
      }
      if (config.trigger_mode && config.trigger_slope) {
        this.triggerMode.textContent = `${config.trigger_mode}, ${config.trigger_slope}`;
      }
    }
  }

  formatTime(s) {
    if (s >= 1) return `${s.toFixed(2)} s`;
    if (s >= 0.001) return `${(s * 1000).toFixed(0)} ms`;
    if (s >= 0.000001) return `${(s * 1000000).toFixed(0)} µs`;
    return `${(s * 1000000000).toFixed(0)} ns`;
  }

  formatVoltage(v) {
    if (v >= 1) return `${v.toFixed(2)} V`;
    return `${(v * 1000).toFixed(0)} mV`;
  }
}