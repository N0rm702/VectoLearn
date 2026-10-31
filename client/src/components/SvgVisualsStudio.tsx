import React, { useState, useEffect, useMemo } from 'react';
import type { LecturePayload } from '../types/lecture';
import {
  detectVisualEngine,
  resolveVisualToSvg,
  type VisualEngineType,
  type VisualResolutionResult,
} from '../services/visualEngineResolver';
import {
  Sparkles,
  Copy,
  Check,
  Download,
  Play,
  Code,
  Layers,
  Plus,
  AlertCircle,
  CheckCircle,
  Eye,
  GitBranch,
  BarChart2,
  Compass,
  FileCode,
} from 'lucide-react';

interface SvgVisualsStudioProps {
  currentLecture: LecturePayload;
  onSeekToFrame?: (timestampSeconds: number) => void;
  onInjectCustomSvg?: (svgMarkup: string, label: string) => void;
}

const TEMPLATES: Record<
  VisualEngineType,
  { label: string; code: string; title: string; hint: string }
> = {
  mermaid: {
    label: 'Mermaid.js Flowchart',
    title: 'System Architectural Flowchart',
    hint: 'Relational logic, state transitions & algorithmic branching',
    code: `flowchart TD
  A["Physical Signal / Sensor Input"] --> B["Digital Signal Processor"]
  B --> C["Feature Extraction Model"]
  C --> D["Adaptive Neural Classifier"]
  D --> E["Low-Latency Output Stream"]
  style A fill:#eff6ff,stroke:#2563eb,stroke-width:2px
  style B fill:#eff6ff,stroke:#2563eb,stroke-width:2px
  style C fill:#eff6ff,stroke:#2563eb,stroke-width:2px
  style D fill:#eff6ff,stroke:#2563eb,stroke-width:2px
  style E fill:#f0fdf4,stroke:#16a34a,stroke-width:2px`,
  },
  d3: {
    label: 'D3.js Coordinate Model',
    title: 'Quantitative Curve Distribution',
    hint: 'Calculus curves, probability distributions & coordinate plots',
    code: `{
  "title": "Quantum Wavefunction & Energy State",
  "xLabel": "Radial Distance r (Bohr Radii)",
  "yLabel": "Probability Density |Ψ|²",
  "points": [
    [0, 5],
    [1, 28],
    [2, 75],
    [3, 94],
    [4, 82],
    [5, 53],
    [6, 30],
    [7, 16],
    [8, 8],
    [9, 4],
    [10, 2]
  ]
}`,
  },
  manim: {
    label: 'Manim Vector Math (3B1B)',
    title: 'Dynamic Vector Field Manifold',
    hint: 'Chalkboard aesthetics, vector fields & tangent derivatives',
    code: `manim-vector: Topic: Vector Calculus & Directional Gradient Field. Formula: ∇f(x,y) = [∂f/∂x, ∂f/∂y] • dy/dx = tan(θ). Showing tangent velocity vectors and 2D curvature manifold.`,
  },
  svg: {
    label: 'Pure Vector SVG',
    title: 'Physical & Anatomical Cross-Section',
    hint: 'Precise geometric schematics, physical hardware & anatomy',
    code: `<svg viewBox="0 0 800 450" xmlns="http://www.w3.org/2000/svg" data-engine="svg">
  <rect width="800" height="450" fill="#ffffff" rx="14" stroke="#e2e8f0" stroke-width="1.5"/>
  <rect x="40" y="20" width="720" height="34" rx="8" fill="#eff6ff" stroke="#bfdbfe" stroke-width="1.2"/>
  <text x="400" y="42" font-family="system-ui, sans-serif" font-size="14" font-weight="700" fill="#1e40af" text-anchor="middle">ATOMIC ORBITAL &amp; ELECTRON CONFIGURATION SCHEMATIC</text>

  <!-- Left: Physical Orbital System -->
  <g transform="translate(180, 245)">
    <circle cx="0" cy="0" r="140" fill="none" stroke="#93c5fd" stroke-width="1.5" stroke-dasharray="6,4"/>
    <circle cx="0" cy="0" r="95" fill="none" stroke="#3b82f6" stroke-width="2" stroke-dasharray="8,5"/>
    <circle cx="0" cy="0" r="50" fill="#eff6ff" stroke="#2563eb" stroke-width="2.5"/>
    <circle cx="0" cy="0" r="18" fill="#1d4ed8"/>
    <!-- Orbiting Electrons -->
    <circle cx="95" cy="0" r="6" fill="#f59e0b" stroke="#ffffff" stroke-width="1.5"/>
    <circle cx="-67" cy="67" r="6" fill="#f59e0b" stroke="#ffffff" stroke-width="1.5"/>
    <circle cx="0" cy="-140" r="6" fill="#10b981" stroke="#ffffff" stroke-width="1.5"/>
    <text x="0" y="175" font-family="system-ui, sans-serif" font-size="12" font-weight="700" fill="#0f172a" text-anchor="middle">Quantized Shell Radii (n=1, n=2, n=3)</text>
  </g>

  <!-- Right: Energy Levels & Structural Key -->
  <rect x="440" y="80" width="310" height="300" rx="12" fill="#f8fafc" stroke="#e2e8f0" stroke-width="1.5"/>
  <text x="460" y="115" font-family="system-ui, sans-serif" font-size="13" font-weight="700" fill="#0f172a">STRUCTURAL PROPERTIES</text>
  <line x1="460" y1="128" x2="730" y2="128" stroke="#cbd5e1" stroke-width="1"/>
  <text x="460" y="160" font-family="system-ui, sans-serif" font-size="11" font-weight="600" fill="#2563eb">• Nucleus: High-density proton/neutron core</text>
  <text x="460" y="195" font-family="system-ui, sans-serif" font-size="11" font-weight="600" fill="#059669">• Ground State n=1: Maximum binding energy</text>
  <text x="460" y="230" font-family="system-ui, sans-serif" font-size="11" font-weight="600" fill="#d97706">• Excited State n=2: Valence transition orbital</text>
  <text x="460" y="265" font-family="system-ui, sans-serif" font-size="11" font-weight="600" fill="#475569">• Potential Well: V(r) = -k·e²/r Coulomb attraction</text>
  <rect x="460" y="295" width="270" height="60" rx="8" fill="#eff6ff" stroke="#bfdbfe" stroke-width="1"/>
  <text x="595" y="322" font-family="system-ui, sans-serif" font-size="11" font-weight="700" fill="#1e40af" text-anchor="middle">ΔE = h·ν = E₂ - E₁</text>
  <text x="595" y="342" font-family="system-ui, sans-serif" font-size="10" fill="#64748b" text-anchor="middle">Photon Emission / Absorption Wavelength</text>
</svg>`,
  },
};

const EngineBadge: React.FC<{ engine: VisualEngineType; size?: 'sm' | 'md' }> = ({
  engine,
  size = 'sm',
}) => {
  const styles = {
    mermaid: {
      bg: 'bg-indigo-50 text-indigo-700 border-indigo-200',
      dot: 'bg-indigo-600',
      label: 'Mermaid.js Flowchart',
      shortLabel: 'Mermaid',
    },
    d3: {
      bg: 'bg-sky-50 text-sky-700 border-sky-200',
      dot: 'bg-sky-600',
      label: 'D3.js Coordinate Model',
      shortLabel: 'D3.js',
    },
    manim: {
      bg: 'bg-amber-50 text-amber-800 border-amber-200',
      dot: 'bg-amber-600',
      label: 'Manim Vector Math (3B1B)',
      shortLabel: 'Manim',
    },
    svg: {
      bg: 'bg-emerald-50 text-emerald-700 border-emerald-200',
      dot: 'bg-emerald-600',
      label: 'Pure Vector SVG',
      shortLabel: 'Pure SVG',
    },
  }[engine] || {
    bg: 'bg-slate-100 text-slate-700 border-slate-200',
    dot: 'bg-slate-500',
    label: 'Vector SVG',
    shortLabel: 'SVG',
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-mono font-medium rounded border ${styles.bg} ${
        size === 'sm' ? 'px-1.5 py-0.5 text-[10px]' : 'px-2 py-0.5 text-xs'
      }`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${styles.dot}`} />
      <span>{size === 'sm' ? styles.shortLabel : styles.label}</span>
    </span>
  );
};

export const SvgVisualsStudio: React.FC<SvgVisualsStudioProps> = ({
  currentLecture,
  onSeekToFrame,
  onInjectCustomSvg,
}) => {
  const [selectedFrameIdx, setSelectedFrameIdx] = useState<number>(0);
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const [showRawCode, setShowRawCode] = useState<boolean>(false);
  const [engineFilter, setEngineFilter] = useState<'all' | VisualEngineType>('all');

  // Resolved visuals cache for the current lecture
  const [resolvedMap, setResolvedMap] = useState<Record<number, VisualResolutionResult>>({});

  // Custom visual playground injector
  const [customInput, setCustomInput] = useState<string>(TEMPLATES.mermaid.code);
  const [previewResolved, setPreviewResolved] = useState<VisualResolutionResult | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [injectionSuccess, setInjectionSuccess] = useState<string | null>(null);

  const frames = currentLecture.frames || [];
  const activeFrame = frames[selectedFrameIdx] || frames[0];

  // Resolve all lecture frames to render Mermaid, D3, Manim & SVG cleanly
  useEffect(() => {
    let isMounted = true;
    const resolveAll = async () => {
      const results: Record<number, VisualResolutionResult> = {};
      for (let i = 0; i < frames.length; i++) {
        const frame = frames[i];
        if (frame.svgPayload) {
          try {
            const res = await resolveVisualToSvg(
              frame.svgPayload,
              currentLecture.topicTitle || 'Educational Lesson'
            );
            results[i] = res;
          } catch (e) {
            console.warn(`Frame ${i} resolution failed:`, e);
            results[i] = {
              svg: frame.svgPayload,
              engine: (frame.visualEngine as VisualEngineType) || detectVisualEngine(frame.svgPayload),
              rawPayload: frame.svgPayload,
            };
          }
        }
      }
      if (isMounted) {
        setResolvedMap(results);
      }
    };

    resolveAll();
    return () => {
      isMounted = false;
    };
  }, [currentLecture.topicTitle, frames]);

  // Resolve custom visual preview on input change
  useEffect(() => {
    let isMounted = true;
    const runResolution = async () => {
      setPreviewError(null);
      if (!customInput.trim()) {
        setPreviewResolved(null);
        return;
      }
      try {
        const res = await resolveVisualToSvg(
          customInput,
          currentLecture.topicTitle || 'Custom Vector Visual'
        );
        if (isMounted) {
          setPreviewResolved(res);
        }
      } catch (err: any) {
        if (isMounted) {
          setPreviewError(err?.message || 'Failed to compile visual markup');
        }
      }
    };

    const timer = setTimeout(runResolution, 200);
    return () => {
      isMounted = false;
      clearTimeout(timer);
    };
  }, [customInput, currentLecture.topicTitle]);

  // Frame counts per engine
  const engineCounts = useMemo(() => {
    const counts: Record<string, number> = {
      all: frames.length,
      mermaid: 0,
      d3: 0,
      manim: 0,
      svg: 0,
    };
    frames.forEach((f, idx) => {
      const eng = resolvedMap[idx]?.engine || detectVisualEngine(f.svgPayload || '');
      counts[eng] = (counts[eng] || 0) + 1;
    });
    return counts;
  }, [frames, resolvedMap]);

  // Filtered frames
  const filteredFrames = useMemo(() => {
    return frames
      .map((frame, originalIdx) => {
        const engine =
          resolvedMap[originalIdx]?.engine ||
          (frame.visualEngine as VisualEngineType) ||
          detectVisualEngine(frame.svgPayload || '');
        const resolvedSvg = resolvedMap[originalIdx]?.svg || frame.svgPayload;
        return { frame, originalIdx, engine, resolvedSvg };
      })
      .filter((item) => engineFilter === 'all' || item.engine === engineFilter);
  }, [frames, resolvedMap, engineFilter]);

  const activeResolved = resolvedMap[selectedFrameIdx] || {
    svg: activeFrame?.svgPayload || '',
    engine:
      (activeFrame?.visualEngine as VisualEngineType) ||
      detectVisualEngine(activeFrame?.svgPayload || ''),
    rawPayload: activeFrame?.svgPayload || '',
  };

  const handleCopySvg = (svgText: string, idx: number) => {
    navigator.clipboard.writeText(svgText);
    setCopiedIdx(idx);
    setTimeout(() => setCopiedIdx(null), 2000);
  };

  const handleDownloadSvg = (svgText: string, filename: string) => {
    const blob = new Blob([svgText], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${filename}.svg`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleSelectTemplate = (eng: VisualEngineType) => {
    setCustomInput(TEMPLATES[eng].code);
  };

  const handleInjectCustom = () => {
    setPreviewError(null);
    setInjectionSuccess(null);

    if (!customInput.trim()) {
      setPreviewError('Visual code cannot be empty');
      return;
    }

    if (onInjectCustomSvg) {
      const eng = detectVisualEngine(customInput);
      const title = TEMPLATES[eng]?.title || 'Custom Visual Model';
      onInjectCustomSvg(customInput, title);
      setInjectionSuccess(`Successfully injected ${eng.toUpperCase()} model into player canvas stage!`);
      setTimeout(() => setInjectionSuccess(null), 3500);
    }
  };

  return (
    <div className="minimal-card p-6 rounded-2xl w-full shadow-sm flex flex-col gap-6">
      {/* Header bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-100">
        <div>
          <div className="flex items-center gap-2">
            <Layers className="w-5 h-5 text-slate-800" />
            <h3 className="text-base font-semibold text-slate-900 tracking-tight">
              Multi-Engine Visuals Studio &amp; Model Inspector
            </h3>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Interactive multi-model pipeline: Mermaid.js, D3.js, Pure SVG, and Manim Vector SVG ({frames.length} frames • 16:9 Widescreen 800x450 ViewBox)
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowRawCode(!showRawCode)}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono transition-all flex items-center gap-1.5 cursor-pointer border ${
              showRawCode
                ? 'bg-slate-900 border-slate-900 text-white font-medium'
                : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300'
            }`}
          >
            <Code className="w-3.5 h-3.5" />
            <span>{showRawCode ? 'Hide Code' : 'View Source / XML'}</span>
          </button>
        </div>
      </div>

      {/* Engine Filter Bar */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-mono text-slate-500 mr-1">Filter by Engine:</span>

        <button
          onClick={() => setEngineFilter('all')}
          className={`px-2.5 py-1 rounded-lg text-xs font-mono transition-all cursor-pointer border ${
            engineFilter === 'all'
              ? 'bg-slate-900 text-white border-slate-900 font-semibold shadow-sm'
              : 'bg-white text-slate-600 border-slate-200 hover:border-slate-300'
          }`}
        >
          All ({engineCounts.all || 0})
        </button>

        <button
          onClick={() => setEngineFilter('mermaid')}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-mono transition-all cursor-pointer border ${
            engineFilter === 'mermaid'
              ? 'bg-indigo-600 text-white border-indigo-600 font-semibold shadow-sm'
              : 'bg-white text-slate-600 border-slate-200 hover:border-slate-300'
          }`}
        >
          <GitBranch className="w-3 h-3" />
          <span>Mermaid.js ({engineCounts.mermaid || 0})</span>
        </button>

        <button
          onClick={() => setEngineFilter('d3')}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-mono transition-all cursor-pointer border ${
            engineFilter === 'd3'
              ? 'bg-sky-600 text-white border-sky-600 font-semibold shadow-sm'
              : 'bg-white text-slate-600 border-slate-200 hover:border-slate-300'
          }`}
        >
          <BarChart2 className="w-3 h-3" />
          <span>D3.js ({engineCounts.d3 || 0})</span>
        </button>

        <button
          onClick={() => setEngineFilter('manim')}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-mono transition-all cursor-pointer border ${
            engineFilter === 'manim'
              ? 'bg-amber-600 text-white border-amber-600 font-semibold shadow-sm'
              : 'bg-white text-slate-600 border-slate-200 hover:border-slate-300'
          }`}
        >
          <Compass className="w-3 h-3" />
          <span>Manim 3B1B ({engineCounts.manim || 0})</span>
        </button>

        <button
          onClick={() => setEngineFilter('svg')}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-mono transition-all cursor-pointer border ${
            engineFilter === 'svg'
              ? 'bg-emerald-600 text-white border-emerald-600 font-semibold shadow-sm'
              : 'bg-white text-slate-600 border-slate-200 hover:border-slate-300'
          }`}
        >
          <FileCode className="w-3 h-3" />
          <span>Pure SVG ({engineCounts.svg || 0})</span>
        </button>
      </div>

      {/* Main Grid: Active Frame Showcase + Thumbnails Selector */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Active Selected Frame Preview (400x400 Canvas Display) */}
        <div className="lg:col-span-7 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono font-medium text-slate-700 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
                FRAME {selectedFrameIdx + 1} OF {frames.length}
              </span>
              <span className="text-xs font-mono text-slate-500">
                ⏱ {Math.floor((activeFrame?.timestampSeconds || 0) / 60)}:
                {String(Math.floor((activeFrame?.timestampSeconds || 0) % 60)).padStart(2, '0')}
              </span>
              <EngineBadge engine={activeResolved.engine} size="md" />
            </div>

            <div className="flex items-center gap-2">
              {onSeekToFrame && activeFrame && (
                <button
                  onClick={() => onSeekToFrame(activeFrame.timestampSeconds)}
                  className="px-3 py-1 bg-slate-900 hover:bg-slate-800 text-white font-medium text-xs font-mono rounded-lg transition-all flex items-center gap-1.5 cursor-pointer shadow-sm"
                >
                  <Play className="w-3 h-3 fill-white" />
                  <span>Seek in Player</span>
                </button>
              )}

              {activeResolved.svg && (
                <>
                  <button
                    onClick={() => handleCopySvg(activeResolved.svg, selectedFrameIdx)}
                    title="Copy resolved SVG markup"
                    className="p-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg transition-colors cursor-pointer border border-slate-200"
                  >
                    {copiedIdx === selectedFrameIdx ? (
                      <Check className="w-3.5 h-3.5 text-emerald-600" />
                    ) : (
                      <Copy className="w-3.5 h-3.5" />
                    )}
                  </button>

                  <button
                    onClick={() =>
                      handleDownloadSvg(
                        activeResolved.svg,
                        `frame_${selectedFrameIdx + 1}_${activeResolved.engine}_${currentLecture.topicTitle
                          .toLowerCase()
                          .replace(/[^a-z0-9]/g, '_')}`
                      )
                    }
                    title="Download .svg file"
                    className="p-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg transition-colors cursor-pointer border border-slate-200"
                  >
                    <Download className="w-3.5 h-3.5" />
                  </button>
                </>
              )}
            </div>
          </div>

          {/* Rendered Visual Box */}
          <div className="bg-white border border-slate-200 rounded-2xl p-3 flex items-center justify-center overflow-hidden w-full aspect-[16/9] min-h-[300px] md:min-h-[380px] shadow-sm">
            {activeResolved.svg ? (
              <div
                className="w-full h-full flex items-center justify-center"
                dangerouslySetInnerHTML={{ __html: activeResolved.svg }}
              />
            ) : (
              <div className="text-slate-400 font-mono text-xs">Compiling visual engine model...</div>
            )}
          </div>

          {/* Accompanying Teacher Narration */}
          {activeFrame?.spokenText && (
            <div className="bg-slate-50 border border-slate-200 p-3.5 rounded-xl text-xs text-slate-700 leading-relaxed">
              <span className="text-slate-900 font-semibold block mb-1">
                Teacher Narration Script:
              </span>
              "{activeFrame.spokenText}"
            </div>
          )}

          {/* Raw Source Code Viewer */}
          {showRawCode && (
            <div className="relative">
              <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl text-[11px] font-mono text-slate-200 overflow-x-auto max-h-56 leading-relaxed">
                <div className="text-[10px] text-slate-400 mb-2 border-b border-slate-800 pb-1">
                  Engine: {activeResolved.engine.toUpperCase()} • Raw Payload &amp; Compiled SVG
                </div>
                {activeFrame?.svgPayload}
              </div>
            </div>
          )}
        </div>

        {/* Right: Filtered Chapter Cards */}
        <div className="lg:col-span-5 flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-slate-500 uppercase tracking-wider">
              {engineFilter === 'all' ? 'All Visual Models' : `${engineFilter.toUpperCase()} Models`} ({filteredFrames.length}):
            </span>
            <span className="text-[10px] font-mono text-slate-400">Click card to inspect</span>
          </div>

          <div className="flex flex-col gap-2.5 max-h-[360px] overflow-y-auto pr-1">
            {filteredFrames.length === 0 ? (
              <div className="text-center py-8 text-xs font-mono text-slate-400 bg-slate-50 rounded-xl border border-dashed border-slate-200">
                No frames match filter "{engineFilter}"
              </div>
            ) : (
              filteredFrames.map(({ frame, originalIdx, engine, resolvedSvg }) => {
                const isSelected = selectedFrameIdx === originalIdx;
                return (
                  <div
                    key={originalIdx}
                    onClick={() => setSelectedFrameIdx(originalIdx)}
                    className={`p-2.5 rounded-xl border transition-all cursor-pointer flex items-center gap-3 ${
                      isSelected
                        ? 'bg-slate-50 border-slate-900 shadow-sm ring-1 ring-slate-900/10'
                        : 'bg-white border-slate-200 hover:border-slate-300'
                    }`}
                  >
                    {/* Thumbnail Preview */}
                    <div
                      className="w-16 h-16 rounded-lg bg-slate-50 border border-slate-200 flex items-center justify-center shrink-0 overflow-hidden p-0.5"
                      dangerouslySetInnerHTML={{ __html: resolvedSvg || frame.svgPayload }}
                    />

                    <div className="flex flex-col flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-mono font-semibold text-slate-900">
                          Chapter {originalIdx + 1}
                        </span>
                        <EngineBadge engine={engine} size="sm" />
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-mono text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">
                          ⏱ {Math.floor(frame.timestampSeconds / 60)}:
                          {String(Math.floor(frame.timestampSeconds % 60)).padStart(2, '0')}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-600 line-clamp-1 mt-1">
                        {frame.spokenText}
                      </p>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* Multi-Engine Playground & Live Custom Injector */}
      <div className="bg-slate-50 border border-slate-200 p-5 rounded-2xl flex flex-col gap-4 mt-2">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 pb-3">
          <div className="flex items-center gap-2">
            <Plus className="w-4 h-4 text-slate-800" />
            <h4 className="text-sm font-semibold text-slate-900">
              Multi-Engine Visual Playground &amp; Injector
            </h4>
          </div>
          <span className="text-[10px] font-mono text-slate-500">
            Auto-detects engine • 0-Latency Client-Side Compiler
          </span>
        </div>

        {/* Template Buttons */}
        <div className="flex flex-col gap-1.5">
          <span className="text-xs font-mono text-slate-600 font-medium">
            Load Template Preset:
          </span>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {(['mermaid', 'd3', 'manim', 'svg'] as VisualEngineType[]).map((eng) => (
              <button
                key={eng}
                onClick={() => handleSelectTemplate(eng)}
                className="px-3 py-2 bg-white hover:bg-slate-100 border border-slate-200 rounded-xl text-left transition-all cursor-pointer shadow-2xs flex flex-col gap-0.5"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono font-semibold text-slate-800">
                    + {eng === 'manim' ? 'Manim 3B1B' : eng === 'd3' ? 'D3 Chart' : eng === 'mermaid' ? 'Mermaid Flow' : 'Pure SVG'}
                  </span>
                  <EngineBadge engine={eng} size="sm" />
                </div>
                <span className="text-[10px] text-slate-500 line-clamp-1">
                  {TEMPLATES[eng].hint}
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* Code Editor & Live Preview Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          {/* Input Textarea */}
          <div className="lg:col-span-7 flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono text-slate-700 font-medium">
                Visual Code Payload:
              </span>
              {previewResolved && <EngineBadge engine={previewResolved.engine} size="sm" />}
            </div>

            <textarea
              rows={9}
              value={customInput}
              onChange={(e) => setCustomInput(e.target.value)}
              className="w-full bg-white border border-slate-200 rounded-xl p-3 text-[11px] font-mono text-slate-800 focus:outline-none focus:border-slate-400 focus:ring-1 focus:ring-slate-400 font-mono resize-y"
              placeholder="Paste Mermaid flowchart syntax, D3 chart spec JSON, Manim vector description, or <svg> markup..."
            />
          </div>

          {/* Real-time Render Preview */}
          <div className="lg:col-span-5 flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono text-slate-700 font-medium flex items-center gap-1.5">
                <Eye className="w-3.5 h-3.5 text-slate-600" />
                Live 16:9 Preview:
              </span>
              <span className="text-[10px] font-mono text-slate-400">Realtime</span>
            </div>

            <div className="w-full aspect-[16/9] bg-white border border-slate-200 rounded-xl p-2 flex items-center justify-center overflow-hidden shadow-2xs">
              {previewError ? (
                <div className="text-rose-600 font-mono text-xs text-center p-3">
                  {previewError}
                </div>
              ) : previewResolved?.svg ? (
                <div
                  className="w-full h-full flex items-center justify-center"
                  dangerouslySetInnerHTML={{ __html: previewResolved.svg }}
                />
              ) : (
                <div className="text-slate-400 font-mono text-xs">Waiting for input...</div>
              )}
            </div>
          </div>
        </div>

        {previewError && (
          <div className="flex items-center gap-2 text-rose-700 text-xs font-mono bg-rose-50 p-2.5 rounded-lg border border-rose-200">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{previewError}</span>
          </div>
        )}

        {injectionSuccess && (
          <div className="flex items-center gap-2 text-emerald-800 text-xs font-mono bg-emerald-50 p-2.5 rounded-lg border border-emerald-200">
            <CheckCircle className="w-4 h-4 shrink-0" />
            <span>{injectionSuccess}</span>
          </div>
        )}

        <button
          onClick={handleInjectCustom}
          className="w-full py-2.5 bg-slate-900 hover:bg-slate-800 text-white font-medium text-xs font-mono rounded-xl transition-all flex items-center justify-center gap-2 cursor-pointer shadow-sm"
        >
          <Sparkles className="w-4 h-4" />
          <span>Inject Model into Player Canvas Stage</span>
        </button>
      </div>
    </div>
  );
};
