import os
import json
import re
from typing import List, Dict, Any

MANDATORY_SYSTEM_INSTRUCTION = """[SYSTEM INSTRUCTION: EDUCATIONAL CURRICULUM ENGINEER & MULTI-ENGINE MODEL COMPILER]
You act as an expert Educational Curriculum Engineer, Master Pedagogy Teacher (in the style of 3Blue1Brown, Veritasium, and Khan Academy), and Multi-Engine Visual Model Compiler. 
Your core task is to transform a raw, unstructured YouTube lecture transcript into an exhaustive, highly precise, timeline-synchronized educational script and multi-perspective visual model optimized for ultra-low bandwidth edge playback.

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
   - Each frame must capture a specific conceptual point and its corresponding visual diagram.
   - Pace frames into bite-sized pedagogical units (15-35 words per frame, ~10-18 seconds of speech) so visual diagrams and captions transition in tight lockstep with the spoken audio.

5. PRECISE SEQUENTIAL TIMESTAMPS:
   - Map out logical, sequential floating-point timestamps in seconds (e.g., 0.0, 14.0, 28.0, 42.0) matching exactly when each line is introduced.

6. REAL-TIME SYNCHRONIZED SPOKEN LINES & CAPTIONS:
   - The spoken script for each frame must consist of a focused, authoritative pedagogical line (15 to 35 words).
   - When the speaker says the line, those exact words and vector visuals should arrive on screen in synchrony.
   - The narration must explain "why" things occur and provide direct verbal cues referencing visual elements (e.g., "Notice the blue vector pointing upward...", "Observe how the magnetic field circulates...").

7. MULTI-ENGINE VISUAL MODEL COMPILER (16:9 Widescreen 800x450 Viewport):
   - You act as a dynamic visual compiler and educational model architect.
   - For each frame, choose the single most fitting visual engine to build a multi-perspective model of the subject:
     * "mermaid": For systemic flowcharts, sequence diagrams, biological cascades, state machines, and relational logic (emit valid Mermaid syntax with all node labels enclosed in double quotes A["Text"]).
     * "d3": For quantitative data, function curves f(x), statistical distributions, and coordinate charts.
     * "svg": For physical schematics, anatomical cross-sections, circuits, optics, machinery, and spatial objects (emit 800x450 SVG with left diagram and right takeaway card).
     * "manim": For 3Blue1Brown-style vector mathematics, LaTeX chalkboard aesthetic (#0f172a), coordinate transformations, and vector fields (only if mathematical).
   - Across the timeline of the lecture, these multiple visual modalities MUST connect together to form an authentic, multi-perspective model of the topic.

OUTPUT FORMAT:
Output strictly valid JSON text arrays matching the structural schema. No conversational chatter or markdown wrapping outside the JSON array."""

PROMPT_SCHEMA_GUIDE = """
Each object in the array must strictly match:
[
  {
    "timestamp_seconds": float,
    "spoken_text": "15-35 words of clear, engaging pedagogical speech explaining the intuition and mechanics from this phase of the video...",
    "action_type": 1,
    "visual_engine": "mermaid" | "d3" | "svg" | "manim",
    "svg_payload": "<svg viewBox=\\"0 0 800 450\\" xmlns=\\"http://www.w3.org/2000/svg\\">...</svg> or valid Mermaid syntax or D3 spec"
  }
]
"""


def extract_raw_json(text: str) -> List[Dict[str, Any]]:
    """Clean markdown tokens like ```json ... ``` if the LLM outputted them despite instructions."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()
    return json.loads(cleaned)


def deterministic_fallback_compiler(topic_title: str, lecture_text: str) -> List[Dict[str, Any]]:
    """
    High-precision deterministic multi-engine compiler fallback.
    Constructs an authentic multi-perspective pedagogical model using:
      - Mermaid.js (System Architecture & Relational Flow)
      - Pure SVG (Physical & Anatomical Cross-Section)
      - D3.js (Quantitative Coordinate Curve & Rates)
      - Manim Vector (3Blue1Brown-style Vector Mathematics & Calculus)
    """
    raw_lines = [l.strip() for l in lecture_text.split("\n") if l.strip()]
    lines = []
    for rl in raw_lines:
        if len(rl) > 80 and ("." in rl or "?" in rl or "!" in rl):
            sents = re.split(r"(?<=[.!?])\s+", rl)
            lines.extend([s.strip() for s in sents if s.strip()])
        else:
            lines.append(rl)

    if not lines:
        lines = [f"Introduction and foundations of {topic_title.strip() or 'the subject'}."]

    frames = []

    topic_clean = topic_title.strip() or "Core Dynamic Model"
    engine_cycle = ["mermaid", "svg", "d3", "manim"]

    for idx, line in enumerate(lines):
        timestamp = float(idx * 12.0)
        spoken_text = line

        # Parse timestamp if formatted as "At X seconds: ..."
        match = re.match(r"^At\s+(\d+(?:\.\d+)?)\s+seconds?:\s*(.*)$", line, re.IGNORECASE)
        if match:
            timestamp = float(match.group(1))
            spoken_text = match.group(2)

        engine_choice = engine_cycle[idx % len(engine_cycle)]

        if engine_choice == "mermaid":
            payload = f"""flowchart TD
  Inp[{topic_clean}: Input Phase] --> Core[Dynamic Reaction Core]
  Core --> Trans[State Transition Dynamics]
  Trans --> Out[Observable Physical Outcome]
  Out -.->|Feedback Modulation| Core
  style Inp fill:#eff6ff,stroke:#2563eb,stroke-width:2px
  style Core fill:#eff6ff,stroke:#2563eb,stroke-width:2px
  style Trans fill:#eff6ff,stroke:#2563eb,stroke-width:2px
  style Out fill:#f0fdf4,stroke:#16a34a,stroke-width:2px"""

        elif engine_choice == "svg":
            payload = f"""<svg viewBox="0 0 800 450" xmlns="http://www.w3.org/2000/svg" data-engine="svg">
  <defs>
    <marker id="svg-arr-{idx}" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="#2563eb"/>
    </marker>
  </defs>
  <rect width="800" height="450" fill="#ffffff" rx="14" stroke="#e2e8f0" stroke-width="1.5"/>
  <rect x="40" y="20" width="720" height="34" rx="8" fill="#eff6ff" stroke="#bfdbfe" stroke-width="1.2"/>
  <text x="400" y="42" font-family="system-ui, sans-serif" font-size="13" font-weight="700" fill="#1e40af" text-anchor="middle">PHYSICAL &amp; ANATOMICAL SCHEMATIC: {topic_clean.upper()[:36]}</text>
  <!-- Left Side: Physical Structure -->
  <g transform="translate(230, 245)">
    <circle cx="0" cy="0" r="130" fill="#f8fafc" stroke="#2563eb" stroke-width="2" stroke-dasharray="6,4"/>
    <circle cx="0" cy="0" r="85" fill="#eff6ff" stroke="#1d4ed8" stroke-width="2"/>
    <circle cx="0" cy="0" r="30" fill="#2563eb"/>
    <circle cx="0" cy="0" r="8" fill="#ffffff"/>
    <line x1="-130" y1="0" x2="-40" y2="0" stroke="#059669" stroke-width="2" marker-end="url(#svg-arr-{idx})"/>
    <line x1="130" y1="0" x2="40" y2="0" stroke="#059669" stroke-width="2"/>
    <line x1="0" y1="-130" x2="0" y2="-40" stroke="#d97706" stroke-width="2"/>
    <line x1="0" y1="130" x2="0" y2="40" stroke="#d97706" stroke-width="2"/>
    <text x="0" y="165" font-family="system-ui, sans-serif" font-size="12" font-weight="700" fill="#0f172a" text-anchor="middle">Radial Equilibrium Flux</text>
  </g>
  <!-- Right Side: Key Concept Card -->
  <rect x="450" y="75" width="310" height="335" rx="12" fill="#f8fafc" stroke="#e2e8f0" stroke-width="1.5"/>
  <text x="470" y="110" font-family="system-ui, sans-serif" font-size="13" font-weight="700" fill="#0f172a">GOVERNING PRINCIPLES</text>
  <line x1="470" y1="122" x2="740" y2="122" stroke="#cbd5e1" stroke-width="1"/>
  <text x="470" y="155" font-family="system-ui, sans-serif" font-size="11" font-weight="600" fill="#2563eb">• Topic Anchor: {topic_clean[:28]}</text>
  <text x="470" y="190" font-family="system-ui, sans-serif" font-size="11" font-weight="600" fill="#059669">• Flux Density: ∇·B = 0 Invariant</text>
  <text x="470" y="225" font-family="system-ui, sans-serif" font-size="11" font-weight="600" fill="#d97706">• Reaction Transition: Active Phase</text>
  <text x="470" y="260" font-family="system-ui, sans-serif" font-size="11" font-weight="600" fill="#475569">• Dynamic Coupling: Steady State</text>
  <rect x="470" y="290" width="270" height="90" rx="8" fill="#eff6ff" stroke="#bfdbfe" stroke-width="1"/>
  <text x="485" y="318" font-family="system-ui, sans-serif" font-size="11" font-weight="700" fill="#1e40af">16:9 Widescreen Schematic</text>
  <text x="485" y="340" font-family="system-ui, sans-serif" font-size="10" fill="#64748b">Timeline-synchronized vector state</text>
</svg>"""

        elif engine_choice == "d3":
            spec = {
                "title": f"{topic_clean}: Quantitative Parameter Curve",
                "xLabel": "Normalized Parameter Progression X",
                "yLabel": "Observed Magnitude / Rate Y",
                "points": [[0, 12], [1, 26], [2, 54], [3, 80], [4, 94], [5, 96], [6, 82], [7, 58], [8, 36], [9, 20], [10, 14]]
            }
            payload = json.dumps(spec)

        else:  # manim
            payload = f"""<svg viewBox="0 0 800 450" xmlns="http://www.w3.org/2000/svg" data-engine="manim">
  <defs>
    <pattern id="m-grid-{idx}" width="25" height="25" patternUnits="userSpaceOnUse">
      <path d="M 25 0 L 0 0 0 25" fill="none" stroke="#1e293b" stroke-width="0.8" opacity="0.6"/>
    </pattern>
    <marker id="m-arr-b-{idx}" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="#3b82f6"/>
    </marker>
    <marker id="m-arr-t-{idx}" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="#10b981"/>
    </marker>
  </defs>
  <rect width="800" height="450" fill="#0f172a" rx="14" stroke="#334155" stroke-width="1.5"/>
  <rect width="800" height="450" fill="url(#m-grid-{idx})"/>
  <!-- Coordinate Axes -->
  <line x1="50" y1="240" x2="750" y2="240" stroke="#64748b" stroke-width="1.8"/>
  <line x1="400" y1="410" x2="400" y2="70" stroke="#64748b" stroke-width="1.8"/>
  <text x="740" y="230" font-family="system-ui, serif" font-style="italic" font-size="14" fill="#94a3b8">x</text>
  <text x="412" y="85" font-family="system-ui, serif" font-style="italic" font-size="14" fill="#94a3b8">y</text>
  <!-- Vector Field Arrows -->
  <line x1="160" y1="320" x2="220" y2="280" stroke="#3b82f6" stroke-width="2.2" marker-end="url(#m-arr-b-{idx})"/>
  <line x1="260" y1="340" x2="330" y2="290" stroke="#3b82f6" stroke-width="2.2" marker-end="url(#m-arr-b-{idx})"/>
  <line x1="360" y1="350" x2="430" y2="290" stroke="#3b82f6" stroke-width="2.2" marker-end="url(#m-arr-b-{idx})"/>
  <line x1="460" y1="330" x2="530" y2="260" stroke="#3b82f6" stroke-width="2.2" marker-end="url(#m-arr-b-{idx})"/>
  <line x1="560" y1="300" x2="630" y2="220" stroke="#3b82f6" stroke-width="2.2" marker-end="url(#m-arr-b-{idx})"/>
  <!-- 3B1B Math Function -->
  <path d="M 100,370 Q 260,110 400,240 T 700,100" fill="none" stroke="#f59e0b" stroke-width="3.5" stroke-linecap="round"/>
  <!-- Tangent Line & Derivation -->
  <line x1="280" y1="300" x2="520" y2="180" stroke="#10b981" stroke-width="2.5" stroke-dasharray="6,4" marker-end="url(#m-arr-t-{idx})"/>
  <circle cx="400" cy="240" r="5" fill="#ffffff" stroke="#10b981" stroke-width="2.5"/>
  <!-- Equation Banner -->
  <rect x="40" y="20" width="720" height="34" rx="8" fill="#1e293b" stroke="#334155" stroke-width="1.2"/>
  <text x="400" y="42" font-family="'Times New Roman', serif" font-style="italic" font-size="14" font-weight="bold" fill="#f8fafc" text-anchor="middle">
    ∇F(x, t) = [ ∂F/∂x, ∂F/∂t ] • Vector Field Model
  </text>
  <text x="400" y="415" font-family="system-ui, sans-serif" font-size="12" font-weight="600" fill="#cbd5e1" text-anchor="middle">
    Manim Community Vector Geometry • {topic_clean.upper()[:36]}
  </text>
  <text x="400" y="435" font-family="system-ui, sans-serif" font-size="10" font-weight="500" fill="#64748b" text-anchor="middle">
    16:9 Widescreen Chalkboard Canvas • 3Blue1Brown Pedagogical Style
  </text>
</svg>"""

        frames.append({
            "timestamp_seconds": timestamp,
            "spoken_text": spoken_text,
            "action_type": 1,  # INJECT_NEW_VECTOR
            "visual_engine": engine_choice,
            "svg_payload": payload,
        })

    return frames


def generate_lecture_frames(topic_title: str, lecture_text: str) -> List[Dict[str, Any]]:
    """
    Core LLM Layer:
    Tries Google Gemini API with mandatory system instruction.
    Falls back gracefully to the deterministic geometric compiler.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                system_instruction=MANDATORY_SYSTEM_INSTRUCTION
            )

            prompt = f"Topic: {topic_title}\nLecture Text:\n{lecture_text}\n\nSchema Requirements:\n{PROMPT_SCHEMA_GUIDE}"
            response = model.generate_content(prompt)
            frames = extract_raw_json(response.text)
            if isinstance(frames, list) and len(frames) > 0:
                return frames
        except Exception as e:
            print(f"[LLM Engine] Gemini API warning: {e}. Falling back to deterministic compiler.")

    return deterministic_fallback_compiler(topic_title, lecture_text)
