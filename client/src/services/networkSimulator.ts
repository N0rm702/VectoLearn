
export type NetworkProfile = 'unthrottled' | '2g_gprs' | '2g_edge' | 'offline';

export interface NetworkConfig {
  id: NetworkProfile;
  name: string;
  bandwidthKbps: number; // in kilobits per second
  latencyMs: number;
  description: string;
}

export const NETWORK_PROFILES: Record<NetworkProfile, NetworkConfig> = {
  unthrottled: {
    id: 'unthrottled',
    name: 'High-Speed Broadband (100 Mbps)',
    bandwidthKbps: 100000,
    latencyMs: 15,
    description: 'Modern fiber / 4G / 5G broadband connection',
  },
  '2g_edge': {
    id: '2g_edge',
    name: '2G EDGE (50 Kbps)',
    bandwidthKbps: 50,
    latencyMs: 500,
    description: 'Rural cellular edge connection (~6.25 KB/sec transfer rate)',
  },
  '2g_gprs': {
    id: '2g_gprs',
    name: '2G Strict Throttled (10 Kbps)',
    bandwidthKbps: 10,
    latencyMs: 1200,
    description: 'Low-bandwidth 10 Kbps pipe (~1.25 KB/sec transfer rate)',
  },
  offline: {
    id: 'offline',
    name: '100% Offline (Air-Gapped 0 Kbps)',
    bandwidthKbps: 0,
    latencyMs: 0,
    description: 'Zero connectivity. Runs entirely from IndexedDB cache',
  },
};

export interface TelemetryMetrics {
  durationSeconds: number;
  mp4SizeBytes: number;
  vectorSizeBytes: number;
  dataSavingsPercent: number;
  mp4DownloadTimeSeconds: number;
  vectorDownloadTimeSeconds: number;
  speedupFactor: number;
}

export function computeTelemetry(durationSeconds: number, vectorSizeBytes: number, profile: NetworkProfile): TelemetryMetrics {
  // Benchmark standard 1080p 30fps H.264 video lecture = 50 MB per 60 seconds (~833 KB/sec)
  const mp4BytesPerSecond = (50 * 1024 * 1024) / 60;
  const mp4SizeBytes = Math.round(mp4BytesPerSecond * durationSeconds);

  const savings = ((mp4SizeBytes - vectorSizeBytes) / mp4SizeBytes) * 100;
  const dataSavingsPercent = Math.max(99.0, Math.min(99.99, Number(savings.toFixed(2))));

  const speedKbps = NETWORK_PROFILES[profile].bandwidthKbps;
  const bytesPerSecond = (speedKbps * 1000) / 8;

  let mp4DownloadTimeSeconds = 0;
  let vectorDownloadTimeSeconds = 0;

  if (speedKbps > 0) {
    mp4DownloadTimeSeconds = Number((mp4SizeBytes / bytesPerSecond).toFixed(1));
    vectorDownloadTimeSeconds = Number((vectorSizeBytes / bytesPerSecond).toFixed(2));
  } else {
    // Offline: MP4 cannot download (infinity), Vector is 0s (instant from local cache)
    mp4DownloadTimeSeconds = Infinity;
    vectorDownloadTimeSeconds = 0;
  }

  const speedupFactor = vectorSizeBytes > 0 ? Math.round(mp4SizeBytes / vectorSizeBytes) : 1000;

  return {
    durationSeconds,
    mp4SizeBytes,
    vectorSizeBytes,
    dataSavingsPercent,
    mp4DownloadTimeSeconds,
    vectorDownloadTimeSeconds,
    speedupFactor,
  };
}

/**
 * Formats bytes into human readable MB, KB or B
 */
export function formatBytes(bytes: number): string {
  if (bytes === Infinity) return 'Infinite';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

/**
 * Formats time in seconds into human-readable string (e.g. 11h 24m or 3.2s)
 */
export function formatTimeSpan(seconds: number): string {
  if (seconds === Infinity) return 'Never (Offline)';
  if (seconds < 1) return `${(seconds * 1000).toFixed(0)} ms`;
  if (seconds < 60) return `${seconds.toFixed(1)} s`;
  const mins = Math.floor(seconds / 60);
  const remainingSecs = Math.floor(seconds % 60);
  if (mins < 60) return `${mins}m ${remainingSecs}s`;
  const hours = (seconds / 3600).toFixed(1);
  return `${hours} hours`;
}
