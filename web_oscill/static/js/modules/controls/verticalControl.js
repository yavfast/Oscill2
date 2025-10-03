import { createButton, createLabel, createSlider, setButtonActive } from './uiHelpers.js';

const VDIV_VALUES_MV = [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000];
const VPOS_MIN = 0;
const VPOS_MAX = 255;

export class VerticalControl {
  constructor({ layer, onConfigChange, formatVoltage, onAutoVScale, onAutoVOffset }) {
    this.layer = layer;
    this.onConfigChange = onConfigChange;
    this.formatVoltage = formatVoltage;
    this.onAutoVScale = onAutoVScale;
    this.onAutoVOffset = onAutoVOffset;

    this.currentVIndex = 3; // 200 mV
    this.currentVDivMV = VDIV_VALUES_MV[this.currentVIndex];
    this.vOffsetRaw = 128;
    this.coupling = 'DC';

    this.ui = {};
  }

  build({ padX, y, colWidth }) {
    let nextY = y;
    this.ui.label = createLabel({ x: padX, y: nextY, text: 'Vertical', fontSize: 16, color: '#ccc' });
    nextY += 22;

    this.ui.vdivMinus = createButton(this.layer, {
      x: padX,
      y: nextY,
      width: 36,
      height: 28,
      label: '−',
      onClick: () => this.changeVDiv(-1),
    });

    this.ui.vdivValue = createLabel({
      x: padX + 44,
      y: nextY + 6,
      text: this.formatVoltage(this.currentVDivMV),
      fontSize: 14,
      color: '#fff',
    });

    this.ui.vdivPlus = createButton(this.layer, {
      x: padX + 180,
      y: nextY,
      width: 36,
      height: 28,
      label: '+',
      onClick: () => this.changeVDiv(1),
    });

    this.ui.vdivAuto = createButton(this.layer, {
      x: padX + 224,
      y: nextY,
      width: 48,
      height: 28,
      label: 'Auto',
      onClick: () => {
        console.log('[VerticalControl] Auto V/div clicked');
        this.onAutoVScale && this.onAutoVScale();
      },
    });
    nextY += 36;

    this.ui.vposLabel = createLabel({ x: padX, y: nextY, text: 'Position' });
    this.ui.vposSlider = createSlider(this.layer, {
      x: padX + 80,
      y: nextY - 6,
      width: colWidth - 160,
      min: VPOS_MIN,
      max: VPOS_MAX,
      value: this.vOffsetRaw,
      onChange: (val) => this.previewVPosition(val),
      onCommit: (val) => this.changeVPosition(val),
      format: (v) => `${Math.round(v)}`,
    });

    this.ui.vposCenter = createButton(this.layer, {
      x: colWidth - 60,
      y: nextY - 6,
      width: 60,
      height: 28,
      label: 'Center',
      onClick: () => {
        console.log('[VerticalControl] Center V position clicked');
        this.onAutoVOffset && this.onAutoVOffset();
      },
    });
    nextY += 40;

    this.ui.cplLabel = createLabel({ x: padX, y: nextY, text: 'Coupling' });
    this.ui.cplAc = createButton(this.layer, {
      x: padX + 80,
      y: nextY - 6,
      width: 60,
      height: 28,
      label: 'AC',
      onClick: () => this.changeCoupling('AC'),
      active: this.coupling === 'AC',
    });
    this.ui.cplDc = createButton(this.layer, {
      x: padX + 146,
      y: nextY - 6,
      width: 60,
      height: 28,
      label: 'DC',
      onClick: () => this.changeCoupling('DC'),
      active: this.coupling === 'DC',
    });
    this.ui.cplGnd = createButton(this.layer, {
      x: padX + 212,
      y: nextY - 6,
      width: 60,
      height: 28,
      label: 'GND',
      onClick: () => this.changeCoupling('GND'),
      active: this.coupling === 'GND',
    });
    nextY += 46;

    this.layer.add(
      this.ui.label,
      this.ui.vdivMinus.group,
      this.ui.vdivValue,
      this.ui.vdivPlus.group,
      this.ui.vdivAuto.group,
      this.ui.vposLabel,
      this.ui.vposSlider.group,
      this.ui.vposCenter.group,
      this.ui.cplLabel,
      this.ui.cplAc.group,
      this.ui.cplDc.group,
      this.ui.cplGnd.group,
    );
    return nextY;
  }

  changeVDiv(delta) {
    const nextIndex = Math.max(0, Math.min(VDIV_VALUES_MV.length - 1, this.currentVIndex + delta));
    this.currentVIndex = nextIndex;
    this.currentVDivMV = VDIV_VALUES_MV[this.currentVIndex];
    if (this.ui.vdivValue) {
      this.ui.vdivValue.text(this.formatVoltage(this.currentVDivMV));
    }
    this.layer.batchDraw();
    this.onConfigChange && this.onConfigChange({ v_div: { v: VDIV_VALUES_MV[this.currentVIndex], u: 'mV' } });
  }

  changeVPosition(value) {
    const raw = Math.round(value);
    const slider = this.ui.vposSlider;
    this.vOffsetRaw = slider ? Math.max(slider.min, Math.min(slider.max, raw)) : raw;
    if (slider) {
      slider.render(this.vOffsetRaw);
    }
    this.onConfigChange && this.onConfigChange({ v_offset: this.vOffsetRaw });
    this.layer.batchDraw();
  }

  previewVPosition(value) {
    this.vOffsetRaw = Math.max(VPOS_MIN, Math.min(VPOS_MAX, Math.round(value)));
  }

  changeCoupling(coupling) {
    this.coupling = coupling;
    setButtonActive(this.ui.cplAc, coupling === 'AC');
    setButtonActive(this.ui.cplDc, coupling === 'DC');
    setButtonActive(this.ui.cplGnd, coupling === 'GND');
    this.layer.batchDraw();
    this.onConfigChange && this.onConfigChange({ coupling });
  }

  layout(colWidth) {
    if (this.ui.vposSlider) {
      this.ui.vposSlider.setWidth(colWidth - 160);
    }
  }

  updateFromConfig(config) {
    if (!config) return;

    if (config.v_div) {
      let vValue = config.v_div.v;
      if (config.v_div.u === 'V') vValue *= 1000;
      const idx = VDIV_VALUES_MV.indexOf(vValue);
      if (idx !== -1) {
        this.currentVIndex = idx;
        this.currentVDivMV = VDIV_VALUES_MV[idx];
      }
      if (this.ui.vdivValue) {
        const displayMv = typeof config.v_div.v === 'number'
          ? (config.v_div.u === 'V' ? config.v_div.v * 1000 : config.v_div.v)
          : this.currentVDivMV;
        this.currentVDivMV = displayMv;
        this.ui.vdivValue.text(this.formatVoltage(displayMv));
      }
    }

    const vOffsetEntry = config.v_offset;
    // Only update if slider is not being dragged
    if (!this.ui.vposSlider?.isDragging && (typeof vOffsetEntry === 'number' || (vOffsetEntry && typeof vOffsetEntry.v === 'number'))) {
      const raw = typeof vOffsetEntry === 'number' ? vOffsetEntry : vOffsetEntry.v;
      this.vOffsetRaw = Math.max(VPOS_MIN, Math.min(VPOS_MAX, raw));
      if (this.ui.vposSlider) {
        this.ui.vposSlider.render(this.vOffsetRaw);
      }
    }

    if (config.coupling) {
      this.coupling = config.coupling;
      setButtonActive(this.ui.cplAc, this.coupling === 'AC');
      setButtonActive(this.ui.cplDc, this.coupling === 'DC');
      setButtonActive(this.ui.cplGnd, this.coupling === 'GND');
    }
  }
}
