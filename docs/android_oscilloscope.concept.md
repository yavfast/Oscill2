# Concept: Android Oscilloscope App (C_AOS)

> **ID:** C_AOS
> **Status:** active
> **Area:** Android app
> **Changelog:** Initialized from existing codebase via onboard procedure (2026-04-22)

## Philosophy

The Android app is the original oscilloscope client — a native Android application that connects directly to the device over USB (no Python server in the middle). It provides a real-time waveform display on a phone/tablet screen, with the oscilloscope connected via USB OTG. The architecture uses a static orchestrator (OscillManager) and an event bus to keep the UI layer decoupled from device logic.

## Domain Model

| Entity | Description |
|--------|-------------|
| Oscill | Low-level device: OBEX register read/write, frame acquisition, device properties |
| OscillConfig | Composition of all typed config parameters (V1, TS, MC, O1, M1, etc.) |
| OscillData | One acquired and parsed frame: iData (raw), vData (voltages), frequency, stats |
| OscillManager | Static singleton: connection lifecycle, acquisition loop, event broadcasting |
| Sync Queue | Dedicated serial thread for all device operations |
| Event Bus | EventsController: OnOscillConnected, OnOscillData, OnOscillError, OnOscillConfigChanged |
| Config Parameter | Typed class per register: BaseOscillSetting subclasses in controller/config/ |

## Mechanisms

**USB connection:** Android UsbManager detects the CP210x USB serial device, requests permission, creates UsbObexTransport, which wraps the USB port as an OBEX transport. ClientSession runs the OBEX protocol over this transport.

**Config parameter hierarchy:** Each device register is a Java class (e.g., ChannelSensitivity wraps V1 register). OscillConfig composes all 14+ config classes. Changes go through `OscillManager.runConfigTask()` which serializes them on the sync queue and broadcasts OnOscillConfigChanged.

**Acquisition loop:** OscillManager.start() queues a self-rescheduling task on the sync queue that calls `OscillConfig.requestData()`, parses the result into OscillData, and sends OnOscillData events to MainActivity for rendering.

**Signal analysis:** OscillData computes frequency via the same segment-counting algorithm as Python's calculations.py. An FFT path exists (math.fft.Fourier) but the segment method is the primary one.

## Integration Points

- **Depends on:** Android USB APIs, usbserial driver library (in-tree)
- **Used by:** Single user on Android device with USB OTG to oscilloscope
- **Independent of:** Python backend, web frontend
