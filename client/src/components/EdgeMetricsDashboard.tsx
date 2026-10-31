import React, { useState } from 'react';
import type { NetworkProfile } from '../services/networkSimulator';
import {
  NETWORK_PROFILES,
  computeTelemetry,
  formatBytes,
  formatTimeSpan,
} from '../services/networkSimulator';
import {
  Wifi,
  Radio,
  WifiOff,
  TrendingDown,
  HardDrive,
  Download,
  CheckCircle2,
  Clock,
  Sparkles,
  Zap,
} from 'lucide-react';

interface EdgeMetricsDashboardProps {
  durationSeconds: number;
  binarySizeBytes: number;
  onSimulateDownload?: (profile: NetworkProfile) => Promise<void>;
}

export const EdgeMetricsDashboard: React.FC<EdgeMetricsDashboardProps> = ({
  durationSeconds,
  binarySizeBytes,
  onSimulateDownload,
}) => {
  const [selectedProfile, setSelectedProfile] = useState<NetworkProfile>('2g_gprs');
  const [isSimulating, setIsSimulating] = useState<boolean>(false);
  const [downloadProgress, setDownloadProgress] = useState<number>(100);
  const [transferredBytes, setTransferredBytes] = useState<number>(binarySizeBytes);

  const telemetry = computeTelemetry(durationSeconds, binarySizeBytes, selectedProfile);

  const runSimulation = async () => {
    setIsSimulating(true);
    setDownloadProgress(0);
    setTransferredBytes(0);

    const speedKbps = NETWORK_PROFILES[selectedProfile].bandwidthKbps;
    if (speedKbps === 0) {
      // Offline: instant retrieval from IndexedDB
      setTimeout(() => {
        setDownloadProgress(100);
        setTransferredBytes(binarySizeBytes);
        setIsSimulating(false);
      }, 300);
      return;
    }

    const bytesPerSecond = (speedKbps * 1000) / 8;
    const totalBytes = binarySizeBytes;
    const intervalMs = 100;
    const bytesPerInterval = (bytesPerSecond * intervalMs) / 1000;

    let current = 0;
    const timer = setInterval(() => {
      current += bytesPerInterval;
      if (current >= totalBytes) {
        current = totalBytes;
        clearInterval(timer);
        setDownloadProgress(100);
        setTransferredBytes(totalBytes);
        setIsSimulating(false);
      } else {
        setTransferredBytes(Math.round(current));
        setDownloadProgress(Math.round((current / totalBytes) * 100));
      }
    }, intervalMs);

    if (onSimulateDownload) {
      await onSimulateDownload(selectedProfile);
    }
  };

  return (
    <div className="minimal-card p-6 rounded-2xl w-full shadow-sm flex flex-col gap-6">
      {/* Top Banner */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-100">
        <div>
          <div className="flex items-center gap-2">
            <Radio className="w-5 h-5 text-slate-700" />
            <h3 className="text-base font-semibold text-slate-900 tracking-tight">
              Edge Telemetry & Transmission
            </h3>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Real-time payload efficiency comparing legacy 1080p MP4 vs. ByteClass vector payloads
          </p>
        </div>

        {/* Footprint Reduction Badge */}
        <div className="flex items-center gap-2 bg-emerald-50 text-emerald-800 border border-emerald-200 px-3.5 py-1.5 rounded-xl font-medium">
          <TrendingDown className="w-4 h-4 text-emerald-700" />
          <span className="text-sm font-mono font-bold">
            {telemetry.dataSavingsPercent}% FOOTPRINT REDUCTION
          </span>
        </div>
      </div>

      {/* Primary Metrics Comparison Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Legacy MP4 Card */}
        <div className="bg-slate-50 border border-slate-200 p-4 rounded-xl flex flex-col justify-between">
          <div>
            <div className="text-xs font-mono uppercase text-slate-500 flex items-center justify-between">
              <span>Legacy MP4 Video</span>
              <span className="text-[10px] bg-rose-50 text-rose-700 px-1.5 py-0.5 rounded border border-rose-200 font-medium">
                50 MB / min
              </span>
            </div>
            <div className="text-2xl font-mono font-bold text-rose-700 mt-2">
              {formatBytes(telemetry.mp4SizeBytes)}
            </div>
            <p className="text-[11px] text-slate-500 mt-1">
              Standard H.264 video buffer footprint for {durationSeconds.toFixed(0)}s runtime.
            </p>
          </div>
          <div className="mt-4 pt-3 border-t border-slate-200 text-xs font-mono text-slate-500 flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-rose-600" />
            <span>2G Transfer: </span>
            <span className="text-rose-700 font-semibold">
              {formatTimeSpan(telemetry.mp4DownloadTimeSeconds)}
            </span>
          </div>
        </div>

        {/* ByteClass Vector Card */}
        <div className="bg-blue-50/50 border border-blue-200 p-4 rounded-xl flex flex-col justify-between relative overflow-hidden">
          <div>
            <div className="text-xs font-mono uppercase text-blue-900 flex items-center justify-between">
              <span className="flex items-center gap-1 font-semibold">
                <Sparkles className="w-3.5 h-3.5 text-blue-600" /> ByteClass .bin Payload
              </span>
              <span className="text-[10px] bg-blue-100 text-blue-800 px-1.5 py-0.5 rounded border border-blue-200 font-medium">
                &lt; 50 KB / min
              </span>
            </div>
            <div className="text-2xl font-mono font-bold text-blue-700 mt-2">
              {formatBytes(telemetry.vectorSizeBytes)}
            </div>
            <p className="text-[11px] text-slate-600 mt-1">
              Protobuf binary array with synchronized SVG vectors & speech markers.
            </p>
          </div>
          <div className="mt-4 pt-3 border-t border-blue-100 text-xs font-mono text-blue-800 flex items-center gap-1.5">
            <Zap className="w-3.5 h-3.5 text-blue-600" />
            <span>2G Transfer: </span>
            <span className="text-blue-900 font-bold">
              {formatTimeSpan(telemetry.vectorDownloadTimeSeconds)}
            </span>
          </div>
        </div>

        {/* Compression Multiplier Card */}
        <div className="bg-slate-50 border border-slate-200 p-4 rounded-xl flex flex-col justify-between">
          <div>
            <div className="text-xs font-mono uppercase text-slate-500">Bandwidth Efficiency</div>
            <div className="text-2xl font-mono font-bold text-slate-900 mt-2">
              {telemetry.speedupFactor}x Smaller
            </div>
            <p className="text-[11px] text-slate-500 mt-1">
              Transmittable even over rural intermittent 2G GSM cellular signals.
            </p>
          </div>
          <div className="mt-4 pt-3 border-t border-slate-200 text-xs font-mono text-slate-600 flex items-center gap-1.5">
            <HardDrive className="w-3.5 h-3.5 text-slate-500" />
            <span>Local IndexedDB: </span>
            <span className="text-slate-900 font-medium">100% Offline Ready</span>
          </div>
        </div>
      </div>

      {/* Network Profile Selector & Live Pipe Simulation */}
      <div className="bg-slate-50 border border-slate-200 p-4 rounded-xl flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="text-xs font-mono uppercase text-slate-500 tracking-wider">
            Simulate Cellular Transmission Pipe:
          </span>

          {/* Network Switcher Buttons */}
          <div className="flex flex-wrap gap-1 bg-white p-1 rounded-xl border border-slate-200 shadow-sm">
            {(Object.keys(NETWORK_PROFILES) as NetworkProfile[]).map((profKey) => {
              const prof = NETWORK_PROFILES[profKey];
              const isSelected = selectedProfile === profKey;
              return (
                <button
                  key={profKey}
                  onClick={() => setSelectedProfile(profKey)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-mono transition-all flex items-center gap-1.5 cursor-pointer ${
                    isSelected
                      ? 'bg-slate-900 text-white font-medium shadow-sm'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                  }`}
                >
                  {profKey === 'offline' ? (
                    <WifiOff className="w-3.5 h-3.5" />
                  ) : profKey.startsWith('2g') ? (
                    <Radio className="w-3.5 h-3.5" />
                  ) : (
                    <Wifi className="w-3.5 h-3.5" />
                  )}
                  <span>{prof.name.split(' (')[0]}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Selected pipe description */}
        <div className="flex flex-wrap items-center justify-between text-xs font-mono text-slate-600 bg-white p-2.5 rounded-lg border border-slate-200">
          <span>{NETWORK_PROFILES[selectedProfile].description}</span>
          <span className="text-slate-900 font-semibold">
            Speed: {NETWORK_PROFILES[selectedProfile].bandwidthKbps} Kbps
          </span>
        </div>

        {/* Simulation Transfer Trigger */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="text-slate-700">
              Payload Delivery Status:{' '}
              {isSimulating ? (
                <span className="text-amber-700">Streaming packets...</span>
              ) : downloadProgress === 100 ? (
                <span className="text-emerald-700 flex-inline items-center gap-1">
                  Cached in IndexedDB <CheckCircle2 className="w-3.5 h-3.5 inline text-emerald-600" />
                </span>
              ) : (
                <span className="text-slate-500">Ready for transfer test</span>
              )}
            </span>
            <span className="text-slate-900 font-semibold">
              {formatBytes(transferredBytes)} / {formatBytes(binarySizeBytes)} ({downloadProgress}%)
            </span>
          </div>

          {/* Progress bar */}
          <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden">
            <div
              className="bg-slate-900 h-full rounded-full transition-all duration-150"
              style={{ width: `${downloadProgress}%` }}
            />
          </div>

          <div className="flex justify-end mt-1">
            <button
              onClick={runSimulation}
              disabled={isSimulating}
              className="px-4 py-1.5 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white text-xs font-mono rounded-lg transition-colors flex items-center gap-2 cursor-pointer shadow-sm"
            >
              <Download className="w-3.5 h-3.5" />
              <span>{isSimulating ? 'Simulating Transmission...' : 'Test Transmission Benchmark'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
