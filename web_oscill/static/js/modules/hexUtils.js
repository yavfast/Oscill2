/**
 * Utility functions for hex encoding/decoding of sample data
 */

/**
 * Decode hex string to array of integers
 * @param {string} hexStr - Hex string (e.g., "80827D")
 * @param {number} bytesPerSample - Bytes per sample (1 or 2)
 * @returns {number[]} Array of sample values
 */
export function hexToSamples(hexStr, bytesPerSample = 1) {
  if (!hexStr || typeof hexStr !== 'string') {
    return [];
  }
  
  const charsPerSample = bytesPerSample * 2;
  const samples = [];
  
  for (let i = 0; i < hexStr.length; i += charsPerSample) {
    const hexChunk = hexStr.substring(i, i + charsPerSample);
    if (hexChunk.length === charsPerSample) {
      samples.push(parseInt(hexChunk, 16));
    }
  }
  
  return samples;
}

/**
 * Encode array of integers to hex string
 * @param {number[]} samples - Array of sample values
 * @param {number} bytesPerSample - Bytes per sample (1 or 2)
 * @returns {string} Hex string
 */
export function samplesToHex(samples, bytesPerSample = 1) {
  if (!samples || !Array.isArray(samples)) {
    return '';
  }
  
  if (bytesPerSample === 1) {
    return samples.map(s => s.toString(16).padStart(2, '0')).join('');
  } else if (bytesPerSample === 2) {
    return samples.map(s => s.toString(16).padStart(4, '0')).join('');
  }
  
  return samples.map(s => s.toString(16).padStart(2, '0')).join('');
}

/**
 * Process frame with hex-encoded samples and convert to array format
 * @param {object} frame - Frame object that may contain hex-encoded samples
 * @returns {object} Frame object with decoded samples as arrays
 */
export function decodeFrameSamples(frame) {
  if (!frame) {
    return frame;
  }
  
  const sampleBytes = frame.sample_bytes || 1;
  const decoded = { ...frame };
  
  // Decode main samples
  if (frame.samples_hex !== undefined) {
    decoded.samples = hexToSamples(frame.samples_hex, sampleBytes);
    delete decoded.samples_hex;
  }
  
  // Decode peak min
  if (frame.samples_peak_min_hex !== undefined) {
    decoded.samples_peak_min = hexToSamples(frame.samples_peak_min_hex, sampleBytes);
    delete decoded.samples_peak_min_hex;
  }
  
  // Decode peak max
  if (frame.samples_peak_max_hex !== undefined) {
    decoded.samples_peak_max = hexToSamples(frame.samples_peak_max_hex, sampleBytes);
    delete decoded.samples_peak_max_hex;
  }
  
  return decoded;
}

/**
 * Calculate approximate size savings from hex encoding
 * @param {number} sampleCount - Number of samples
 * @param {number} bytesPerSample - Bytes per sample (1 or 2)
 * @returns {object} Size comparison { jsonArray, hexString, savings }
 */
export function calculateSizeSavings(sampleCount, bytesPerSample = 1) {
  // JSON array: "[128,130,125]" - avg ~5 bytes per number (including comma/space)
  const jsonArraySize = sampleCount * 5;
  
  // Hex string: "80827D" - exactly 2 chars per byte
  const hexStringSize = sampleCount * bytesPerSample * 2;
  
  const savings = jsonArraySize - hexStringSize;
  const savingsPercent = ((savings / jsonArraySize) * 100).toFixed(1);
  
  return {
    jsonArray: jsonArraySize,
    hexString: hexStringSize,
    savings,
    savingsPercent: `${savingsPercent}%`
  };
}
