export class ScopeView {
  constructor(containerId) {
    this.containerId = containerId;
    this.plot = null;
    this.triggerLevel = 128;
    this.vOffset = 0;
    this.tOffset = 0;
    this.currentCfgId = null; // Track current config ID
  }

  init() {
    const layout = {
      paper_bgcolor: '#1e1e1e',
      plot_bgcolor: '#1e1e1e',
      font: { color: '#ffffff' },
      xaxis: {
        gridcolor: '#666666',
        linecolor: '#666666',
        linewidth: 1,
        tickcolor: '#666666',
        tickfont: { color: '#ffffff' },
        range: [-5, 5],
        autorange: false,
        dtick: 1.0,
        tickvals: [-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5],
        ticktext: ['-5', '-4', '-3', '-2', '-1', '0', '1', '2', '3', '4', '5'],
        showgrid: true,
        gridwidth: 1,
        zeroline: true,
        zerolinecolor: '#cccccc',
        zerolinewidth: 3,
        minor: {
          showgrid: true,
          gridcolor: '#333333',
          gridwidth: 0.5,
          dtick: 0.2
        },
        nticks: 50
      },
      yaxis: {
        gridcolor: '#666666',
        linecolor: '#666666',
        linewidth: 1,
        tickcolor: '#666666',
        tickfont: { color: '#ffffff' },
        range: [-4, 4],
        autorange: false,
        dtick: 1.0,
        tickvals: [-4, -3, -2, -1, 0, 1, 2, 3, 4],
        ticktext: ['-4', '-3', '-2', '-1', '0', '1', '2', '3', '4'],
        showgrid: true,
        gridwidth: 1,
        zeroline: true,
        zerolinecolor: '#cccccc',
        zerolinewidth: 3,
        minor: {
          showgrid: true,
          gridcolor: '#333333',
          gridwidth: 0.5,
          dtick: 0.5
        },
        nticks: 40
      },
      margin: { l: 50, r: 20, t: 20, b: 40 },
      shapes: [],
      showlegend: false
    };

    const data = [{
      x: [],
      y: [],
      type: 'scatter',
      mode: 'lines',
      line: { color: '#00ff00', width: 2 }
    }];

    const config = {
      responsive: true,
      displayModeBar: false,
      displaylogo: false,
      modeBarButtonsToRemove: ['zoom2d', 'pan2d', 'select2d', 'lasso2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'resetScale2d', 'hoverClosestCartesian', 'hoverCompareCartesian', 'toggleSpikelines'],
      scrollZoom: false,
      doubleClick: false,
      staticPlot: false
    };

    Plotly.newPlot(this.containerId, data, layout, config);
    this.plot = document.getElementById(this.containerId);
  }

  update(frames, config) {
    if (!frames || frames.length === 0) return;

    // Update current config ID
    if (config && config.cfg_id !== undefined) {
      this.currentCfgId = config.cfg_id;
    }

    const latestFrame = frames[frames.length - 1];
    const samples = latestFrame.samples || [];
    if (samples.length === 0) return;

    // Skip frames with old config
    if (latestFrame.config && latestFrame.config.cfg_id !== undefined && 
        this.currentCfgId !== null && latestFrame.config.cfg_id < this.currentCfgId) {
      return; // Skip old config frames
    }

    // Assuming samples are 0-255, convert to voltage
    const vDiv = config.v_div ? config.v_div.v / 1000 : 0.2; // default 200mV
    const tDiv = config.t_div ? config.t_div.v : 0.005; // default 5ms
    const samplesPerDiv = config.samples_per_div || 32;

    const x = [];
    const y = [];
    const totalDivsX = 10;
    const totalDivsY = 8;
    const totalTime = tDiv * totalDivsX;
    const totalVoltage = vDiv * totalDivsY;

    for (let i = 0; i < samples.length; i++) {
      const time = (i / samples.length) * totalTime - totalTime / 2 + this.tOffset;
      const voltage = ((samples[i] - 128) / 128) * (totalVoltage / 2) + this.vOffset;
      x.push(time);
      y.push(voltage);
    }

    const updateData = {
      x: [x],
      y: [y]
    };

    const updateLayout = {
      xaxis: {
        title: `Time (${this.formatTime(tDiv)}/div)`,
        range: [-totalTime / 2 + this.tOffset, totalTime / 2 + this.tOffset],
        showgrid: true,
        gridcolor: '#666666',
        gridwidth: 1,
        linecolor: '#666666',
        linewidth: 1,
        tickcolor: '#666666',
        zeroline: true,
        zerolinecolor: '#cccccc',
        zerolinewidth: 3,
        dtick: totalTime / 10, // 10 divisions
        minor: {
          showgrid: true,
          gridcolor: '#333333',
          gridwidth: 0.5,
          dtick: totalTime / 50 // 5 minor divisions per major
        }
      },
      yaxis: {
        title: `Voltage (${this.formatVoltage(vDiv)}/div)`,
        range: [-totalVoltage / 2 + this.vOffset, totalVoltage / 2 + this.vOffset],
        showgrid: true,
        gridcolor: '#666666',
        gridwidth: 1,
        linecolor: '#666666',
        linewidth: 1,
        tickcolor: '#666666',
        zeroline: true,
        zerolinecolor: '#cccccc',
        zerolinewidth: 3,
        dtick: totalVoltage / 8, // 8 divisions
        minor: {
          showgrid: true,
          gridcolor: '#333333',
          gridwidth: 0.5,
          dtick: totalVoltage / 40 // 5 minor divisions per major
        }
      },
      shapes: [{
        type: 'line',
        x0: -totalTime / 2 + this.tOffset,
        x1: totalTime / 2 + this.tOffset,
        y0: this.triggerLevelToVoltage(this.triggerLevel, totalVoltage),
        y1: this.triggerLevelToVoltage(this.triggerLevel, totalVoltage),
        line: { color: '#ff0000', width: 2, dash: 'dash' }
      }]
    };

    Plotly.update(this.containerId, updateData, updateLayout);
  }

  setTriggerLevel(level) {
    this.triggerLevel = level;
  }

  setVOffset(offset) {
    this.vOffset = offset;
  }

  setTOffset(offset) {
    this.tOffset = offset;
  }

  triggerLevelToVoltage(level, totalVoltage) {
    return ((level - 128) / 128) * (totalVoltage / 2);
  }

  formatTime(seconds) {
    if (seconds >= 1) return `${seconds.toFixed(2)} s`;
    if (seconds >= 0.001) return `${(seconds * 1000).toFixed(0)} ms`;
    if (seconds >= 0.000001) return `${(seconds * 1000000).toFixed(0)} µs`;
    return `${(seconds * 1000000000).toFixed(0)} ns`;
  }

  formatVoltage(volts) {
    if (volts >= 1) return `${volts.toFixed(2)} V`;
    return `${(volts * 1000).toFixed(0)} mV`;
  }
}