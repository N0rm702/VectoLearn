import React, { useState, useEffect, useRef, useCallback } from 'react';
import type { LectureFrame } from '../types/lecture';
import { FrameAction } from '../types/lecture';
import { speechSynthesizer } from '../services/speechSynthesizer';
import { resolveVisualToSvg, type VisualEngineType } from '../services/visualEngineResolver';
import {
  Play,
  Pause,
  RotateCcw,
  Volume2,
  VolumeX,
  FastForward,
  ExternalLink,
  FileJson,
  Bookmark,
  CheckCircle,
  Download,
  FileDown,
  HardDrive,
  SkipBack,
  SkipForward,
  Layers,
  Sparkles,
} from 'lucide-react';

const YoutubeIcon: React.FC<{ className?: string }> = ({ className = 'w-4 h-4' }) => (
  <svg className={className} viewBox="0 0 24 24" fill="currentColor">
    <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
  </svg>
);

interface OfflineVectorPlayerProps {
  frameData: LectureFrame[];
  topicTitle?: string;
  sourceVideoUrl?: string;
  sourceType?: 'youtube' | 'json_file';
  targetDurationSeconds?: number;
  onPlaybackComplete?: () => void;
  playbackSpeed?: number;
  isSavedOffline?: boolean;
  onSaveOffline?: () => void;
  onDownloadJson?: () => void;
  onDownloadBinary?: () => void;
}

export const OfflineVectorPlayer: React.FC<OfflineVectorPlayerProps> = ({
  frameData,
  topicTitle,
  sourceVideoUrl,
  sourceType = 'youtube',
  targetDurationSeconds = 0,
  onPlaybackComplete,
  playbackSpeed = 1.0,
  isSavedOffline = false,
  onSaveOffline,
  onDownloadJson,
  onDownloadBinary,
}) => {
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [currentTime, setCurrentTime] = useState<number>(0);
  const [activeCaptionLine, setActiveCaptionLine] = useState<string>('');
  const [showCc, setShowCc] = useState<boolean>(true);
  const [currentVisualEngine, setCurrentVisualEngine] = useState<VisualEngineType>('svg');
  const [isMuted, setIsMuted] = useState<boolean>(false);
  const [activeFrameIndex, setActiveFrameIndex] = useState<number>(-1);
  const [speed, setSpeed] = useState<number>(playbackSpeed);
  const [activeLanguage, setActiveLanguage] = useState<'en' | 'hi'>('en');
  const [selectedNeuralVoice, setSelectedNeuralVoice] = useState<string>('en-US-GuyNeural');

  const canvasRef = useRef<HTMLDivElement>(null);
  const spokenIndicesRef = useRef<Set<number>>(new Set());
  const currentTimeRef = useRef<number>(0);
  const isPlayingRef = useRef<boolean>(false);
  const speedRef = useRef<number>(playbackSpeed);
  const isMutedRef = useRef<boolean>(false);
  const neuralAudioRef = useRef<HTMLAudioElement | null>(null);
  const neuralAudioCacheRef = useRef<Map<number, HTMLAudioElement>>(new Map());
  const seekDebounceRef = useRef<number | null>(null);

  // Keep refs in sync for RAF loop
  currentTimeRef.current = currentTime;
  isPlayingRef.current = isPlaying;
  speedRef.current = speed;
  isMutedRef.current = isMuted;

  // Resolves the spoken text according to the selected language track
  const getFrameText = useCallback(
    (frame: LectureFrame, lang: 'en' | 'hi' = activeLanguage): string => {
      if (lang === 'hi') {
        if (frame.spokenTextHi && frame.spokenTextHi.trim()) {
          return frame.spokenTextHi;
        }
        if (/[\u0900-\u097F]/.test(frame.spokenText || '')) {
          return frame.spokenText;
        }
      }
      return frame.spokenText || '';
    },
    [activeLanguage]
  );

  // Resolves chapter title according to the selected language track
  const getFrameTitle = useCallback(
    (frame: LectureFrame, lang: 'en' | 'hi' = activeLanguage, idx?: number): string => {
      if (lang === 'hi' && frame.chapterTitleHi && frame.chapterTitleHi.trim()) {
        return frame.chapterTitleHi;
      }
      return frame.chapterTitle || (idx !== undefined ? `Milestone ${idx + 1}` : 'Milestone');
    },
    [activeLanguage]
  );

  // Auto-detect Hindi language in frames and select Madhur Neural voice
  useEffect(() => {
    const isPureHindi = frameData.some((f) => /[\u0900-\u097F]/.test(f.spokenText || '')) && !frameData.some((f) => f.spokenTextHi);
    if (isPureHindi) {
      setActiveLanguage('hi');
      if (!selectedNeuralVoice.startsWith('hi-IN')) {
        setSelectedNeuralVoice('hi-IN-MadhurNeural');
      }
    }
  }, [frameData]);

  // Compute total duration dynamically based on target duration or last frame timestamp + spoken speech reading duration
  const lastFrame = frameData[frameData.length - 1];
  const lastWordsCount = lastFrame?.spokenText ? lastFrame.spokenText.trim().split(/\s+/).length : 0;
  const lastSpeechDuration = Math.max(10.0, Math.ceil(lastWordsCount / 2.2));
  const computedDuration = frameData.length > 0
    ? Math.max(...frameData.map((f) => f.timestampSeconds)) + lastSpeechDuration
    : 10.0;
  const maxTimestamp = Math.max(targetDurationSeconds, computedDuration);

  // Apply frame action to canvas with multi-engine visual resolution
  const applyFrameAction = useCallback(
    async (frame: LectureFrame) => {
      if (!canvasRef.current) return;

      switch (frame.actionType) {
        case FrameAction.CLEAR_CANVAS_RESET:
          canvasRef.current.innerHTML = `
            <div class="flex flex-col items-center justify-center h-full text-slate-500 font-mono text-xs">
              <span>[CANVAS RESET]</span>
            </div>`;
          break;

        case FrameAction.INJECT_NEW_VECTOR:
        case FrameAction.ANIMATE_EXISTING_VECTOR:
          if (frame.svgPayload && frame.svgPayload.trim()) {
            try {
              const resolved = await resolveVisualToSvg(frame.svgPayload, topicTitle);
              if (canvasRef.current) {
                canvasRef.current.innerHTML = resolved.svg;
              }
              setCurrentVisualEngine(resolved.engine);
            } catch (err) {
              console.warn('Error resolving visual engine:', err);
              if (canvasRef.current) {
                canvasRef.current.innerHTML = frame.svgPayload;
              }
            }
          }
          break;

        case FrameAction.RENDER_TEXT_ONLY:
        default:
          // Text is handled in transcript box, keep canvas as-is
          break;
      }
    },
    [topicTitle]
  );

  // Update canvas state based on seeking to a specific time
  const seekToTime = useCallback(
    (targetSeconds: number) => {
      const clamped = Math.max(0, Math.min(maxTimestamp, targetSeconds));
      setCurrentTime(clamped);
      currentTimeRef.current = clamped;

      // Find all frames up to targetSeconds
      const pastFrames = frameData
        .map((frame, index) => ({ frame, index }))
        .filter((item) => item.frame.timestampSeconds <= clamped);

      // Mark all past frames INCLUDING the active frame as processed in spokenIndicesRef
      // This prevents the requestAnimationFrame playLoop from blindly re-triggering this frame from 0s on the next tick
      spokenIndicesRef.current = new Set(pastFrames.map((item) => item.index));

      if (pastFrames.length > 0) {
        const latest = pastFrames[pastFrames.length - 1];
        setActiveFrameIndex(latest.index);

        const frameText = getFrameText(latest.frame);
        const sents = speechSynthesizer.splitIntoSentences(frameText);
        const elapsedInFrame = Math.max(0, clamped - latest.frame.timestampSeconds);

        let activeLine = sents[0] || frameText;
        let activeSentIdx = 0;
        if (sents.length > 1) {
          let accum = 0;
          for (let i = 0; i < sents.length; i++) {
            const s = sents[i];
            const wordCount = s.trim().split(/\s+/).filter(Boolean).length;
            const dur = Math.max(1.8, wordCount / (2.4 * speedRef.current));
            if (elapsedInFrame < accum + dur) {
              activeLine = s;
              activeSentIdx = i;
              break;
            }
            accum += dur;
            activeLine = s;
            activeSentIdx = i;
          }
        }
        setActiveCaptionLine(activeLine);

        // If currently playing during seek, cleanly debounce speech trigger so rapid scrubbing doesn't stutter or repeat
        if (isPlayingRef.current && !isMutedRef.current && frameText && frameText.trim()) {
          if (seekDebounceRef.current !== null) {
            clearTimeout(seekDebounceRef.current);
          }
          seekDebounceRef.current = window.setTimeout(() => {
            playSpeech(frameText, latest.index, activeSentIdx, elapsedInFrame);
          }, 100);
        }

        // Find the latest vector-bearing frame to render
        const lastVectorFrame = [...pastFrames]
          .reverse()
          .find((item) => item.frame.svgPayload && item.frame.svgPayload.trim());

        if (lastVectorFrame) {
          applyFrameAction(lastVectorFrame.frame);
        } else if (canvasRef.current) {
          canvasRef.current.innerHTML = `
            <div class="flex items-center justify-center h-full text-slate-600 font-mono text-xs">
              [Canvas Ready]
            </div>`;
        }
      } else {
        setActiveFrameIndex(-1);
        setActiveCaptionLine('');
        if (canvasRef.current) {
          if (frameData.length === 0) {
            canvasRef.current.innerHTML = `
              <div class="flex flex-col items-center justify-center h-full text-slate-500 font-mono text-xs gap-2 p-6 text-center">
                <span class="text-slate-800 font-semibold text-sm">No Vector Frames Loaded</span>
                <span class="text-slate-400 text-[11px]">Add a YouTube link or upload a JSON file to begin</span>
              </div>`;
          } else {
            canvasRef.current.innerHTML = `
              <div class="flex flex-col items-center justify-center h-full text-slate-500 font-mono text-xs gap-1">
                <span class="text-slate-800 font-semibold">[READY FOR PLAYBACK]</span>
                <span class="text-slate-400 text-[11px]">16:9 Widescreen Local Vector Stage</span>
              </div>`;
          }
        }
      }
    },
    [frameData, maxTimestamp, applyFrameAction, getFrameText]
  );

  // Jump to specific visual frame
  const jumpToFrame = useCallback(
    (index: number) => {
      if (index >= 0 && index < frameData.length) {
        seekToTime(frameData[index].timestampSeconds);
      }
    },
    [frameData, seekToTime]
  );

  // Skip to previous visual milestone
  const jumpToPrevVisual = useCallback(() => {
    if (frameData.length === 0) return;
    const currentIdx = activeFrameIndex >= 0 ? activeFrameIndex : 0;
    const currentFrame = frameData[currentIdx];
    if (currentFrame && (currentTimeRef.current - currentFrame.timestampSeconds) > 2.0) {
      seekToTime(currentFrame.timestampSeconds);
    } else if (currentIdx > 0) {
      seekToTime(frameData[currentIdx - 1].timestampSeconds);
    } else {
      seekToTime(0);
    }
  }, [activeFrameIndex, frameData, seekToTime]);

  // Skip to next visual milestone
  const jumpToNextVisual = useCallback(() => {
    if (frameData.length === 0) return;
    const currentIdx = activeFrameIndex >= 0 ? activeFrameIndex : 0;
    if (currentIdx < frameData.length - 1) {
      seekToTime(frameData[currentIdx + 1].timestampSeconds);
    }
  }, [activeFrameIndex, frameData, seekToTime]);

  // Stop any playing speech (local synthesis or neural audio)
  const stopAllAudio = useCallback(() => {
    speechSynthesizer.cancel();
    if (neuralAudioRef.current) {
      neuralAudioRef.current.pause();
      neuralAudioRef.current = null;
    }
  }, []);

  // Play narration speech using Studio Neutral Audio
  const playSpeech = useCallback(
    (
      text: string,
      frameIdx?: number,
      startSentenceIdx: number = 0,
      elapsedSecondsInFrame: number = 0,
      overrideVoice?: string
    ) => {
      stopAllAudio();
      if (!text || !text.trim()) return;

      const sentences = speechSynthesizer.splitIntoSentences(text);
      if (sentences.length > 0) {
        const safeIdx = Math.max(0, Math.min(startSentenceIdx, sentences.length - 1));
        setActiveCaptionLine(sentences[safeIdx]);
      }

      const voice = overrideVoice || selectedNeuralVoice;
      let audio: HTMLAudioElement | undefined;
      if (frameIdx !== undefined && neuralAudioCacheRef.current.has(frameIdx)) {
        const cached = neuralAudioCacheRef.current.get(frameIdx);
        if (cached && cached.src.includes(`voice=${encodeURIComponent(voice)}`)) {
          audio = cached;
        }
      }
      if (!audio) {
        const url = `http://127.0.0.1:8000/api/tts?text=${encodeURIComponent(text)}&voice=${voice}`;
        audio = new Audio(url);
      }
      neuralAudioRef.current = audio;
      audio.playbackRate = speedRef.current;

      const applySeekTime = () => {
        if (audio && audio.duration && !isNaN(audio.duration) && audio.duration > 0) {
          audio.currentTime = Math.min(Math.max(0, audio.duration - 0.2), elapsedSecondsInFrame);
        }
      };

      if (audio.readyState >= 1) {
        applySeekTime();
      } else {
        audio.onloadedmetadata = applySeekTime;
      }

      audio.ontimeupdate = () => {
        if (audio && audio.duration && audio.duration > 0 && sentences.length > 1) {
          const progress = Math.min(1.0, audio.currentTime / audio.duration);
          const targetSentenceIdx = Math.min(
            sentences.length - 1,
            Math.floor(progress * sentences.length)
          );
          setActiveCaptionLine(sentences[targetSentenceIdx]);
        }
      };

      audio.play().catch((err) => {
        console.warn('Studio Neutral voice playback notice:', err);
      });
    },
    [selectedNeuralVoice, stopAllAudio]
  );

  // Seamlessly switch between English and Hindi audio/caption tracks during live playback
  const switchLanguage = useCallback(
    (newLang: 'en' | 'hi') => {
      if (newLang === activeLanguage) return;
      setActiveLanguage(newLang);
      const targetVoice = newLang === 'hi' ? 'hi-IN-MadhurNeural' : 'en-US-GuyNeural';
      setSelectedNeuralVoice(targetVoice);

      // Invalidate cached audio so newly selected language voice is generated
      neuralAudioCacheRef.current.clear();

      const currentIdx = activeFrameIndex >= 0 ? activeFrameIndex : 0;
      const currentFrame = frameData[currentIdx];
      if (currentFrame) {
        const text = getFrameText(currentFrame, newLang);
        const sents = speechSynthesizer.splitIntoSentences(text);
        const elapsedInFrame = Math.max(0, currentTimeRef.current - currentFrame.timestampSeconds);

        let targetSentIdx = 0;
        if (sents.length > 1) {
          let accum = 0;
          for (let i = 0; i < sents.length; i++) {
            const wordCount = sents[i].trim().split(/\s+/).filter(Boolean).length;
            const dur = Math.max(1.8, wordCount / (2.4 * speedRef.current));
            if (elapsedInFrame < accum + dur) {
              targetSentIdx = i;
              break;
            }
            accum += dur;
            targetSentIdx = i;
          }
        }

        setActiveCaptionLine(sents[targetSentIdx] || text);

        if (isPlayingRef.current && !isMutedRef.current && text.trim()) {
          playSpeech(text, currentIdx, targetSentIdx, elapsedInFrame, targetVoice);
        }
      }
    },
    [activeLanguage, activeFrameIndex, frameData, getFrameText, playSpeech]
  );

  // Pre-buffer Studio voice audio in the background for instant zero-lag playback
  useEffect(() => {
    neuralAudioCacheRef.current.clear();
    if (frameData.length > 0) {
      frameData.forEach((frame, index) => {
        const text = getFrameText(frame);
        if (text && text.trim()) {
          const url = `http://127.0.0.1:8000/api/tts?text=${encodeURIComponent(text)}&voice=${selectedNeuralVoice}`;
          const audio = new Audio();
          audio.preload = 'auto';
          audio.src = url;
          neuralAudioCacheRef.current.set(index, audio);
        }
      });
    }
  }, [frameData, selectedNeuralVoice, activeLanguage, getFrameText]);

  // YouTube 'c' key shortcut to toggle captions
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key === 'c' || e.key === 'C') {
        setShowCc((prev) => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Initialize canvas on mount or when frameData changes
  useEffect(() => {
    seekToTime(0);
  }, [frameData, seekToTime]);

  // RequestAnimationFrame clock loop (Clock Synchronized Loop)
  useEffect(() => {
    let animationFrameId: number;
    let lastPerformanceNow = performance.now();

    const playLoop = (now: number) => {
      if (!isPlayingRef.current) return;

      const deltaSeconds = ((now - lastPerformanceNow) / 1000) * speedRef.current;
      lastPerformanceNow = now;

      const newElapsed = currentTimeRef.current + deltaSeconds;

      if (newElapsed >= maxTimestamp) {
        setCurrentTime(maxTimestamp);
        setIsPlaying(false);
        stopAllAudio();
        onPlaybackComplete?.();
        return;
      }

      setCurrentTime(newElapsed);

      // Evaluate the data payload timeline frames
      frameData.forEach((frame, index) => {
        // Trigger localized execution when timeline reaches or passes frame timestamp
        const timeDiff = newElapsed - frame.timestampSeconds;

        if (timeDiff >= 0 && !spokenIndicesRef.current.has(index)) {
          spokenIndicesRef.current.add(index);
          setActiveFrameIndex(index);

          // Voice Execution Trigger (Instant Studio Neural)
          const text = getFrameText(frame);
          if (!isMutedRef.current && text && text.trim()) {
            playSpeech(text, index, 0, 0);
          }

          // Handle Vector Injector Updates directly inside the local client window
          applyFrameAction(frame);
        }
      });

      animationFrameId = requestAnimationFrame(playLoop);
    };

    if (isPlaying) {
      lastPerformanceNow = performance.now();
      animationFrameId = requestAnimationFrame(playLoop);
    } else {
      stopAllAudio();
    }

    return () => {
      cancelAnimationFrame(animationFrameId);
    };
  }, [isPlaying, frameData, maxTimestamp, applyFrameAction, onPlaybackComplete, playSpeech, stopAllAudio, getFrameText]);

  const togglePlay = () => {
    if (frameData.length === 0) return;

    if (currentTime >= maxTimestamp) {
      seekToTime(0);
    }

    setIsPlaying((prev) => {
      const willPlay = !prev;
      if (willPlay) {
        // Immediately resume voice for current active frame at the exact sentence matching playback position
        const currentIdx = activeFrameIndex >= 0 ? activeFrameIndex : 0;
        const frame = frameData[currentIdx];
        const text = frame ? getFrameText(frame) : '';
        if (frame && text && text.trim() && !isMutedRef.current) {
          const sents = speechSynthesizer.splitIntoSentences(text);
          const elapsedInFrame = Math.max(0, currentTimeRef.current - frame.timestampSeconds);
          let targetSentIdx = 0;
          if (sents.length > 1) {
            let accum = 0;
            for (let i = 0; i < sents.length; i++) {
              const wordCount = sents[i].trim().split(/\s+/).filter(Boolean).length;
              const dur = Math.max(1.8, wordCount / (2.4 * speedRef.current));
              if (elapsedInFrame < accum + dur) {
                targetSentIdx = i;
                break;
              }
              accum += dur;
              targetSentIdx = i;
            }
          }

          spokenIndicesRef.current.add(currentIdx);
          setActiveFrameIndex(currentIdx);
          playSpeech(text, currentIdx, targetSentIdx, elapsedInFrame);
          applyFrameAction(frame);
        }
      } else {
        stopAllAudio();
      }
      return willPlay;
    });
  };

  const handleReset = () => {
    setIsPlaying(false);
    stopAllAudio();
    seekToTime(0);
  };

  const handleSeekChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value);
    stopAllAudio();
    seekToTime(val);
  };

  const cycleSpeed = () => {
    const speeds = [0.75, 1.0, 1.25, 1.5];
    const nextIdx = (speeds.indexOf(speed) + 1) % speeds.length;
    setSpeed(speeds[nextIdx]);
  };

  const toggleMute = () => {
    if (!isMuted) {
      stopAllAudio();
    }
    setIsMuted(!isMuted);
  };

  return (
    <div className="flex flex-col items-center bg-white border border-slate-200 p-6 rounded-2xl w-full max-w-4xl shadow-sm relative overflow-hidden">
      {/* Header bar */}
      <div className="w-full flex flex-col gap-2 mb-4 pb-3 border-b border-slate-100">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 truncate">
            <div className={`w-2 h-2 rounded-full shrink-0 ${isPlaying ? 'bg-blue-600' : 'bg-slate-400'}`} />
            <span className="text-xs font-mono font-bold tracking-wide text-slate-900 uppercase truncate">
              {topicTitle || 'Edge Vector Playback'}
            </span>
          </div>
          <span className="text-[11px] font-mono text-slate-500 shrink-0">
            {activeFrameIndex >= 0 ? `Frame ${activeFrameIndex + 1}/${frameData.length}` : 'Idle'}
          </span>
        </div>

        {/* Source metadata row: YouTube link or JSON tag */}
        <div className="flex items-center justify-between gap-2 pt-1">
          {sourceVideoUrl ? (
            <a
              href={sourceVideoUrl}
              target="_blank"
              rel="noreferrer"
              title="Open Original Video on YouTube"
              className="flex items-center gap-1.5 text-[10px] font-mono px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200 hover:bg-slate-200 hover:text-slate-900 transition-colors cursor-pointer"
            >
              <YoutubeIcon className="w-3.5 h-3.5 text-red-600" />
              <span className="truncate max-w-[200px]">YouTube Source Video</span>
              <ExternalLink className="w-2.5 h-2.5 shrink-0 text-slate-400" />
            </a>
          ) : (
            <span className="flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200">
              <FileJson className="w-3 h-3 text-slate-500" />
              <span>{sourceType === 'json_file' ? 'Uploaded JSON File' : 'Offline Vector Payload'}</span>
            </span>
          )}

          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
            0 KB Stream Bandwidth
          </span>
        </div>
      </div>

      {/* Offline Hardware Graphics Board (Native Browser SVG DOM / 16:9 Widescreen Canvas) */}
      <div className="relative group w-full">
        <div
          ref={canvasRef}
          className="vector-stage rounded-2xl flex items-center justify-center overflow-hidden transition-all duration-300 relative w-full aspect-[16/9] min-h-[320px] md:min-h-[420px]"
        />

        {/* Visual Engine Indicator Badge */}
        {frameData.length > 0 && (
          <div className="absolute top-3 left-3 z-20 pointer-events-none">
            <span className="text-[10px] font-mono px-2.5 py-1 rounded-md font-semibold bg-white/90 text-slate-800 border border-slate-200/90 shadow-xs flex items-center gap-1.5 backdrop-blur-xs">
              <span
                className={`w-2 h-2 rounded-full ${
                  currentVisualEngine === 'mermaid'
                    ? 'bg-indigo-600'
                    : currentVisualEngine === 'd3'
                    ? 'bg-sky-600'
                    : currentVisualEngine === 'manim'
                    ? 'bg-amber-600'
                    : 'bg-emerald-600'
                }`}
              />
              <span>
                {currentVisualEngine === 'mermaid' && 'Mermaid.js Flowchart'}
                {currentVisualEngine === 'd3' && 'D3.js Coordinate Model'}
                {currentVisualEngine === 'manim' && 'Manim Vector Math (3B1B)'}
                {currentVisualEngine === 'svg' && 'Pure Vector SVG'}
              </span>
            </span>
          </div>
        )}

        {/* YouTube-Style Floating Closed Captions Overlay on Video */}
        {showCc && activeCaptionLine && (
          <div className="absolute bottom-3.5 left-2 right-2 flex justify-center pointer-events-none z-20 transition-all duration-150">
            <div className="bg-black/85 backdrop-blur-xs text-white font-sans text-xs sm:text-sm font-medium px-3.5 py-1.5 rounded shadow-lg text-center max-w-[90%] leading-relaxed tracking-normal select-none">
              {activeCaptionLine}
            </div>
          </div>
        )}
      </div>

      {/* Timeline Scrubber Bar with Visual Milestone Markers */}
      <div className="w-full mt-4 flex flex-col gap-1.5 relative">
        <div className="flex justify-between text-xs font-mono text-slate-500 px-0.5">
          <span>{currentTime.toFixed(1)}s</span>
          <span className="text-[11px] text-slate-400 font-sans flex items-center gap-1">
            <Layers className="w-3 h-3 text-slate-400" />
            <span>{frameData.length} Visual Milestones</span>
          </span>
          <span>{maxTimestamp.toFixed(1)}s</span>
        </div>
        <div className="relative w-full flex items-center h-4">
          <input
            type="range"
            min={0}
            max={maxTimestamp}
            step={0.1}
            value={currentTime}
            onChange={handleSeekChange}
            disabled={frameData.length === 0}
            className="w-full h-1.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-slate-900 hover:accent-slate-800 disabled:opacity-50 transition-all z-10"
          />
          {/* Milestone markers along timeline */}
          {maxTimestamp > 0 &&
            frameData.map((f, i) => {
              const pct = Math.min(100, Math.max(0, (f.timestampSeconds / maxTimestamp) * 100));
              const isActive = i === activeFrameIndex;
              return (
                <button
                  key={i}
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    jumpToFrame(i);
                  }}
                  title={`Visual ${i + 1}: ${getFrameTitle(f, activeLanguage)} (${f.timestampSeconds.toFixed(1)}s)`}
                  style={{ left: `${pct}%` }}
                  className={`absolute w-1.5 h-3 -translate-x-1/2 rounded-full cursor-pointer transition-all hover:scale-150 z-20 focus:outline-none ${
                    isActive ? 'bg-blue-600 ring-2 ring-blue-300 scale-125' : 'bg-slate-400/80 hover:bg-slate-700'
                  }`}
                />
              );
            })}
        </div>
      </div>

      {/* Control Surface UI */}
      <div className="mt-5 flex flex-wrap items-center justify-between w-full gap-3">
        <div className="flex items-center gap-2">
          {/* Prev Visual Milestone */}
          <button
            onClick={jumpToPrevVisual}
            disabled={frameData.length === 0}
            title="Jump to Previous Visual Milestone (Snappy Seek)"
            className="p-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 rounded-xl transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <SkipBack className="w-4 h-4" />
          </button>

          {/* Play/Pause Button */}
          <button
            onClick={togglePlay}
            disabled={frameData.length === 0}
            className="flex items-center gap-2 px-5 py-2.5 bg-slate-900 hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed active:scale-95 font-medium rounded-xl transition-all text-white shadow-sm cursor-pointer font-mono text-xs"
          >
            {isPlaying ? (
              <>
                <Pause className="w-4 h-4 fill-current" />
                <span>PAUSE SYSTEM</span>
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-current" />
                <span>EXECUTE OFFLINE LESSON</span>
              </>
            )}
          </button>

          {/* Next Visual Milestone */}
          <button
            onClick={jumpToNextVisual}
            disabled={frameData.length === 0 || activeFrameIndex >= frameData.length - 1}
            title="Jump to Next Visual Milestone (Snappy Seek)"
            className="p-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 rounded-xl transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <SkipForward className="w-4 h-4" />
          </button>

          {/* Reset button */}
          <button
            onClick={handleReset}
            title="Reset to beginning"
            className="p-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 rounded-xl transition-colors cursor-pointer"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
        </div>

        <div className="flex items-center gap-2">
          {/* Dual-Track Bilingual Audio/Caption Switcher */}
          <div className="flex items-center bg-slate-100 p-0.5 rounded-xl border border-slate-200 shadow-2xs">
            <button
              onClick={() => switchLanguage('en')}
              title="Switch to English Teacher Narration"
              className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-mono font-semibold transition-all cursor-pointer ${
                activeLanguage === 'en'
                  ? 'bg-white text-slate-900 shadow-xs ring-1 ring-slate-200'
                  : 'text-slate-500 hover:text-slate-900'
              }`}
            >
              <span>🇬🇧</span>
              <span>EN</span>
            </button>
            <button
              onClick={() => switchLanguage('hi')}
              title="Switch to Hindi Teacher Narration (हिन्दी शिक्षक व्याख्या)"
              className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-mono font-semibold transition-all cursor-pointer ${
                activeLanguage === 'hi'
                  ? 'bg-emerald-600 text-white shadow-xs'
                  : 'text-slate-500 hover:text-slate-900'
              }`}
            >
              <span>🇮🇳</span>
              <span>हिन्दी</span>
            </button>
          </div>

          {/* YouTube Closed Caption (CC) Toggle Button */}
          <button
            onClick={() => setShowCc((prev) => !prev)}
            title={showCc ? 'Turn off captions (c)' : 'Turn on captions (c)'}
            className={`px-3 py-2 rounded-xl border text-xs font-mono font-bold transition-all cursor-pointer flex items-center justify-center relative ${
              showCc
                ? 'bg-slate-900 text-white border-slate-900 shadow-sm'
                : 'bg-slate-100 text-slate-400 border-slate-200 hover:text-slate-700'
            }`}
          >
            <span>CC</span>
            {showCc && (
              <span className="absolute -bottom-0.5 left-2 right-2 h-0.5 bg-red-500 rounded-full" />
            )}
          </button>

          {/* Speed Toggle */}
          <button
            onClick={cycleSpeed}
            title="Change Playback Speed"
            className="flex items-center gap-1 px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 text-xs font-mono font-medium rounded-xl transition-colors cursor-pointer"
          >
            <FastForward className="w-3.5 h-3.5 text-slate-600" />
            <span>{speed}x</span>
          </button>

          {/* Mute Toggle */}
          <button
            onClick={toggleMute}
            title={isMuted ? 'Unmute Audio' : 'Mute Speech Synthesizer'}
            className={`p-2.5 rounded-xl transition-colors cursor-pointer border ${
              isMuted
                ? 'bg-rose-50 text-rose-700 border-rose-200'
                : 'bg-slate-100 hover:bg-slate-200 text-slate-700 border-slate-200'
            }`}
          >
            {isMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
          </button>

          {/* Clock Track Display */}
          <div className="bg-slate-50 px-3 py-2 rounded-xl border border-slate-200 font-mono text-xs text-slate-700">
            <span className="text-slate-500">Clock: </span>
            <span className="text-slate-900 font-semibold">{currentTime.toFixed(1)}s</span>
          </div>
        </div>
      </div>

      {/* Interactive Visual Milestones Navigation Bar */}
      {frameData.length > 0 && (
        <div className="w-full mt-4 pt-3 border-t border-slate-100 flex flex-col gap-2">
          <div className="flex items-center justify-between text-xs font-mono text-slate-600">
            <span className="flex items-center gap-1.5 font-semibold text-slate-800">
              <Sparkles className="w-3.5 h-3.5 text-amber-500" />
              <span>Visual Milestones ({frameData.length} Scenes)</span>
            </span>
            <span className="text-[11px] text-slate-400">
              Click any scene to jump directly to its visual &amp; audio
            </span>
          </div>
          <div className="flex items-center gap-2 overflow-x-auto pb-1.5 pt-0.5 no-scrollbar scroll-smooth">
            {frameData.map((f, idx) => {
              const isActive = idx === activeFrameIndex;
              const formatSecs = (s: number) => {
                const m = Math.floor(s / 60);
                const remainder = Math.floor(s % 60);
                return `${m}:${remainder.toString().padStart(2, '0')}`;
              };
              return (
                <button
                  key={idx}
                  type="button"
                  onClick={() => jumpToFrame(idx)}
                  className={`shrink-0 flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-mono border transition-all cursor-pointer ${
                    isActive
                      ? 'bg-blue-50 text-blue-900 border-blue-400 shadow-xs ring-2 ring-blue-200/60 font-semibold'
                      : 'bg-slate-50 hover:bg-slate-100 text-slate-700 border-slate-200 hover:border-slate-300'
                  }`}
                >
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${
                      isActive ? 'bg-blue-600 animate-pulse' : 'bg-slate-400'
                    }`}
                  />
                  <span className="text-[10px] text-slate-400">#{idx + 1}</span>
                  <span className="truncate max-w-[140px] text-[11px]">
                    {getFrameTitle(f, activeLanguage, idx)}
                  </span>
                  <span
                    className={`text-[10px] px-1.5 py-0.2 rounded ${
                      isActive ? 'bg-blue-100 text-blue-800' : 'bg-slate-200/80 text-slate-600'
                    }`}
                  >
                    {formatSecs(f.timestampSeconds)}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Voice Engine & Speaker Selector Bar */}
      <div className="w-full mt-4 pt-3 border-t border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
        <div className="flex items-center gap-2 text-xs">
          <span className="font-mono text-slate-700 font-semibold flex items-center gap-1.5">
            <Volume2 className="w-3.5 h-3.5 text-blue-600" />
            <span>Voice Engine:</span>
          </span>
          <span className="px-2.5 py-1 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-lg text-[11px] font-mono font-medium flex items-center gap-1.5 shadow-2xs">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            Studio Neutral (High-Fidelity Neural Audio)
          </span>
        </div>

        {/* Voice Dropdown & Language Switcher */}
        <div className="flex items-center gap-2 text-xs font-mono">
          <button
            onClick={() => switchLanguage(activeLanguage === 'hi' ? 'en' : 'hi')}
            title="Toggle between English and Hindi voiceover"
            className="px-2 py-1 rounded-lg border text-[11px] font-mono cursor-pointer transition-all bg-slate-100 hover:bg-slate-200 text-slate-800 flex items-center gap-1 font-semibold"
          >
            {activeLanguage === 'hi' ? '🇮🇳 HI' : '🇬🇧 EN'}
          </button>
          <span className="text-slate-500 shrink-0">Speaker Voice:</span>
          <select
            value={selectedNeuralVoice}
            onChange={(e) => setSelectedNeuralVoice(e.target.value)}
            className="bg-white text-slate-800 border border-slate-300 rounded-lg px-2.5 py-1 text-xs font-mono focus:outline-none focus:border-blue-500 max-w-[320px] truncate cursor-pointer shadow-sm"
          >
            <optgroup label="🇮🇳 Hindi Studio Neural">
              <option value="hi-IN-MadhurNeural">🇮🇳 Madhur Neural (Hindi Documentary Narrator)</option>
              <option value="hi-IN-SwaraNeural">🇮🇳 Swara Neural (Hindi Female Instructor)</option>
            </optgroup>
            <optgroup label="🇬🇧 English Studio Neural">
              <option value="en-US-GuyNeural">🎙️ Studio Neutral (Documentary Narrator)</option>
              <option value="en-US-ChristopherNeural">🎙️ Christopher Neural (Engaging Educator)</option>
              <option value="en-US-JennyNeural">🎙️ Jenny Neural (Clear Female Instructor)</option>
              <option value="en-US-AriaNeural">🎙️ Aria Neural (Natural Expressive)</option>
            </optgroup>
          </select>
        </div>
      </div>

      {/* Offline Persistence & Local Export Control Bar */}
      {frameData.length > 0 && (
        <div className="w-full mt-4 pt-3.5 border-t border-slate-200 flex flex-col gap-2.5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono font-semibold text-slate-700 flex items-center gap-1.5">
              <HardDrive className="w-3.5 h-3.5 text-blue-600" />
              <span>Offline Persistence &amp; Local Export:</span>
            </span>
            <span
              className={`text-[10px] font-mono px-2 py-0.5 rounded-full border font-semibold flex items-center gap-1 ${
                isSavedOffline
                  ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                  : 'bg-amber-50 text-amber-800 border-amber-200'
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  isSavedOffline ? 'bg-emerald-600' : 'bg-amber-500 animate-pulse'
                }`}
              />
              <span>{isSavedOffline ? '100% Offline Ready (Cached)' : 'Unsaved in Local Cache'}</span>
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            {/* 1. Save to Offline Cache Button */}
            <button
              onClick={onSaveOffline}
              title="Store full lesson and vector SVGs in IndexedDB for 100% offline playback"
              className={`flex items-center justify-center gap-1.5 px-3 py-2.5 rounded-xl text-xs font-mono font-medium transition-all cursor-pointer border shadow-xs ${
                isSavedOffline
                  ? 'bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border-emerald-300'
                  : 'bg-slate-900 hover:bg-slate-800 text-white border-slate-900 active:scale-95'
              }`}
            >
              {isSavedOffline ? (
                <>
                  <CheckCircle className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Saved in Cache</span>
                </>
              ) : (
                <>
                  <Bookmark className="w-3.5 h-3.5" />
                  <span>Save for Offline</span>
                </>
              )}
            </button>

            {/* 2. Download Offline JSON file */}
            <button
              onClick={onDownloadJson}
              title="Download standalone .json lesson file to backup or open on any air-gapped device"
              className="flex items-center justify-center gap-1.5 px-3 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-200 text-xs font-mono font-medium transition-colors cursor-pointer"
            >
              <Download className="w-3.5 h-3.5 text-slate-600" />
              <span>Export .json</span>
            </button>

            {/* 3. Download Protobuf Binary (.bin) */}
            <button
              onClick={onDownloadBinary}
              title="Download ultra-compressed binary payload (<50 KB) for edge transmission"
              className="flex items-center justify-center gap-1.5 px-3 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-200 text-xs font-mono font-medium transition-colors cursor-pointer"
            >
              <FileDown className="w-3.5 h-3.5 text-slate-600" />
              <span>Download .bin</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
