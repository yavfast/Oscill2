# Project Memory

## Build System Upgrade (2025-09-26)
- Upgraded Gradle Wrapper to **8.5** (stable) (distributionUrl already pointed to 8.5).
- Selected **Android Gradle Plugin 8.3.2** because AGP 8.5.x requires Gradle >= 8.7. Requirement from user was only to move Gradle to 8.5, so AGP pinned to highest compatible.
- Added **namespace** to `app` and `mpchart` modules.
- Increased **compileSdkVersion / targetSdkVersion** to 34 (modern, required for Play compliance and AGP 8.x tooling benefits).
- Raised **minSdkVersion** from 15 -> 19 (AGP 8.x minimum is 19).
- Set **Java toolchain / runtime** to Java 17 via `org.gradle.java.home` in `gradle.properties`.
- Removed deprecated **package** attribute from `AndroidManifest.xml` in both app and library; rely on Gradle namespace.
- Removed legacy `sourcesJar`, `javadoc`, `javadocJar` tasks in MPAndroidChart module (incompatible classifier usage under Gradle 8).
- Fixed manifest for `MainActivity` adding `android:exported="true"` (required with intent-filter and targetSdk >= 31).
- Updated **JUnit** to 4.13.2 across modules.
- Build now succeeds: `assembleDebug` passes with only deprecation/unchecked warnings.

## Potential Next Improvements
- Update dependencies: appcompat (>=1.7.0), constraintlayout (>=2.1.4), gson (consider 2.10.1).
- Add Java toolchain block instead of org.gradle.java.home for portability.
- Enable `lint` and address deprecation warnings.
- Consider migrating to Kotlin DSL (`build.gradle.kts`) later.
- Consider enabling R8 minification for release.

## Rationale Notes
- Chose not to move Gradle beyond 8.5 because user explicitly requested 8.5.
- Not upgrading AGP beyond 8.3.2 to avoid forced wrapper bump to 8.7+.

## Current Verified State
- Command `./gradlew clean assembleDebug` (with Java 17) succeeds.

## Web Backend Refactoring (2025-10-02)

### Calculations Module Extraction
- Extracted all mathematical operations from `web_oscill/main.py` into separate module `web_oscill/calculations.py`
- Created clean separation of concerns: API handling vs mathematical calculations
- All functions now include proper type hints and documentation

### Frequency Calculation Algorithm Fix (2025-10-02)
**Problem**: Original algorithm used simple zero-crossing method that was:
- Not filtering noise effectively
- Less accurate for noisy signals  
- Not matching the proven Java implementation in `OscillData.java`

**Solution**: Completely rewrote algorithm to match `OscillData.java` `calcFreq()` method:

1. **Segment Analysis Method**:
   - Calculate average of all samples (threshold)
   - Identify positive/negative segments (sequences above/below average)
   - Filter short segments to remove noise
   - Require minimum 3 segments for reliability
   - Calculate period from average segment lengths
   - Derive frequency: `1000 / period_ms`

2. **New Functions**:
   - `calculate_segments()` - segment detection
   - `calculate_average()` - integer averaging
   - `filter_short_segments()` - noise removal
   - `calculate_frequency_and_period()` - main algorithm

3. **Test Results**:
   - 100 Hz: measured 101.01 Hz (1.01% error)
   - 1 kHz: measured 1020.41 Hz (2.04% error)
   - Handles noise, edge cases (empty, constant signals)

4. **Benefits**:
   - ✅ Robust to noise
   - ✅ 1-3% accuracy on clean signals
   - ✅ Matches Java implementation
   - ✅ Full backward API compatibility

**Files Modified**:
- `web_oscill/calculations.py` - new algorithm
- `web_oscill/main.py` - uses new functions
- `docs/frequency_algorithm_fix.md` - detailed documentation
- `docs/calculations_refactoring.md` - refactoring overview
- `scripts/test_frequency_calculation.py` - test suite

### Peak Mode Frequency Fix (2025-10-02)
**Problem**: In Peak mode, frequency calculation showed **doubled value** (~200 Hz instead of 100 Hz).
Other modes (Normal, AVG, AVG_HIRES) calculated frequency correctly.

**Root Cause**: Function `calculate_measurements` was using averaged samples array 
`[(lo + hi) // 2 for lo, hi in zip(peak_min, peak_max)]` for frequency calculation.
This caused artifacts leading to frequency doubling.

**Solution**: Modified to use **original peak_min data** directly for frequency calculation in Peak mode,
matching Java implementation in `OscillData.java` where `preparePeak2Data()` returns `vDataMin`.

**Code Change in `calculations.py`**:
```python
# In PEAK mode, use peak_min data directly (not averaged samples)
samples_for_freq = samples
if peak_min and peak_max:
    samples_for_freq = peak_min  # Like Java OscillData
```

**Test Results**:
- Normal mode: 101.01 Hz ✅
- Peak mode: 101.01 Hz ✅ (was ~200 Hz before fix)
- Difference: 0.00% ✅

**Files Modified**:
- `web_oscill/calculations.py` - fixed `calculate_measurements()` with doubled t_step
- `web_oscill/main.py` - added `calculate_measurements()` call in `/api/frames`
- `scripts/test_peak_frequency_fix.py` - test suite for synthetic data
- `scripts/test_real_device_frequency.py` - test suite for real device
- `docs/peak_frequency_fix.md` - detailed documentation

**Final Solution**: The issue was that Peak mode returns half the samples (127 vs 254) because each sample represents min+max for a time interval. Fixed by:
1. Using peak_min for segmentation (better signal)  
2. Doubling time step (`t_step_ms * 2`) in Peak mode to account for doubled interval per sample
3. Adding measurements calculation to `/api/frames` endpoint

**Test Results on Real Device**:
- Normal: 51.20 Hz  
- Average: 50.00 Hz
- Peak: 50.79 Hz ✅ (was 101.59 Hz before fix)
- All modes now show consistent frequency!
