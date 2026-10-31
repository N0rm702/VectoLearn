import React, { useState, useEffect } from 'react';
import type { LecturePayload, SavedLectureMetadata, LectureFrame } from './types/lecture';
import { FrameAction } from './types/lecture';
import { serializeLectureBinary, deserializeLectureBinary } from './services/protobufDecoder';
import { detectVisualEngine } from './services/visualEngineResolver';
import {
  saveLectureToStorage,
  getAllCachedLectures,
  getLectureById,
  deleteLectureFromStorage,
} from './services/indexedDbStore';
import { OfflineVectorPlayer } from './components/OfflineVectorPlayer';
import { EdgeMetricsDashboard } from './components/EdgeMetricsDashboard';
import { JsonUploadStudio } from './components/JsonUploadStudio';
import { SvgVisualsStudio } from './components/SvgVisualsStudio';
import {
  Volume2,
  ShieldCheck,
  CheckCircle,
  FileJson,
  Upload,
  Layers,
  BookOpen,
  Sparkles,
  Radio,
  Trash2,
  HardDrive,
  Download,
  Play,
  ArrowRight,
} from 'lucide-react';

const YoutubeIcon: React.FC<{ className?: string }> = ({ className = 'w-4 h-4' }) => (
  <svg className={className} viewBox="0 0 24 24" fill="currentColor">
    <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
  </svg>
);

const EMPTY_LECTURE: LecturePayload = {
  lectureId: '',
  topicTitle: '',
  sourceVideoUrl: '',
  sourceType: 'youtube',
  frames: [],
};

type TabType = 'player' | 'offline-library' | 'youtube-links' | 'json-upload' | 'svg-visuals' | 'telemetry';

export const App: React.FC = () => {
  const [currentLecture, setCurrentLecture] = useState<LecturePayload>(EMPTY_LECTURE);
  const [currentBinarySize, setCurrentBinarySize] = useState<number>(0);
  const [cachedLectures, setCachedLectures] = useState<SavedLectureMetadata[]>([]);
  const [activeTab, setActiveTab] = useState<TabType>('player');
  const [voiceName, setVoiceName] = useState<string>('Studio Neutral (Guy Neural)');
  const [activeToast, setActiveToast] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setActiveToast(msg);
    setTimeout(() => setActiveToast(null), 3500);
  };

  // Initialize IndexedDB: Clean out old legacy preloaded demo lessons
  useEffect(() => {
    const initStorage = async () => {
      try {
        let existing = await getAllCachedLectures();

        // Remove old synthetic and preloaded demo lessons
        const legacyPreloadedIds = [
          'photosynthesis-01',
          'bohr-atom-02',
          'dna-double-helix-03',
          'orbital-mechanics-04',
          'yt-3b1b-neural-networks',
          'yt-khan-mitosis',
          'yt-veritasium-speed-of-light',
          'yt-veritasium-double-slit',
        ];
        const foundLegacy = existing.filter((l) => legacyPreloadedIds.includes(l.id) || !l.isCustom);
        if (foundLegacy.length > 0) {
          for (const leg of foundLegacy) {
            await deleteLectureFromStorage(leg.id);
          }
          existing = await getAllCachedLectures();
        }

        setCachedLectures(existing);

        // If user already has cached custom lectures, load the first one
        if (existing.length > 0) {
          const latest = existing[0];
          const cached = await getLectureById(latest.id);
          if (cached) {
            const payload = deserializeLectureBinary(cached.binaryBlob);
            payload.sourceVideoUrl = cached.sourceVideoUrl || payload.sourceVideoUrl;
            payload.sourceType = cached.sourceType || payload.sourceType;
            setCurrentLecture(payload);
          }
        }
      } catch (err) {
        console.warn('IndexedDB initial seed note:', err);
      }
    };

    initStorage();
  }, []);

  // Compute binary size for current lecture
  useEffect(() => {
    try {
      if (currentLecture.frames.length > 0) {
        const bin = serializeLectureBinary(currentLecture);
        setCurrentBinarySize(bin.length);
      } else {
        setCurrentBinarySize(0);
      }
    } catch (err) {
      console.warn('Protobuf size calculation warning:', err);
      setCurrentBinarySize(0);
    }
  }, [currentLecture]);

  // Active Studio Neutral Voice
  useEffect(() => {
    setVoiceName('Studio Neutral (Guy Neural)');
  }, []);

  const selectLectureById = async (id: string) => {
    try {
      const cached = await getLectureById(id);
      if (cached) {
        const payload = deserializeLectureBinary(cached.binaryBlob);
        payload.sourceVideoUrl = cached.sourceVideoUrl || payload.sourceVideoUrl;
        payload.sourceType = cached.sourceType || payload.sourceType;
        setCurrentLecture(payload);
        showToast(`Loaded "${cached.title}" from IndexedDB (0 KB Network)`);
        setActiveTab('player');
        return;
      }
    } catch (err) {
      console.warn('Local storage retrieval error:', err);
    }
  };

  const handleDeleteCached = async (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    try {
      await deleteLectureFromStorage(id);
      const remaining = await getAllCachedLectures();
      setCachedLectures(remaining);
      if (currentLecture.lectureId === id) {
        if (remaining.length > 0) {
          selectLectureById(remaining[0].id);
        } else {
          setCurrentLecture(EMPTY_LECTURE);
        }
      }
      showToast('Removed lesson from cache');
    } catch (err) {
      console.warn('Failed to delete cached lecture:', err);
    }
  };

  const handleLoadCustomLecture = async (payload: LecturePayload, binaryData: Uint8Array) => {
    setCurrentLecture(payload);
    const duration = payload.frames.length > 0
      ? Math.max(...payload.frames.map((f) => f.timestampSeconds)) + 25.0
      : 60.0;
    const mp4Bytes = Math.round(((50 * 1024 * 1024) / 60) * duration);

    try {
      await saveLectureToStorage({
        id: payload.lectureId,
        title: payload.topicTitle,
        sourceVideoUrl: payload.sourceVideoUrl || '',
        sourceType: payload.sourceVideoUrl ? 'youtube' : 'json_file',
        frameCount: payload.frames.length,
        durationSeconds: duration,
        binarySizeBytes: binaryData.length,
        mp4EquivalentBytes: mp4Bytes,
        compressionRatio: Number((((mp4Bytes - binaryData.length) / mp4Bytes) * 100).toFixed(2)),
        createdAt: new Date().toISOString(),
        binaryBlob: binaryData.buffer as ArrayBuffer,
        isCustom: true,
      });

      const updated = await getAllCachedLectures();
      setCachedLectures(updated);
      showToast(`Saved "${payload.topicTitle}" into offline cache`);
    } catch (err) {
      console.warn('Could not cache custom lecture to IndexedDB:', err);
    }

    setActiveTab('player');
  };

  const handleInjectCustomSvg = (svgMarkup: string, label: string) => {
    const engine = detectVisualEngine(svgMarkup);
    const newFrame: LectureFrame = {
      timestampSeconds: 0.0,
      spokenText: label,
      actionType: FrameAction.INJECT_NEW_VECTOR,
      svgPayload: svgMarkup,
      visualEngine: engine,
    };
    const updatedLecture: LecturePayload = {
      ...currentLecture,
      topicTitle: currentLecture.topicTitle ? `${currentLecture.topicTitle} (Custom Visual)` : 'Custom Visual Model',
      frames: [newFrame, ...currentLecture.frames],
    };
    setCurrentLecture(updatedLecture);
    setActiveTab('player');
    showToast(`Injected custom ${engine.toUpperCase()} visual into player stage!`);
  };

  const isCurrentLectureSaved = Boolean(
    currentLecture.lectureId && cachedLectures.some((l) => l.id === currentLecture.lectureId)
  );

  const handleSaveCurrentLectureToOffline = async () => {
    if (!currentLecture.lectureId || currentLecture.frames.length === 0) {
      showToast('No active lesson data to save');
      return;
    }
    try {
      const binaryData = serializeLectureBinary(currentLecture);
      const duration = Math.max(...currentLecture.frames.map((f) => f.timestampSeconds)) + 25.0;
      const mp4Bytes = Math.round(((50 * 1024 * 1024) / 60) * duration);

      await saveLectureToStorage({
        id: currentLecture.lectureId,
        title: currentLecture.topicTitle,
        sourceVideoUrl: currentLecture.sourceVideoUrl || '',
        sourceType: currentLecture.sourceVideoUrl ? 'youtube' : 'json_file',
        frameCount: currentLecture.frames.length,
        durationSeconds: duration,
        binarySizeBytes: binaryData.length,
        mp4EquivalentBytes: mp4Bytes,
        compressionRatio: Number((((mp4Bytes - binaryData.length) / mp4Bytes) * 100).toFixed(2)),
        createdAt: new Date().toISOString(),
        binaryBlob: binaryData.buffer as ArrayBuffer,
        isCustom: true,
      });

      const updated = await getAllCachedLectures();
      setCachedLectures(updated);
      showToast(`Saved "${currentLecture.topicTitle}" for 100% offline playback`);
    } catch (err) {
      console.warn('Could not save current lecture to offline cache:', err);
      showToast('Failed to save to offline storage');
    }
  };

  const handleDownloadCurrentLectureJson = () => {
    if (!currentLecture.lectureId || currentLecture.frames.length === 0) {
      showToast('No active lesson to export');
      return;
    }
    const jsonString = JSON.stringify(currentLecture, null, 2);
    const blob = new Blob([jsonString], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const safeTitle = (currentLecture.topicTitle || 'lesson')
      .toLowerCase()
      .replace(/[^a-z0-9]/g, '_')
      .replace(/_+/g, '_');
    a.download = `byteclass_${safeTitle}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast(`Exported "${a.download}" (Offline JSON)`);
  };

  const handleDownloadCurrentLectureBinary = () => {
    if (!currentLecture.lectureId || currentLecture.frames.length === 0) {
      showToast('No active lesson to export');
      return;
    }
    const binaryData = serializeLectureBinary(currentLecture);
    const blob = new Blob([binaryData.buffer as ArrayBuffer], { type: 'application/octet-stream' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const safeTitle = (currentLecture.topicTitle || 'lesson')
      .toLowerCase()
      .replace(/[^a-z0-9]/g, '_')
      .replace(/_+/g, '_');
    a.download = `byteclass_${safeTitle}.bin`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast(`Downloaded binary payload (${binaryData.length} B)`);
  };

  const handleExportSavedLessonJson = async (item: SavedLectureMetadata, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    try {
      const cached = await getLectureById(item.id);
      if (!cached) return;
      const payload = deserializeLectureBinary(cached.binaryBlob);
      payload.sourceVideoUrl = cached.sourceVideoUrl || payload.sourceVideoUrl;
      payload.sourceType = cached.sourceType || payload.sourceType;
      const jsonString = JSON.stringify(payload, null, 2);
      const blob = new Blob([jsonString], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const safeTitle = (item.title || 'lesson')
        .toLowerCase()
        .replace(/[^a-z0-9]/g, '_')
        .replace(/_+/g, '_');
      a.download = `byteclass_${safeTitle}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showToast(`Exported "${item.title}" as JSON`);
    } catch (err) {
      console.warn('Failed to export cached JSON:', err);
      showToast('Export failed');
    }
  };

  const handleExportSavedLessonBinary = async (item: SavedLectureMetadata, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    try {
      const cached = await getLectureById(item.id);
      if (!cached) return;
      const blob = new Blob([cached.binaryBlob], { type: 'application/octet-stream' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const safeTitle = (item.title || 'lesson')
        .toLowerCase()
        .replace(/[^a-z0-9]/g, '_')
        .replace(/_+/g, '_');
      a.download = `byteclass_${safeTitle}.bin`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showToast(`Exported "${item.title}" binary (${cached.binarySizeBytes} B)`);
    } catch (err) {
      console.warn('Failed to export cached binary:', err);
      showToast('Export failed');
    }
  };

  const lectureDuration = currentLecture.frames.length > 0
    ? Math.max(...currentLecture.frames.map((f) => f.timestampSeconds)) + 25.0
    : 60.0;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col items-center">
      {/* Toast Notification */}
      {activeToast && (
        <div className="fixed top-5 right-5 z-50 bg-white text-slate-900 px-4 py-2.5 rounded-xl font-mono text-xs font-medium shadow-md flex items-center gap-2 border border-slate-200">
          <CheckCircle className="w-4 h-4 text-slate-700" />
          <span>{activeToast}</span>
        </div>
      )}

      {/* Top Global Navigation Bar */}
      <header className="w-full border-b border-slate-200 bg-white/90 backdrop-blur-md sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 py-3 flex flex-wrap items-center justify-between gap-4">
          {/* Logo & Subtitle */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-slate-900 text-white flex items-center justify-center shadow-sm">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-base tracking-tight text-slate-900">
                  Project ByteClass
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200 font-medium flex items-center gap-1">
                  <YoutubeIcon className="w-2.5 h-2.5 text-red-600" /> YouTube &amp; JSON
                </span>
              </div>
              <p className="text-[11px] text-slate-500 font-mono">
                Video &amp; Audio Player • &lt;50KB/min Vector Payloads (99.9% Footprint Reduction)
              </p>
            </div>
          </div>

          {/* Navigation Tabs */}
          <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-xl border border-slate-200">
            <button
              onClick={() => setActiveTab('player')}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-all cursor-pointer ${
                activeTab === 'player'
                  ? 'bg-white text-slate-900 font-semibold shadow-sm'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-white/50'
              }`}
            >
              <BookOpen className="w-3.5 h-3.5 text-slate-700" />
              <span>Player</span>
            </button>

            <button
              onClick={() => setActiveTab('offline-library')}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-all cursor-pointer ${
                activeTab === 'offline-library'
                  ? 'bg-white text-slate-900 font-semibold shadow-sm'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-white/50'
              }`}
            >
              <HardDrive className="w-3.5 h-3.5 text-slate-700" />
              <span>Saved Offline ({cachedLectures.length})</span>
            </button>

            <button
              onClick={() => setActiveTab('youtube-links')}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-all cursor-pointer ${
                activeTab === 'youtube-links'
                  ? 'bg-white text-slate-900 font-semibold shadow-sm'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-white/50'
              }`}
            >
              <YoutubeIcon className="w-3.5 h-3.5 text-red-600" />
              <span>YouTube Links</span>
            </button>

            <button
              onClick={() => setActiveTab('json-upload')}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-all cursor-pointer ${
                activeTab === 'json-upload'
                  ? 'bg-white text-slate-900 font-semibold shadow-sm'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-white/50'
              }`}
            >
              <Upload className="w-3.5 h-3.5 text-slate-700" />
              <span>Upload JSON</span>
            </button>

            <button
              onClick={() => setActiveTab('svg-visuals')}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-all cursor-pointer ${
                activeTab === 'svg-visuals'
                  ? 'bg-white text-slate-900 font-semibold shadow-sm'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-white/50'
              }`}
            >
              <Layers className="w-3.5 h-3.5 text-slate-700" />
              <span>SVG Visuals ({currentLecture.frames.length})</span>
            </button>

            <button
              onClick={() => setActiveTab('telemetry')}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-all cursor-pointer ${
                activeTab === 'telemetry'
                  ? 'bg-white text-slate-900 font-semibold shadow-sm'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-white/50'
              }`}
            >
              <Radio className="w-3.5 h-3.5 text-slate-700" />
              <span>Telemetry</span>
            </button>
          </div>

          {/* Offline Hardware Audio Telemetry */}
          <div className="hidden lg:flex items-center gap-3 text-xs font-mono bg-slate-50 px-3 py-1.5 rounded-xl border border-slate-200 text-slate-700">
            <div className="flex items-center gap-1.5 text-slate-800 font-medium">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
              <span>0 KB Network Streaming</span>
            </div>
            <span className="text-slate-300">|</span>
            <div className="flex items-center gap-1.5 text-slate-600">
              <Volume2 className="w-3.5 h-3.5 text-blue-600" />
              <span className="truncate max-w-[150px]">{voiceName}</span>
            </div>
            {cachedLectures.length > 0 && (
              <>
                <span className="text-slate-300">|</span>
                <div className="flex items-center gap-1.5 text-slate-600">
                  <Layers className="w-3.5 h-3.5" />
                  <span>{cachedLectures.length} Cached</span>
                </div>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Main Workspace */}
      <main className="w-full max-w-7xl px-4 py-8 flex flex-col gap-8 flex-1">
        {/* Active Generated Lesson Banner */}
        {currentLecture.lectureId && (
          <div className="bg-white border-2 border-slate-900 p-4 rounded-xl flex items-center justify-between gap-4 shadow-sm">
            <div className="flex items-center gap-3 truncate">
              <div className="w-2.5 h-2.5 rounded-full bg-blue-600 shrink-0" />
              <div className="flex flex-col truncate">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200 uppercase">
                    ACTIVE LESSON
                  </span>
                  <span className="text-xs font-mono font-bold text-slate-900 truncate">
                    {currentLecture.topicTitle}
                  </span>
                </div>
                <span className="text-[11px] font-mono text-slate-500 mt-0.5">
                  {currentLecture.frames.length} Chapters • {currentBinarySize} Bytes Protobuf Payload
                </span>
              </div>
            </div>
            <button
              onClick={() => setActiveTab('player')}
              className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white font-medium font-mono text-xs rounded-xl transition-all shadow-sm shrink-0 cursor-pointer"
            >
              ▶ PLAY IN VECTOR PLAYER
            </button>
          </div>
        )}

        {/* Saved Educational Lessons Bar (Only shown if user has saved lessons) */}
        {cachedLectures.length > 0 && activeTab !== 'offline-library' && (
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono text-slate-500 uppercase tracking-wider flex items-center gap-1.5 font-medium">
                <Layers className="w-4 h-4 text-slate-700" />
                <span>SAVED EDUCATIONAL LESSONS ({cachedLectures.length}):</span>
              </span>
              <button
                onClick={() => setActiveTab('offline-library')}
                className="text-xs font-mono text-slate-600 hover:text-slate-900 font-medium flex items-center gap-1 cursor-pointer transition-colors"
              >
                <span>Open Offline Library</span>
                <ArrowRight className="w-3 h-3" />
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {cachedLectures.map((item) => {
                const isSelected = currentLecture.lectureId === item.id;
                return (
                  <div
                    key={item.id}
                    className={`p-3.5 rounded-xl border transition-all flex flex-col justify-between gap-2.5 bg-white ${
                      isSelected
                        ? 'border-slate-900 shadow-sm ring-1 ring-slate-900'
                        : 'border-slate-200 hover:border-slate-300 hover:shadow-sm'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex flex-col truncate">
                        <span className="text-xs font-mono font-bold text-slate-900 truncate">
                          {item.title}
                        </span>
                        <span className="text-[11px] font-mono text-slate-500 mt-0.5">
                          {item.frameCount} Chapters • {item.binarySizeBytes} Bytes • {Math.round(item.durationSeconds)}s
                        </span>
                      </div>
                      <button
                        onClick={(e) => handleDeleteCached(item.id, e)}
                        title="Remove from saved lessons"
                        className="text-slate-400 hover:text-rose-600 p-1 cursor-pointer transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>

                    <div className="flex items-center justify-between pt-1">
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200 font-medium">
                        {item.compressionRatio}% Data Saved
                      </span>
                      <button
                        onClick={() => selectLectureById(item.id)}
                        className={`text-xs font-mono font-semibold px-2.5 py-1 rounded-lg transition-all cursor-pointer ${
                          isSelected
                            ? 'bg-slate-900 text-white'
                            : 'bg-slate-100 hover:bg-slate-200 text-slate-800'
                        }`}
                      >
                        {isSelected ? 'Currently Active' : 'Load Lesson'}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Welcome Empty State if no lessons exist and no active lecture */}
        {cachedLectures.length === 0 && !currentLecture.lectureId && activeTab !== 'offline-library' && (
          <div className="bg-white border border-slate-200 p-8 rounded-2xl flex flex-col items-center text-center gap-4 shadow-sm max-w-xl mx-auto my-2">
            <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center text-slate-800">
              <Sparkles className="w-6 h-6 text-slate-700" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-slate-900">
                Educational Vector Lecture Studio
              </h3>
              <p className="text-xs text-slate-500 mt-1 max-w-md leading-relaxed font-mono">
                Paste any YouTube educational video link or upload a JSON file to automatically generate an in-depth teacher explanation and 400×400 SVG visuals.
              </p>
            </div>
            <div className="flex items-center gap-3 mt-1">
              <button
                onClick={() => setActiveTab('youtube-links')}
                className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white text-xs font-mono font-medium rounded-xl transition-all shadow-sm flex items-center gap-2 cursor-pointer"
              >
                <YoutubeIcon className="w-3.5 h-3.5 text-red-500" />
                <span>Paste YouTube Link</span>
              </button>
              <button
                onClick={() => setActiveTab('json-upload')}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-mono font-medium rounded-xl border border-slate-200 transition-all flex items-center gap-2 cursor-pointer"
              >
                <Upload className="w-3.5 h-3.5 text-slate-700" />
                <span>Upload JSON File</span>
              </button>
            </div>
          </div>
        )}

        {/* Tab 1: Video Player & Audio Player */}
        {activeTab === 'player' && (
          <div className="flex flex-col items-center justify-center gap-6 w-full max-w-4xl mx-auto">
            <OfflineVectorPlayer
              frameData={currentLecture.frames}
              topicTitle={currentLecture.topicTitle}
              sourceVideoUrl={currentLecture.sourceVideoUrl}
              sourceType={currentLecture.sourceType}
              targetDurationSeconds={currentLecture.targetDurationSeconds || (currentLecture as any).target_duration_seconds}
              isSavedOffline={isCurrentLectureSaved}
              onSaveOffline={handleSaveCurrentLectureToOffline}
              onDownloadJson={handleDownloadCurrentLectureJson}
              onDownloadBinary={handleDownloadCurrentLectureBinary}
            />

            {/* Quick Navigation Action Cards */}
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 w-full max-w-4xl">
              <button
                onClick={() => setActiveTab('offline-library')}
                className="bg-white border border-slate-200 hover:border-slate-300 shadow-sm p-2.5 rounded-xl text-center cursor-pointer transition-all flex flex-col items-center gap-1 text-slate-700 hover:text-slate-900"
              >
                <HardDrive className="w-4 h-4 text-slate-600" />
                <span className="text-[11px] font-mono font-semibold">Saved ({cachedLectures.length})</span>
              </button>

              <button
                onClick={() => setActiveTab('youtube-links')}
                className="bg-white border border-slate-200 hover:border-slate-300 shadow-sm p-2.5 rounded-xl text-center cursor-pointer transition-all flex flex-col items-center gap-1 text-slate-700 hover:text-slate-900"
              >
                <YoutubeIcon className="w-4 h-4 text-red-600" />
                <span className="text-[11px] font-mono font-semibold">YouTube Links</span>
              </button>

              <button
                onClick={() => setActiveTab('json-upload')}
                className="bg-white border border-slate-200 hover:border-slate-300 shadow-sm p-2.5 rounded-xl text-center cursor-pointer transition-all flex flex-col items-center gap-1 text-slate-700 hover:text-slate-900"
              >
                <FileJson className="w-4 h-4 text-slate-600" />
                <span className="text-[11px] font-mono font-semibold">Upload JSON</span>
              </button>

              <button
                onClick={() => setActiveTab('svg-visuals')}
                className="bg-white border border-slate-200 hover:border-slate-300 shadow-sm p-2.5 rounded-xl text-center cursor-pointer transition-all flex flex-col items-center gap-1 text-slate-700 hover:text-slate-900"
              >
                <Layers className="w-4 h-4 text-slate-600" />
                <span className="text-[11px] font-mono font-semibold">SVG ({currentLecture.frames.length})</span>
              </button>

              <button
                onClick={() => setActiveTab('telemetry')}
                className="bg-white border border-slate-200 hover:border-slate-300 shadow-sm p-2.5 rounded-xl text-center cursor-pointer transition-all flex flex-col items-center gap-1 text-slate-700 hover:text-slate-900"
              >
                <Radio className="w-4 h-4 text-slate-600" />
                <span className="text-[11px] font-mono font-semibold">Telemetry</span>
              </button>
            </div>
          </div>
        )}

        {/* Tab 2: Saved Offline Lessons Library */}
        {activeTab === 'offline-library' && (
          <div className="max-w-5xl mx-auto w-full flex flex-col gap-6">
            {/* Header Banner */}
            <div className="bg-white border border-slate-200 p-6 rounded-2xl shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-xl bg-slate-900 text-white flex items-center justify-center shrink-0 shadow-sm">
                  <HardDrive className="w-6 h-6" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-lg font-bold text-slate-900 tracking-tight">
                      Saved Offline Lessons Library
                    </h2>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 font-semibold flex items-center gap-1">
                      <ShieldCheck className="w-3 h-3 text-emerald-600" /> 100% Offline Ready
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 font-mono mt-1 max-w-xl leading-relaxed">
                    All lessons below are saved locally in your browser's persistent IndexedDB storage.
                    They stream with <strong className="text-slate-700">0 KB network data</strong> and synthesize audio directly via your device hardware.
                  </p>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex flex-wrap items-center gap-2 shrink-0">
                {currentLecture.lectureId && !isCurrentLectureSaved && (
                  <button
                    onClick={handleSaveCurrentLectureToOffline}
                    className="px-3.5 py-2 bg-slate-900 hover:bg-slate-800 text-white font-mono text-xs font-semibold rounded-xl transition-all shadow-sm flex items-center gap-1.5 cursor-pointer"
                  >
                    <HardDrive className="w-3.5 h-3.5" />
                    <span>Save Current Lesson</span>
                  </button>
                )}
                <button
                  onClick={() => setActiveTab('youtube-links')}
                  className="px-3.5 py-2 bg-slate-100 hover:bg-slate-200 text-slate-800 font-mono text-xs font-medium rounded-xl border border-slate-200 transition-all flex items-center gap-1.5 cursor-pointer"
                >
                  <YoutubeIcon className="w-3.5 h-3.5 text-red-600" />
                  <span>New from YouTube</span>
                </button>
                <button
                  onClick={() => setActiveTab('json-upload')}
                  className="px-3.5 py-2 bg-slate-100 hover:bg-slate-200 text-slate-800 font-mono text-xs font-medium rounded-xl border border-slate-200 transition-all flex items-center gap-1.5 cursor-pointer"
                >
                  <Upload className="w-3.5 h-3.5 text-slate-700" />
                  <span>Import JSON</span>
                </button>
              </div>
            </div>

            {/* Offline Summary Bar */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="bg-white border border-slate-200 p-3.5 rounded-xl shadow-sm">
                <span className="text-[11px] font-mono text-slate-500 block">Total Stored</span>
                <span className="text-base font-mono font-bold text-slate-900 mt-0.5 block">
                  {cachedLectures.length} {cachedLectures.length === 1 ? 'Lesson' : 'Lessons'}
                </span>
              </div>
              <div className="bg-white border border-slate-200 p-3.5 rounded-xl shadow-sm">
                <span className="text-[11px] font-mono text-slate-500 block">Combined Size</span>
                <span className="text-base font-mono font-bold text-slate-900 mt-0.5 block">
                  {(cachedLectures.reduce((acc, c) => acc + c.binarySizeBytes, 0) / 1024).toFixed(1)} KB
                </span>
              </div>
              <div className="bg-white border border-slate-200 p-3.5 rounded-xl shadow-sm">
                <span className="text-[11px] font-mono text-slate-500 block">Audio Synthesis</span>
                <span className="text-base font-mono font-bold text-emerald-700 mt-0.5 block">
                  0 KB Audio Stream
                </span>
              </div>
              <div className="bg-white border border-slate-200 p-3.5 rounded-xl shadow-sm">
                <span className="text-[11px] font-mono text-slate-500 block">Voice Engine</span>
                <span className="text-xs font-mono font-semibold text-slate-800 mt-1 block truncate">
                  Studio Neutral (Neural Audio)
                </span>
              </div>
            </div>

            {/* Saved Lessons Cards Grid */}
            {cachedLectures.length === 0 ? (
              <div className="bg-white border border-slate-200 p-12 rounded-2xl flex flex-col items-center text-center gap-4 shadow-sm">
                <div className="w-14 h-14 rounded-full bg-slate-100 flex items-center justify-center text-slate-600">
                  <HardDrive className="w-7 h-7 text-slate-600" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-900">No Offline Lessons Saved Yet</h3>
                  <p className="text-xs text-slate-500 font-mono mt-1.5 max-w-md leading-relaxed">
                    Generate an educational lesson from any YouTube link or upload a lesson JSON file. Once generated or imported, click "Save for Offline" to store it in your browser cache forever.
                  </p>
                </div>
                <div className="flex items-center gap-3 mt-2">
                  <button
                    onClick={() => setActiveTab('youtube-links')}
                    className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white font-mono text-xs font-medium rounded-xl transition-all shadow-sm flex items-center gap-2 cursor-pointer"
                  >
                    <YoutubeIcon className="w-3.5 h-3.5 text-red-500" />
                    <span>Paste YouTube Link</span>
                  </button>
                  <button
                    onClick={() => setActiveTab('json-upload')}
                    className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-800 font-mono text-xs font-medium rounded-xl border border-slate-200 transition-all flex items-center gap-2 cursor-pointer"
                  >
                    <Upload className="w-3.5 h-3.5 text-slate-700" />
                    <span>Upload JSON File</span>
                  </button>
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {cachedLectures.map((item) => {
                  const isActive = currentLecture.lectureId === item.id;
                  const mins = Math.floor(item.durationSeconds / 60);
                  const secs = Math.floor(item.durationSeconds % 60);
                  const formattedDuration = `${mins}m ${secs.toString().padStart(2, '0')}s`;

                  return (
                    <div
                      key={item.id}
                      className={`bg-white border rounded-2xl p-5 shadow-sm transition-all flex flex-col justify-between gap-4 ${
                        isActive
                          ? 'border-slate-900 ring-2 ring-slate-900/10'
                          : 'border-slate-200 hover:border-slate-300'
                      }`}
                    >
                      {/* Top Header */}
                      <div className="flex flex-col gap-2">
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex flex-col gap-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-[10px] font-mono px-2 py-0.5 rounded font-medium bg-slate-100 text-slate-700 border border-slate-200">
                                {item.sourceType === 'youtube' ? 'YouTube Lecture' : 'JSON Lesson'}
                              </span>
                              {isActive && (
                                <span className="text-[10px] font-mono px-2 py-0.5 rounded font-semibold bg-blue-50 text-blue-700 border border-blue-200">
                                  CURRENTLY LOADED
                                </span>
                              )}
                            </div>
                            <h3 className="text-sm font-bold text-slate-900 truncate tracking-tight mt-1">
                              {item.title}
                            </h3>
                          </div>

                          <button
                            onClick={(e) => handleDeleteCached(item.id, e)}
                            title="Delete lesson from offline cache"
                            className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors cursor-pointer shrink-0"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>

                        {/* Metadata row */}
                        <div className="grid grid-cols-3 gap-2 py-2 border-y border-slate-100 text-xs font-mono">
                          <div>
                            <span className="text-[10px] text-slate-400 block">CHAPTERS</span>
                            <span className="font-semibold text-slate-700">{item.frameCount} Frames</span>
                          </div>
                          <div>
                            <span className="text-[10px] text-slate-400 block">RUNTIME</span>
                            <span className="font-semibold text-slate-700">{formattedDuration}</span>
                          </div>
                          <div>
                            <span className="text-[10px] text-slate-400 block">BINARY SIZE</span>
                            <span className="font-semibold text-slate-700">
                              {(item.binarySizeBytes / 1024).toFixed(1)} KB
                            </span>
                          </div>
                        </div>

                        <div className="flex items-center justify-between text-[11px] font-mono text-slate-500">
                          <span className="flex items-center gap-1 text-emerald-700 font-medium">
                            <CheckCircle className="w-3.5 h-3.5 text-emerald-600" />
                            <span>100% Offline Ready</span>
                          </span>
                          <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200 font-medium">
                            {item.compressionRatio}% Bandwidth Saved
                          </span>
                        </div>
                      </div>

                      {/* Action Buttons */}
                      <div className="flex items-center gap-2 pt-1">
                        <button
                          onClick={() => selectLectureById(item.id)}
                          className={`flex-1 py-2 px-3 rounded-xl font-mono text-xs font-semibold flex items-center justify-center gap-2 transition-all cursor-pointer ${
                            isActive
                              ? 'bg-slate-900 text-white hover:bg-slate-800'
                              : 'bg-slate-900 hover:bg-slate-800 text-white shadow-sm'
                          }`}
                        >
                          <Play className="w-3.5 h-3.5 fill-current" />
                          <span>{isActive ? 'Play in Player' : 'Load & Play Offline'}</span>
                        </button>

                        <button
                          onClick={(e) => handleExportSavedLessonJson(item, e)}
                          title="Export self-contained JSON file"
                          className="px-2.5 py-2 bg-slate-50 hover:bg-slate-100 text-slate-700 font-mono text-xs font-medium rounded-xl border border-slate-200 transition-all flex items-center gap-1 cursor-pointer"
                        >
                          <FileJson className="w-3.5 h-3.5" />
                          <span>.json</span>
                        </button>

                        <button
                          onClick={(e) => handleExportSavedLessonBinary(item, e)}
                          title="Download ultra-compact Protobuf .bin file"
                          className="px-2.5 py-2 bg-slate-50 hover:bg-slate-100 text-slate-700 font-mono text-xs font-medium rounded-xl border border-slate-200 transition-all flex items-center gap-1 cursor-pointer"
                        >
                          <Download className="w-3.5 h-3.5" />
                          <span>.bin</span>
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Offline Playback Architecture Card */}
            <div className="bg-white border border-slate-200 p-5 rounded-2xl shadow-sm">
              <h4 className="text-xs font-mono uppercase text-slate-900 font-bold mb-2 flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-600" />
                How Offline Playback Works (0 KB Streaming)
              </h4>
              <p className="text-xs text-slate-600 font-mono leading-relaxed mb-4">
                ByteClass decouples visual diagrams and voice instruction from video bitstreams:
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs font-mono text-slate-700">
                <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-200">
                  <span className="text-slate-900 font-bold block mb-1">1. Vector SVG Geometry</span>
                  Mathematical paths, shapes, and colors are cached directly in your browser. No video pixels are ever buffered.
                </div>
                <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-200">
                  <span className="text-slate-900 font-bold block mb-1">2. Studio Voice Synthesis</span>
                  High-fidelity neural voiceover synthesized with realistic documentary pacing. No heavy video pixel downloads.
                </div>
                <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-200">
                  <span className="text-slate-900 font-bold block mb-1">3. Offline IndexedDB Storage</span>
                  Each lesson is stored as an ultra-compact binary blob (&lt;50 KB) that persists even when disconnected.
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Upload JSON Files */}
        {activeTab === 'json-upload' && (
          <div className="max-w-5xl mx-auto w-full">
            <JsonUploadStudio
              onLoadLecture={handleLoadCustomLecture}
              initialMode="upload"
            />
          </div>
        )}

        {/* Tab 3: YouTube Links Ingestion */}
        {activeTab === 'youtube-links' && (
          <div className="max-w-5xl mx-auto w-full">
            <JsonUploadStudio
              onLoadLecture={handleLoadCustomLecture}
              initialMode="youtube"
            />
          </div>
        )}

        {/* Tab 4: SVG Visuals Gallery & Inspector */}
        {activeTab === 'svg-visuals' && (
          <div className="max-w-5xl mx-auto w-full">
            <SvgVisualsStudio
              currentLecture={currentLecture}
              onSeekToFrame={(_ts) => {
                setActiveTab('player');
              }}
              onInjectCustomSvg={handleInjectCustomSvg}
            />
          </div>
        )}

        {/* Tab 5: Edge Telemetry & Transmission */}
        {activeTab === 'telemetry' && (
          <div className="max-w-5xl mx-auto w-full flex flex-col gap-6">
            <EdgeMetricsDashboard
              durationSeconds={lectureDuration}
              binarySizeBytes={currentBinarySize}
            />

            {/* Compression Blueprint Card */}
            <div className="bg-white border border-slate-200 p-5 rounded-2xl shadow-sm">
              <h4 className="text-xs font-mono uppercase text-slate-800 font-bold mb-3 flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-emerald-600" />
                Vector Micro-Lecture Architecture
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs font-mono text-slate-700">
                <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-200">
                  <span className="text-slate-900 font-bold block mb-1">
                    Timeline Vector Synchronization
                  </span>
                  400x400 SVG visuals render directly on client hardware with 0 KB streaming data.
                </div>
                <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-200">
                  <span className="text-slate-900 font-bold block mb-1">
                    Zero Audio Streaming Bandwidth
                  </span>
                  Voiceover speech is synthesized by device hardware, eliminating MP3/MP4 audio downloads.
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

export default App;
