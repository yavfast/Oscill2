import { formatUniversal, Quantity, FormatType } from './format.js';
import { AcquisitionControl } from './controls/acquisitionControl.js';
import { ProcessingControl } from './controls/processingControl.js';
import { FilterControl } from './controls/filterControl.js';
import { VerticalControl } from './controls/verticalControl.js';
import { HorizontalControl } from './controls/horizontalControl.js';
import { TriggerControl } from './controls/triggerControl.js';

const PAD_X = 12;
const MODE_GAP = 12;

export class ControlPanel {
  constructor(onConfigChange, onAcquisitionChange, onAutoAdjust) {
    this.onConfigChange = onConfigChange;
    this.onAcquisitionChange = onAcquisitionChange;
    this.onAutoAdjust = onAutoAdjust;

    this.container = null;
    this.stage = null;
    this.layer = null;
    this.controls = {};
    this.currentConfig = null;
    this._resizeObserver = null;
  }

  init() {
    console.log('[ControlPanel] init() - onAutoAdjust callback:', typeof this.onAutoAdjust);
    this.container = document.getElementById('control-panel');
    if (!this.container) return;

    this.container.innerHTML = '';
    const width = this.container.clientWidth || 320;
    const height = this.container.clientHeight || window.innerHeight - 60;

    this.stage = new Konva.Stage({ container: this.container, width, height });
    this.layer = new Konva.Layer();
    this.stage.add(this.layer);

    this._buildUI();
    this._layoutUI();

    this._resizeObserver = new ResizeObserver(() => this._resize());
    this._resizeObserver.observe(this.container);
  }

  _buildUI() {
    if (!this.layer || !this.stage) return;

    const colWidth = this.stage.width() - PAD_X * 2;
    let y = 8;

    this.controls.acquisition = new AcquisitionControl({
      layer: this.layer,
      onAcquisitionChange: this.onAcquisitionChange,
    });
    y = this.controls.acquisition.build({ padX: PAD_X, y, colWidth, gap: MODE_GAP });

    this.controls.processing = new ProcessingControl({
      layer: this.layer,
      onConfigChange: this.onConfigChange,
      modeGap: MODE_GAP,
    });
    y = this.controls.processing.build({ padX: PAD_X, y, colWidth });

    this.controls.filters = new FilterControl({
      layer: this.layer,
      onConfigChange: this.onConfigChange,
      modeGap: MODE_GAP,
    });
    y = this.controls.filters.build({ padX: PAD_X, y, colWidth });

    this.controls.vertical = new VerticalControl({
      layer: this.layer,
      onConfigChange: this.onConfigChange,
      formatVoltage: (value) => this.formatVoltage(value),
      onAutoVScale: () => {
        console.log('[ControlPanel] onAutoVScale callback triggered');
        this.onAutoAdjust && this.onAutoAdjust('v_div');
      },
      onAutoVOffset: () => {
        console.log('[ControlPanel] onAutoVOffset callback triggered');
        this.onAutoAdjust && this.onAutoAdjust('v_offset');
      },
    });
    y = this.controls.vertical.build({ padX: PAD_X, y, colWidth });

    this.controls.horizontal = new HorizontalControl({
      layer: this.layer,
      onConfigChange: this.onConfigChange,
      formatTime: (value) => this.formatTime(value),
      onAutoTScale: () => this.onAutoAdjust && this.onAutoAdjust('t_div'),
    });
    y = this.controls.horizontal.build({ padX: PAD_X, y, colWidth });

    this.controls.trigger = new TriggerControl({
      layer: this.layer,
      onConfigChange: this.onConfigChange,
      onAutoTrigger: () => this.onAutoAdjust && this.onAutoAdjust('trigger'),
    });
    y = this.controls.trigger.build({ padX: PAD_X, y, colWidth, modeGap: MODE_GAP });

    this.layer.draw();
  }

  _layoutUI() {
    if (!this.stage || !this.layer) return;
    const colWidth = this.stage.width() - PAD_X * 2;

    if (this.controls.vertical && typeof this.controls.vertical.layout === 'function') {
      this.controls.vertical.layout(colWidth);
    }
    if (this.controls.horizontal && typeof this.controls.horizontal.layout === 'function') {
      this.controls.horizontal.layout(colWidth);
    }
    if (this.controls.trigger && typeof this.controls.trigger.layout === 'function') {
      this.controls.trigger.layout(colWidth);
    }

    this.layer.batchDraw();
  }

  _resize() {
    if (!this.container || !this.stage) return;
    const w = this.container.clientWidth || 320;
    const h = this.container.clientHeight || window.innerHeight - 60;
    this.stage.size({ width: w, height: h });
    this._layoutUI();
  }

  setAcquisitionState(state) {
    if (this.controls.acquisition && typeof this.controls.acquisition.setAcquisitionState === 'function') {
      this.controls.acquisition.setAcquisitionState(state);
    }
  }

  setSingleEnabled(enabled) {
    if (this.controls.acquisition && typeof this.controls.acquisition.setSingleEnabled === 'function') {
      this.controls.acquisition.setSingleEnabled(enabled);
      if (this.layer) this.layer.batchDraw();
    }
  }

  setTriggerLevelChangeCallback(callback) {
    if (this.controls.trigger && typeof this.controls.trigger.setTriggerLevelChangeCallback === 'function') {
      this.controls.trigger.setTriggerLevelChangeCallback(callback);
    }
  }

  updateControls(config) {
    this.currentConfig = config || {};

    if (this.controls.vertical) {
      this.controls.vertical.updateFromConfig(this.currentConfig);
    }
    if (this.controls.horizontal) {
      this.controls.horizontal.updateFromConfig(this.currentConfig);
    }
    if (this.controls.processing) {
      this.controls.processing.updateFromConfig(this.currentConfig);
    }
    if (this.controls.filters) {
      this.controls.filters.updateFromConfig(this.currentConfig);
    }
    if (this.controls.trigger) {
      this.controls.trigger.updateFromConfig(this.currentConfig);
    }

    if (this.layer) this.layer.batchDraw();
  }

  formatVoltage(valueMV) {
    return formatUniversal(valueMV, 'm', 'auto', Quantity.V, FormatType.std);
  }

  formatTime(valueMS) {
    return formatUniversal(valueMS, 'm', 'auto', Quantity.s, FormatType.std);
  }

  isVOffsetDragging() {
    return this.controls.vertical?.ui?.vposSlider?.isDragging || false;
  }

  isTOffsetDragging() {
    return this.controls.horizontal?.ui?.hposSlider?.isDragging || false;
  }
}