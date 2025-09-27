"""
Helper functions for converting values between different units.
Used in the oscilloscope web app for normalizing measurements and configurations.
"""

# Prefix multipliers relative to base unit
PREFIX_MAP = {
    "p": 1e-12,  # pico
    "n": 1e-9,   # nano
    "u": 1e-6,   # micro
    "m": 1e-3,   # milli
    "_": 1,      # base
    "k": 1e3,    # kilo
    "M": 1e6     # mega
}

# Supported physical quantities
QUANTITIES = {"V", "s", "Hz", "_"}

def parse_unit(unit: str) -> tuple[str, str]:
    """Parse unit into quantity and prefix."""
    if unit in QUANTITIES:
        return unit, "_"
    
    if len(unit) >= 2 and unit[0] in PREFIX_MAP and unit[1:] in QUANTITIES:
        return unit[1:], unit[0]
    
    raise ValueError(f"Unsupported unit: {unit}")

def convert(value: float, from_unit: str, to_unit: str) -> float:
    """Universal function to convert value from one unit to another."""
    if from_unit == to_unit:
        return value
    
    from_quantity, from_prefix = parse_unit(from_unit)
    to_quantity, to_prefix = parse_unit(to_unit)
    
    if from_quantity != to_quantity:
        raise ValueError(f"Cannot convert between different quantities: {from_quantity} to {to_quantity}")
    
    # Calculate conversion factor
    factor = PREFIX_MAP[from_prefix] / PREFIX_MAP[to_prefix]
    result = value * factor

    # Round to avoid floating-point artifacts
    return round(result, 10)


def _extract_structured_entry(config: dict, key: str) -> tuple[float, str]:
    """Return value-unit pair from structured config entry."""
    try:
        entry = config[key]
    except KeyError as exc:
        raise KeyError(f"Missing '{key}' configuration entry") from exc

    if not isinstance(entry, dict):
        raise TypeError(f"'{key}' entry must be a mapping with 'v' and 'u' keys")

    try:
        return entry["v"], entry["u"]
    except KeyError as exc:
        raise KeyError(f"'{key}' entry must contain 'v' and 'u' keys") from exc

def get_voltage_mv(config: dict) -> float:
    """
    Extract voltage division value in millivolts from config.
    Requires structured format {v, u} under the 'v_div' key.
    """
    value, unit = _extract_structured_entry(config, "v_div")
    return convert(value, unit, "mV")

def get_time_ms(config: dict) -> float:
    """
    Extract time division value in milliseconds from config.
    Requires structured format {v, u} under the 't_div' key.
    """
    value, unit = _extract_structured_entry(config, "t_div")
    return convert(value, unit, "ms")