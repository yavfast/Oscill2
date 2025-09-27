import { formatSecondsAxis, formatVoltsAxis } from './format.js';

export class ScopeView {
  constructor(containerId) {
    this.containerId = containerId;
    // Konva stage and layers
    this.stage = null;
    this.gridLayer = null;
    this.waveLayer = null;
    this.overlayLayer = null;
  this.axisLayer = null;

    // Shapes
    this.waveLine = null;
    this.triggerGroup = null; // line + triangle, vertical drag
    this.centerYGroup = null;  // cyan horizontal line + triangle, vertical drag
    this.centerXGroup = null;  // magenta vertical line + triangle, horizontal drag

    // State
    this.triggerLevel = 128;
    this.tempTriggerLevel = 128;
    this.currentCfgId = null;
    this.onTriggerLevelChange = null;

    this.isDraggingTrigger = false;

    this.xRange = null; // [min,max] seconds
    this.yRange = null; // [min,max] volts
    this.pendingApply = null;

    // Throttling

    this.lastFrames = null;
    this.lastConfig = null;

    this.totalDivsX = 10;
    this.totalDivsY = 8;

    // Plot margins for axis labels (pixels)
    this.margins = { left: 56, right: 16, top: 8, bottom: 24 };
  }

  init() {
    const container = document.getElementById(this.containerId);
    if (!container) return;
    const width = Math.max(10, container.clientWidth);
    const height = Math.max(10, container.clientHeight);
    this.stage = new Konva.Stage({ container: this.containerId, width, height });

  this.gridLayer = new Konva.Layer();
  this.axisLayer = new Konva.Layer();
  this.waveLayer = new Konva.Layer();
  this.overlayLayer = new Konva.Layer();
  // Order: grid (back), axis labels, waveform, overlays (top)
  this.stage.add(this.gridLayer, this.axisLayer, this.waveLayer, this.overlayLayer);

  this.waveLine = new Konva.Line({ points: [], stroke: '#ffd700', strokeWidth: 2, lineCap: 'round', lineJoin: 'round' });
    this.waveLayer.add(this.waveLine);

    this.triggerGroup = this._createTriggerGroup();
    this.overlayLayer.add(this.triggerGroup);
    this.centerYGroup = this._createCenterYGroup();
    this.overlayLayer.add(this.centerYGroup);
    this.centerXGroup = this._createCenterXGroup();
    this.overlayLayer.add(this.centerXGroup);

    // Bind and subscribe resize
    this.handleResize = this.handleResize.bind(this);
    window.addEventListener('resize', this.handleResize);

    this.stage.draw();
  }

  update(frames, config) {
    if (!frames || frames.length === 0) return;
    this.lastFrames = frames;
    this.lastConfig = config;
    if (config && config.cfg_id !== undefined) this.currentCfgId = config.cfg_id;

    const latestFrame = frames[frames.length - 1];
    const samples = latestFrame.samples || [];
    if (samples.length === 0) return;

    if (
      latestFrame.config && latestFrame.config.cfg_id !== undefined &&
      this.currentCfgId !== null && latestFrame.config.cfg_id < this.currentCfgId
    ) {
      return;
    }

    // Scale
    let vDiv = 0.2;
    if (config.v_div) {
      vDiv = config.v_div.u === 'mV' ? config.v_div.v / 1000 : config.v_div.v;
    }
    let tDiv = 0.005;
    if (config.t_div) {
      tDiv = config.t_div.u === 'ms' ? config.t_div.v / 1000 : config.t_div.v;
    }
    const totalTime = tDiv * this.totalDivsX;
    const totalVoltage = vDiv * this.totalDivsY;
    this.xRange = [-totalTime / 2, totalTime / 2];
    this.yRange = [-totalVoltage / 2, totalVoltage / 2];

    // Grid
    this.drawGrid();

    // Inner plot rect and mappers
    const inner = this.getInnerRect();
    const toX = (time) => {
      const [xmin, xmax] = this.xRange; const w = inner.width;
      return inner.left + ((time - xmin) / (xmax - xmin)) * w;
    };
    const toY = (volt) => {
      const [ymin, ymax] = this.yRange; const h = inner.height;
      return inner.top + (1 - (volt - ymin) / (ymax - ymin)) * h;
    };

    // Waveform
    const points = [];
    for (let i = 0; i < samples.length; i++) {
      const time = (i / samples.length) * totalTime - totalTime / 2; // do not apply tOffset visually
      const voltage = ((samples[i] - 128) / 128) * (totalVoltage / 2);
      points.push(toX(time), toY(voltage));
    }
    this.waveLine.points(points);
    this.waveLayer.batchDraw();

    // Overlays
    const currentTriggerLevel = this.isDraggingTrigger ? this.tempTriggerLevel : this.triggerLevel;
    const trigYVolt = this.triggerLevelToVoltage(currentTriggerLevel, totalVoltage);
    this._positionTriggerGroup(toY(trigYVolt));
    this._positionCenterYGroup(toY(0));
    this._positionCenterXGroup(toX(0));
  }

  setTriggerLevel(level) {
    if (this.isDraggingTrigger) { this.pendingApply = level; return; }
    this.triggerLevel = level; this.tempTriggerLevel = level;
    if (this.yRange) {
      const totalVoltage = this.yRange[1] - this.yRange[0];
      const yVolt = this.triggerLevelToVoltage(level, totalVoltage);
      this._positionTriggerGroup(this.dataToYPixel(yVolt));
    }
  }

  setTriggerLevelChangeCallback(callback) { this.onTriggerLevelChange = callback; }

  triggerLevelToVoltage(level, totalVoltage) { return ((level - 128) / 128) * (totalVoltage / 2); }
  // Formatting delegated to format.js
  

  // Helpers
  dataToXPixel(xVal) {
    if (!this.xRange || !this.stage) return 0;
    const inner = this.getInnerRect();
    const [xmin, xmax] = this.xRange; return inner.left + ((xVal - xmin) / (xmax - xmin)) * inner.width;
  }
  dataToYPixel(yVal) {
    if (!this.yRange || !this.stage) return 0;
    const inner = this.getInnerRect();
    const [ymin, ymax] = this.yRange; return inner.top + (1 - (yVal - ymin) / (ymax - ymin)) * inner.height;
  }
  yPixelToLevel(yPix) {
    if (!this.yRange || !this.stage) return 128;
    const [ymin, ymax] = this.yRange; const r = this.getInnerRect();
    const clamped = Math.max(r.top, Math.min(r.top + r.height, yPix));
    const yData = ymin + (1 - ((clamped - r.top) / Math.max(1, r.height))) * (ymax - ymin);
    const ratio = (yData - ymin) / (ymax - ymin);
    return Math.max(0, Math.min(255, Math.round(ratio * 255)));
  }

  handleResize() {
    const container = document.getElementById(this.containerId);
    if (!container || !this.stage) return;
    const width = Math.max(10, container.clientWidth);
    const height = Math.max(10, container.clientHeight);
    this.stage.size({ width, height });
    this.drawGrid();
    if (this.xRange && this.yRange) {
      const totalVoltage = this.yRange[1] - this.yRange[0];
      const trigYVolt = this.triggerLevelToVoltage(this.isDraggingTrigger ? this.tempTriggerLevel : this.triggerLevel, totalVoltage);
      this._positionTriggerGroup(this.dataToYPixel(trigYVolt));
      this._positionCenterYGroup(this.dataToYPixel(0));
      this._positionCenterXGroup(this.dataToXPixel(0));
    }
    this.redrawWave();
  }

  redrawWave() {
    if (!this.lastFrames || !this.lastConfig || !this.xRange || !this.yRange || !this.stage) return;
    const latestFrame = this.lastFrames[this.lastFrames.length - 1];
    const samples = latestFrame.samples || [];
    const totalTime = this.xRange[1] - this.xRange[0];
    const totalVoltage = this.yRange[1] - this.yRange[0];
    const inner = this.getInnerRect();
    const toX = (time) => { const [xmin, xmax] = this.xRange; const w = inner.width; return inner.left + ((time - xmin) / (xmax - xmin)) * w; };
    const toY = (volt) => { const [ymin, ymax] = this.yRange; const h = inner.height; return inner.top + (1 - (volt - ymin) / (ymax - ymin)) * h; };
    const points = [];
    for (let i = 0; i < samples.length; i++) {
      const time = (i / samples.length) * totalTime + this.xRange[0];
      const voltage = ((samples[i] - 128) / 128) * (totalVoltage / 2);
      points.push(toX(time), toY(voltage));
    }
    this.waveLine.points(points);
    this.waveLayer.batchDraw();
  }

  drawGrid() {
    if (!this.gridLayer || !this.stage) return;
    this.gridLayer.destroyChildren();
    if (this.axisLayer) this.axisLayer.destroyChildren();
    const w = this.stage.width();
    const h = this.stage.height();
    const majorColor = '#666666';
    const minorColor = '#333333';
    const zeroColor = '#cccccc';
    const bg = new Konva.Rect({ x: 0, y: 0, width: w, height: h, fill: '#1e1e1e' });
    this.gridLayer.add(bg);

    const inner = this.getInnerRect();
    // Plot background
    this.gridLayer.add(new Konva.Rect({ x: inner.left, y: inner.top, width: inner.width, height: inner.height, fill: '#1a1a1a' }));

    // Minor grid (5 subdivisions per major)
    const minorX = this.totalDivsX * 5;
    const minorY = this.totalDivsY * 5;
    for (let i = 0; i <= minorX; i++) {
      const x = inner.left + (i / minorX) * inner.width;
      this.gridLayer.add(new Konva.Line({ points: [x, inner.top, x, inner.top + inner.height], stroke: minorColor, strokeWidth: 0.5 }));
    }
    for (let j = 0; j <= minorY; j++) {
      const y = inner.top + (j / minorY) * inner.height;
      this.gridLayer.add(new Konva.Line({ points: [inner.left, y, inner.left + inner.width, y], stroke: minorColor, strokeWidth: 0.5 }));
    }
    // Major grid
    for (let i = 0; i <= this.totalDivsX; i++) {
      const x = inner.left + (i / this.totalDivsX) * inner.width;
      this.gridLayer.add(new Konva.Line({ points: [x, inner.top, x, inner.top + inner.height], stroke: majorColor, strokeWidth: 1 }));
    }
    for (let j = 0; j <= this.totalDivsY; j++) {
      const y = inner.top + (j / this.totalDivsY) * inner.height;
      this.gridLayer.add(new Konva.Line({ points: [inner.left, y, inner.left + inner.width, y], stroke: majorColor, strokeWidth: 1 }));
    }
    // Zero axes
    if (this.xRange && this.yRange) {
      const yZero = this.dataToYPixel(0);
      const xZero = this.dataToXPixel(0);
      this.gridLayer.add(new Konva.Line({ points: [inner.left, yZero, inner.left + inner.width, yZero], stroke: zeroColor, strokeWidth: 2 }));
      this.gridLayer.add(new Konva.Line({ points: [xZero, inner.top, xZero, inner.top + inner.height], stroke: zeroColor, strokeWidth: 2 }));
    }
    this.gridLayer.batchDraw();

    // Axis tick labels (time X-axis at bottom, voltage Y-axis at left)
    if (this.axisLayer && this.xRange && this.yRange) {
      const [xmin, xmax] = this.xRange;
      const [ymin, ymax] = this.yRange;
      const fontFamily = 'system-ui, -apple-system, Segoe UI, Roboto, Arial';
      const labelColor = '#aaaaaa';

      // X labels at major divisions
      for (let i = 0; i <= this.totalDivsX; i++) {
        const frac = i / this.totalDivsX;
        const x = inner.left + frac * inner.width;
        const t = xmin + frac * (xmax - xmin);
        const txt = new Konva.Text({
          x: x,
          y: inner.top + inner.height + 4,
          text: formatSecondsAxis(t),
          fontSize: 10,
          fill: labelColor,
          fontFamily,
          align: 'center',
        });
        // center horizontally
        txt.offsetX(txt.width() / 2);
        this.axisLayer.add(txt);
      }

      // Y labels at major divisions (right-aligned to the left edge of inner plot)
      for (let j = 0; j <= this.totalDivsY; j++) {
        const frac = j / this.totalDivsY;
        const y = inner.top + frac * inner.height;
        const v = ymax - frac * (ymax - ymin);
        const txt = new Konva.Text({
          x: inner.left - 4, // small gap from plot area
          y: y - 6,
          text: formatVoltsAxis(v),
          fontSize: 10,
          fill: labelColor,
          fontFamily,
        });
        // Align the right edge of text to the left edge of the plot
        txt.offsetX(txt.width());
        this.axisLayer.add(txt);
      }
      this.axisLayer.batchDraw();
    }
  }

  getInnerRect() {
    const w = this.stage ? this.stage.width() : 0;
    const h = this.stage ? this.stage.height() : 0;
    const m = this.margins;
    const left = m.left;
    const top = m.top;
    const width = Math.max(0, w - m.left - m.right);
    const height = Math.max(0, h - m.top - m.bottom);
    return { left, top, width, height };
  }

  _createTriggerGroup() {
    const group = new Konva.Group({ x: 0, y: 0, draggable: true });
    const inner = () => this.getInnerRect();
    const markerX = inner().width;
    const line = new Konva.Line({ name: 'lineTrig', points: [0, 0, markerX, 0], stroke: '#ff0000', strokeWidth: 1, dash: [6, 4] });
    const tri = new Konva.RegularPolygon({ name: 'triTrig', x: markerX + 3, y: 0, sides: 3, radius: 6, fill: '#ff0000' });
    tri.rotation(270); 
    const rect = new Konva.Rect({ name: 'rectTrig', x: markerX + 6, y: -5, width: 10, height: 10, fill: '#ff0000', stroke: '#ff0000', strokeWidth: 1 });
    const text = new Konva.Text({ name: 'textTrig', x: markerX + 7, y: -4, text: 'T', fontSize: 10, fill: '#ffffff', fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto, Arial' });
    group.add(line, tri, rect, text);
    group.on('draw', () => { const r = inner(); const mx = r.width - 30; line.points([0, 0, mx, 0]); tri.x(mx); rect.x(mx + 6); text.x(mx + 8); });
    group.dragBoundFunc((pos) => { const r = inner(); const y = Math.max(r.top, Math.min(r.top + r.height, pos.y)); return { x: r.left, y }; });
    group.on('mouseenter', () => { this.stage.container().style.cursor = 'ns-resize'; });
    group.on('mouseleave', () => { this.stage.container().style.cursor = 'default'; });
    group.on('dragstart', () => { this.isDraggingTrigger = true; this.tempTriggerLevel = this.triggerLevel; });
    group.on('dragmove', () => { const yPix = group.y(); this.tempTriggerLevel = this.yPixelToLevel(yPix); });
    group.on('dragend', () => {
      this.isDraggingTrigger = false; this.triggerLevel = this.tempTriggerLevel;
      if (this.onTriggerLevelChange) this.onTriggerLevelChange(this.triggerLevel);
      if (this.pendingApply !== null) { this.setTriggerLevel(this.pendingApply); this.pendingApply = null; }
    });
    return group;
  }

  _positionTriggerGroup(yPix) { if (!this.triggerGroup) return; const r = this.getInnerRect(); this.triggerGroup.position({ x: r.left, y: yPix }); this.overlayLayer.batchDraw(); }

  _createCenterYGroup() {
    const group = new Konva.Group({ x: 0, y: 0 });
    const inner = () => this.getInnerRect();
    const line = new Konva.Line({ name: 'lineCY', points: [0, 0, inner().width, 0], stroke: '#00bcd4', strokeWidth: 1, dash: [4, 4] });
    const tri = new Konva.RegularPolygon({ name: 'triCY', x: inner().width - Math.max(8, inner().width * 0.02), y: 0, sides: 3, radius: Math.max(5, inner().height * 0.011), fill: '#00bcd4' });
    tri.rotation(90);
    group.add(line, tri);
    group.on('draw', () => { const r = inner(); line.points([0, 0, r.width, 0]); tri.x(r.width - Math.max(8, r.width * 0.02)); tri.radius(Math.max(5, r.height * 0.011)); });
    return group;
  }

  _positionCenterYGroup(yPix) { if (!this.centerYGroup) return; const r = this.getInnerRect(); this.centerYGroup.position({ x: r.left, y: yPix }); this.overlayLayer.batchDraw(); }

  _createCenterXGroup() {
    const group = new Konva.Group({ x: 0, y: 0 });
    const inner = () => this.getInnerRect();
    const line = new Konva.Line({ name: 'lineCX', points: [0, 0, 0, inner().height], stroke: '#e91e63', strokeWidth: 1, dash: [4, 4] });
    const tri = new Konva.RegularPolygon({ name: 'triCX', x: 0, y: Math.max(10, inner().height * 0.05), sides: 3, radius: Math.max(5, inner().height * 0.011), fill: '#e91e63' });
    tri.rotation(180);
    group.add(line, tri);
    group.on('draw', () => { const r = inner(); line.points([0, 0, 0, r.height]); tri.y(Math.max(10, r.height * 0.05)); tri.radius(Math.max(5, r.height * 0.011)); });
    return group;
  }

  _positionCenterXGroup(xPix) { if (!this.centerXGroup) return; const r = this.getInnerRect(); this.centerXGroup.position({ x: xPix, y: r.top }); this.overlayLayer.batchDraw(); }
}