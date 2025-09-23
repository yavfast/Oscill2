import { ApiService } from './js/modules/api.js';
import { ScopeView } from './js/modules/scopeView.js';
import { ControlPanel } from './js/modules/controlPanel.js';
import { StatusBar } from './js/modules/statusBar.js';
import { MeasurementPanel } from './js/modules/measurementPanel.js';

class App {
  constructor() {
    this.api = new ApiService();
    this.scopeView = new ScopeView('scope-view');
    this.controlPanel = new ControlPanel(this.onConfigChange.bind(this), this.onAcquisitionChange.bind(this));
    this.statusBar = new StatusBar();
    this.measurementPanel = new MeasurementPanel();
    this.isRunning = false;
    this.pollInterval = null;
    this.currentCfgId = null; // Track current config ID
    this.lastStatusCheck = null; // Track last status check time
  }

  async init() {
    this.scopeView.init();
    this.controlPanel.init();

    // Try to get initial status
    try {
      const status = await this.api.getStatus();
      this.updateStatus(status);
    } catch (e) {
      console.log('Initial status check failed:', e);
    }

    // Start polling
    this.startPolling();
  }

  startPolling() {
    if (this.pollInterval) clearInterval(this.pollInterval);
    this.pollInterval = setInterval(async () => {
      // Always check status periodically (every 2 seconds)
      const now = Date.now();
      if (!this.lastStatusCheck || now - this.lastStatusCheck > 2000) {
        try {
          const status = await this.api.getStatus();
          this.updateStatus(status);
          this.lastStatusCheck = now;
        } catch (e) {
          console.log('Status check failed:', e);
        }
      }

      if (!this.isRunning) return;

      try {
        const data = await this.api.getFrames(this.api.getLastSeq());
        if (data.frames && data.frames.length > 0) {
          this.scopeView.update(data.frames, data.config || {});
          const latestFrame = data.frames[data.frames.length - 1];
          this.measurementPanel.displayMeasurements(latestFrame.measurements);
        }
        if (data.config) {
          // Update current config ID if it's newer
          if (data.config.cfg_id !== undefined && 
              (this.currentCfgId === null || data.config.cfg_id >= this.currentCfgId)) {
            this.currentCfgId = data.config.cfg_id;
            this.controlPanel.updateControls(data.config);
            this.statusBar.updateStatus(null, data.config);
          }
        }
      } catch (e) {
        console.error('Polling error:', e);
      }
    }, 100); // 10 Hz
  }

  updateStatus(status) {
    this.statusBar.updateStatus(status, status?.config);
    if (status?.config) {
      // Update current config ID
      if (status.config.cfg_id !== undefined) {
        this.currentCfgId = status.config.cfg_id;
      }
      this.controlPanel.updateControls(status.config);
    }
  }

  onConfigChange(changes) {
    this.api.applyConfig(changes).then(response => {
      if (response.config) {
        // Update current config ID
        if (response.config.cfg_id !== undefined) {
          this.currentCfgId = response.config.cfg_id;
        }
        this.controlPanel.updateControls(response.config);
        this.statusBar.updateStatus(null, response.config);
      }
    }).catch(e => {
      console.error('Config change error:', e);
    });
  }

  onAcquisitionChange(action) {
    if (action === 'run') {
      this.isRunning = true;
    } else if (action === 'stop') {
      this.isRunning = false;
    } else if (action === 'single') {
      // For single, we might need to implement single acquisition
    }
  }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  const app = new App();
  app.init();
});
