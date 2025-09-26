// Enums for quantity types and dimensions with SI prefixes
export const Quantity = Object.freeze({ V: 'V', s: 's', Hz: 'Hz' });
export const Dim = Object.freeze({
  p: { code: 'p', factor: 1e-12, prefix: 'p' },
  n: { code: 'n', factor: 1e-9, prefix: 'n' },
  u: { code: 'u', factor: 1e-6, prefix: 'µ' },
  m: { code: 'm', factor: 1e-3, prefix: 'm' },
  _: { code: '_', factor: 1, prefix: '' },
  k: { code: 'k', factor: 1e3, prefix: 'k' },
  M: { code: 'M', factor: 1e6, prefix: 'M' },
  G: { code: 'G', factor: 1e9, prefix: 'G' },
});

export const FormatType = Object.freeze({ axis: 'axis', std: 'std' });

const DIM_ORDER_DESC = ['G', 'M', 'k', '_', 'm', 'u', 'n', 'p'];
const isValidDim = (d) => Object.prototype.hasOwnProperty.call(Dim, d);
const dimOf = (d) => Dim[d];

function withSign(value, s) {
  const sign = value < 0 ? '-' : '';
  return sign + s;
}

function chooseAutoDim(absBaseValue) {
  if (!isFinite(absBaseValue) || absBaseValue === 0) return '_';
  for (const code of DIM_ORDER_DESC) {
    const f = dimOf(code).factor;
    if (absBaseValue / f >= 1) return code;
  }
  return 'p';
}

function decimalsFor(quantity, dimCode, formatType) {
  // Heuristics similar to existing UI rules
  if (formatType === FormatType.axis) {
    if (quantity === Quantity.s) {
      return dimCode === '_' ? 2 : 0; // s -> 2 dp, ms/us/ns -> 0 dp
    }
    if (quantity === Quantity.V) {
      return dimCode === '_' ? 2 : 0; // V -> 2 dp, mV -> 0 dp
    }
    if (quantity === Quantity.Hz) {
      // Hz axis: use 1 dp for k/M/G, 0 for Hz and sub-1 prefixes
      return (dimCode === 'k' || dimCode === 'M' || dimCode === 'G') ? 1 : 0;
    }
  }
  // std
  if (quantity === Quantity.s) return dimCode === '_' ? 2 : 2;
  if (quantity === Quantity.V) return 2; // both V and mV -> 2 dp
  if (quantity === Quantity.Hz) return (dimCode === '_' ? 2 : 2);
  return 2;
}

function unitSuffix(quantity) {
  return quantity;
}

// Universal formatter
// value: number; currentDim: 'p'|'n'|'u'|'m'|'_'|'k'|'M'|'G'
// targetDim: same as above or 'auto' to select based on magnitude
// quantity: 'V' | 's' | 'Hz'
// formatType: 'axis' | 'std'
export function formatUniversal(value, currentDim, targetDim, quantity, formatType = FormatType.std) {
  if (value === null || value === undefined || Number.isNaN(value)) return '-';
  const cur = isValidDim(currentDim) ? currentDim : '_';
  let target = targetDim === 'auto' ? 'auto' : (isValidDim(targetDim) ? targetDim : '_');
  const absBase = Math.abs(value) * dimOf(cur).factor;
  if (target === 'auto') target = chooseAutoDim(absBase);
  const baseValue = value * dimOf(cur).factor;
  const shown = baseValue / dimOf(target).factor;
  const dp = decimalsFor(quantity, target, formatType);
  const num = Math.abs(shown).toFixed(dp);
  const prefix = dimOf(target).prefix;
  const suffix = unitSuffix(quantity);
  return withSign(shown, `${num} ${prefix}${suffix}`.trim());
}

// Wrapper helpers keeping existing API surface
export function formatSecondsAxis(seconds) {
  return formatUniversal(seconds, '_', 'auto', Quantity.s, FormatType.axis);
}
export function formatSecondsStd(seconds) {
  return formatUniversal(seconds, '_', 'auto', Quantity.s, FormatType.std);
}
export function formatVoltsAxis(volts) {
  return formatUniversal(volts, '_', 'auto', Quantity.V, FormatType.axis);
}
export function formatVoltsStd(volts) {
  return formatUniversal(volts, '_', 'auto', Quantity.V, FormatType.std);
}
export function formatHertzAxis(hz) {
  return formatUniversal(hz, '_', 'auto', Quantity.Hz, FormatType.axis);
}
export function formatHertzStd(hz) {
  return formatUniversal(hz, '_', 'auto', Quantity.Hz, FormatType.std);
}
export function formatUnitAxis(value, unit) {
  if (unit === Quantity.s || unit === 's') return formatSecondsAxis(value);
  if (unit === Quantity.V || unit === 'V') return formatVoltsAxis(value);
  if (unit === Quantity.Hz || unit === 'Hz') return formatHertzAxis(value);
  return `${value}` + (unit ? ` ${unit}` : '');
}
export function formatUnitStd(value, unit) {
  if (unit === Quantity.s || unit === 's') return formatSecondsStd(value);
  if (unit === Quantity.V || unit === 'V') return formatVoltsStd(value);
  if (unit === Quantity.Hz || unit === 'Hz') return formatHertzStd(value);
  return `${Number(value).toFixed(2)}${unit ? ` ${unit}` : ''}`;
}

// Helper for measurement objects { v, u }
export function formatValueWithUnit(obj) {
  if (!obj || typeof obj.v !== 'number') return '-';
  const u = obj.u || '';
  if (u === 's') return formatSecondsStd(obj.v);
  if (u === 'V') return formatVoltsStd(obj.v);
  if (u === 'Hz') return formatHertzStd(obj.v);
  return `${Number(obj.v).toFixed(2)}${u ? ` ${u}` : ''}`;
}
