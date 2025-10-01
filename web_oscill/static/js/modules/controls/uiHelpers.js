export function createButton(layer, { x, y, width, height, label, onClick, active = false }) {
  const group = new Konva.Group({ x, y });
  const rect = new Konva.Rect({
    width,
    height,
    cornerRadius: 6,
    fill: active ? '#007acc' : '#3c3c3c',
    stroke: active ? '#007acc' : '#555',
    strokeWidth: 1,
  });
  const text = new Konva.Text({
    x: 0,
    y: 0,
    width,
    height,
    align: 'center',
    verticalAlign: 'middle',
    text: label,
    fontSize: 14,
    fill: '#fff',
  });

  group.add(rect, text);
  group._isActive = !!active;
  group.on('mouseenter', () => {
    document.body.style.cursor = 'pointer';
    rect.fill(group._isActive ? '#1286d8' : '#4c4c4c');
    layer.draw();
  });
  group.on('mouseleave', () => {
    document.body.style.cursor = 'default';
    rect.fill(group._isActive ? '#007acc' : '#3c3c3c');
    layer.draw();
  });
  group.on('click', () => onClick && onClick());

  return { group, rect, text };
}

export function createLabel({ x, y, text, fontSize = 14, color = '#ccc' }) {
  return new Konva.Text({ x, y, text, fontSize, fill: color });
}

export function setButtonActive(buttonRef, active) {
  if (!buttonRef) return;
  if (buttonRef.group) {
    buttonRef.group._isActive = !!active;
  }
  buttonRef.rect.fill(active ? '#007acc' : '#3c3c3c');
  buttonRef.rect.stroke(active ? '#007acc' : '#555');
}

export function createSlider(layer, { x, y, width, min, max, value, onChange, onCommit, format }) {
  const group = new Konva.Group({ x, y });
  const track = new Konva.Rect({ x: 0, y: 10, width, height: 4, fill: '#555', cornerRadius: 2 });
  const handle = new Konva.Circle({ x: 0, y: 12, radius: 8, fill: '#999', stroke: '#ddd', strokeWidth: 1, draggable: true });
  const formatFn = format || ((v) => `${Math.round(v)}`);
  const valueText = new Konva.Text({ x: width + 8, y: 4, text: '', fontSize: 12, fill: '#ddd' });

  const slider = {
    group,
    track,
    handle,
    valueText,
    formatFn,
    min: Number(min),
    max: Number(max),
    width: Math.max(0, width),
    currentValue: Number(value),
  };

  const clampValue = (val) => {
    const numeric = Number.isFinite(val) ? val : slider.min;
    if (slider.max === slider.min) return slider.min;
    return Math.max(slider.min, Math.min(slider.max, numeric));
  };
  const range = () => Math.max(1e-9, slider.max - slider.min);

  slider.toX = (val) => {
    if (slider.width <= 0) return 0;
    const clamped = clampValue(val);
    return ((clamped - slider.min) / range()) * slider.width;
  };
  slider.toVal = (px) => {
    if (slider.width <= 0) return slider.min;
    const clampedPx = Math.max(0, Math.min(slider.width, px));
    return slider.min + (clampedPx / slider.width) * range();
  };
  slider.clamp = (val) => clampValue(val);
  slider.render = (val) => {
    slider.currentValue = clampValue(val);
    const xPos = slider.toX(slider.currentValue);
    slider.handle.x(xPos);
    slider.valueText.text(slider.formatFn(slider.currentValue));
  };
  slider.setRange = (newMin, newMax) => {
    slider.min = Number(newMin);
    slider.max = Math.max(slider.min, Number(newMax));
    slider.render(slider.currentValue);
  };
  slider.setWidth = (newWidth) => {
    slider.width = Math.max(0, newWidth);
    slider.track.width(slider.width);
    slider.valueText.x(slider.width + 8);
    slider.render(slider.currentValue);
  };
  slider.setValue = (val, { silent = false, skipCommit = false } = {}) => {
    slider.render(val);
    if (!silent) {
      onChange && onChange(slider.currentValue);
      if (!skipCommit) onCommit && onCommit(slider.currentValue);
    }
  };

  const handleBaseY = handle.y();
  const clampLocalX = (localX) => Math.max(0, Math.min(slider.width, localX));
  handle.dragBoundFunc((pos) => {
    const parent = handle.getParent();
    if (!parent) return pos;
    const parentAbsTransform = parent.getAbsoluteTransform().copy();
    const localTransform = parentAbsTransform.copy().invert();
    const localPoint = localTransform.point(pos);
    localPoint.x = clampLocalX(localPoint.x);
    localPoint.y = handleBaseY;
    return parentAbsTransform.point(localPoint);
  });

  slider.render(value);
  handle.x(slider.toX(slider.currentValue));

  handle.on('dragmove', () => {
    const nx = Math.max(0, Math.min(slider.width, handle.x()));
    handle.x(nx);
    const val = slider.clamp(slider.toVal(nx));
    slider.currentValue = val;
    slider.valueText.text(slider.formatFn(val));
    onChange && onChange(val);
    layer.batchDraw();
  });
  handle.on('dragend', () => {
    onCommit && onCommit(slider.currentValue);
  });

  group.add(track, handle, valueText);
  return slider;
}
