"""
Auto-adjustment algorithms for oscilloscope parameters.
Automatically finds optimal V/div, Time/div, V offset, and trigger level.
"""
import logging
import time
from typing import Dict, Any, Optional, List, Tuple
from calculations import calculate_measurements, calculate_frequency_and_period
from converters import get_voltage_mv, get_time_ms

logger = logging.getLogger(__name__)

# Constants for V/div (voltage per division) in millivolts
VDIV_VALUES_MV = [20.0, 50.0, 100.0, 200.0, 500.0, 1000.0, 2000.0, 5000.0, 10000.0]

# Constants for Time/div in milliseconds
TDIV_VALUES_MS = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500]

# Auto V/div parameters
FILL_FACTOR_MIN = 0.2  # Signal should use at least 20% of screen
FILL_FACTOR_MAX = 0.8  # Signal should use at most 80% of screen

# Auto Time/div parameters
SEGMENTS_COUNT_MIN = 4  # At least 4 half-periods on screen
SEGMENTS_COUNT_MAX = 8  # At most 8 half-periods on screen

# General parameters
# [PL_AUDIT_WEB_B13] Hard cap on recursive step adjustments. Termination normally
# comes from the value list boundary, but a signal sitting exactly between two
# adjacent steps can oscillate; this bounds the recursion so it can never hit
# Python's RecursionError (each level performs a real device apply_config).
MAX_AUTO_ITERATIONS = len(TDIV_VALUES_MS) + 2

# Offset parameters
V_OFFSET_MIN = 0
V_OFFSET_MAX = 255
V_OFFSET_CENTER = 128

TRIGGER_LEVEL_MIN = 0
TRIGGER_LEVEL_MAX = 255


def _apply_failed(warnings: List[str]) -> bool:
    """[PL_AUDIT_WEB_02] True when apply_config reported an actual device write
    failure (vs a benign 'Unsupported <field>' warning). _apply_config_internal
    swallows hardware errors and returns them as a 'config update failed: ...'
    warning without raising, so auto-adjust must inspect the warnings to know a
    change did NOT take effect."""
    return any(str(w).startswith("config update failed") for w in (warnings or []))


def find_next_step(values: List[float], current: float, direction: int) -> Optional[float]:
    """
    Find the next value in a sorted step list, in the given direction.

    [PL_AUDIT_WEB_B4] Shared implementation for find_next_vdiv / find_next_tdiv,
    which were byte-for-byte identical except for the list.

    Args:
        values: Ascending list of valid step values.
        current: Current value.
        direction: +1 for the next larger step, -1 for the next smaller.

    Returns:
        Next step value, or None if already at the boundary.
    """
    try:
        next_idx = values.index(current) + direction
        if 0 <= next_idx < len(values):
            return values[next_idx]
        return None
    except ValueError:
        # Current value not in list, find closest in the requested direction
        if direction > 0:
            larger = [v for v in values if v > current]
            return larger[0] if larger else None
        smaller = [v for v in values if v < current]
        return smaller[-1] if smaller else None


def find_next_vdiv(current_mv: float, direction: int) -> Optional[float]:
    """Find next V/div value in the list. +1 = zoom out, -1 = zoom in."""
    return find_next_step(VDIV_VALUES_MV, current_mv, direction)


def find_next_tdiv(current_ms: float, direction: int) -> Optional[float]:
    """Find next Time/div value in the list. +1 = more time, -1 = less time."""
    return find_next_step(TDIV_VALUES_MS, current_ms, direction)


def auto_adjust_v_div(device_service, config: Dict[str, Any], _depth: int = 0) -> bool:
    """
    Automatically adjust voltage scale (V/div) so signal uses 20-80% of screen vertically.

    Algorithm:
    1. Get current frame and measurements
    2. Calculate fill_factor = data_v_range / full_v_range
    3. If fill_factor > 0.8: increase V/div (zoom out) and recurse
    4. If fill_factor < 0.2: decrease V/div (zoom in) and recurse
    5. Otherwise: optimal, stop

    Args:
        device_service: Device service instance
        config: Current device configuration
        _depth: Internal recursion depth guard (do not set from callers)

    Returns:
        True if adjustment was made or optimal, False if no signal
    """
    try:
        # [PL_AUDIT_WEB_B13] Stop if we've stepped too many times (oscillation guard).
        if _depth >= MAX_AUTO_ITERATIONS:
            logger.warning("[AUTO V/div] Max iterations reached; stopping")
            return True
        # Get fresh frame and measurements
        frame = device_service.get_latest_frame()
        if not frame or 'samples' not in frame:
            return False
        
        measurements = calculate_measurements(frame, config)
        if not measurements:
            return False
        
        # Get current V/div
        v_div_mv = get_voltage_mv(config)
        full_v_range_mv = v_div_mv * 8.0  # 8 divisions vertically
        
        # Get signal amplitude
        v_max = measurements.get('v_max', {})
        v_min = measurements.get('v_min', {})
        
        if not v_max or not v_min:
            return False
        
        v_data_max_mv = abs(v_max.get('v', 0))
        v_data_min_mv = abs(v_min.get('v', 0))
        data_v_range_mv = 2.0 * max(v_data_max_mv, v_data_min_mv)
        
        # Calculate fill factor
        if full_v_range_mv <= 0:
            return False
        
        fill_factor = data_v_range_mv / full_v_range_mv
        
        logger.info(f"[AUTO V/div] v_div={v_div_mv}mV, fill_factor={fill_factor:.3f}")
        
        # Decision logic
        if fill_factor > FILL_FACTOR_MAX:
            # Signal too large - increase V/div (zoom out)
            next_vdiv = find_next_vdiv(v_div_mv, +1)
            if next_vdiv is None:
                return True  # At max, consider success
            
            # Apply new V/div
            changes = {'v_div': {'v': next_vdiv, 'u': 'mV'}}
            new_config, warnings = device_service.apply_config(changes)
            if _apply_failed(warnings):
                logger.warning(f"[AUTO V/div] apply failed: {warnings}")
                return False
            config.update(new_config)

            # Recurse
            return auto_adjust_v_div(device_service, config, _depth + 1)

        elif fill_factor < FILL_FACTOR_MIN:
            # Signal too small - decrease V/div (zoom in)
            next_vdiv = find_next_vdiv(v_div_mv, -1)
            if next_vdiv is None:
                return True  # At min, consider success

            # Apply new V/div
            changes = {'v_div': {'v': next_vdiv, 'u': 'mV'}}
            new_config, warnings = device_service.apply_config(changes)
            if _apply_failed(warnings):
                logger.warning(f"[AUTO V/div] apply failed: {warnings}")
                return False
            config.update(new_config)

            # Recurse
            return auto_adjust_v_div(device_service, config, _depth + 1)
            
        else:
            # Optimal fill factor
            return True
            
    except Exception as e:
        logger.error(f"[AUTO V/div] Error: {e}")
        return False


def auto_adjust_t_div(device_service, config: Dict[str, Any], _depth: int = 0) -> bool:
    """
    Automatically adjust time base (Time/div) so 4-8 signal cycles are visible on screen.

    Algorithm:
    1. Get current frame and calculate frequency (segments count)
    2. If segments_count < 4: increase Time/div (show more time) and recurse
    3. If segments_count > 8: decrease Time/div (show less time) and recurse
    4. Otherwise: optimal, stop

    Args:
        device_service: Device service instance
        config: Current device configuration
        _depth: Internal recursion depth guard (do not set from callers)

    Returns:
        True if adjustment was made or optimal, False if no signal
    """
    try:
        # [PL_AUDIT_WEB_B13] Oscillation guard (see auto_adjust_v_div).
        if _depth >= MAX_AUTO_ITERATIONS:
            logger.warning("[AUTO T/div] Max iterations reached; stopping")
            return True
        # Get fresh frame
        frame = device_service.get_latest_frame()
        if not frame or 'samples' not in frame:
            return False
        
        # Calculate frequency and segments count
        samples = frame.get('samples', [])
        t_step_ms = frame.get('t_step_ms', 0.001)
        
        freq_data = calculate_frequency_and_period(samples, t_step_ms)
        segments_count = freq_data.get('segments_count', 0) or 0
        
        # Get current Time/div
        t_div_ms = get_time_ms(config)
        
        logger.info(f"[AUTO T/div] t_div={t_div_ms}ms, segments={segments_count}")
        
        # Check if signal is detected
        if segments_count == 0 or segments_count is None:
            return False
        
        # Decision logic
        if segments_count < SEGMENTS_COUNT_MIN:
            # Too few cycles - increase Time/div (show more time)
            next_tdiv = find_next_tdiv(t_div_ms, +1)
            if next_tdiv is None:
                return True  # At max, consider success
            
            # Apply new Time/div
            changes = {'t_div': {'v': next_tdiv, 'u': 'ms'}}
            new_config, warnings = device_service.apply_config(changes)
            if _apply_failed(warnings):
                logger.warning(f"[AUTO T/div] apply failed: {warnings}")
                return False
            config.update(new_config)

            # Recurse
            return auto_adjust_t_div(device_service, config, _depth + 1)

        elif segments_count > SEGMENTS_COUNT_MAX:
            # Too many cycles - decrease Time/div (show less time)
            next_tdiv = find_next_tdiv(t_div_ms, -1)
            if next_tdiv is None:
                return True  # At min, consider success

            # Apply new Time/div
            changes = {'t_div': {'v': next_tdiv, 'u': 'ms'}}
            new_config, warnings = device_service.apply_config(changes)
            if _apply_failed(warnings):
                logger.warning(f"[AUTO T/div] apply failed: {warnings}")
                return False
            config.update(new_config)

            # Recurse
            return auto_adjust_t_div(device_service, config, _depth + 1)
            
        else:
            # Optimal segments count
            return True
            
    except Exception as e:
        logger.error(f"[AUTO T/div] Error: {e}")
        return False


def auto_adjust_v_offset(device_service, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Automatically center signal vertically on screen.
    
    Algorithm:
    1. Get current frame and measurements
    2. Calculate signal center: (v_max + v_min) / 2
    3. Calculate required offset to center signal at 0V
    4. Convert to native value (0-255) and apply
    
    Args:
        device_service: Device service instance
        config: Current device configuration
        
    Returns:
        Dictionary with adjustment results
    """
    result = {
        'success': False,
        'iterations': 1,
        'old_value': config.get('v_offset', V_OFFSET_CENTER),
        'new_value': None,
        'reason': None
    }
    
    try:
        # Get fresh frame and measurements (wait if needed)
        frame = device_service.get_latest_frame()
        if not frame or 'samples' not in frame:
            result['reason'] = 'no_signal'
            return result
        
        measurements = calculate_measurements(frame, config)
        if not measurements:
            result['reason'] = 'no_measurements'
            return result
        
        # Get signal voltage range
        v_max = measurements.get('v_max', {})
        v_min = measurements.get('v_min', {})
        
        if not v_max or not v_min:
            result['reason'] = 'no_voltage_data'
            return result
        
        v_max_mv = v_max.get('v', 0)
        v_min_mv = v_min.get('v', 0)
        
        # Calculate signal center (offset from 0V)
        signal_center_mv = (v_max_mv + v_min_mv) / 2.0
        
        # Calculate required offset to center at 0V
        target_offset_mv = -signal_center_mv
        
        # Convert to native value (0-255)
        v_div_mv = get_voltage_mv(config)
        full_range_mv = v_div_mv * 8.0
        
        if full_range_mv <= 0:
            result['reason'] = 'invalid_range'
            return result
        
        # Normalize to -0.5 .. +0.5 range
        offset_normalized = target_offset_mv / full_range_mv
        
        # Convert to 0-255 range (128 is center)
        v_offset_raw = V_OFFSET_CENTER + (offset_normalized * 256.0)
        
        # Clamp to valid range
        v_offset_raw = max(V_OFFSET_MIN, min(V_OFFSET_MAX, int(round(v_offset_raw))))
        
        # Apply new offset
        changes = {'v_offset': v_offset_raw}
        new_config, warnings = device_service.apply_config(changes)
        if _apply_failed(warnings):
            logger.warning(f"[AUTO V Offset] apply failed: {warnings}")
            result['reason'] = f'apply_failed: {warnings}'
            return result
        config.update(new_config)

        result['success'] = True
        result['new_value'] = v_offset_raw
        result['reason'] = 'centered'
        
        logger.info(f"[AUTO V Offset] Signal center: {signal_center_mv:.1f}mV, "
                   f"offset: {result['old_value']} -> {v_offset_raw}")
        
    except Exception as e:
        logger.error(f"[AUTO V Offset] Error: {e}")
        result['reason'] = f'error: {str(e)}'
    
    return result


def auto_adjust_trigger_level(device_service, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Automatically set trigger level to middle of signal amplitude.
    
    Algorithm:
    1. Get current frame and measurements
    2. Calculate middle level: (v_max + v_min) / 2
    3. Convert to native value (0-255) considering current V/div and V offset
    4. Apply trigger level
    
    Args:
        device_service: Device service instance
        config: Current device configuration
        
    Returns:
        Dictionary with adjustment results
    """
    result = {
        'success': False,
        'iterations': 1,
        'old_value': config.get('trigger_level', 128),
        'new_value': None,
        'reason': None
    }
    
    try:
        # Get fresh frame (wait if needed)
        frame = device_service.get_latest_frame()
        if not frame or 'samples' not in frame:
            result['reason'] = 'no_signal'
            return result
        
        # Simple approach: use average of samples directly
        samples = frame.get('samples', [])
        if not samples:
            result['reason'] = 'no_samples'
            return result
        
        # Calculate average sample value (already in 0-255 range for 8-bit)
        samples_avg = sum(samples) / len(samples)
        trigger_raw = int(round(samples_avg))
        
        # Clamp to valid range
        trigger_raw = max(TRIGGER_LEVEL_MIN, min(TRIGGER_LEVEL_MAX, trigger_raw))
        
        # Apply new trigger level
        changes = {'trigger_level': trigger_raw}
        new_config, warnings = device_service.apply_config(changes)
        if _apply_failed(warnings):
            logger.warning(f"[AUTO Trigger] apply failed: {warnings}")
            result['reason'] = f'apply_failed: {warnings}'
            return result
        config.update(new_config)

        result['success'] = True
        result['new_value'] = trigger_raw
        result['reason'] = 'centered'
        
        logger.info(f"[AUTO Trigger] Level: {result['old_value']} -> {trigger_raw}")
        
    except Exception as e:
        logger.error(f"[AUTO Trigger] Error: {e}")
        result['reason'] = f'error: {str(e)}'
    
    return result


def auto_adjust_multiple(device_service, config: Dict[str, Any],
                        types: List[str]) -> bool:
    """
    Apply multiple auto-adjustments in correct order.
    
    Order matters:
    1. v_div - voltage scale first
    2. v_offset - vertical centering (depends on v_div)
    3. trigger - trigger level (depends on v_div and v_offset)
    4. t_div - time base (independent)
    
    Args:
        device_service: Device service instance
        config: Current device configuration
        types: List of adjustment types to apply
        
    Returns:
        True if all adjustments succeeded
    """
    # Ensure we have a recent frame for adjustment
    frame = device_service.ensure_frame_available()
    if not frame:
        logger.warning("[AUTO Multiple] No frame available for adjustment")
        return False
    
    # Define correct order
    ordered_types = ['v_div', 'v_offset', 'trigger', 't_div']
    
    # Filter and sort requested types by correct order
    types_to_apply = [t for t in ordered_types if t in types]
    
    success = True
    
    for adjust_type in types_to_apply:
        try:
            if adjust_type == 'v_div':
                adj_result = auto_adjust_v_div(device_service, config)
            elif adjust_type == 'v_offset':
                adj_result = auto_adjust_v_offset(device_service, config)
            elif adjust_type == 'trigger':
                adj_result = auto_adjust_trigger_level(device_service, config)
            elif adjust_type == 't_div':
                adj_result = auto_adjust_t_div(device_service, config)
            else:
                continue

            # [PL_AUDIT_WEB_02] v_offset/trigger return a result DICT (always truthy);
            # v_div/t_div return a bool. `if not adj_result` treated a failed dict
            # ({'success': False, ...}) as success. Normalize both shapes to the real
            # success flag so /api/auto reports failures honestly.
            if isinstance(adj_result, dict):
                ok = bool(adj_result.get('success'))
                if not ok:
                    logger.warning(f"[AUTO Multiple] {adjust_type} did not succeed: "
                                   f"{adj_result.get('reason')}")
            else:
                ok = bool(adj_result)
            if not ok:
                success = False

        except Exception as e:
            logger.error(f"[AUTO Multiple] Error in {adjust_type}: {e}")
            success = False

    return success
