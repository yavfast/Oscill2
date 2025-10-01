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
    this.peakArea = null;

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
    this.onVOffsetChange = null;
    this.onTOffsetChange = null;

    this.isDraggingTrigger = false;
    this.isDraggingVOffset = false;
    this.isDraggingTOffset = false;

    this.xRange = null; // [min,max] seconds
    this.yRange = null; // [min,max] volts
    this.pendingApply = null;

    // Throttling

    this.lastFrames = null;
    this.lastConfig = null;
    this.currentVOffsetRaw = 128;
    this.currentTOffsetRaw = 128;
    this.vAxisValueVolts = 0;
  this.tAxisPositionSeconds = 0;
  this.tAxisLabelSeconds = 0;

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

    this.peakArea = new Konva.Line({
      points: [],
      closed: true,
      strokeEnabled: false,
      listening: false,
      fill: 'rgba(255, 204, 0, 0.28)',
      visible: false,
    });

    this.waveLine = new Konva.Line({
      points: [],
      stroke: '#ffd700',
      strokeWidth: 2,
      lineCap: 'round',
      lineJoin: 'round',
    });
    this.waveLayer.add(this.peakArea);
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

  redrawWave() {
    if (!this.lastFrames || !this.lastConfig || !this.xRange || !this.yRange || !this.stage) return;
    const latestFrame = this.lastFrames[this.lastFrames.length - 1];
    const samples = latestFrame.samples || [];
    if (samples.length === 0) {
      this.waveLine.points([]);
      if (this.peakArea) {
        this.peakArea.points([]);
        this.peakArea.visible(false);
      }
      this.waveLayer.batchDraw();
      return;
    }
    const sampleBits = Math.max(1, latestFrame.sample_bits || 8);
    const peakMin = latestFrame.samples_peak_min || [];
    const peakMax = latestFrame.samples_peak_max || [];
    const totalTime = this.xRange[1] - this.xRange[0];
    const totalVoltage = this.yRange[1] - this.yRange[0];
    const inner = this.getInnerRect();
    const toX = (time) => {
      const [xmin, xmax] = this.xRange;
      const width = inner.width;
      return inner.left + ((time - xmin) / (xmax - xmin)) * width;
    };
    const toY = (volt) => {
      const [ymin, ymax] = this.yRange;
      const height = inner.height;
      return inner.top + (1 - (volt - ymin) / (ymax - ymin)) * height;
    };
    const points = [];
    for (let i = 0; i < samples.length; i++) {
      const time = (i / Math.max(1, samples.length)) * totalTime + this.xRange[0];
      const voltage = this.sampleToVoltage(samples[i], sampleBits, totalVoltage);
      points.push(toX(time), toY(voltage));
    }
    this._updatePeakArea(peakMin, peakMax, sampleBits, totalTime, totalVoltage, toX, toY);
    this.waveLine.points(points);
    this.waveLayer.batchDraw();

    const currentTriggerLevel = this.isDraggingTrigger ? this.tempTriggerLevel : this.triggerLevel;
    const trigYPix = this.triggerLevelToYPixel(currentTriggerLevel);
    this._positionTriggerGroup(trigYPix);
    this._positionCenterYGroup(toY(this.vAxisValueVolts));
    this._positionCenterXGroup(toX(this.tAxisPositionSeconds));
  }

  update(frames, config) {
    if (!frames || frames.length === 0) return;
    this.lastFrames = frames;
    this.lastConfig = config;
    if (config && config.cfg_id !== undefined) this.currentCfgId = config.cfg_id;

    const latestFrame = frames[frames.length - 1];
    const samples = latestFrame.samples || [];
    const peakMin = latestFrame.samples_peak_min || [];
    const peakMax = latestFrame.samples_peak_max || [];
    if (samples.length === 0) return;

    const sampleBits = Math.max(1, latestFrame.sample_bits || 8);

    if (config) {
      // Only update v_offset if not currently being dragged
      if (config.v_offset !== undefined && !this.isDraggingVOffset) {
        const entry = config.v_offset;
        let raw = this.currentVOffsetRaw;
        if (typeof entry === 'number') {
          raw = entry;
        } else if (entry && typeof entry === 'object') {
          if (typeof entry.v === 'number') raw = entry.v;
          else if (typeof entry.raw === 'number') raw = entry.raw;
        }
        this.currentVOffsetRaw = Math.max(0, Math.min(0xFF, Math.round(raw)));
      }
      // Only update t_offset if not currently being dragged
      if (config.t_offset !== undefined && !this.isDraggingTOffset) {
        const entry = config.t_offset;
        let raw = this.currentTOffsetRaw;
        if (typeof entry === 'number') {
          raw = entry;
        } else if (entry && typeof entry === 'object') {
          if (typeof entry.v === 'number') raw = entry.v;
          else if (typeof entry.raw === 'number') raw = entry.raw;
        }
        this.currentTOffsetRaw = Math.max(0, Math.min(0xFFFF, Math.round(raw)));
      }
    }

    const frameCfgId = latestFrame.cfg_id;
    if (
      frameCfgId !== undefined && frameCfgId !== null &&
      this.currentCfgId !== null && frameCfgId < this.currentCfgId
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
    
    // Розраховуємо vOffset в вольтах (як в OscillData.java)
    const vOffsetVolts = ((this.currentVOffsetRaw - 128) / 128) * (totalVoltage / 2);
    
    // Зміщуємо діапазон напруги на vOffset (як в OscillData.java: vMin = range.lower + vOffset)
    this.xRange = [-totalTime / 2, totalTime / 2];
    this.yRange = [-totalVoltage / 2 + vOffsetVolts, totalVoltage / 2 + vOffsetVolts];
    
    // Маркер "0" показує де знаходиться 0V - це завжди центр екрану мінус vOffset
    this.vAxisValueVolts = 0; // Маркер завжди на 0V
    
    // Розраховуємо позицію маркера t_offset на сигналі
    // t_offset визначає яка точка сигналу відповідає нульовому часу
    const nominalSamples = (config && typeof config.samples_total === 'number' && config.samples_total > 1)
      ? Math.round(config.samples_total)
      : Math.max(samples.length, 2);
    const denom = Math.max(1, nominalSamples - 1);
    const rawOffset = Number.isFinite(this.currentTOffsetRaw) ? this.currentTOffsetRaw : 0;
    const clampedTOffset = Math.max(0, Math.min(rawOffset, denom));
    const fraction = denom > 0 ? clampedTOffset / denom : 0;
    
    // Позиція маркера на сигналі: fraction * totalTime від початку (лівого краю)
    // Якщо fraction = 0, маркер зліва; якщо fraction = 1, маркер справа; якщо fraction = 0.5, маркер в центрі
    const tOffsetPositionSeconds = this.xRange[0] + fraction * totalTime;
    this.tAxisPositionSeconds = Number.isFinite(tOffsetPositionSeconds) ? tOffsetPositionSeconds : 0;
    this.tAxisLabelSeconds = 0; // Маркер завжди показує 0 секунд

    // Grid
    this.drawGrid();

    // Inner plot rect and mappers
    const inner = this.getInnerRect();
    const toX = (time) => {
      const [xmin, xmax] = this.xRange;
      const width = inner.width;
      return inner.left + ((time - xmin) / (xmax - xmin)) * width;
    };
    const toY = (volt) => {
      const [ymin, ymax] = this.yRange;
      const height = inner.height;
      return inner.top + (1 - (volt - ymin) / (ymax - ymin)) * height;
    };

    // Waveform
    const count = samples.length;
    const points = [];
    for (let i = 0; i < count; i++) {
      const time = (i / count) * totalTime - totalTime / 2;
      const voltage = this.sampleToVoltage(samples[i], sampleBits, totalVoltage, vOffsetVolts);
      points.push(toX(time), toY(voltage));
    }

    this._updatePeakArea(peakMin, peakMax, sampleBits, totalTime, totalVoltage, toX, toY, vOffsetVolts);
    this.waveLine.points(points);
    this.waveLayer.batchDraw();

    // Overlays - update positions only if not dragging
    const currentTriggerLevel = this.isDraggingTrigger ? this.tempTriggerLevel : this.triggerLevel;
    const trigYPix = this.triggerLevelToYPixel(currentTriggerLevel);
    this._positionTriggerGroup(trigYPix);
    
    // Don't reposition v_offset marker if user is dragging it
    if (!this.isDraggingVOffset) {
      this._positionCenterYGroup(toY(this.vAxisValueVolts));
    }
    
    // Don't reposition t_offset marker if user is dragging it
    if (!this.isDraggingTOffset) {
      this._positionCenterXGroup(toX(this.tAxisPositionSeconds));
    }
  }

  _updatePeakArea(peakMin, peakMax, sampleBits, totalTime, totalVoltage, toX, toY, vOffsetVolts) {
    if (!this.peakArea) return;
    const count = Math.min(peakMin.length || 0, peakMax.length || 0);
    if (!count) {
      this.peakArea.points([]);
      this.peakArea.visible(false);
      return;
    }

    const polygonPoints = [];
    const upper = [];
    const lower = [];
    const denom = Math.max(1, count);
    for (let i = 0; i < count; i++) {
      const time = (i / denom) * totalTime - totalTime / 2;
      const vMax = this.sampleToVoltage(peakMax[i], sampleBits, totalVoltage, vOffsetVolts);
      const vMin = this.sampleToVoltage(peakMin[i], sampleBits, totalVoltage, vOffsetVolts);
      const x = toX(time);
      const yMax = toY(vMax);
      const yMin = toY(vMin);
      upper.push(x, yMax);
      lower.push(x, yMin);
    }

    for (let i = 0; i < count; i++) {
      polygonPoints.push(upper[2 * i], upper[2 * i + 1]);
    }
    for (let i = count - 1; i >= 0; i--) {
      polygonPoints.push(lower[2 * i], lower[2 * i + 1]);
    }

    if (polygonPoints.length < 6) {
      this.peakArea.points([]);
      this.peakArea.visible(false);
      return;
    }

    this.peakArea.points(polygonPoints);
    this.peakArea.visible(true);
  }

  setTriggerLevel(level) {
    if (this.isDraggingTrigger) { this.pendingApply = level; return; }
    this.triggerLevel = level; this.tempTriggerLevel = level;
    // trigger_level - абсолютне значення 0-255, конвертуємо безпосередньо в Y-координату
    const yPix = this.triggerLevelToYPixel(level);
    this._positionTriggerGroup(yPix);
  }

  setTriggerLevelChangeCallback(callback) { this.onTriggerLevelChange = callback; }
  setVOffsetChangeCallback(callback) { this.onVOffsetChange = callback; }
  setTOffsetChangeCallback(callback) { this.onTOffsetChange = callback; }

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

  yPixelToVOffset(yPix) {
    // Конвертує Y-координату в значення v_offset (0-255)
    // В Python API: "raw 0..255 offsets" - просте нативне значення без прив'язки до вольтажу
    // 0 = top екрану, 255 = bottom екрану, 128 = center
    if (!this.stage) return 128;
    const r = this.getInnerRect();
    const clamped = Math.max(r.top, Math.min(r.top + r.height, yPix));
    
    // Позиція маркера на екрані (0 = top, 1 = bottom)
    const screenPosNormalized = (clamped - r.top) / Math.max(1, r.height);
    
    // Конвертуємо в 0-255
    // Але інвертуємо: top екрану (мінімальна Y-координата) = мінімальне значення offset = 0
    // bottom екрану (максимальна Y-координата) = максимальне значення offset = 255
    const raw = Math.round(screenPosNormalized * 255);
    
    console.log('yPixelToVOffset:', {
      yPix,
      clamped,
      heightRange: `${r.top} - ${r.top + r.height}`,
      screenPosNormalized,
      raw,
      currentVOffsetRaw: this.currentVOffsetRaw
    });
    
    return Math.max(0, Math.min(255, raw));
  }

  triggerLevelToYPixel(level) {
    // Конвертує trigger_level (0-255) в Y-координату на екрані
    // trigger_level - абсолютне значення, не залежить від діапазону напруги
    // 0 = низ екрану (bottom), 255 = верх екрану (top), 128 = center
    if (!this.stage) return 0;
    const r = this.getInnerRect();
    
    // ІНВЕРТОВАНА ЛОГІКА: level = 0 -> bottom, level = 255 -> top
    const normalized = level / 255;
    const yPix = r.top + (1 - normalized) * r.height;
    
    return yPix;
  }

  yPixelToTriggerLevel(yPix) {
    // Конвертує Y-координату в trigger_level (0-255)
    // ІНВЕРТОВАНА ЛОГІКА: top екрану -> 255, bottom екрану -> 0
    if (!this.stage) return 128;
    const r = this.getInnerRect();
    const clamped = Math.max(r.top, Math.min(r.top + r.height, yPix));
    
    const screenPosNormalized = (clamped - r.top) / Math.max(1, r.height);
    // Інвертуємо: top (screenPos=0) -> level=255, bottom (screenPos=1) -> level=0
    const raw = Math.round((1 - screenPosNormalized) * 255);
    
    return Math.max(0, Math.min(255, raw));
  }

  xPixelToTOffset(xPix) {
    // Конвертує X-координату маркера в значення t_offset
    // Маркер показує 0 секунд, тому позиція маркера визначає яка точка сигналу відповідає 0 секунд
    if (!this.xRange || !this.stage || !this.lastConfig) return 128;
    const [xmin, xmax] = this.xRange;
    const r = this.getInnerRect();
    const clamped = Math.max(r.left, Math.min(r.left + r.width, xPix));
    
    // Знаходимо час в цій точці (від -totalTime/2 до +totalTime/2)
    const timeAtMarker = xmin + ((clamped - r.left) / Math.max(1, r.width)) * (xmax - xmin);
    
    // Конвертуємо в raw значення t_offset
    const totalTime = xmax - xmin;
    const samples = this.lastFrames?.[this.lastFrames.length - 1]?.samples || [];
    const nominalSamples = (this.lastConfig && typeof this.lastConfig.samples_total === 'number' && this.lastConfig.samples_total > 1)
      ? Math.round(this.lastConfig.samples_total)
      : Math.max(samples.length, 2);
    const denom = Math.max(1, nominalSamples - 1);
    
    // Якщо маркер в центрі (timeAtMarker=0), то t_offset має бути в центрі діапазону
    // Якщо маркер зліва (timeAtMarker=-totalTime/2), то t_offset=0
    // Якщо маркер справа (timeAtMarker=+totalTime/2), то t_offset=denom
    const fraction = (timeAtMarker - xmin) / totalTime;
    const raw = Math.round(fraction * denom);
    
    return Math.max(0, Math.min(denom, raw));
  }

  handleResize() {
    const container = document.getElementById(this.containerId);
    if (!container || !this.stage) return;
    const width = Math.max(10, container.clientWidth);
    const height = Math.max(10, container.clientHeight);
    this.stage.size({ width, height });
    this.drawGrid();
    if (this.xRange && this.yRange) {
      const currentTriggerLevel = this.isDraggingTrigger ? this.tempTriggerLevel : this.triggerLevel;
      const trigYPix = this.triggerLevelToYPixel(currentTriggerLevel);
      this._positionTriggerGroup(trigYPix);
      const axisVolt = Number.isFinite(this.vAxisValueVolts) ? this.vAxisValueVolts : 0;
      const axisTime = Number.isFinite(this.tAxisPositionSeconds) ? this.tAxisPositionSeconds : 0;
      this._positionCenterYGroup(this.dataToYPixel(axisVolt));
      this._positionCenterXGroup(this.dataToXPixel(axisTime));
    }
    this.redrawWave();
  }

  redrawWave() {
    if (!this.lastFrames || !this.lastConfig || !this.xRange || !this.yRange || !this.stage) return;
    const latestFrame = this.lastFrames[this.lastFrames.length - 1];
    const samples = latestFrame.samples || [];
    if (samples.length === 0) {
      this.waveLine.points([]);
      if (this.peakArea) {
        this.peakArea.points([]);
        this.peakArea.visible(false);
      }
      this.waveLayer.batchDraw();
      return;
    }
    const sampleBits = Math.max(1, latestFrame.sample_bits || 8);
    const peakMin = latestFrame.samples_peak_min || [];
    const peakMax = latestFrame.samples_peak_max || [];
    const totalTime = this.xRange[1] - this.xRange[0];
    const totalVoltage = this.yRange[1] - this.yRange[0];
    
    // Розраховуємо vOffsetVolts для передачі в sampleToVoltage
    const vOffsetVolts = ((this.currentVOffsetRaw - 128) / 128) * (totalVoltage / 2);
    
    const inner = this.getInnerRect();
    const toX = (time) => {
      const [xmin, xmax] = this.xRange;
      const width = inner.width;
      return inner.left + ((time - xmin) / (xmax - xmin)) * width;
    };
    const toY = (volt) => {
      const [ymin, ymax] = this.yRange;
      const height = inner.height;
      return inner.top + (1 - (volt - ymin) / (ymax - ymin)) * height;
    };
    const points = [];
    const count = samples.length;
    for (let i = 0; i < count; i++) {
      const time = (i / count) * totalTime + this.xRange[0];
      const voltage = this.sampleToVoltage(samples[i], sampleBits, totalVoltage, vOffsetVolts);
      points.push(toX(time), toY(voltage));
    }
    this._updatePeakArea(peakMin, peakMax, sampleBits, totalTime, totalVoltage, toX, toY, vOffsetVolts);
    this.waveLine.points(points);
    this.waveLayer.batchDraw();

    // Don't reposition trigger marker if user is dragging it
    if (!this.isDraggingTrigger) {
      const trigYPix = this.triggerLevelToYPixel(this.triggerLevel);
      this._positionTriggerGroup(trigYPix);
    }
    
    // Don't reposition v_offset marker if user is dragging it
    if (!this.isDraggingVOffset) {
      this._positionCenterYGroup(toY(this.vAxisValueVolts));
    }
    
    // Don't reposition t_offset marker if user is dragging it
    if (!this.isDraggingTOffset) {
      this._positionCenterXGroup(toX(this.tAxisPositionSeconds));
    }
  }

  sampleToVoltage(sample, sampleBits, totalVoltage, vOffsetVolts = 0) {
    // Як в OscillData.java: vData[idx] = vMin + (data[idx] * vStep)
    // де vMin вже містить vOffset
    const bits = Math.max(1, sampleBits || 8);
    if (bits === 1) {
      const normalized = sample ? 1 : -1;
      return normalized * (totalVoltage / 2) + vOffsetVolts;
    }
    const maxValue = (2 ** bits) - 1;
    const vStep = totalVoltage / (maxValue + 1);
    const vMin = -totalVoltage / 2 + vOffsetVolts;
    return vMin + (sample * vStep);
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
      // Вісь часу (вертикальна біла лінія) показує позицію маркера t_offset
      // Це точка на сигналі, яка відповідає нульовому часу
      const xZero = this.dataToXPixel(this.tAxisPositionSeconds || 0);
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
      // Підписи показують час відносно позиції маркера t_offset (нульової осі)
      const tOffsetPos = this.tAxisPositionSeconds || 0;
      for (let i = 0; i <= this.totalDivsX; i++) {
        const frac = i / this.totalDivsX;
        const x = inner.left + frac * inner.width;
        const tAbsolute = xmin + frac * (xmax - xmin);
        // Час відносно нульової осі (маркера t_offset)
        const tRelative = tAbsolute - tOffsetPos;
        const txt = new Konva.Text({
          x: x,
          y: inner.top + inner.height + 4,
          text: formatSecondsAxis(tRelative),
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
    group.on('dragmove', () => { const yPix = group.y(); this.tempTriggerLevel = this.yPixelToTriggerLevel(yPix); });
    group.on('dragend', () => {
      this.isDraggingTrigger = false; 
      const yPix = group.y();
      const newTriggerLevel = this.yPixelToTriggerLevel(yPix);
      this.triggerLevel = newTriggerLevel;
      if (this.onTriggerLevelChange) this.onTriggerLevelChange(newTriggerLevel);
      if (this.pendingApply !== null) { this.setTriggerLevel(this.pendingApply); this.pendingApply = null; }
    });
    return group;
  }

  _positionTriggerGroup(yPix) { if (!this.triggerGroup) return; const r = this.getInnerRect(); this.triggerGroup.position({ x: r.left, y: yPix }); this.overlayLayer.batchDraw(); }

  _createCenterYGroup() {
    const group = new Konva.Group({ x: 0, y: 0, draggable: true });
    const inner = () => this.getInnerRect();
    const color = '#ffd700'; // Yellow color like trigger marker
    const markerX = 0; // Start from left side
    const line = new Konva.Line({ name: 'lineVOff', points: [0, 0, inner().width, 0], stroke: color, strokeWidth: 1, dash: [6, 4] });
    const tri = new Konva.RegularPolygon({ name: 'triCY', x: -3, y: 0, sides: 3, radius: 6, fill: color });
    tri.rotation(90); // Point to the left
    const rect = new Konva.Rect({ name: 'rectCY', x: -16, y: -5, width: 10, height: 10, fill: color, stroke: color, strokeWidth: 1 });
    const text = new Konva.Text({ name: 'textCY', x: -15, y: -4, text: '0', fontSize: 10, fill: '#000000', fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto, Arial' });
    group.add(line, tri, rect, text);
    group.on('draw', () => { const r = inner(); line.points([0, 0, r.width, 0]); });
    group.dragBoundFunc((pos) => { const r = inner(); const y = Math.max(r.top, Math.min(r.top + r.height, pos.y)); return { x: r.left, y }; });
    group.on('mouseenter', () => { this.stage.container().style.cursor = 'ns-resize'; });
    group.on('mouseleave', () => { this.stage.container().style.cursor = 'default'; });
    group.on('dragstart', () => { this.isDraggingVOffset = true; });
    group.on('dragmove', () => { /* User is dragging, update will be sent on dragend */ });
    group.on('dragend', () => {
      this.isDraggingVOffset = false;
      // Calculate new v_offset value and send to server
      const yPix = group.y();
      const newVOffset = this.yPixelToVOffset(yPix);
      if (this.onVOffsetChange) {
        this.onVOffsetChange(newVOffset);
      }
    });
    return group;
  }

  _positionCenterYGroup(yPix) { if (!this.centerYGroup) return; const r = this.getInnerRect(); this.centerYGroup.position({ x: r.left, y: yPix }); this.overlayLayer.batchDraw(); }



  _createCenterXGroup() {
    const group = new Konva.Group({ x: 0, y: 0, draggable: true });
    const inner = () => this.getInnerRect();
    const color = '#ffffff'; // White color
    const markerY = inner().height;
    const line = new Konva.Line({ name: 'lineTOff', points: [0, 0, 0, markerY], stroke: color, strokeWidth: 1, dash: [6, 4] });
    const tri = new Konva.RegularPolygon({ name: 'triCX', x: 0, y: markerY + 3, sides: 3, radius: 6, fill: color });
    tri.rotation(180);
    group.add(line, tri);
    group.on('draw', () => { const r = inner(); const my = r.height - 30; line.points([0, 0, 0, my]); tri.y(my); });
    group.dragBoundFunc((pos) => { const r = inner(); const x = Math.max(r.left, Math.min(r.left + r.width, pos.x)); return { x, y: r.top }; });
    group.on('mouseenter', () => { this.stage.container().style.cursor = 'ew-resize'; });
    group.on('mouseleave', () => { this.stage.container().style.cursor = 'default'; });
    group.on('dragstart', () => { this.isDraggingTOffset = true; });
    group.on('dragmove', () => { /* User is dragging, update will be sent on dragend */ });
    group.on('dragend', () => {
      this.isDraggingTOffset = false;
      // Calculate new t_offset value and send to server
      const xPix = group.x();
      const newTOffset = this.xPixelToTOffset(xPix);
      if (this.onTOffsetChange) {
        this.onTOffsetChange(newTOffset);
      }
    });
    return group;
  }

  _positionCenterXGroup(xPix) { if (!this.centerXGroup) return; const r = this.getInnerRect(); this.centerXGroup.position({ x: xPix, y: r.top }); this.overlayLayer.batchDraw(); }
}