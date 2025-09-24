export class ScopeView {
  constructor(containerId) {
    this.containerId = containerId;
    this.plot = null;
    this.triggerLevel = 128;
    this.tempTriggerLevel = 128; // Temporary trigger level during dragging
    this.vOffset = 0;
    this.tOffset = 0;
    this.currentCfgId = null; // Track current config ID
    this.onTriggerLevelChange = null; // Callback for trigger level changes
    this.isDraggingTrigger = false;
    this.triangleGeom = null; // Store geometry of trigger triangle for hit-test
    this.xRange = null;
    this.yRange = null;
    this.pendingApply = null; // queued apply while dragging
  }

  init() {
    const layout = {
      paper_bgcolor: '#1e1e1e',
      plot_bgcolor: '#1e1e1e',
      font: { color: '#ffffff' },
      // Disable box/region selection & zoom via drag
      dragmode: false,
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
    
    // Add mouse event listeners for trigger level dragging
    this.plot.addEventListener('mousedown', this.handleMouseDown.bind(this));
    this.plot.addEventListener('mousemove', this.handleMouseMove.bind(this));
    this.plot.addEventListener('mouseup', this.handleMouseUp.bind(this));
    this.plot.addEventListener('mouseleave', this.handleMouseUp.bind(this));
    this.plot.addEventListener('mousemove', this.handleHoverCursor.bind(this));
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
    const currentTriggerLevel = this.isDraggingTrigger ? this.tempTriggerLevel : this.triggerLevel;

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
        y0: this.triggerLevelToVoltage(currentTriggerLevel, totalVoltage),
        y1: this.triggerLevelToVoltage(currentTriggerLevel, totalVoltage),
        line: { color: '#ff0000', width: 1, dash: 'dash' }
      }, {
        // Smaller trigger triangle shifted a bit to the left (inside plot)
        type: 'path',
        // Geometry: left-pointing triangle
        // tipX moved left by 2% of total time axis; width reduced; height reduced
        path: (() => {
          const yLevel = this.triggerLevelToVoltage(currentTriggerLevel, totalVoltage);
            const tipX = totalTime / 2 + this.tOffset - totalTime * 0.02; // shift left
            const baseX = tipX + totalTime * 0.015; // narrower width
            const halfH = totalVoltage * 0.01; // smaller height
            // Save geometry for hit test
            this.triangleGeom = { tipX, baseX, yLevel, halfH };
            return `M ${tipX} ${yLevel} L ${baseX} ${yLevel - halfH} L ${baseX} ${yLevel + halfH} Z`;
        })(),
        fillcolor: '#00ff00',
        line: { color: '#00ff00', width: 1 }
      }]
    };

    Plotly.update(this.containerId, updateData, updateLayout);

    // Store axis ranges for coordinate transforms in hit-test
    this.xRange = updateLayout.xaxis.range.slice();
    this.yRange = updateLayout.yaxis.range.slice();
  }

  setTriggerLevel(level) {
    // If user is actively dragging, ignore external set (will apply after release)
    if (this.isDraggingTrigger) {
      this.pendingApply = level;
      return;
    }
    this.triggerLevel = level;
    this.tempTriggerLevel = level;
    this.redrawTriggerShape();
  }

  setVOffset(offset) {
    this.vOffset = offset;
  }

  setTOffset(offset) {
    this.tOffset = offset;
  }

  handleMouseDown(event) {
    const rect = this.plot.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    if (!this.triangleGeom || !this.xRange || !this.yRange) return;

    const { tipX, baseX, yLevel, halfH } = this.triangleGeom;
    const plotWidth = rect.width;
    const plotHeight = rect.height;

    // Convert pixel to data coordinates
    const xData = this.xRange[0] + (x / plotWidth) * (this.xRange[1] - this.xRange[0]);
    const yData = this.yRange[0] + (1 - (y / plotHeight)) * (this.yRange[1] - this.yRange[0]);

    // Bounding box + small padding
    const padX = (baseX - tipX) * 0.4;
    const padY = halfH * 0.6;
    const withinX = xData >= tipX - padX && xData <= baseX + padX;
    const withinY = yData >= (yLevel - halfH - padY) && yData <= (yLevel + halfH + padY);

    if (withinX && withinY) {
      this.isDraggingTrigger = true;
      this.tempTriggerLevel = this.triggerLevel; // Store current level
      event.preventDefault();
    }
  }

  handleMouseMove(event) {
    if (!this.isDraggingTrigger) return;
    if (!this.yRange) return;

    const rect = this.plot.getBoundingClientRect();
    const y = event.clientY - rect.top;
    const plotHeight = rect.height;

    // Convert pixel y to data y (voltage domain currently used in layout)
    const yData = this.yRange[0] + (1 - (y / plotHeight)) * (this.yRange[1] - this.yRange[0]);

    // Map voltage range (yRange) to 0..255 trigger scale
    const minY = this.yRange[0];
    const maxY = this.yRange[1];
    const clampedY = Math.max(minY, Math.min(maxY, yData));
    const ratio = (clampedY - minY) / (maxY - minY); // 0..1 from bottom to top
    const level = Math.round(ratio * 255);

    this.tempTriggerLevel = Math.max(0, Math.min(255, level));
    // Just force a redraw by calling update with empty frames but current config? Simpler: rely on next polling update.
    // We can optionally issue a lightweight Plotly.relayout to move shapes without data fetch.
    this.redrawTriggerShape();
    event.preventDefault();
  }

  handleHoverCursor(event) {
    if (this.isDraggingTrigger) {
      this.plot.style.cursor = 'ns-resize';
      return;
    }
    if (!this.triangleGeom || !this.xRange || !this.yRange) {
      this.plot.style.cursor = 'default';
      return;
    }
    const rect = this.plot.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const plotWidth = rect.width;
    const plotHeight = rect.height;
    const xData = this.xRange[0] + (x / plotWidth) * (this.xRange[1] - this.xRange[0]);
    const yData = this.yRange[0] + (1 - (y / plotHeight)) * (this.yRange[1] - this.yRange[0]);
    const { tipX, baseX, yLevel, halfH } = this.triangleGeom;
    const padX = (baseX - tipX) * 0.5;
    const padY = halfH * 0.8;
    const withinX = xData >= tipX - padX && xData <= baseX + padX;
    const withinY = yData >= (yLevel - halfH - padY) && yData <= (yLevel + halfH + padY);
    if (withinX && withinY) {
      this.plot.style.cursor = 'ns-resize';
    } else {
      this.plot.style.cursor = 'default';
    }
  }

  handleMouseUp(event) {
    if (this.isDraggingTrigger) {
      // Apply the trigger level change only when mouse is released
      this.triggerLevel = this.tempTriggerLevel;
      if (this.onTriggerLevelChange) {
        this.onTriggerLevelChange(this.triggerLevel);
      }
      this.isDraggingTrigger = false;
      // If while dragging we received an external update, apply it now (but do not send back to API)
      if (this.pendingApply !== null) {
        this.triggerLevel = this.pendingApply;
        this.tempTriggerLevel = this.pendingApply;
        this.pendingApply = null;
        this.redrawTriggerShape();
      }
    }
  }

  updateTriggerLevelFromMouse(yFraction) {
    // This method is no longer used - trigger changes are applied on mouse release
  }

  updateTriggerDisplay() {
    // This method is no longer used - visual updates happen in the main update method
  }

  redrawTriggerShape() {
    if (!this.plot || !this.triangleGeom || !this.xRange || !this.yRange) return;
    const shapes = this.plot.layout.shapes || [];
    if (shapes.length < 2) return;
    const totalTime = this.xRange[1] - this.xRange[0];
    const totalVoltage = this.yRange[1] - this.yRange[0];
    const currentTriggerLevel = this.isDraggingTrigger ? this.tempTriggerLevel : this.triggerLevel;
    const yLevel = this.triggerLevelToVoltage(currentTriggerLevel, totalVoltage);

    // Update line (shape 0)
    shapes[0].y0 = yLevel;
    shapes[0].y1 = yLevel;

    // Recompute triangle path with stored geometry base relationships
    const { tipX, baseX, halfH } = this.triangleGeom;
    shapes[1].path = `M ${tipX} ${yLevel} L ${baseX} ${yLevel - halfH} L ${baseX} ${yLevel + halfH} Z`;

    Plotly.relayout(this.plot, { shapes });
  }

  setTriggerLevelChangeCallback(callback) {
    this.onTriggerLevelChange = callback;
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