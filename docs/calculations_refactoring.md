# Calculations Module Refactoring

## Overview
All mathematical operations and data processing functions have been extracted from `web_oscill/main.py` into a separate dedicated module `web_oscill/calculations.py`.

## Changes Made

### New Module: `web_oscill/calculations.py`
Created a new module containing all mathematical and data processing functions:

1. **`samples_to_hex(samples, sample_bytes)`** - Convert samples to hex string for compact transmission
2. **`samples_from_hex(hex_str, sample_bytes)`** - Decode hex string back to samples
3. **`samples_to_millivolts(samples, sample_bits, config)`** - Convert raw ADC samples to millivolts
4. **`calculate_voltage_range(samples, sample_bits, config, peak_min, peak_max)`** - Calculate min/max voltage from samples
5. **`calculate_segments(samples, threshold)`** - Calculate positive and negative segments relative to threshold
6. **`calculate_average(values)`** - Calculate integer average of a list of values
7. **`filter_short_segments(segments, min_length)`** - Filter out segments shorter than min_length (noise removal)
8. **`calculate_frequency_and_period(samples, t_step_ms)`** - Calculate frequency and period using segment analysis algorithm (matching OscillData.java)
9. **`calculate_measurements(frame, config)`** - Calculate comprehensive measurements (frequency, period, Vpp, Vmax, Vmin, Vavg)

### Frequency Calculation Algorithm (Updated)
The frequency calculation algorithm has been updated to match the implementation in `OscillData.java`:

**Old Algorithm (Zero-Crossing Method):**
- Simple detection of threshold crossings
- No noise filtering
- Less accurate for noisy signals

**New Algorithm (Segment Analysis Method):**
1. Calculate average value of all samples (threshold)
2. Identify positive segments (sequences above average) and negative segments (sequences below average)
3. Calculate average segment length
4. Filter out short segments (removes noise) - segments shorter than average are discarded
5. Require at least 3 segments for reliable frequency calculation
6. Calculate period as: `(avg_positive_length + avg_negative_length) * time_per_sample`
7. Calculate frequency as: `1000 / period_ms` (converts to Hz)

**Benefits of New Algorithm:**
- More robust to noise
- Better filtering of spurious signals
- Matches the proven Java implementation
- More accurate frequency measurements

### Modified: `web_oscill/main.py`
- Added import of calculation functions from the new module
- Replaced internal function calls (`_samples_to_hex`, `_samples_to_millivolts`, etc.) with imported functions
- Removed all internal mathematical function definitions:
  - `_samples_to_hex()`
  - `_samples_from_hex()`
  - `_samples_to_millivolts()`
  - `calculate_measurements()`
- Simplified voltage range calculation in `api_acquire_single()` using the new `calculate_voltage_range()` function

## Benefits

1. **Separation of Concerns** - Mathematical logic is separated from API endpoint logic
2. **Reusability** - Calculation functions can now be easily imported and used in other modules
3. **Testability** - Mathematical functions can be unit tested independently
4. **Maintainability** - Changes to calculation logic are isolated in one module
5. **Clarity** - The main.py file is now cleaner and focused on API handling

## API Compatibility
All API endpoints maintain backward compatibility. No changes to the API interface or response formats.

## Type Safety
All functions include proper type hints with explicit type annotations to ensure type checker compatibility.
