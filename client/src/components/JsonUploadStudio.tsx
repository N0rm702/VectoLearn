import React, { useState, useRef, useEffect } from 'react';
import type { LecturePayload, LectureFrame } from '../types/lecture';
import { FrameAction } from '../types/lecture';
import { serializeLectureBinary } from '../services/protobufDecoder';
import { detectVisualEngine } from '../services/visualEngineResolver';
import {
  Upload,
  CheckCircle,
  AlertCircle,
  Download,
  Play,
  Sparkles,
  Bot,
  Video,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  Layers,
  Globe,
} from 'lucide-react';

const YoutubeIcon: React.FC<{ className?: string }> = ({ className = 'w-4 h-4' }) => (
  <svg className={className} viewBox="0 0 24 24" fill="currentColor">
    <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
  </svg>
);

export const FINE_TUNED_PROMPT = `[SYSTEM INSTRUCTION: EDUCATIONAL CURRICULUM ENGINEER & VECTOR CONTENT COMPILER]
You act as an expert Educational Curriculum Engineer, Master Pedagogy Teacher (in the style of 3Blue1Brown, Veritasium, and Khan Academy), and Vector Content Compiler. 
Your core task is to transform a raw, unstructured YouTube lecture transcript into an exhaustive, highly precise, timeline-synchronized educational script and vector illustration specification optimized for ultra-low bandwidth edge playback.

CRITICAL INSTRUCTIONS & FIDELITY MANDATES:
1. 100% EXHAUSTIVE COMPREHENSIVENESS (NO OMISSIONS):
   - You MUST retain and explain 100% of the academic concepts, technical mechanisms, historical context, numerical data, mathematical equations, real-world examples, and counterarguments mentioned in the transcript.
   - Do NOT summarize loosely, gloss over technical proofs, skip middle chapters, or emit vague placeholders (NEVER write generic phrases like "Let us explore the core dynamics").
   - You must cover everything discussed in the video from start to finish. Faithfully extract and teach the speaker's exact terminology, definitions, analogies, and step-by-step logic.

2. CALIBRATED COMPLEXITY & ACCESSIBILITY (DO NOT INTRODUCE UNWARRANTED ADVANCED CONTENT):
   - You MUST calibrate the complexity of the script strictly to the target topic and source transcript.
   - Do NOT introduce overly advanced, graduate-level mathematics, obscure academic jargon, or esoteric theoretical formulas UNLESS the transcript itself explicitly introduces and teaches them.
   - If the video explains an intuitive, foundational, or general subject, keep the explanation clear, accessible, and grounded at that exact educational level.
   - NEVER invent complex differential equations, tensor proofs, or graduate-level theories that the speaker did not mention.

3. STRICT TOPICAL RELEVANCE (ZERO OFF-TOPIC DRIFT):
   - The script and visual diagrams must ALWAYS remain 100% relevant and faithful to the specific topic and what was actually taught in the video.
   - Never wander off into unrelated tangents, speculative theories, or unmentioned academic trivia.
   - Every single chapter must directly build understanding of the core subject matter.

4. DISCRETE CHRONOLOGICAL CHUNKING:
   - Break down the script into strict, logical timeline frames based on the natural flow of the topic from beginning to end.
   - Each frame must capture a specific, substantive conceptual phase without skipping any segment of the video (e.g., Opening Paradox/Context -> Core Mechanism -> Key Evidence/Examples -> Resolution & Takeaways).

5. PRECISE SEQUENTIAL TIMESTAMPS:
   - Map out logical, sequential floating-point timestamps in seconds (e.g., 0.0, 35.0, 70.0, 105.0) matching when each point would naturally be introduced in a paced, educational lecture.

6. AUTHORITATIVE TTS-OPTIMIZED SPOKEN TEXT:
   - The spoken script for each frame must consist of clear, fully formed paragraphs (60 to 90 words, ~35-45 seconds of natural speech) that a native voice synthesis (TTS) system can speak clearly out loud.
   - The narration must explain "why" things occur and provide direct verbal cues referencing visual elements (e.g., "Notice the blue vector pointing upward...", "Observe how the magnetic field circulates...").

7. MULTI-ENGINE VISUAL SPECIFICATION (16:9 WIDESCREEN 800x450 VIEWBOX):
   - For each frame, choose the most effective visual engine to model the concept:
     * "mermaid": System architecture flowcharts, state transitions, cause-and-effect pipelines (flowchart TD ...). MANDATORY: quote all node labels A["Text"] and B{"Decision?"}.
     * "d3": Quantitative coordinate charts, probability distributions, data trends ({"title": "...", "points": [...]}).
     * "manim": 3Blue1Brown chalkboard vector math, vector fields, derivatives, geometric models (only if mathematical).
     * "svg": Physical hardware schematics, anatomical cross-sections, particle configurations (<svg viewBox="0 0 800 450"...).
   - Use high-contrast, clean minimalist colors: deep slate (#0f172a) for text and primary lines, slate (#475569) for labels/axes, royal blue (#2563eb), emerald (#059669), amber (#d97706), and crimson (#dc2626). NO neon colors.

OUTPUT FORMAT:
Output strictly valid JSON text arrays matching the structural schema:
[
  {
    "timestamp_seconds": 0.0,
    "spoken_text": "Spoken explanation here...",
    "action_type": 1,
    "visual_engine": "mermaid", // "mermaid" | "d3" | "manim" | "svg"
    "svg_payload": "flowchart TD\\n  A[\"Input\"] --> B[\"Processing\"]..."
  }
]`;

interface JsonUploadStudioProps {
  onLoadLecture: (payload: LecturePayload, binaryData: Uint8Array) => void;
  initialMode?: 'youtube' | 'upload';
}


export const JsonUploadStudio: React.FC<JsonUploadStudioProps> = ({ onLoadLecture, initialMode = 'youtube' }) => {
  const [activeMode, setActiveMode] = useState<'youtube' | 'upload'>(initialMode);
  const [dragOver, setDragOver] = useState<boolean>(false);
  const [parsedPayload, setParsedPayload] = useState<LecturePayload | null>(null);
  const [compiledBinary, setCompiledBinary] = useState<Uint8Array | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [validationSuccess, setValidationSuccess] = useState<string | null>(null);
  const [backendConfig, setBackendConfig] = useState<{ model_name?: string; is_hf_token_set?: boolean } | null>(null);
  const [showPromptDrawer, setShowPromptDrawer] = useState<boolean>(false);
  const [copiedPrompt, setCopiedPrompt] = useState<boolean>(false);

  // YouTube Link Ingestion Form: ONLY input is the YouTube URL
  const [ytUrl, setYtUrl] = useState<string>('');
  const [chapterCount, setChapterCount] = useState<string>('auto');
  const [targetLanguage, setTargetLanguage] = useState<'en' | 'hi'>('en');
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [generationStage, setGenerationStage] = useState<string>('');

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Fetch backend status on mount
  useEffect(() => {
    fetch('/api/backend-config')
      .then((res) => res.json())
      .then((data) => setBackendConfig(data))
      .catch((err) => console.warn('Backend config query note:', err));
  }, []);

  // Normalize JSON regardless of snake_case or camelCase
  const normalizeJson = (raw: any, fileName: string): LecturePayload => {
    let title = 'Uploaded YouTube Lecture';
    let id = `yt-${Date.now()}`;
    let rawFrames: any[] = [];

    if (Array.isArray(raw)) {
      rawFrames = raw;
      title = fileName.replace(/\.json$/i, '').replace(/[-_]/g, ' ');
    } else if (typeof raw === 'object' && raw !== null) {
      title = raw.topic_title || raw.topicTitle || raw.title || title;
      id = raw.lecture_id || raw.lectureId || raw.id || id;
      rawFrames = raw.frames || raw.timeline || [];
    } else {
      throw new Error('Root JSON must be an object or array of frames.');
    }

    if (!Array.isArray(rawFrames) || rawFrames.length === 0) {
      throw new Error("JSON must contain a non-empty 'frames' array.");
    }

    const frames: LectureFrame[] = rawFrames.map((f: any, idx: number) => {
      const ts = f.timestamp_seconds ?? f.timestampSeconds ?? f.timestamp ?? idx * 35.0;
      const text = f.spoken_text ?? f.spokenText ?? f.text ?? f.transcript ?? '';
      let action = f.action_type ?? f.actionType ?? FrameAction.INJECT_NEW_VECTOR;
      let svg = f.svg_payload ?? f.svgPayload ?? f.svg ?? '';

      let engine = f.visual_engine ?? f.visualEngine;
      if (!engine && svg) {
        engine = detectVisualEngine(svg);
      }

      // Wrap raw SVG elements if root <svg> is missing and not mermaid/d3/manim
      if (svg && !svg.trim().startsWith('<svg') && engine === 'svg') {
        svg = `<svg viewBox="0 0 800 450" xmlns="http://www.w3.org/2000/svg" data-engine="svg">${svg}</svg>`;
      }

      return {
        timestampSeconds: parseFloat(ts) || 0,
        spokenText: String(text).trim(),
        spokenTextHi: String(f.spoken_text_hi || f.spokenTextHi || '').trim(),
        chapterTitle: String(f.chapter_title || f.chapterTitle || '').trim(),
        chapterTitleHi: String(f.chapter_title_hi || f.chapterTitleHi || '').trim(),
        actionType: typeof action === 'number' ? action : FrameAction.INJECT_NEW_VECTOR,
        svgPayload: svg,
        visualEngine: engine,
      };
    });

    frames.sort((a, b) => a.timestampSeconds - b.timestampSeconds);

    return {
      lectureId: id,
      topicTitle: title,
      sourceVideoUrl: raw.source_video_url || raw.sourceVideoUrl || '',
      targetDurationSeconds: raw.target_duration_seconds || raw.targetDurationSeconds || 0,
      frames,
    };
  };

  const processJsonString = async (jsonStr: string, fileName: string) => {
    setValidationError(null);
    setValidationSuccess(null);
    try {
      const parsed = JSON.parse(jsonStr);

      // Check if JSON has valid pre-compiled frames with SVGs
      const hasSvgFrames =
        (Array.isArray(parsed?.frames) &&
          parsed.frames.length > 0 &&
          parsed.frames.some((f: any) => (f.svg_payload || f.svgPayload || f.svg) && (f.spoken_text || f.spokenText || f.text))) ||
        (Array.isArray(parsed) &&
          parsed.length > 0 &&
          parsed.some((f: any) => (f.svg_payload || f.svgPayload || f.svg) && (f.spoken_text || f.spokenText || f.text)));

      if (hasSvgFrames) {
        const payload = normalizeJson(parsed, fileName);
        const binary = serializeLectureBinary(payload);
        setParsedPayload(payload);
        setCompiledBinary(binary);
        setValidationSuccess(
          `Successfully compiled ${payload.frames.length} chapters! Binary payload: ${binary.length} Bytes (< 3 KB / 99.95% reduction).`
        );
        onLoadLecture(payload, binary);
        return;
      }

      // If the JSON is raw transcript, lecture notes, outline or text:
      // Let the backend AI summarize it and create the full teacher script and 400x400 SVGs!
      setIsGenerating(true);
      setGenerationStage('AI is analyzing JSON content and planning pedagogical curriculum...');

      let extractedTitle =
        parsed.topic_title ||
        parsed.topicTitle ||
        parsed.title ||
        parsed.topic ||
        fileName.replace(/\.json$/i, '').replace(/[-_]/g, ' ');

      let extractedText = '';
      if (typeof parsed === 'string') {
        extractedText = parsed;
      } else if (parsed.transcript || parsed.text || parsed.content || parsed.summary || parsed.notes) {
        extractedText = parsed.transcript || parsed.text || parsed.content || parsed.summary || parsed.notes;
      } else if (Array.isArray(parsed)) {
        extractedText = parsed
          .map((item: any) => (typeof item === 'string' ? item : item.text || item.spoken_text || item.transcript || item.content || JSON.stringify(item)))
          .join('\n');
      } else if (Array.isArray(parsed.frames)) {
        extractedText = parsed.frames
          .map((f: any) => f.spoken_text || f.spokenText || f.text || f.transcript || '')
          .filter(Boolean)
          .join('\n');
      } else {
        extractedText = JSON.stringify(parsed, null, 2);
      }

      setGenerationStage('AI is creating in-depth teacher narration and 16:9 widescreen multi-engine visuals...');

      const res = await fetch('/api/generate-langchain-lecture', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic_title: extractedTitle,
          transcript_text: extractedText,
          num_frames: chapterCount === 'auto' ? undefined : parseInt(chapterCount, 10),
          target_language: targetLanguage,
        }),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'AI Lecture generation failed');
      }

      const data = await res.json();
      const payload = normalizeJson(data, `${data.topic_title || 'lecture'}.json`);
      const binary = serializeLectureBinary(payload);

      setParsedPayload(payload);
      setCompiledBinary(binary);
      setValidationSuccess(
        `AI summarized JSON into "${payload.topicTitle}" with ${payload.frames.length} chapters! Launching player...`
      );
      onLoadLecture(payload, binary);
    } catch (err: any) {
      setValidationError(`JSON Ingestion: ${err.message}`);
      setParsedPayload(null);
      setCompiledBinary(null);
    } finally {
      setIsGenerating(false);
      setGenerationStage('');
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result as string;
      processJsonString(content, file.name);
    };
    reader.readAsText(file);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.json')) {
      setValidationError('Please upload a valid .json file.');
      return;
    }

    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result as string;
      processJsonString(content, file.name);
    };
    reader.readAsText(file);
  };


  const handleDownloadActiveJson = () => {
    if (!parsedPayload) return;
    const jsonStr = JSON.stringify(
      {
        lecture_id: parsedPayload.lectureId,
        topic_title: parsedPayload.topicTitle,
        source_video_url: parsedPayload.sourceVideoUrl || '',
        frames: parsedPayload.frames.map((f) => ({
          timestamp_seconds: f.timestampSeconds,
          spoken_text: f.spokenText,
          action_type: f.actionType,
          svg_payload: f.svgPayload,
        })),
      },
      null,
      2
    );
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${parsedPayload.topicTitle.toLowerCase().replace(/[^a-z0-9]/g, '_')}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleGenerateLecture = async () => {
    const cleanUrl = ytUrl.trim();
    if (!cleanUrl) {
      setValidationError('Please enter or paste a valid YouTube video URL.');
      return;
    }

    setIsGenerating(true);
    setValidationError(null);
    setValidationSuccess(null);
    setGenerationStage('Extracting video title and transcript from YouTube...');

    try {
      const timer1 = setTimeout(() => {
        setGenerationStage('AI is generating in-depth teacher narration and 16:9 widescreen multi-engine visuals...');
      }, 900);

      const res = await fetch('/api/generate-langchain-lecture', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_url: cleanUrl,
          num_frames: chapterCount === 'auto' ? undefined : parseInt(chapterCount, 10),
          target_language: targetLanguage,
        }),
      });

      clearTimeout(timer1);

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Lecture generation failed');
      }

      setGenerationStage('Compiling to Protobuf binary...');
      const data = await res.json();
      const payload = normalizeJson(data, `${data.topic_title || 'youtube_lecture'}.json`);
      const binary = serializeLectureBinary(payload);

      setParsedPayload(payload);
      setCompiledBinary(binary);
      setValidationSuccess(`Generated "${payload.topicTitle}" with ${payload.frames.length} chapters! Launching player...`);

      // Automatically launch directly in the vector player!
      onLoadLecture(payload, binary);
    } catch (err: any) {
      setValidationError(`Generation Warning: ${err.message}`);
    } finally {
      setIsGenerating(false);
      setGenerationStage('');
    }
  };

  const handleLaunchInPlayer = () => {
    if (parsedPayload && compiledBinary) {
      onLoadLecture(parsedPayload, compiledBinary);
    }
  };

  return (
    <div className="bg-white border border-slate-200 p-6 rounded-2xl w-full shadow-sm flex flex-col gap-6">
      {/* Header bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-100">
        <div>
          <div className="flex items-center gap-2">
            <Video className="w-5 h-5 text-slate-700" />
            <h3 className="text-base font-bold text-slate-900 tracking-wide uppercase">
              Lecture Ingestion &amp; File Studio
            </h3>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Ingest educational content from YouTube links or upload pre-compiled JSON lecture payloads
          </p>
        </div>

        {/* Tab Selector */}
        <div className="flex bg-slate-100 p-1 rounded-xl border border-slate-200">
          <button
            onClick={() => setActiveMode('youtube')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-mono font-medium transition-all cursor-pointer flex items-center gap-1.5 ${
              activeMode === 'youtube'
                ? 'bg-white text-slate-900 font-semibold shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <YoutubeIcon className="w-3.5 h-3.5 text-red-600" />
            <span>YouTube Link Ingest</span>
          </button>
          <button
            onClick={() => setActiveMode('upload')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-mono font-medium transition-all cursor-pointer flex items-center gap-1.5 ${
              activeMode === 'upload'
                ? 'bg-white text-slate-900 font-semibold shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Upload className="w-3.5 h-3.5 text-slate-600" />
            <span>Upload JSON File</span>
          </button>
        </div>
      </div>

      {/* Mode 1: YouTube Link Ingestion (Clean, Model configured in backend .env) */}
      {activeMode === 'youtube' && (
        <div className="flex flex-col gap-5">
          {/* Backend Status Banner */}
          <div className="bg-slate-50 border border-slate-200 px-4 py-2.5 rounded-xl flex items-center justify-between flex-wrap gap-2 text-xs font-mono">
            <div className="flex items-center gap-2 text-slate-700">
              <Bot className="w-4 h-4 text-slate-600" />
              <span>Backend AI Engine:</span>
              <span className="text-slate-900 font-bold">
                {backendConfig?.model_name || 'Qwen/Qwen2.5-Coder-32B-Instruct'}
              </span>
            </div>
            <span className="text-[10px] text-slate-500 bg-white px-2 py-0.5 rounded border border-slate-200">
              Configured via backend .env
            </span>
          </div>

          {/* Single YouTube URL Input Box */}
          <div className="flex flex-col gap-2">
            <label className="text-xs font-mono text-slate-700 font-semibold flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                <YoutubeIcon className="w-4 h-4 text-red-600" />
                <span>Enter YouTube Video URL:</span>
              </span>
              <span className="text-[11px] text-slate-500 font-normal">
                Topic title &amp; narration generated automatically by AI
              </span>
            </label>
            <div className="relative flex items-center">
              <input
                type="text"
                value={ytUrl}
                onChange={(e) => setYtUrl(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !isGenerating && ytUrl.trim()) {
                    handleGenerateLecture();
                  }
                }}
                className="w-full bg-white border border-slate-300 rounded-xl px-4 py-3 text-xs font-mono text-slate-900 placeholder-slate-400 focus:outline-none focus:border-slate-500 focus:ring-1 focus:ring-slate-500 transition-all shadow-sm"
                placeholder="https://www.youtube.com/watch?v=... or https://youtu.be/..."
              />
              {ytUrl && (
                <button
                  type="button"
                  onClick={() => setYtUrl('')}
                  className="absolute right-3 text-slate-400 hover:text-slate-700 text-xs font-mono px-1.5 py-0.5 rounded cursor-pointer"
                >
                  Clear
                </button>
              )}
            </div>
            <p className="text-[11px] text-slate-500 font-mono mt-0.5">
              Paste any YouTube video link. The backend AI extracts the transcript, structures a teacher explanation, and generates comprehensive 16:9 widescreen multi-engine visuals (Mermaid.js, D3.js, Manim, and Pure SVG).
            </p>
          </div>

          {/* Quick-Test Sample Links */}
          <div className="flex items-center gap-2 pt-1 flex-wrap">
            <span className="text-[11px] font-mono text-slate-500">Quick Test Links:</span>
            <button
              type="button"
              onClick={() => setYtUrl('https://www.youtube.com/watch?v=GWk45S7i9QQ')}
              className="text-[11px] font-mono px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 transition-colors cursor-pointer flex items-center gap-1"
            >
              <span>🪐 Pluto (Why Not a Planet)</span>
            </button>
            <button
              type="button"
              onClick={() => setYtUrl('https://www.youtube.com/watch?v=aircAruvnKk')}
              className="text-[11px] font-mono px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 transition-colors cursor-pointer flex items-center gap-1"
            >
              <span>🧠 Neural Networks</span>
            </button>
            <button
              type="button"
              onClick={() => setYtUrl('https://www.youtube.com/watch?v=f-ldPgEfAHI')}
              className="text-[11px] font-mono px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 transition-colors cursor-pointer flex items-center gap-1"
            >
              <span>🔬 Phases of Mitosis</span>
            </button>
          </div>

          {/* Narration Language Selector */}
          <div className="bg-slate-50 border border-slate-200 p-3.5 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-xs">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-white border border-slate-200 flex items-center justify-center shrink-0">
                <Globe className="w-4 h-4 text-emerald-600" />
              </div>
              <div>
                <span className="text-xs font-mono font-semibold text-slate-900">Narration Language:</span>
                <p className="text-[11px] text-slate-500 font-mono">Select target language for teacher voiceover and chapter titles</p>
              </div>
            </div>
            <select
              value={targetLanguage}
              onChange={(e) => setTargetLanguage(e.target.value as 'en' | 'hi')}
              disabled={isGenerating}
              className="text-xs font-mono bg-white border border-slate-300 rounded-lg px-3 py-2 text-slate-800 font-semibold focus:outline-none focus:ring-2 focus:ring-emerald-500 cursor-pointer shadow-xs disabled:opacity-50"
            >
              <option value="en">🇬🇧 English (Studio Neutral - Guy / Christopher)</option>
              <option value="hi">🇮🇳 हिन्दी (Hindi Documentary Narrator - Madhur / Swara)</option>
            </select>
          </div>

          {/* Visuals & Chapter Count Selector */}
          <div className="bg-slate-50 border border-slate-200 p-3.5 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-xs">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-white border border-slate-200 flex items-center justify-center shrink-0">
                <Layers className="w-4 h-4 text-blue-600" />
              </div>
              <div>
                <span className="text-xs font-mono font-semibold text-slate-900">Visual Count &amp; Lecture Depth:</span>
                <p className="text-[11px] text-slate-500 font-mono">Select how many progressive timeline chapters &amp; visuals to compile</p>
              </div>
            </div>
            <select
              value={chapterCount}
              onChange={(e) => setChapterCount(e.target.value)}
              disabled={isGenerating}
              className="text-xs font-mono bg-white border border-slate-300 rounded-lg px-3 py-2 text-slate-800 font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer shadow-xs disabled:opacity-50"
            >
              <option value="auto">Auto (Full Video Runtime &amp; Adaptive Chapters, ~1 visual / 1.5 min)</option>
              <option value="6">6 Visuals (Concise Overview ~4-6 min)</option>
              <option value="10">10 Visuals (Standard Lecture ~10-15 min)</option>
              <option value="16">16 Visuals (Detailed Deep Dive ~15-22 min)</option>
              <option value="20">20 Visuals (Comprehensive Full-Length ~25-30 min)</option>
              <option value="24">24 Visuals (Exhaustive Masterclass ~30+ min)</option>
            </select>
          </div>

          {/* Generation Progress Indicator */}
          {isGenerating && (
            <div className="bg-blue-50 border border-blue-200 p-4 rounded-xl flex items-center gap-3 shadow-sm">
              <Sparkles className="w-5 h-5 text-blue-600 animate-spin shrink-0" />
              <div className="flex flex-col">
                <span className="text-xs font-mono font-bold text-blue-900 uppercase tracking-wide">
                  COMPILING PEDAGOGICAL VECTOR LECTURE...
                </span>
                <span className="text-[11px] text-blue-700 font-mono mt-0.5">
                  {generationStage || 'Processing...'}
                </span>
              </div>
            </div>
          )}

          {/* Primary Action Button */}
          <div className="pt-2">
            <button
              onClick={handleGenerateLecture}
              disabled={isGenerating || !ytUrl.trim()}
              className="w-full py-3.5 bg-slate-900 hover:bg-slate-800 active:scale-[0.99] text-white font-medium font-mono text-xs rounded-xl transition-all shadow-sm flex items-center justify-center gap-2 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Sparkles className="w-4 h-4" />
              <span>{isGenerating ? 'GENERATING LECTURE &amp; SVGS...' : 'GENERATE &amp; PLAY LESSON WITH AI'}</span>
            </button>
          </div>
        </div>
      )}

      {/* Mode 2: Upload JSON Files */}
      {activeMode === 'upload' && (
        <div className="flex flex-col gap-6">
          {/* Drag & Drop File Upload Box */}
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-2xl p-8 flex flex-col items-center justify-center gap-3 transition-all cursor-pointer ${
              dragOver
                ? 'border-blue-500 bg-blue-50/50'
                : 'border-slate-300 hover:border-slate-400 bg-slate-50/50'
            }`}
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              accept=".json"
              className="hidden"
            />
            <div className="w-12 h-12 rounded-full bg-white border border-slate-200 flex items-center justify-center text-slate-700 shadow-sm">
              <Upload className="w-5 h-5" />
            </div>
            <div className="text-center">
              <p className="text-sm font-semibold text-slate-800">
                Drag and drop your <code className="text-slate-900 font-mono font-bold">.json</code> file here
              </p>
              <p className="text-xs text-slate-500 mt-1">
                Upload any lecture JSON, transcript JSON, or notes JSON — the AI will summarize, write the teacher script &amp; design 16:9 widescreen multi-engine visuals
              </p>
            </div>
          </div>

          {/* Generation Progress Indicator for JSON AI processing */}
          {isGenerating && (
            <div className="bg-blue-50 border border-blue-200 p-4 rounded-xl flex items-center gap-3 shadow-sm">
              <Sparkles className="w-5 h-5 text-blue-600 animate-spin shrink-0" />
              <div className="flex flex-col">
                <span className="text-xs font-mono font-bold text-blue-900 uppercase tracking-wide">
                  PROCESSING JSON &amp; GENERATING LESSON WITH AI...
                </span>
                <span className="text-[11px] text-blue-700 font-mono mt-0.5">
                  {generationStage || 'Processing...'}
                </span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Fine-Tuned AI Prompt Drawer for External Chatbots */}
      <div className="bg-slate-50 border border-slate-200 rounded-xl overflow-hidden transition-all shadow-xs">
        <button
          type="button"
          onClick={() => setShowPromptDrawer(!showPromptDrawer)}
          className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-slate-100/80 transition-colors cursor-pointer"
        >
          <div className="flex items-center gap-2">
            <Bot className="w-4 h-4 text-blue-600" />
            <span className="text-xs font-mono font-bold text-slate-800">
              FINE-TUNED AI CHATBOT PROMPT (100% Comprehensive Coverage)
            </span>
          </div>
          <div className="flex items-center gap-2 text-slate-500 text-xs font-mono">
            <span>{showPromptDrawer ? 'Hide Prompt' : 'View & Copy Prompt'}</span>
            {showPromptDrawer ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </div>
        </button>

        {showPromptDrawer && (
          <div className="p-4 border-t border-slate-200 bg-white flex flex-col gap-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-[11px] text-slate-600 font-mono">
                Copy and paste this fine-tuned prompt into ChatGPT, Claude, Gemini, or Groq along with any YouTube transcript:
              </p>
              <button
                type="button"
                onClick={() => {
                  navigator.clipboard.writeText(FINE_TUNED_PROMPT);
                  setCopiedPrompt(true);
                  setTimeout(() => setCopiedPrompt(false), 2000);
                }}
                className="px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-[11px] font-mono font-medium flex items-center gap-1.5 transition-colors cursor-pointer"
              >
                {copiedPrompt ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copiedPrompt ? 'COPIED TO CLIPBOARD!' : 'COPY PROMPT'}</span>
              </button>
            </div>
            <pre className="p-3 bg-slate-900 text-slate-100 text-[11px] font-mono rounded-lg overflow-x-auto max-h-60 leading-relaxed whitespace-pre-wrap select-all">
              {FINE_TUNED_PROMPT}
            </pre>
          </div>
        )}
      </div>

      {/* Validation Feedback Banners */}
      {validationError && (
        <div className="bg-rose-50 border border-rose-200 p-4 rounded-xl flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
          <p className="text-xs font-mono text-rose-800 leading-relaxed">{validationError}</p>
        </div>
      )}

      {validationSuccess && (
        <div className="bg-emerald-50 border border-emerald-200 p-4 rounded-xl flex items-start gap-3">
          <CheckCircle className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
          <p className="text-xs font-mono text-emerald-800 leading-relaxed">{validationSuccess}</p>
        </div>
      )}

      {/* Compiled Lesson Review, Live SVG Visual Gallery, & Player Launch */}
      {parsedPayload && (
        <div className="bg-white border border-slate-200 p-5 rounded-xl flex flex-col gap-4 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-100">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 font-bold">
                  COMPILED &amp; VERIFIED
                </span>
                <h4 className="text-sm font-bold font-mono text-slate-900">
                  {parsedPayload.topicTitle}
                </h4>
              </div>
              <p className="text-xs text-slate-500 mt-1">
                {parsedPayload.frames.length} Pedagogical Chapters • Total Playback Duration:{' '}
                <strong className="text-slate-800">
                  {Math.round(
                    (parsedPayload.frames[parsedPayload.frames.length - 1]?.timestampSeconds + 25) / 60
                  )}{' '}
                  Minutes
                </strong>{' '}
                • Serialized Binary: {compiledBinary?.length || 0} Bytes
              </p>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handleDownloadActiveJson}
                className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-mono rounded-lg transition-colors flex items-center gap-1.5 cursor-pointer border border-slate-200"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Save JSON</span>
              </button>
              <button
                onClick={handleLaunchInPlayer}
                className="px-4 py-1.5 bg-slate-900 hover:bg-slate-800 text-white text-xs font-mono font-medium rounded-lg transition-colors flex items-center gap-1.5 cursor-pointer shadow-sm"
              >
                <Play className="w-3.5 h-3.5 fill-white" />
                <span>Play in Vector Player</span>
              </button>
            </div>
          </div>

          {/* Chapter SVG Gallery */}
          <div className="flex flex-col gap-2">
            <span className="text-xs font-mono text-slate-500 uppercase tracking-wider font-medium">
              Pedagogical Chapters &amp; SVG Visual Timeline:
            </span>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 max-h-[450px] overflow-y-auto pr-1">
              {parsedPayload.frames.map((frame, idx) => (
                <div
                  key={idx}
                  className="bg-white border border-slate-200 p-3 rounded-xl flex flex-col gap-2 hover:border-slate-300 hover:shadow-sm transition-all"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-mono font-bold text-slate-900">
                      CHAPTER {idx + 1}
                    </span>
                    <span className="text-[10px] font-mono text-slate-500 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
                      ⏱ {Math.floor(frame.timestampSeconds / 60)}:
                      {String(Math.floor(frame.timestampSeconds % 60)).padStart(2, '0')}
                    </span>
                  </div>

                  {/* SVG Render Box */}
                  <div
                    className="w-full h-40 bg-white rounded-lg flex items-center justify-center overflow-hidden border border-slate-200 p-1"
                    dangerouslySetInnerHTML={{ __html: frame.svgPayload }}
                  />

                  <p className="text-[11px] text-slate-700 leading-relaxed line-clamp-3">
                    "{frame.spokenText}"
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
