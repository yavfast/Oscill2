import { createButton } from './uiHelpers.js';

export class AcquisitionControl {
  constructor({ layer, onAcquisitionChange }) {
    this.layer = layer;
    this.onAcquisitionChange = onAcquisitionChange;
    this.isAcquiring = false;
    this.ui = {};
  }

  build({ padX, y, colWidth, gap = 12 }) {
    const buttonW = (colWidth - gap) / 2;
    this.ui.runStop = createButton(this.layer, {
      x: padX,
      y,
      width: buttonW,
      height: 36,
      label: '▶ Run',
      onClick: () => this.toggleRunStop(),
    });
    this.ui.single = createButton(this.layer, {
      x: padX + buttonW + gap,
      y,
      width: buttonW,
      height: 36,
      label: '⏺ Single',
      onClick: () => this.onAcquisitionChange && this.onAcquisitionChange('single'),
    });

    this.layer.add(this.ui.runStop.group, this.ui.single.group);
    this.layer.draw();
    this.setSingleEnabled(true);
    return y + 46;
  }

  toggleRunStop() {
    const willStart = !this.isAcquiring;
    if (willStart) {
      this.isAcquiring = true;
      this.updateRunButtonLabel();
      this.setSingleEnabled(false);
      this.onAcquisitionChange && this.onAcquisitionChange('run');
    } else {
      this.isAcquiring = false;
      this.updateRunButtonLabel();
      this.setSingleEnabled(true);
      this.onAcquisitionChange && this.onAcquisitionChange('stop');
    }
    this.layer.batchDraw();
  }

  setAcquisitionState(state) {
    if (state === 'run') {
      this.isAcquiring = true;
      this.setSingleEnabled(false);
    } else if (state === 'stop') {
      this.isAcquiring = false;
      this.setSingleEnabled(true);
    }
    this.updateRunButtonLabel();
    this.layer.batchDraw();
  }

  setSingleEnabled(enabled) {
    if (!this.ui.single) return;
    const { group, rect, text } = this.ui.single;
    group.listening(enabled);
    rect.listening(enabled);
    text.listening(enabled);
    const fill = enabled ? '#3c3c3c' : '#1f1f1f';
    const stroke = enabled ? '#555' : '#2a2a2a';
    const labelColor = enabled ? '#fff' : '#777';
    rect.fill(fill);
    rect.stroke(stroke);
    text.fill(labelColor);
    group.opacity(enabled ? 1 : 0.5);
  }

  updateRunButtonLabel() {
    if (!this.ui.runStop) return;
    const iconLabel = this.isAcquiring ? '⏹ Stop' : '▶ Run';
    this.ui.runStop.text.text(iconLabel);
  }
}
