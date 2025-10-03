import { ApiService } from './js/modules/api.js';
import { ScopeView } from './js/modules/scopeView.js';
import { ControlPanel } from './js/modules/controlPanel.js';
import { StatusBar } from './js/modules/statusBar.js';
import { MeasurementPanel } from './js/modules/measurementPanel.js';

class App {
  constructor() {
    this.api = new ApiService();
    this.scopeView = new ScopeView('scope-view');
    this.controlPanel = new ControlPanel(
      this.onConfigChange.bind(this),
      this.onAcquisitionChange.bind(this),
      this.handleAutoAdjust.bind(this)
    );
    this.statusBar = new StatusBar();
    this.measurementPanel = new MeasurementPanel();
    this.isRunning = false;
    this.pollInterval = null;
    this.statusInterval = null;
    this.currentCfgId = null; // Track current config ID
    this.isDeviceConnected = false; // Track device connection status
    this.frameRequestInFlight = false; // Guard to avoid overlapping frame requests
    this.autoAdjustInProgress = false; // Guard for auto-adjust operations
  }

  async init() {
    // Apply absolute layout before initializing Konva components
    this.applyAbsoluteLayout();
    // Keep layout stable on window resize
    window.addEventListener('resize', () => this.applyAbsoluteLayout());

    this.scopeView.init();
    this.controlPanel.init();

    // Connect scope view trigger level changes: callback fires on mouseup (end of drag)
    this.scopeView.setTriggerLevelChangeCallback((level) => {
      // Send config only after drag completes
      this.onConfigChange({ trigger_level: level });
    });

    // Connect scope view v_offset changes: callback fires on mouseup (end of drag)
    this.scopeView.setVOffsetChangeCallback((vOffset) => {
      this.onConfigChange({ v_offset: vOffset });
    });

    // Connect scope view t_offset changes: callback fires on mouseup (end of drag)
    this.scopeView.setTOffsetChangeCallback((tOffset) => {
      this.onConfigChange({ t_offset: tOffset });
    });

    // Connect control panel trigger level changes to scope view
    this.controlPanel.setTriggerLevelChangeCallback((level) => {
      this.scopeView.setTriggerLevel(level);
    });
    
    // Auto-connect and initialize on page load
    await this.autoConnectAndStart();
  }

  async autoConnectAndStart() {
    console.log('[App] Auto-connecting on page load...');
    
    try {
      // 1. Try to connect (will auto-detect device or return current status if already connected)
      const connectResult = await this.api.connect();
      console.log('[App] Connect result:', connectResult);
      
      if (connectResult.status === 'ok' && connectResult.is_connected) {
        this.isDeviceConnected = true;
        
        // 2. Apply saved configuration (if any)
        const savedConfig = this.loadSavedConfig();
        if (savedConfig && Object.keys(savedConfig).length > 0) {
          console.log('[App] Applying saved config:', savedConfig);
          try {
            await this.api.applyConfig(savedConfig);
          } catch (e) {
            console.warn('[App] Failed to apply saved config:', e);
          }
        }
        
        // 3. Get current status to update UI
        const status = await this.api.getStatus();
        this.updateStatus(status);
        
        // 4. Automatically start acquisition
        console.log('[App] Starting acquisition...');
        await this.api.start();
        this.isRunning = true;
        this.controlPanel.setAcquisitionState('run');
        
        // 5. Start polling for frames
        this.startPolling();
        
        console.log('[App] Auto-connect and start complete');
      } else {
        console.log('[App] Device not connected, manual connection required');
        // Try to get status anyway
        try {
          const status = await this.api.getStatus();
          this.updateStatus(status);
        } catch (e) {
          console.log('[App] Status check failed:', e);
        }
      }
    } catch (e) {
      console.error('[App] Auto-connect failed:', e);
      // Still try to get status
      try {
        const status = await this.api.getStatus();
        this.updateStatus(status);
      } catch (statusErr) {
        console.log('[App] Status check failed:', statusErr);
      }
    }
  }

  loadSavedConfig() {
    // Load configuration from localStorage
    try {
      const saved = localStorage.getItem('oscill_config');
      if (saved) {
        const config = JSON.parse(saved);
        console.log('[App] Loaded saved config from localStorage');
        return config;
      }
    } catch (e) {
      console.warn('[App] Failed to load saved config:', e);
    }
    return null;
  }

  saveConfig(config) {
    // Save configuration to localStorage
    try {
      localStorage.setItem('oscill_config', JSON.stringify(config));
      console.log('[App] Saved config to localStorage');
    } catch (e) {
      console.warn('[App] Failed to save config:', e);
    }
  }

  applyAbsoluteLayout() {
    const ww = window.innerWidth || document.documentElement.clientWidth;
    const wh = window.innerHeight || document.documentElement.clientHeight;

    const STATUS_H = 40; // status bar height
    const RIGHT_W = 320; // control panel width
    const MEAS_H = 72;   // measurement panel height

    const statusBar = document.getElementById('status-bar');
    const statusCanvas = document.getElementById('status-canvas');
    const mainArea = document.getElementById('main-area');
    const leftPane = document.getElementById('left-pane');
    const controlPanel = document.getElementById('control-panel');
    const scopeView = document.getElementById('scope-view');
    const measurementPanel = document.getElementById('measurement-panel');

    if (!statusBar || !mainArea || !leftPane || !controlPanel || !scopeView || !measurementPanel) return;

    // Status bar
    statusBar.style.height = `${STATUS_H}px`;
    if (statusCanvas) statusCanvas.style.height = `${STATUS_H}px`;

    // Main area sizes
    const mainH = Math.max(0, wh - STATUS_H);
    const leftW = Math.max(0, ww - RIGHT_W);
    mainArea.style.height = `${mainH}px`;
    leftPane.style.width = `${leftW}px`;
    leftPane.style.height = `${mainH}px`;

    controlPanel.style.width = `${RIGHT_W}px`;
    controlPanel.style.minWidth = `${RIGHT_W}px`;
    controlPanel.style.maxWidth = `${RIGHT_W}px`;
    controlPanel.style.height = `${mainH}px`;

    // Left pane children
    const scopeH = Math.max(120, mainH - MEAS_H);
    scopeView.style.width = `${leftW}px`;
    scopeView.style.height = `${scopeH}px`;
    measurementPanel.style.width = `${leftW}px`;
    measurementPanel.style.height = `${MEAS_H}px`;
  }

  startPolling() {
    if (this.pollInterval) clearInterval(this.pollInterval);
    this.pollInterval = setInterval(async () => {
      // Avoid launching new request if:
      // 1) Acquisition stopped
      // 2) Previous request still in flight (prevents duplicates you observed)
      if (!this.isRunning || this.frameRequestInFlight) return;

      this.frameRequestInFlight = true;
      try {
        const lastSeq = this.api.getLastSeq();
        const data = await this.api.getFrames(lastSeq);
        this.handleFrameResponse(data);
      } catch (e) {
        console.error('Polling error:', e);
      } finally {
        this.frameRequestInFlight = false;
      }
    }, 100); // 10 Hz
  }

  stopPolling() {
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
      this.pollInterval = null;
    }
    this.frameRequestInFlight = false; // Reset guard
  }

  async acquireSingleFrame() {
    if (this.isRunning || this.frameRequestInFlight) {
      console.warn('Single acquisition request ignored while busy');
      return;
    }

    const startTimeSec = Date.now() / 1000;
    let baselineSeq = this.api.getLastSeq();
    this.frameRequestInFlight = true;
    this.controlPanel.setSingleEnabled(false);
    let didStart = false;

    try {
      await this.api.start();
      didStart = true;
      this.isRunning = true;
      this.controlPanel.setAcquisitionState('run');

      let data = null;
      for (let attempt = 0; attempt < 10; attempt++) {
        if (attempt > 0) await this.delay(100);
        const response = await this.api.getFrames(baselineSeq);

        if (typeof response?.newest_seq !== 'undefined') {
          baselineSeq = response.newest_seq;
        }

        const frames = response?.frames || [];
        const freshFrames = frames.filter((fr) => {
          if (typeof fr.time !== 'number') return true;
          return fr.time >= startTimeSec;
        });

        if (freshFrames.length > 0) {
          data = { ...response, frames: freshFrames };
          break;
        }

        await this.delay(80);
      }

      if (data && data.frames.length > 0) {
        this.handleFrameResponse(data);
      } else {
        console.warn('Single acquisition did not produce a fresh frame');
      }
    } catch (e) {
      console.error('Single acquisition error:', e);
    } finally {
      if (didStart) {
        try {
          await this.api.stop();
        } catch (e) {
          console.error('Stop acquisition error:', e);
        }
      }
      this.isRunning = false;
      this.controlPanel.setAcquisitionState('stop');
      this.frameRequestInFlight = false;
    }
  }

  updateStatus(status) {
    const wasConnected = this.isDeviceConnected;
    this.isDeviceConnected = status?.is_connected || false;
    const wasRunning = this.isRunning;
    this.isRunning = status?.is_acquiring || false;

    console.log('Status update:', { status: status?.status, is_connected: status?.is_connected, is_acquiring: status?.is_acquiring, wasConnected, isNowConnected: this.isDeviceConnected, wasRunning, isNowRunning: this.isRunning });

    this.statusBar.updateStatus(status, status?.config);

    // Start/stop frame polling based on connection and acquisition status
    if (this.isDeviceConnected && !wasConnected) {
      // Device just became connected - start frame polling
      console.log('Device connected - starting frame polling');
      this.startPolling();
    } else if (!this.isDeviceConnected && wasConnected) {
      // Device just disconnected - stop frame polling
      console.log('Device disconnected - stopping frame polling');
      this.stopPolling();
      this.onDeviceDisconnected();
    }

    // Update acquisition state based on server status
    if (this.isRunning !== wasRunning) {
      this.controlPanel.setAcquisitionState(this.isRunning ? 'run' : 'stop');
    }

    if (status?.config) {
      // Update current config ID
      if (status.config.cfg_id !== undefined) {
        this.currentCfgId = status.config.cfg_id;
      }
      this.controlPanel.updateControls(status.config);
      // Update scope view trigger level
      if (typeof status.config.trigger_level === 'number') {
        if (!this.scopeView.isDraggingTrigger) {
          this.scopeView.setTriggerLevel(status.config.trigger_level);
        }
      }
    }
  }

  async onConfigChange(changes) {
    // Stop frame polling during config change
    const wasPolling = !!this.pollInterval;
    if (wasPolling) {
      this.stopPolling();
    }
    
    try {
      const response = await this.api.applyConfig(changes);
      
      if (response.config) {
        // Update current config ID
        if (response.config.cfg_id !== undefined) {
          this.currentCfgId = response.config.cfg_id;
        }
        this.controlPanel.updateControls(response.config);
        this.statusBar.updateStatus(null, response.config);
        
        // Save the updated configuration to localStorage
        this.saveConfig(changes);
      }
      
      // Always request one frame to update UI after config change
      if (this.isDeviceConnected) {
        console.log('[App] Requesting frame after config change (isRunning:', this.isRunning, ')');
        try {
          const lastSeq = this.api.getLastSeq();
          const data = await this.api.getFrames(lastSeq);
          this.handleFrameResponse(data);
        } catch (e) {
          console.error('Frame request after config change failed:', e);
        }
      }
      
      // Resume frame polling if it was running and device is still connected
      if (wasPolling && this.isDeviceConnected && this.isRunning) {
        this.startPolling();
      }
    } catch (e) {
      console.error('Config change error:', e);
      
      // Resume frame polling even on error if it was running
      if (wasPolling && this.isDeviceConnected && this.isRunning) {
        this.startPolling();
      }
    }
  }

  async handleAutoAdjust(types) {
    console.log(`[App] handleAutoAdjust called with types: ${types}`);
    
    if (this.autoAdjustInProgress) {
      console.warn('[App] Auto-adjust already in progress');
      return;
    }

    if (!this.isDeviceConnected) {
      console.warn('[App] Cannot auto-adjust: device not connected');
      return;
    }

    console.log(`[App] Starting auto-adjust: ${types}`);
    this.autoAdjustInProgress = true;
    
    // Stop polling during auto-adjust
    const wasPolling = this.pollInterval !== null;
    if (wasPolling) {
      this.stopPolling();
    }

    try {
      // Call auto-adjust API
      const response = await fetch(`/api/auto?types=${types}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!response.ok) {
        const error = await response.text();
        throw new Error(`Auto-adjust failed: ${error}`);
      }

      const result = await response.json();
      console.log('[App] Auto-adjust result:', result);

      if (result.success) {
        // Update UI with new configuration
        if (result.config) {
          // Update current config ID
          if (result.config.cfg_id !== undefined) {
            this.currentCfgId = result.config.cfg_id;
          }
          this.controlPanel.updateControls(result.config);
          this.scopeView.updateConfig(result.config);
          this.statusBar.updateStatus(null, result.config);
          
          // Save the updated configuration to localStorage
          this.saveConfig(result.config);
        }

        // Log results
        const applied = result.applied || [];
        const iterations = result.iterations || {};
        console.log(`[App] Auto-adjust complete: applied ${applied.join(', ')}`);
        
        applied.forEach(type => {
          const iter = iterations[type] || 0;
          console.log(`  - ${type}: ${iter} iteration(s)`);
        });
        
        // Always request one frame to update UI after auto-adjust
        if (this.isDeviceConnected) {
          console.log('[App] Requesting frame after auto-adjust');
          try {
            const lastSeq = this.api.getLastSeq();
            const data = await this.api.getFrames(lastSeq);
            this.handleFrameResponse(data);
          } catch (e) {
            console.error('Frame request after auto-adjust failed:', e);
          }
        }
      } else {
        console.warn('[App] Auto-adjust reported failure:', result);
      }

    } catch (e) {
      console.error('[App] Auto-adjust error:', e);
    } finally {
      this.autoAdjustInProgress = false;
      
      // Resume polling if it was running
      if (wasPolling && this.isDeviceConnected && this.isRunning) {
        this.startPolling();
      }
    }
  }

  async onAcquisitionChange(action) {
    if (action === 'run') {
      console.log('[App] Starting acquisition...');
      try {
        await this.api.start();
        this.isRunning = true;
        // Start polling when acquisition starts
        this.startPolling();
        console.log('[App] Acquisition started and polling resumed');
      } catch (e) {
        console.error('Start acquisition error:', e);
      }
    } else if (action === 'stop') {
      console.log('[App] Stopping acquisition...');
      try {
        await this.api.stop();
        this.isRunning = false;
        // Stop polling when acquisition stops
        this.stopPolling();
        console.log('[App] Acquisition stopped and polling paused');
      } catch (e) {
        console.error('Stop acquisition error:', e);
      }
    } else if (action === 'single') {
      this.acquireSingleFrame();
    }
  }

  onDeviceDisconnected() {
    // Stop acquisition when device disconnects
    this.isRunning = false;
    this.controlPanel.setAcquisitionState('stop');
  }

  handleFrameResponse(data) {
    if (!data) return;

    if (data.frames && data.frames.length > 0) {
      // Sync dragging state between control sliders and scope markers
      const isDraggingVOffsetControl = this.controlPanel.isVOffsetDragging();
      const isDraggingTOffsetControl = this.controlPanel.isTOffsetDragging();
      
      // Update dragging state in scopeView based on control sliders
      if (isDraggingVOffsetControl && !this.scopeView.isDraggingVOffset) {
        this.scopeView.isDraggingVOffset = true;
      } else if (!isDraggingVOffsetControl && this.scopeView.isDraggingVOffset && !this.scopeView.centerYGroup?.isDragging()) {
        this.scopeView.isDraggingVOffset = false;
      }
      
      if (isDraggingTOffsetControl && !this.scopeView.isDraggingTOffset) {
        this.scopeView.isDraggingTOffset = true;
      } else if (!isDraggingTOffsetControl && this.scopeView.isDraggingTOffset && !this.scopeView.centerXGroup?.isDragging()) {
        this.scopeView.isDraggingTOffset = false;
      }
      
      this.scopeView.update(data.frames, data.config || {});
      const latestFrame = data.frames[data.frames.length - 1];
      this.measurementPanel.displayMeasurements(latestFrame.measurements);
    }

    if (data.config) {
      if (data.config.cfg_id !== undefined &&
          (this.currentCfgId === null || data.config.cfg_id >= this.currentCfgId)) {
        this.currentCfgId = data.config.cfg_id;
        
        // Don't update controls if user is dragging
        if (!this.controlPanel.isVOffsetDragging() && 
            !this.controlPanel.isTOffsetDragging() &&
            !this.scopeView.isDraggingVOffset &&
            !this.scopeView.isDraggingTOffset) {
          this.controlPanel.updateControls(data.config);
        }
        
        this.statusBar.updateStatus(null, data.config);
        
        if (typeof data.config.trigger_level === 'number') {
          if (!this.scopeView.isDraggingTrigger) {
            this.scopeView.setTriggerLevel(data.config.trigger_level);
          }
        }
      }
    }
  }

  delay(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  const app = new App();
  app.init();
});
