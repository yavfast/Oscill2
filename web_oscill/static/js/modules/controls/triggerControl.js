import { createButton, createLabel, createSlider, setButtonActive } from './uiHelpers.js';

const DEFAULT_SYNC_TYPE = 'AUTO';

export class TriggerControl {
  constructor({ layer, onConfigChange }) {
    this.layer = layer;
    this.onConfigChange = onConfigChange;

    this.syncType = DEFAULT_SYNC_TYPE;
    this.syncFront = true;
    this.syncBack = false;
    this.triggerLevel = 128;

    this.ui = {};
    this.onTriggerLevelChange = null;
  }

  build({ padX, y, colWidth, modeGap = 12 }) {
    let nextY = y;
    this.ui.label = createLabel({ x: padX, y: nextY, text: 'Trigger', fontSize: 16, color: '#ccc' });
    nextY += 22;

    const trigBtnW = (colWidth - modeGap * 3) / 4;
    this.ui.trigAuto = createButton(this.layer, {
      x: padX,
      y: nextY,
      width: trigBtnW,
      height: 28,
      label: 'Auto',
      onClick: () => this.setSyncType('AUTO'),
      active: this.syncType === 'AUTO',
    });
    this.ui.trigTimeout = createButton(this.layer, {
      x: padX + (trigBtnW + modeGap),
      y: nextY,
      width: trigBtnW,
      height: 28,
      label: 'Timeout',
      onClick: () => this.setSyncType('WAIT_TIMEOUT'),
      active: this.syncType === 'WAIT_TIMEOUT',
    });
    this.ui.trigWait = createButton(this.layer, {
      x: padX + 2 * (trigBtnW + modeGap),
      y: nextY,
      width: trigBtnW,
      height: 28,
      label: 'Wait',
      onClick: () => this.setSyncType('WAIT'),
      active: this.syncType === 'WAIT',
    });
    this.ui.trigFree = createButton(this.layer, {
      x: padX + 3 * (trigBtnW + modeGap),
      y: nextY,
      width: trigBtnW,
      height: 28,
      label: 'Free',
      onClick: () => this.setSyncType('FREE'),
      active: this.syncType === 'FREE',
    });
    nextY += 36;

    this.ui.edgeLabel = createLabel({ x: padX, y: nextY, text: 'Sync Edges' });
    nextY += 22;

    const edgeBtnW = (colWidth - modeGap) / 2;
    this.ui.trigFront = createButton(this.layer, {
      x: padX,
      y: nextY,
      width: edgeBtnW,
      height: 28,
      label: 'Front',
      onClick: () => this.toggleSyncEdge('front'),
      active: this.syncFront,
    });
    this.ui.trigBack = createButton(this.layer, {
      x: padX + edgeBtnW + modeGap,
      y: nextY,
      width: edgeBtnW,
      height: 28,
      label: 'Back',
      onClick: () => this.toggleSyncEdge('back'),
      active: this.syncBack,
    });
    nextY += 36;

    this.ui.levelLabel = createLabel({ x: padX, y: nextY, text: 'Level' });
    this.ui.levelSlider = createSlider(this.layer, {
      x: padX + 80,
      y: nextY - 6,
      width: colWidth - 160,
      min: 0,
      max: 255,
      value: this.triggerLevel,
      onChange: (val) => this.previewTriggerLevel(Math.round(val)),
      onCommit: (val) => this.changeTriggerLevel(Math.round(val)),
      format: (v) => `${Math.round(v)}`,
    });
    nextY += 60;

    this.layer.add(
      this.ui.label,
      this.ui.trigAuto.group,
      this.ui.trigTimeout.group,
      this.ui.trigWait.group,
      this.ui.trigFree.group,
      this.ui.edgeLabel,
      this.ui.trigFront.group,
      this.ui.trigBack.group,
      this.ui.levelLabel,
      this.ui.levelSlider.group,
    );
    return nextY;
  }

  setSyncType(type) {
    this.applySyncTypeState(type);
    this.layer.batchDraw();
    this.onConfigChange && this.onConfigChange({ sync_type: this.syncType });
  }

  applySyncTypeState(type = this.syncType) {
    const normalized = (type || DEFAULT_SYNC_TYPE).toUpperCase();
    this.syncType = normalized;
    if (this.ui.trigAuto) setButtonActive(this.ui.trigAuto, normalized === 'AUTO');
    if (this.ui.trigTimeout) setButtonActive(this.ui.trigTimeout, normalized === 'WAIT_TIMEOUT');
    if (this.ui.trigWait) setButtonActive(this.ui.trigWait, normalized === 'WAIT');
    if (this.ui.trigFree) setButtonActive(this.ui.trigFree, normalized === 'FREE');
  }

  toggleSyncEdge(edge, explicitValue = null) {
    if (edge === 'front') {
      const next = explicitValue === null ? !this.syncFront : !!explicitValue;
      this.applySyncEdgesState(next, this.syncBack);
    } else if (edge === 'back') {
      const next = explicitValue === null ? !this.syncBack : !!explicitValue;
      this.applySyncEdgesState(this.syncFront, next);
    } else {
      return;
    }
    this.layer.batchDraw();
    this.onConfigChange && this.onConfigChange({ sync_front: this.syncFront, sync_back: this.syncBack });
  }

  applySyncEdgesState(front = this.syncFront, back = this.syncBack) {
    this.syncFront = typeof front === 'boolean' ? front : this.syncFront;
    this.syncBack = typeof back === 'boolean' ? back : this.syncBack;
    if (this.ui.trigFront) setButtonActive(this.ui.trigFront, this.syncFront);
    if (this.ui.trigBack) setButtonActive(this.ui.trigBack, this.syncBack);
  }

  changeTriggerLevel(level) {
    this.triggerLevel = level;
    if (this.ui.levelSlider) {
      this.ui.levelSlider.render(level);
    }
    this.onConfigChange && this.onConfigChange({ trigger_level: level });
    if (this.onTriggerLevelChange) this.onTriggerLevelChange(level);
  }

  previewTriggerLevel(level) {
    this.triggerLevel = level;
    if (this.onTriggerLevelChange) this.onTriggerLevelChange(level);
  }

  setTriggerLevelChangeCallback(callback) {
    this.onTriggerLevelChange = callback;
  }

  layout(colWidth) {
    if (this.ui.levelSlider) {
      this.ui.levelSlider.setWidth(colWidth - 160);
    }
  }

  updateFromConfig(config) {
    if (!config) return;

    if (config.sync_type) {
      this.applySyncTypeState(config.sync_type);
    }

    if (typeof config.sync_front === 'boolean' || typeof config.sync_back === 'boolean') {
      const front = typeof config.sync_front === 'boolean' ? config.sync_front : this.syncFront;
      const back = typeof config.sync_back === 'boolean' ? config.sync_back : this.syncBack;
      this.applySyncEdgesState(front, back);
    }

    if (typeof config.trigger_level === 'number' && this.ui.levelSlider) {
      this.triggerLevel = config.trigger_level;
      this.ui.levelSlider.setValue(config.trigger_level, { silent: true, skipCommit: true });
    }
  }
}
