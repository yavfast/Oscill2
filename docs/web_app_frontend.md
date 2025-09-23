# Web App Frontend: Interface Description and Implementation Plan

This document outlines the design and implementation strategy for a modern, functional web-based oscilloscope interface.

## 1. Interface Description

The UI will be a single-page application (SPA) with a dark theme, providing a user experience similar to professional desktop oscilloscope software. The layout is divided into four main sections.

### 1.1. Top: Status Bar

A persistent horizontal bar at the top of the screen.

-   **Content:**
    -   **Connection Status:** An icon and text indicating the device state (e.g., "Disconnected", "Connecting...", "Connected to /dev/ttyUSB0").
    -   **Acquisition Status:** Displays the current state of data acquisition (e.g., "Run", "Stop", "Trig'd").
    -   **Core Parameters:** A quick-view summary of the most critical settings:
        -   Time/Division (e.g., "5 ms/div")
        -   Volts/Division (e.g., "200 mV/div")
        -   Trigger Mode (e.g., "Auto, Rising Edge")

### 1.2. Right: Control Panel

A vertical panel on the right side for all user adjustments. Controls will be grouped logically.

-   **Vertical Controls:**
    -   **Volts/Div:** A control with +/- buttons to cycle through standard V/div settings, displaying the current value.
    -   **Vertical Position:** A slider to adjust the vertical offset of the waveform.
    -   **Input Coupling:** Buttons to select (AC / DC / GND).

-   **Horizontal Controls:**
    -   **Time/Div:** A control with +/- buttons to cycle through standard timebase settings, displaying the current value.
    -   **Horizontal Position:** A slider to adjust the trigger point offset (pre/post-trigger data).

-   **Trigger Controls:**
    -   **Mode:** Buttons to select trigger mode (Auto, Normal, Single).
    -   **Slope:** Buttons for Rising Edge / Falling Edge.
    -   **Trigger Level:** A slider to adjust the trigger voltage level. This will be visually linked to a line on the main scope view.

-   **Acquisition Controls:**
    -   **Run/Stop Button:** Toggles continuous data acquisition.
    -   **Single Button:** Arms the trigger for a single capture.

### 1.3. Bottom: Measurement Panel

A horizontal panel at the bottom to display automated measurements **calculated by the server for each waveform**.

-   **Content:**
    -   **Frequency:** The calculated frequency of the signal.
    -   **Period:** The calculated period (1/frequency).
    -   **Vpp:** Peak-to-peak voltage.
    -   **Vmax:** Maximum voltage.
    -   **Vmin:** Minimum voltage.
    -   **Vavg:** Average voltage of the waveform.

### 1.4. Main Area: Scope View

The central and largest part of the UI, dedicated to visualizing the waveform.

-   **Chart Library:** **Plotly.js** will be used for its high performance and rich feature set for scientific charting.
-   **Grid:** A standard 10x8 (W x H) division grid will be configured within Plotly.
-   **Waveform:** The captured data points will be rendered as a line trace.
-   **Axes:** The vertical and horizontal axes will display labels corresponding to the current V/div and Time/div settings.
-   **Interactive Elements:**
    -   **Trigger Level Indicator:** A draggable horizontal line (a Plotly shape) on the chart, visually representing and controlling the trigger level.
    -   **Vertical Offset Indicator:** A marker on the vertical axis indicating the ground (0V) level, which moves as the user adjusts the vertical position.
    -   **Horizontal Offset Indicator:** A marker on the horizontal axis indicating the time offset, which moves as the user adjusts the horizontal position.

## 2. Data Communication Structure

To ensure a responsive UI with minimal network overhead, we will use a stateful polling mechanism. The client requests new data since its last received frame, and the server responds with only the necessary updates.

### 2.1. Full vs. Incremental Response

-   **Full Response (`/api/frames`):** The initial request from the client will not have a `since` parameter. The server returns the complete device configuration and a buffer of the most recent frames.
-   **Incremental Response (`/api/frames?since=<last_seq>`):** Subsequent requests include the sequence number (`seq`) of the last frame the client received. The server returns only frames newer than `since`. If the device configuration has changed since the last request, the new `config` object is included in the response.

### 2.2. Data Structure Examples

#### Full Response Example
This is sent when the client first connects or requests a full update.

```json
{
  "config": {
    "v_div": { "v": 200, "u": "mV" },
    "t_div": { "v": 0.005, "u": "s" },
    "v_offset": { "v": 0.0, "u": "V" },
    "t_offset": { "v": 0.0, "u": "s" },
    "trigger_level": 128,
    "trigger_mode": 44,
    "samples_per_div": 32
  },
  "frames": [
    {
      "seq": 101,
      "time": 1678886400.1,
      "samples": [128, 130, 135, ... , 126],
      "measurements": {
        "freq": { "v": 1000.5, "u": "Hz" },
        "period": { "v": 0.0009995, "u": "s" },
        "v_pp": { "v": 2.5, "u": "V" },
        "v_max": { "v": 1.25, "u": "V" },
        "v_min": { "v": -1.25, "u": "V" },
        "v_avg": { "v": 0.01, "u": "V" }
      }
    },
    {
      "seq": 102,
      "time": 1678886400.2,
      "samples": [127, 129, 134, ... , 125],
      "measurements": {
        "freq": { "v": 1000.6, "u": "Hz" },
        "period": { "v": 0.0009994, "u": "s" },
        "v_pp": { "v": 2.51, "u": "V" },
        "v_max": { "v": 1.26, "u": "V" },
        "v_min": { "v": -1.25, "u": "V" },
        "v_avg": { "v": 0.01, "u": "V" }
      }
    }
  ],
  "newest_seq": 102
}
```

#### Incremental Response Example
The client has received frames up to `seq: 102`. A new frame arrives, and the user changes the Volts/Div.

```json
{
  "config": {
    "v_div": { "v": 500, "u": "mV" }
  },
  "frames": [
    {
      "seq": 103,
      "time": 1678886400.3,
      "samples": [128, 140, 155, ... , 120],
      "measurements": {
        "freq": { "v": 1000.5, "u": "Hz" },
        "period": { "v": 0.0009995, "u": "s" },
        "v_pp": { "v": 5.1, "u": "V" },
        "v_max": { "v": 2.55, "u": "V" },
        "v_min": { "v": -2.55, "u": "V" },
        "v_avg": { "v": 0.02, "u": "V" }
      }
    }
  ],
  "newest_seq": 103
}
```
*Note: The `config` object in the incremental response only contains the fields that have changed.*

## 3. Implementation Plan

The frontend logic will be modularized to separate concerns, improve maintainability, and facilitate future expansion. We will use plain JavaScript (ES6 modules).

### Step 1: Project Structure and Initial Setup

1.  **Create File Structure:** Organize the `static/` directory with subfolders for JS modules, CSS, and assets.
    -   `static/js/modules/` for individual JavaScript components.
    -   `static/css/` for styles.
    -   `static/assets/` for icons or images.
2.  **Add Plotly.js:** Download the library or link to a CDN in `index.html`.
3.  **Update `index.html`:** Set up the basic HTML structure with `div` containers for the four main UI sections. Link the main CSS file and the main JavaScript entry point (`app.js`).
4.  **Update `styles.css`:** Implement the basic dark theme, layout using CSS Grid or Flexbox, and initial styling for all sections.

### Step 2: API Service Module (`api.js`)

1.  Create `static/js/modules/api.js`.
2.  This module will be responsible for all communication with the backend.
3.  Implement functions:
    -   `getStatus()`: Gets the current device status and configuration.
    -   `applyConfig(changes)`: Sends configuration updates to the device.
    -   `getFrames(since)`: Fetches new waveform data.
    -   `connect(port)` and `disconnect()`: Manages the device connection.

### Step 3: Scope View Module (`scopeView.js`)

1.  Create `static/js/modules/scopeView.js`.
2.  This module will manage the Plotly.js chart.
3.  **Responsibilities:**
    -   Initialize the Plotly chart with a dark theme layout, a 10x8 grid, and initial empty data.
    -   Implement a `update(frames, config)` function that updates the chart's data traces and layout (e.g., axes ranges) based on the new data and configuration.
    -   Implement logic to draw and update the trigger level line using Plotly's `layout.shapes`.
    -   Handle user interactions on the chart (e.g., dragging the trigger line) and emit events.

### Step 4: Control Panel Module (`controlPanel.js`)

1.  Create `static/js/modules/controlPanel.js`.
2.  **Responsibilities:**
    -   Initialize all the control elements (sliders, buttons).
    -   Add event listeners to all controls.
    -   When a control is changed, it will call a function (e.g., from the main `app.js`) to send the update to the backend via `api.js`.
    -   Implement a function `updateControls(config)` to set the state of the controls based on data received from the device.

### Step 5: Status and Measurement Modules (`statusBar.js`, `measurementPanel.js`)

1.  Create `static/js/modules/statusBar.js` and `static/js/modules/measurementPanel.js`.
2.  **`statusBar.js`:**
    -   Implement a function `updateStatus(status)` that updates the text and icons based on the latest device status.
3.  **`measurementPanel.js`:**
    -   Implement a `displayMeasurements(measurements)` function that receives the measurement object and updates the DOM.

### Step 6: Main Application Logic (`app.js`)

1.  This will be the main entry point that orchestrates all other modules.
2.  **Responsibilities:**
    -   Initialize all modules on page load.
    -   Start a main loop (e.g., using `requestAnimationFrame` or `setInterval`) that periodically calls `api.getFrames()` to fetch new data.
    -   When new data arrives:
        -   Pass the waveform data and config to `scopeView.js` to be rendered.
        -   Pass the `measurements` from the latest frame to `measurementPanel.js` to be displayed.
    -   When the device status changes:
        -   Update the `statusBar.js`.
        -   Update the `controlPanel.js` with the current settings.
    -   Handle callbacks from the `controlPanel.js` to apply configuration changes.

### Step 7: Refinement and Debugging

1.  Thoroughly test all UI interactions and ensure they correctly update the device.
2.  Optimize chart updates for smooth, real-time performance.
3.  Refine CSS for a polished and professional look.
