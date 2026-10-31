import mermaid from 'mermaid';
import * as d3 from 'd3';

export type VisualEngineType = 'mermaid' | 'd3' | 'svg' | 'manim';

export interface VisualResolutionResult {
  svg: string;
  engine: VisualEngineType;
  rawPayload: string;
}

// Initialize Mermaid once with neutral educational theme
let mermaidInitialized = false;
function ensureMermaidInitialized() {
  if (!mermaidInitialized && typeof window !== 'undefined') {
    try {
      mermaid.initialize({
        startOnLoad: false,
        suppressErrorRendering: true,
        theme: 'neutral',
        securityLevel: 'loose',
        fontFamily: 'ui-sans-serif, system-ui, sans-serif',
        themeVariables: {
          primaryColor: '#eff6ff',
          primaryTextColor: '#0f172a',
          primaryBorderColor: '#93c5fd',
          lineColor: '#475569',
          secondaryColor: '#f8fafc',
          tertiaryColor: '#ffffff',
          mainBkg: '#ffffff',
          nodeBorder: '#94a3b8',
        },
      });

      // Override Mermaid parseError to prevent it from injecting error DOM elements into the body
      try {
        (mermaid as any).parseError = (err: any) => {
          console.warn('Suppressed Mermaid parse error:', err);
        };
      } catch {
        // Ignore
      }

      mermaidInitialized = true;
    } catch (e) {
      console.warn('Mermaid initialization warning:', e);
    }
  }
}

/**
 * Sanitizes and repairs raw Mermaid syntax to prevent parsing exceptions
 * (e.g. automatically quotes brackets, parens, colons, and question marks inside node text).
 */
export function sanitizeMermaidCode(code: string): string {
  let clean = code
    .replace(/^```(?:mermaid)?\s*/i, '')
    .replace(/\s*```$/i, '')
    .trim();

  // Ensure standard diagram header exists
  if (!/^(flowchart|graph|sequenceDiagram|stateDiagram|classDiagram|erDiagram|gantt|pie)/m.test(clean)) {
    clean = 'flowchart TD\n' + clean;
  }

  const lines = clean.split('\n');
  const sanitizedLines = lines.map((line) => {
    let l = line.trimEnd();

    // Skip comment lines or style directive lines
    if (l.trim().startsWith('%%') || l.trim().startsWith('style ') || l.trim().startsWith('classDef ')) {
      return l;
    }

    // Auto-quote unquoted square bracket nodes: Node[Text here] -> Node["Text here"]
    l = l.replace(/(?<=[A-Za-z0-9_-])\[([^"\]\n][^\]\n]*?)\]/g, (_match, inner) => {
      const safe = inner.replace(/"/g, "'").trim();
      return `["${safe}"]`;
    });

    // Auto-quote unquoted curly bracket decision nodes: Node{Text here?} -> Node{"Text here?"}
    l = l.replace(/(?<=[A-Za-z0-9_-])\{([^"\}\n][^\}\n]*?)\}/g, (_match, inner) => {
      const safe = inner.replace(/"/g, "'").trim();
      return `{"${safe}"}`;
    });

    // Auto-quote unquoted parentheses nodes: Node(Text here) -> Node("Text here")
    l = l.replace(/(?<=[A-Za-z0-9_-])\((?!\()([^"'\(\)\n][^\(\)\n]*?)\)/g, (_match, inner) => {
      const safe = inner.replace(/"/g, "'").trim();
      return `("${safe}")`;
    });

    // Clean up arrow transition labels with colons
    l = l.replace(/(-->|-.->|==>)\|([^|]+)\|/g, (_match, arrow, label) => {
      const cleanLabel = label.replace(/[":;]/g, ' ').trim();
      return `${arrow}|${cleanLabel}|`;
    });

    return l;
  });

  return sanitizedLines.join('\n');
}

/**
 * Detects which engine should be used for the given raw visual payload.
 */
export function detectVisualEngine(payload: string): VisualEngineType {
  const trimmed = payload.trim();

  // 1. Check for Mermaid syntax or code fence
  if (
    trimmed.startsWith('```mermaid') ||
    trimmed.startsWith('graph ') ||
    trimmed.startsWith('graph\n') ||
    trimmed.startsWith('flowchart ') ||
    trimmed.startsWith('flowchart\n') ||
    trimmed.startsWith('sequenceDiagram') ||
    trimmed.startsWith('stateDiagram') ||
    trimmed.startsWith('classDiagram') ||
    trimmed.startsWith('erDiagram') ||
    trimmed.startsWith('pie ') ||
    (trimmed.includes('-->') && !trimmed.startsWith('<svg'))
  ) {
    return 'mermaid';
  }

  // 2. Check for D3 spec, math_graph equations, or D3 markers
  if (
    trimmed.includes('data-engine="d3"') ||
    trimmed.includes('d3-chart') ||
    trimmed.startsWith('```d3') ||
    (trimmed.startsWith('{') && (
      trimmed.includes('"d3"') ||
      trimmed.includes('"chartType"') ||
      trimmed.includes('"points"') ||
      trimmed.includes('"equation"') ||
      trimmed.includes('"math_graph"')
    ))
  ) {
    return 'd3';
  }

  // 3. Check for Manim markers or parametric templates
  if (
    trimmed.includes('data-engine="manim"') ||
    trimmed.includes('manim-vector') ||
    trimmed.includes('3b1b') ||
    trimmed.includes('vector-field') ||
    (trimmed.startsWith('<svg') && trimmed.includes('manim')) ||
    (trimmed.startsWith('{') && (trimmed.includes('"template"') || trimmed.includes('"parametric_template"')))
  ) {
    return 'manim';
  }

  // Default: Pure SVG / basic_geometry
  return 'svg';
}

/**
 * Compiles Mermaid code into a clean, 16:9 widescreen 800x450 responsive SVG string.
 */
export async function renderMermaidToSvg(code: string): Promise<string> {
  ensureMermaidInitialized();
  const cleanCode = sanitizeMermaidCode(code);
  const renderId = 'diagram-' + Math.random().toString(36).substring(2, 9);

  // Helper to remove any rogue error element that Mermaid by default appends to the document body
  const purgeMermaidErrorElements = () => {
    if (typeof document !== 'undefined') {
      const errElem = document.getElementById(`d${renderId}`);
      if (errElem) errElem.remove();
      const containerElem = document.getElementById(renderId);
      if (containerElem) containerElem.remove();
      // Purge any lingering error elements created by Mermaid
      document.querySelectorAll('.error-icon, .mermaid-error, .error-text').forEach((el) => {
        el.closest('div')?.remove();
        el.remove();
      });
      // Purge any rogue div in body containing mermaid syntax error text
      document.querySelectorAll('body > div').forEach((el) => {
        if (el.textContent?.includes('Syntax error') && el.textContent?.includes('mermaid')) {
          el.remove();
        }
      });
    }
  };

  try {
    const { svg } = await mermaid.render(renderId, cleanCode);
    purgeMermaidErrorElements();

    // Format and fit inside 16:9 800x450 stage using a responsive nested SVG canvas
    const parser = new DOMParser();
    const doc = parser.parseFromString(svg, 'image/svg+xml');
    const svgElem = doc.querySelector('svg');

    if (svgElem) {
      // Remove hardcoded width/height/style constraints so it scales cleanly
      svgElem.removeAttribute('style');
      svgElem.removeAttribute('width');
      svgElem.removeAttribute('height');
      svgElem.setAttribute('x', '24');
      svgElem.setAttribute('y', '20');
      svgElem.setAttribute('width', '752');
      svgElem.setAttribute('height', '410');
      svgElem.setAttribute('preserveAspectRatio', 'xMidYMid meet');

      const innerSvgXml = new XMLSerializer().serializeToString(svgElem);

      return `<svg viewBox="0 0 800 450" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" data-engine="mermaid">
  <rect width="800" height="450" fill="#0f172a" rx="14" stroke="#1e293b" stroke-width="1.5"/>
  ${innerSvgXml}
</svg>`;
    }
    return svg;
  } catch (err) {
    console.warn('Mermaid render error, generating fallback SVG diagram:', err);
    purgeMermaidErrorElements();
    return generateFallbackMermaidSvg(cleanCode);
  } finally {
    purgeMermaidErrorElements();
  }
}

/**
 * Fallback generator for Mermaid syntax when rendering in non-standard environments
 */
function generateFallbackMermaidSvg(code: string): string {
  const lines = code.split('\n').filter((l) => l.includes('-->') || l.includes('->'));
  const nodes = new Set<string>();

  const extractLabel = (raw: string): string => {
    const match = raw.match(/[\[\{\(]["']?([^\]\}\)"']+)["']?[\]\}\)]/);
    if (match && match[1]) {
      return match[1].trim();
    }
    return raw
      .replace(/^[A-Za-z0-9_-]+\s*[:=]?\s*/, '')
      .replace(/["'\[\]\{\}\(\)]/g, '')
      .trim();
  };

  for (const line of lines) {
    const parts = line.split(/-->|->/);
    if (parts.length >= 2) {
      const from = extractLabel(parts[0]);
      const to = extractLabel(parts[1]);
      if (from) nodes.add(from);
      if (to) nodes.add(to);
    }
  }

  const nodeList = Array.from(nodes).slice(0, 5);
  const total = nodeList.length || 3;
  const stepX = 680 / Math.max(total, 1);

  let nodesMarkup = '';
  nodeList.forEach((node, i) => {
    const x = 70 + i * stepX;
    const y = 200;
    const safeNode = node
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .substring(0, 26);

    nodesMarkup += `
      <g>
        <rect x="${x}" y="${y - 32}" width="${Math.min(185, stepX - 22)}" height="64" rx="10" fill="#1e293b" stroke="#38bdf8" stroke-width="2"/>
        <text x="${x + Math.min(185, stepX - 22) / 2}" y="${y + 5}" font-family="system-ui, sans-serif" font-size="11.5" font-weight="600" fill="#f8fafc" text-anchor="middle">${safeNode}</text>
      </g>
    `;
    if (i < total - 1) {
      const nextX = 70 + (i + 1) * stepX;
      nodesMarkup += `
        <line x1="${x + Math.min(185, stepX - 22)}" y1="${y}" x2="${nextX - 8}" y2="${y}" stroke="#38bdf8" stroke-width="2" marker-end="url(#arrow)"/>
      `;
    }
  });

  return `<svg viewBox="0 0 800 450" xmlns="http://www.w3.org/2000/svg" data-engine="mermaid">
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="#38bdf8"/>
    </marker>
  </defs>
  <rect width="800" height="450" fill="#0f172a" rx="14" stroke="#1e293b" stroke-width="1.5"/>
  <rect x="40" y="24" width="720" height="38" rx="8" fill="#1e293b" stroke="#38bdf8" stroke-width="1.5"/>
  <text x="400" y="48" font-family="system-ui, sans-serif" font-size="14" font-weight="700" fill="#38bdf8" text-anchor="middle">MERMAID.JS RELATIONAL ARCHITECTURE &amp; WORKFLOW MODEL</text>
  ${nodesMarkup}
  <text x="400" y="415" font-family="system-ui, sans-serif" font-size="12" font-weight="500" fill="#94a3b8" text-anchor="middle">System State Transition &amp; Sequential Logic Pipeline</text>
</svg>`;
}

/**
 * Compiles a D3 mathematical coordinate chart, parametric curve, or distribution into 800x450 16:9 SVG.
 */
export function renderD3ToSvg(specOrRaw: any): string {
  let spec: any = {};
  if (typeof specOrRaw === 'string') {
    try {
      const cleanJson = specOrRaw.replace(/^```(?:d3|json)?\s*/, '').replace(/\s*```$/, '').trim();
      spec = JSON.parse(cleanJson);
    } catch {
      spec = { title: 'Quantitative Coordinate Analysis', type: 'curve' };
    }
  } else {
    spec = specOrRaw || {};
  }

  const width = 800;
  const height = 450;
  const margin = { top: 65, right: 60, bottom: 65, left: 80 };
  const innerWidth = width - margin.left - margin.right;
  const innerHeight = height - margin.top - margin.bottom;

  const container = document.createElement('div');
  const svg = d3
    .select(container)
    .append('svg')
    .attr('viewBox', `0 0 ${width} ${height}`)
    .attr('xmlns', 'http://www.w3.org/2000/svg')
    .attr('data-engine', 'd3');

  // Background
  svg
    .append('rect')
    .attr('width', width)
    .attr('height', height)
    .attr('fill', '#0b0f19')
    .attr('rx', 14)
    .attr('stroke', '#1e293b')
    .attr('stroke-width', 1.5);

  // Header Title Banner
  const title = spec.title || (spec.equation ? `Function: ${spec.equation}` : 'Quantitative Function Model');
  svg
    .append('rect')
    .attr('x', 40)
    .attr('y', 16)
    .attr('width', width - 80)
    .attr('height', 34)
    .attr('rx', 8)
    .attr('fill', '#1e293b')
    .attr('stroke', '#38bdf8')
    .attr('stroke-width', 1.2);

  svg
    .append('text')
    .attr('x', width / 2)
    .attr('y', 38)
    .attr('text-anchor', 'middle')
    .attr('font-family', 'system-ui, sans-serif')
    .attr('font-size', '13px')
    .attr('font-weight', '700')
    .attr('fill', '#38bdf8')
    .text(title.toUpperCase().slice(0, 55));

  const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

  // Scales
  const xScale = d3.scaleLinear().domain([0, 10]).range([0, innerWidth]);
  const yScale = d3.scaleLinear().domain([0, 100]).range([innerHeight, 0]);

  // Grid lines
  g.append('g')
    .attr('class', 'grid')
    .attr('stroke', '#1e293b')
    .attr('stroke-width', 1)
    .attr('opacity', 0.6)
    .call(
      d3
        .axisLeft(yScale)
        .ticks(6)
        .tickSize(-innerWidth)
        .tickFormat(() => '')
    );

  g.append('g')
    .attr('class', 'grid')
    .attr('stroke', '#1e293b')
    .attr('stroke-width', 1)
    .attr('opacity', 0.6)
    .attr('transform', `translate(0,${innerHeight})`)
    .call(
      d3
        .axisBottom(xScale)
        .ticks(10)
        .tickSize(-innerHeight)
        .tickFormat(() => '')
    );

  // Axes
  const xAxis = d3.axisBottom(xScale).ticks(10);
  const yAxis = d3.axisLeft(yScale).ticks(6);

  g.append('g')
    .attr('transform', `translate(0,${innerHeight})`)
    .call(xAxis)
    .attr('color', '#94a3b8')
    .attr('font-size', '11px');

  g.append('g').call(yAxis).attr('color', '#94a3b8').attr('font-size', '11px');

  // Compute points dynamically from equation or provided points
  let points: [number, number][] = spec.points;
  if (!points || !Array.isArray(points) || points.length === 0) {
    const eq = (spec.equation || '').toLowerCase();
    const steps = 11;
    points = [];

    for (let i = 0; i < steps; i++) {
      const t = i / (steps - 1);
      let yVal = 50;

      if (eq.includes('sin')) {
        yVal = 50 + 40 * Math.sin((t * 2 * Math.PI) - Math.PI / 2);
      } else if (eq.includes('cos')) {
        yVal = 50 + 40 * Math.cos(t * 2 * Math.PI);
      } else if (eq.includes('exp') || eq.includes('decay')) {
        yVal = 95 * Math.exp(-2.5 * t) + 5;
      } else if (eq.includes('log') || eq.includes('growth')) {
        yVal = 10 + 85 * Math.sqrt(t);
      } else if (eq.includes('^2') || eq.includes('quadratic') || eq.includes('parabola')) {
        yVal = 10 + 85 * Math.pow(t, 2);
      } else {
        yVal = 20 + 70 * Math.sin(t * Math.PI);
      }
      points.push([i, Math.max(5, Math.min(98, Number(yVal.toFixed(1))))]);
    }
  }

  const lineGenerator = d3
    .line<[number, number]>()
    .x((d) => xScale(d[0]))
    .y((d) => yScale(d[1]))
    .curve(d3.curveMonotoneX);

  const areaGenerator = d3
    .area<[number, number]>()
    .x((d) => xScale(d[0]))
    .y0(innerHeight)
    .y1((d) => yScale(d[1]))
    .curve(d3.curveMonotoneX);

  // Gradient area
  const defs = svg.append('defs');
  const gradient = defs
    .append('linearGradient')
    .attr('id', 'd3-area-grad')
    .attr('x1', '0')
    .attr('y1', '0')
    .attr('x2', '0')
    .attr('y2', '1');

  gradient.append('stop').attr('offset', '0%').attr('stop-color', '#38bdf8').attr('stop-opacity', 0.35);
  gradient.append('stop').attr('offset', '100%').attr('stop-color', '#0284c7').attr('stop-opacity', 0.01);

  g.append('path').datum(points).attr('fill', 'url(#d3-area-grad)').attr('d', areaGenerator);

  // Curve stroke
  g.append('path')
    .datum(points)
    .attr('fill', 'none')
    .attr('stroke', '#38bdf8')
    .attr('stroke-width', 3.5)
    .attr('d', lineGenerator);

  // Data keypoints
  g.selectAll('circle')
    .data(points)
    .enter()
    .append('circle')
    .attr('cx', (d) => xScale(d[0]))
    .attr('cy', (d) => yScale(d[1]))
    .attr('r', 4.5)
    .attr('fill', '#ffffff')
    .attr('stroke', '#0284c7')
    .attr('stroke-width', 2.5);

  // Axis labels
  svg
    .append('text')
    .attr('x', width / 2)
    .attr('y', height - 16)
    .attr('text-anchor', 'middle')
    .attr('font-family', 'system-ui, sans-serif')
    .attr('font-size', '11px')
    .attr('font-weight', '600')
    .attr('fill', '#cbd5e1')
    .text(spec.xLabel || 'Normalized Parameter Progression / Time Domain X');

  svg
    .append('text')
    .attr('transform', 'rotate(-90)')
    .attr('x', -height / 2)
    .attr('y', 24)
    .attr('text-anchor', 'middle')
    .attr('font-family', 'system-ui, sans-serif')
    .attr('font-size', '11px')
    .attr('font-weight', '600')
    .attr('fill', '#cbd5e1')
    .attr('font-weight', '600')
    .attr('fill', '#64748b')
    .text(spec.yLabel || 'Calculated Metric / Amplitude Y');

  return container.innerHTML;
}

/**
 * Generates an authentic 3Blue1Brown-style Manim vector mathematical visual in 16:9 800x450 SVG.
 */
export function generateManimVectorSvg(topic: string, description: string = ''): string {
  // 3Blue1Brown aesthetic: dark latex canvas #0f172a, mathematical grid, elegant colored vectors
  const cx = 400;
  const cy = 240;

  return `<svg viewBox="0 0 800 450" xmlns="http://www.w3.org/2000/svg" data-engine="manim">
  <defs>
    <pattern id="manim-grid" width="25" height="25" patternUnits="userSpaceOnUse">
      <path d="M 25 0 L 0 0 0 25" fill="none" stroke="#1e293b" stroke-width="0.8" opacity="0.6"/>
    </pattern>
    <marker id="manim-arrow-blue" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="#3b82f6"/>
    </marker>
    <marker id="manim-arrow-gold" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="#f59e0b"/>
    </marker>
    <marker id="manim-arrow-teal" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="#10b981"/>
    </marker>
  </defs>

  <!-- Deep Slate LaTeX Chalkboard Canvas (800x450 Widescreen) -->
  <rect width="800" height="450" fill="#0f172a" rx="14" stroke="#334155" stroke-width="1.5"/>
  <rect width="800" height="450" fill="url(#manim-grid)"/>

  <!-- Coordinate Axes -->
  <line x1="50" y1="${cy}" x2="750" y2="${cy}" stroke="#64748b" stroke-width="1.8"/>
  <line x1="${cx}" y1="410" x2="${cx}" y2="70" stroke="#64748b" stroke-width="1.8"/>
  <text x="740" y="${cy - 10}" font-family="system-ui, serif" font-style="italic" font-size="14" fill="#94a3b8">x</text>
  <text x="${cx + 12}" y="85" font-family="system-ui, serif" font-style="italic" font-size="14" fill="#94a3b8">y</text>

  <!-- Vector Field Arrows Across Plane -->
  <line x1="160" y1="320" x2="220" y2="280" stroke="#3b82f6" stroke-width="2.2" marker-end="url(#manim-arrow-blue)"/>
  <line x1="250" y1="340" x2="320" y2="290" stroke="#3b82f6" stroke-width="2.2" marker-end="url(#manim-arrow-blue)"/>
  <line x1="340" y1="350" x2="420" y2="290" stroke="#3b82f6" stroke-width="2.2" marker-end="url(#manim-arrow-blue)"/>
  <line x1="440" y1="330" x2="520" y2="260" stroke="#3b82f6" stroke-width="2.2" marker-end="url(#manim-arrow-blue)"/>
  <line x1="540" y1="300" x2="620" y2="220" stroke="#3b82f6" stroke-width="2.2" marker-end="url(#manim-arrow-blue)"/>

  <!-- Mathematical Function Graph: f(x) -->
  <path d="M 100,370 Q 260,110 400,240 T 700,100" fill="none" stroke="#f59e0b" stroke-width="3.5" stroke-linecap="round"/>

  <!-- Tangent Line at Center Point (Derivative dy/dx) -->
  <line x1="280" y1="300" x2="520" y2="180" stroke="#10b981" stroke-width="2.5" stroke-dasharray="6,4" marker-end="url(#manim-arrow-teal)"/>
  <circle cx="${cx}" cy="${cy}" r="5.5" fill="#ffffff" stroke="#10b981" stroke-width="2.5"/>

  <!-- Mathematical Equation Banner -->
  <rect x="40" y="20" width="720" height="34" rx="8" fill="#1e293b" stroke="#334155" stroke-width="1.2"/>
  <text x="400" y="42" font-family="'Times New Roman', serif" font-style="italic" font-size="15" font-weight="bold" fill="#f8fafc" text-anchor="middle">
    ∇F(x, y, t) = [ ∂F/∂x, ∂F/∂y, ∂F/∂t ] • Directional Vector Field &amp; Tangent Manifold
  </text>

  <!-- Topic & Engine Subtitle -->
  <text x="400" y="415" font-family="system-ui, sans-serif" font-size="12" font-weight="600" fill="#cbd5e1" text-anchor="middle">
    ${topic.toUpperCase().slice(0, 50)}
  </text>
  <text x="400" y="435" font-family="system-ui, sans-serif" font-size="10" font-weight="500" fill="#64748b" text-anchor="middle">
    ${description ? description.slice(0, 60) : 'Manim Community Vector Geometry • 3Blue1Brown Pedagogical Style'}
  </text>
</svg>`;
}

/**
 * Renders a standardized parametric scientific model (Bohr atom, molecular bond, optics, etc.)
 */
export function renderParametricTemplateToSvg(specOrRaw: any, topicTitle: string = 'Scientific Model'): string {
  let spec: any = {};
  if (typeof specOrRaw === 'string') {
    try {
      const cleanJson = specOrRaw.replace(/^```(?:json)?\s*/, '').replace(/\s*```$/, '').trim();
      spec = JSON.parse(cleanJson);
    } catch {
      spec = { template: 'model', title: topicTitle };
    }
  } else {
    spec = specOrRaw || {};
  }

  const template = (spec.template || '').toLowerCase();
  const title = spec.title || spec.element || topicTitle;

  if (template.includes('atom')) {
    const element = spec.element || 'Atom';
    const protons = spec.protons || 6;
    const electrons = spec.electrons || protons;
    return `<svg viewBox="0 0 800 450" xmlns="http://www.w3.org/2000/svg" data-engine="manim">
  <rect width="800" height="450" fill="#0f172a" rx="14" stroke="#1e293b" stroke-width="1.5"/>
  <rect x="40" y="20" width="720" height="34" rx="8" fill="#1e293b" stroke="#38bdf8" stroke-width="1.2"/>
  <text x="400" y="42" font-family="system-ui, sans-serif" font-size="13" font-weight="700" fill="#38bdf8" text-anchor="middle">BOHR ATOMIC MODEL: ${element.toUpperCase()} (${protons}p⁺, ${electrons}e⁻)</text>
  <!-- Orbital Shells -->
  <ellipse cx="400" cy="240" rx="110" ry="45" fill="none" stroke="#38bdf8" stroke-width="1.5" stroke-dasharray="4,4" opacity="0.7"/>
  <ellipse cx="400" cy="240" rx="190" ry="75" fill="none" stroke="#818cf8" stroke-width="1.5" stroke-dasharray="5,5" opacity="0.6"/>
  <ellipse cx="400" cy="240" rx="260" ry="105" fill="none" stroke="#c084fc" stroke-width="1.5" stroke-dasharray="6,6" opacity="0.5"/>
  <!-- Nucleus -->
  <circle cx="400" cy="240" r="28" fill="#f43f5e" stroke="#fb7185" stroke-width="3"/>
  <text x="400" y="245" font-family="system-ui, sans-serif" font-size="12" font-weight="bold" fill="#ffffff" text-anchor="middle">${protons}P / ${protons}N</text>
  <!-- Orbiting Electrons -->
  <circle cx="290" cy="240" r="7" fill="#38bdf8" stroke="#ffffff" stroke-width="2"/>
  <circle cx="510" cy="240" r="7" fill="#38bdf8" stroke="#ffffff" stroke-width="2"/>
  <circle cx="400" cy="165" r="7" fill="#818cf8" stroke="#ffffff" stroke-width="2"/>
  <circle cx="400" cy="315" r="7" fill="#818cf8" stroke="#ffffff" stroke-width="2"/>
  <circle cx="140" cy="240" r="7" fill="#c084fc" stroke="#ffffff" stroke-width="2"/>
  <circle cx="660" cy="240" r="7" fill="#c084fc" stroke="#ffffff" stroke-width="2"/>
  <text x="400" y="420" font-family="system-ui, sans-serif" font-size="12" font-weight="500" fill="#94a3b8" text-anchor="middle">Quantum Principal Energy Levels &amp; Valency Orbitals</text>
</svg>`;
  }

  return generateManimVectorSvg(title, spec.description || 'Parametric Scientific Model');
}

/**
 * Universal resolver: takes ANY payload (Mermaid, D3, Pure SVG, or Manim)
 * and resolves it into a pure, self-contained, valid 16:9 widescreen 800x450 SVG string.
 */
export async function resolveVisualToSvg(
  payload: string,
  topicTitle: string = 'Educational Vector Stage',
  declaredEngine?: VisualEngineType
): Promise<VisualResolutionResult> {
  const engine = (declaredEngine && declaredEngine !== 'svg') ? declaredEngine : detectVisualEngine(payload);

  if (engine === 'mermaid') {
    const svg = await renderMermaidToSvg(payload);
    return { svg, engine: 'mermaid', rawPayload: payload };
  }

  if (engine === 'd3') {
    const svg = renderD3ToSvg(payload);
    return { svg, engine: 'd3', rawPayload: payload };
  }

  if (engine === 'manim') {
    if (payload.trim().startsWith('<svg')) {
      return { svg: payload, engine: 'manim', rawPayload: payload };
    }
    if (payload.trim().startsWith('{')) {
      const svg = renderParametricTemplateToSvg(payload, topicTitle);
      return { svg, engine: 'manim', rawPayload: payload };
    }
    const svg = generateManimVectorSvg(topicTitle, payload);
    return { svg, engine: 'manim', rawPayload: payload };
  }

  // Pure SVG / Vector Scene
  let cleanSvg = payload.trim();
  if (!cleanSvg.startsWith('<svg')) {
    // Wrap basic geometry primitives in widescreen 16:9 canvas
    cleanSvg = `<svg viewBox="0 0 800 450" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" data-engine="svg">
  <rect width="800" height="450" fill="#0f172a" rx="14" stroke="#1e293b" stroke-width="1.5"/>
  <rect x="40" y="20" width="720" height="34" rx="8" fill="#1e293b" stroke="#38bdf8" stroke-width="1.2"/>
  <text x="400" y="42" font-family="system-ui, sans-serif" font-size="13" font-weight="700" fill="#38bdf8" text-anchor="middle">${topicTitle.toUpperCase().slice(0, 50)}</text>
  <g transform="translate(60, 40)">
    ${cleanSvg}
  </g>
</svg>`;
  } else {
    // Ensure responsive 16:9 widescreen scaling
    if (!cleanSvg.includes('width="100%"')) {
      cleanSvg = cleanSvg.replace(/<svg\b([^>]*)>/, '<svg$1 width="100%" height="100%" preserveAspectRatio="xMidYMid meet">');
    }
    // Ensure dark background rect exists
    if (!cleanSvg.includes('fill="#0f172a"') && !cleanSvg.includes('fill="#0b0f19"') && !cleanSvg.includes('fill="#020617"')) {
      cleanSvg = cleanSvg.replace(/(<svg\b[^>]*>)/, '$1\n  <rect width="800" height="450" fill="#0f172a" rx="14" stroke="#1e293b" stroke-width="1.5"/>');
    }
  }

  return { svg: cleanSvg, engine: 'svg', rawPayload: payload };
}
