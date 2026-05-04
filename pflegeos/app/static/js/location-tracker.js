/**
 * Location Tracker - Automatic GPS submission for PflegeOS
 *
 * Usage in HTML:
 * <script src="{{ url_for('static', filename='js/location-tracker.js') }}"></script>
 * <script>
 *   LocationTracker.init({
 *     submitUrl: '{{ url_for("tracking.submit_location") }}',
 *     interval: 30000,  // 30 seconds
 *     autoStart: true
 *   });
 * </script>
 */

const LocationTracker = {
  config: {
    submitUrl: null,
    interval: 30000,  // 30 seconds
    autoStart: false,
    timeout: 10000    // 10 seconds timeout for geolocation
  },

  isTracking: false,
  trackingInterval: null,
  deviceInfo: null,

  /**
   * Initialize the location tracker
   */
  init(options = {}) {
    this.config = { ...this.config, ...options };

    if (this.config.autoStart) {
      this.start();
    }

    // Get device info if available (Capacitor)
    if (typeof window.Capacitor !== 'undefined') {
      this.getDeviceInfo();
    }
  },

  /**
   * Start tracking location
   */
  start() {
    if (this.isTracking) return;

    this.isTracking = true;
    console.log('[LocationTracker] Started location tracking');

    // Submit immediately on start
    this.submitLocation();

    // Then submit periodically
    this.trackingInterval = setInterval(() => {
      this.submitLocation();
    }, this.config.interval);
  },

  /**
   * Stop tracking location
   */
  stop() {
    if (this.trackingInterval) {
      clearInterval(this.trackingInterval);
      this.trackingInterval = null;
    }
    this.isTracking = false;
    console.log('[LocationTracker] Stopped location tracking');
  },

  /**
   * Get device information
   */
  async getDeviceInfo() {
    try {
      if (typeof window.Capacitor !== 'undefined') {
        const { Device } = window.Capacitor.Plugins;
        this.deviceInfo = await Device.getInfo();
      }
    } catch (error) {
      console.log('[LocationTracker] Device info not available');
    }
  },

  /**
   * Submit current location to server
   */
  async submitLocation() {
    if (!this.config.submitUrl) {
      console.warn('[LocationTracker] Submit URL not configured');
      return;
    }

    try {
      const position = await this.getPosition();

      const data = {
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
        accuracy: position.coords.accuracy
      };

      // Add optional fields
      if (position.coords.speed !== null) {
        data.speed = position.coords.speed;
      }
      if (position.coords.heading !== null) {
        data.heading = position.coords.heading;
      }

      // Add device info if available
      if (this.deviceInfo) {
        data.device_mac = this.deviceInfo.identifierForVendor || '';
        data.device_model = this.deviceInfo.model || '';
      }

      const response = await fetch(this.config.submitUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this.getCsrfToken()
        },
        body: JSON.stringify(data)
      });

      if (response.ok) {
        console.log('[LocationTracker] Location submitted successfully');
      } else {
        console.warn('[LocationTracker] Failed to submit location:', response.status);
      }
    } catch (error) {
      console.error('[LocationTracker] Error submitting location:', error);
    }
  },

  /**
   * Get current position using Capacitor or browser Geolocation API
   */
  async getPosition() {
    // Try Capacitor first
    if (typeof window.Capacitor !== 'undefined') {
      try {
        const { Geolocation } = window.Capacitor.Plugins;
        return await Geolocation.getCurrentPosition();
      } catch (error) {
        console.log('[LocationTracker] Capacitor Geolocation failed, falling back to browser API');
      }
    }

    // Fallback to browser Geolocation API
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        reject(new Error('Geolocation not available'));
        return;
      }

      const timeout = setTimeout(() => {
        reject(new Error('Geolocation timeout'));
      }, this.config.timeout);

      navigator.geolocation.getCurrentPosition(
        (position) => {
          clearTimeout(timeout);
          resolve(position);
        },
        (error) => {
          clearTimeout(timeout);
          reject(error);
        },
        {
          enableHighAccuracy: true,
          timeout: this.config.timeout,
          maximumAge: 0
        }
      );
    });
  },

  /**
   * Get CSRF token from DOM
   */
  getCsrfToken() {
    const tokenElement = document.querySelector('input[name="csrf_token"]');
    if (tokenElement) {
      return tokenElement.value;
    }

    // Try to find it in meta tag
    const metaElement = document.querySelector('meta[name="csrf_token"]');
    if (metaElement) {
      return metaElement.getAttribute('content');
    }

    return '';
  }
};

// Export for use
if (typeof module !== 'undefined' && module.exports) {
  module.exports = LocationTracker;
}
