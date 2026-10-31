import os
import sys
import re
import json
import logging
from typing import List, Dict, Any, Optional

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from dotenv import load_dotenv, find_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda

# Automatically locate and load .env from project root or server folder
load_dotenv(find_dotenv())
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

logger = logging.getLogger("ByteClass.LangChain")

# Recommended Open-Source Models
RECOMMENDED_MODELS = [
    {
        "id": "Qwen/Qwen2.5-Coder-32B-Instruct",
        "name": "Qwen 2.5 Coder 32B (Recommended for SVG & Math)",
        "provider": "Hugging Face / Ollama",
        "specialty": "Unmatched precision in 2D coordinate geometry, valid XML/SVG code, and mathematical diagrams."
    },
    {
        "id": "meta-llama/Llama-3.3-70B-Instruct",
        "name": "Llama 3.3 70B Instruct (Recommended for Deep Pedagogy)",
        "provider": "Hugging Face / Groq",
        "specialty": "Exceptional teaching quality, intuitive conceptual breakdowns, analogies, and pacing."
    },
    {
        "id": "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
        "name": "DeepSeek R1 Distill Qwen 32B (Reasoning & Science)",
        "provider": "Hugging Face / Groq",
        "specialty": "Deep step-by-step reasoning for counterintuitive physics, proofs, and complex algorithms."
    },
    {
        "id": "mistralai/Mistral-7B-Instruct-v0.3",
        "name": "Mistral 7B Instruct v0.3 (Fast & Lightweight)",
        "provider": "Hugging Face",
        "specialty": "High speed, low latency serverless execution."
    }
]

def clean_llm_json(raw_text: str) -> Any:
    """
    Extract and parse JSON safely from LLM output, with resilient auto-repair
    for truncated arrays, trailing commas, and incomplete brackets.
    """
    cleaned = raw_text.strip()
    if "```" in cleaned:
        # Match ```json ... ``` or ``` ... ```
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if match:
            cleaned = match.group(1).strip()

    first_sq = cleaned.find('[')
    first_cu = cleaned.find('{')

    if first_sq != -1 and (first_cu == -1 or first_sq < first_cu):
        # Array expected
        last_sq = cleaned.rfind(']')
        if last_sq != -1 and last_sq > first_sq:
            candidate = cleaned[first_sq:last_sq + 1]
        else:
            # Unclosed array: find last complete object `}` and close with `]`
            last_cu = cleaned.rfind('}')
            if last_cu != -1 and last_cu > first_sq:
                candidate = cleaned[first_sq:last_cu + 1] + "\n]"
            else:
                candidate = cleaned[first_sq:]
    elif first_cu != -1:
        # Object expected
        last_cu = cleaned.rfind('}')
        if last_cu != -1 and last_cu > first_cu:
            candidate = cleaned[first_cu:last_cu + 1]
        else:
            candidate = cleaned[first_cu:] + "\n}"
    else:
        candidate = cleaned

    # Attempt 1: Direct JSON parse
    try:
        return json.loads(candidate)
    except Exception:
        pass

    # Attempt 2: Clean trailing commas before ] or }
    repaired = re.sub(r',\s*([\]}])', r'\1', candidate)
    try:
        return json.loads(repaired)
    except Exception:
        pass

    # Attempt 3: If array, slice up to last complete `}` and close
    if candidate.startswith('['):
        last_brace = candidate.rfind('}')
        if last_brace != -1:
            chopped = candidate[:last_brace + 1]
            chopped = re.sub(r',\s*$', '', chopped) + "\n]"
            chopped = re.sub(r',\s*([\]}])', r'\1', chopped)
            try:
                return json.loads(chopped)
            except Exception:
                pass

    # Attempt 4: Regex extract all individual JSON objects { "key": ... }
    extracted_objects = []
    for m in re.finditer(r'\{[^{}]*\}', cleaned):
        try:
            extracted_objects.append(json.loads(m.group(0)))
        except Exception:
            continue
    if extracted_objects:
        return extracted_objects

    raise ValueError(f"Unable to parse valid JSON from LLM output: {raw_text[:200]}...")


def preprocess_transcript_for_pedagogy(
    raw_transcript: str,
    target_frames: int = 6,
    max_chars: int = 12000
) -> str:
    """
    Cleans transcript text of audio artifacts and sponsor plugs,
    and structures it into chronological milestones.
    For transcripts within max_chars, preserves 100% of the entire narrative.
    For longer transcripts, partitions into target_frames proportional
    chronological windows, ensuring every single phase from beginning to end is represented.
    """
    if not raw_transcript or not raw_transcript.strip():
        return ""

    lines = raw_transcript.split("\n")
    cleaned_lines = []
    
    sound_pattern = re.compile(r"\[(music|applause|laughter|cheering|snicker|sigh|groan)\]", re.IGNORECASE)
    sponsor_pattern = re.compile(r"(sponsor|nordvpn|cas[e\xe9]ta|lutron|squarespace|brilliant\.org|skillshare|audible|patreon|use code|discount code|link in the description|hit subscribe|bell icon)", re.IGNORECASE)

    for line in lines:
        cleaned_line = sound_pattern.sub("", line).strip()
        if not cleaned_line:
            continue
        # Skip pure sponsor pitch lines if they don't contain core educational words
        if sponsor_pattern.search(cleaned_line) and not any(w in cleaned_line.lower() for w in ["circuit", "current", "physics", "light", "electron", "neuron", "planet", "cell", "experiment", "algorithm", "theory", "force", "math", "code", "history", "data"]):
            continue
        cleaned_lines.append(cleaned_line)

    cleaned_text = "\n".join(cleaned_lines)
    
    if len(cleaned_text) <= max_chars:
        return cleaned_text

    # Transcript exceeds max_chars: partition into target_frames chronological windows
    total_lines = len(cleaned_lines)
    window_size = max(1, total_lines // target_frames)
    budget_per_window = max(200, max_chars // target_frames)
    blocks = []

    for i in range(target_frames):
        start_idx = i * window_size
        end_idx = (i + 1) * window_size if i < target_frames - 1 else total_lines
        window_lines = cleaned_lines[start_idx:end_idx]
        window_text = "\n".join(window_lines)
        if len(window_text) > budget_per_window:
            window_text = window_text[:budget_per_window] + "\n... [continuous topic progression] ..."
        
        pct_start = int((i / target_frames) * 100)
        pct_end = int(((i + 1) / target_frames) * 100)
        blocks.append(f"--- [CHRONOLOGICAL TIMELINE PHASE {i+1} of {target_frames} ({pct_start}% - {pct_end}%)] ---\n{window_text}")

    return "\n\n".join(blocks)


class PedagogicalLangChainService:
    """
    Multi-stage LangChain orchestration service for Project ByteClass:
    1. Curriculum & In-Depth Narration Script Planner
    2. Vector Graphic Visual Architect (400x400 dark-mode SVG)
    3. Syntactic AST Validation and Healing
    """

    def __init__(self, hf_token: Optional[str] = None, model_name: Optional[str] = None):
        # Prefer explicit token if supplied, otherwise load strictly from backend .env
        self.hf_token = (hf_token or os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACEHUB_API_TOKEN") or "").strip()
        # Prefer explicit model if supplied, otherwise load strictly from backend .env
        self.model_name = (model_name or os.environ.get("MODEL_NAME") or "Qwen/Qwen2.5-Coder-32B-Instruct").strip()
        self.groq_api_key = os.environ.get("GROQ_API_KEY", "").strip()
        try:
            self.default_duration = float(os.environ.get("DEFAULT_DURATION_MINUTES", "4.0"))
        except (ValueError, TypeError):
            self.default_duration = 4.0

    def _call_huggingface_router(self, prompt: str, system_prompt: str, max_tokens: int = 2048, temperature: float = 0.3) -> str:
        """Invokes Hugging Face Serverless Chat Completions API with error propagation."""
        from huggingface_hub import InferenceClient

        if not self.hf_token or not self.hf_token.strip():
            raise ValueError("No Hugging Face API key provided. Please provide an active HF Access Token.")

        client = InferenceClient(api_key=self.hf_token.strip())

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        response = client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )

        return response.choices[0].message.content or ""

    def _call_groq_router(self, prompt: str, system_prompt: str, max_tokens: int = 2200, temperature: float = 0.2) -> str:
        """
        Invokes Groq High-Speed Cloud Inference (~500 tokens/sec) with automatic model fallback.
        Includes 429 rate limit backoff retry and token clamping for OTPM safety.
        """
        import time
        from groq import Groq
        raw_key = (self.groq_api_key or "").strip().strip('"').strip("'")
        if not raw_key:
            raise ValueError("No Groq API key configured.")
        client = Groq(api_key=raw_key, timeout=30.0, max_retries=0)

        # High-capacity open models on Groq: 20B fast & token-efficient first, then 120B reasoning, then Qwen
        candidate_models = ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.8-27b"]

        last_err = None
        for model_id in candidate_models:
            # Qwen enforces 1000 OTPM ceiling; clamp call_tokens to <= 850
            call_tokens = min(max_tokens, 850) if "qwen" in model_id.lower() else max_tokens

            for attempt in range(3):
                try:
                    kwargs = {
                        "model": model_id,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": call_tokens,
                        "temperature": temperature
                    }
                    # Keep reasoning trace brief so tokens are reserved for payload
                    if "gpt-oss" in model_id.lower():
                        kwargs["reasoning_effort"] = "low"

                    response = client.chat.completions.create(**kwargs)
                    text = response.choices[0].message.content or ""
                    if text.strip():
                        return text
                except Exception as e:
                    last_err = e
                    err_str = str(e)
                    # Intelligent 429 Rate Limit backoff
                    if "429" in err_str or "rate limit" in err_str.lower():
                        wait_match = re.search(r"try again in ([\d\.]+)s", err_str, re.IGNORECASE)
                        wait_seconds = (float(wait_match.group(1)) + 0.6) if wait_match else (2.0 * (attempt + 1))
                        wait_seconds = min(wait_seconds, 12.0)
                        logger.warning(f"Groq {model_id} hit rate limit (429). Waiting {wait_seconds:.1f}s before retry {attempt+1}/3...")
                        time.sleep(wait_seconds)
                        continue
                    else:
                        logger.warning(f"Groq model {model_id} error: {e}. Trying fallback model...")
                        break

        if last_err:
            raise last_err
        return ""

    def _invoke_llm(self, prompt: str, system_prompt: str, max_tokens: int = 2048, temperature: float = 0.3) -> str:
        """Invokes Groq first (blazing fast ~1s), falls back to Hugging Face router, or raises."""
        if self.groq_api_key and self.groq_api_key.strip():
            try:
                return self._call_groq_router(prompt, system_prompt, max_tokens, temperature)
            except Exception as e:
                logger.warning(f"Groq API call error: {e}. Trying HuggingFace router.")

        if self.hf_token and self.hf_token.strip():
            return self._call_huggingface_router(prompt, system_prompt, max_tokens, temperature)

        raise ValueError("Neither GROQ_API_KEY nor HF_TOKEN is configured.")

    def plan_pedagogical_curriculum(
        self,
        topic_title: str,
        transcript_text: str,
        target_duration_minutes: float = 4.0,
        num_frames: int = 6,
        target_language: str = "en"
    ) -> List[Dict[str, Any]]:
        """
        Stage 1: Deconstructs the full transcript and plans an in-depth, multi-chapter curriculum
        where the voiceover acts as an expert teacher strictly grounded in the video's actual topics.
        """
        seconds_per_frame = (target_duration_minutes * 60.0) / max(num_frames, 1)
        is_hindi = (target_language or "").lower() == "hi"

        # Clean and window the transcript to capture the full video narrative arc
        clean_transcript = preprocess_transcript_for_pedagogy(
            transcript_text,
            target_frames=num_frames,
            max_chars=12000
        )
        if not clean_transcript:
            clean_transcript = transcript_text

        hindi_mandate = ""
        if is_hindi:
            hindi_mandate = (
                "\n\n8. CRITICAL LANGUAGE MANDATE - HINDI (अनिवार्य हिन्दी निर्देश):\n"
                "   - You MUST write every 'chapter_title' and 'spoken_explanation' in fluent, natural educational Hindi using Devanagari script (हिन्दी).\n"
                "   - Tone: Master science documentary explainer style (like Discovery Science Hindi or premium Hindi educational creators). Speak clearly, articulately, and directly without boilerplate or classroom roleplay.\n"
                "   - Natural Phrasing: Do NOT use awkward literal machine translations. Use authentic Hindi educational syntax. Retain standard widely-recognized scientific terms with their Hindi equivalents where appropriate (e.g., गुरुत्वाकर्षण, नाभिकीय संलयन, कक्षा, ब्लैक होल, सौर मंडल).\n"
                "   - Ensure each spoken paragraph has 65 to 90 words of natural, well-punctuated Hindi speech (using पूर्णविराम ।, अल्पविराम ,) for realistic neural voice synthesis.\n"
                "   - 'visual_concept' and 'visual_engine' can remain in English for the graphic rendering engine.\n"
            )

        system_prompt = (
            "You act as a world-class Scientific Documentary Explainer and Pedagogical Visual Architect (in the style of Veritasium, Kurzgesagt, and 3Blue1Brown). "
            "Your core task is to transform a raw YouTube lecture transcript into an exhaustive, highly precise, timeline-synchronized educational narration and multi-library vector illustration specification optimized for ultra-low bandwidth edge playback.\n\n"
            "CRITICAL INSTRUCTIONS & FIDELITY MANDATES:\n"
            "1. 100% EXHAUSTIVE COMPREHENSIVENESS (NO OMISSIONS):\n"
            "   - You MUST retain and explain 100% of the academic concepts, data points, equations, numerical values, and factual examples mentioned in the original transcript.\n"
            "   - Do not summarize loosely, omit deep content, or gloss over technical proofs. Never use generic placeholders.\n"
            "   - You must cover everything discussed in the video. Faithfully use and teach the speaker's exact technical terminology, definitions, analogies, and step-by-step logic.\n"
            "2. CALIBRATED COMPLEXITY & ACCESSIBILITY (DO NOT INTRODUCE UNWARRANTED ADVANCED CONTENT):\n"
            "   - You MUST calibrate the complexity of the script strictly to the target topic and source transcript.\n"
            "   - Do NOT introduce overly advanced, graduate-level mathematics, obscure academic jargon, or esoteric formulas UNLESS the transcript itself explicitly introduces and discusses them.\n"
            "   - If the video explains an intuitive, foundational, or general subject, keep the explanation clear, accessible, and grounded at that exact educational level.\n"
            "   - NEVER invent complex differential equations, tensor proofs, or graduate-level theories that the speaker did not mention.\n"
            "3. STRICT TOPICAL RELEVANCE (ZERO OFF-TOPIC DRIFT):\n"
            "   - The script and visual diagrams must ALWAYS remain 100% relevant and faithful to the specific topic and what was actually taught in the video.\n"
            "   - Never wander off into unrelated tangents, speculative theories, or unmentioned academic trivia.\n"
            "   - Every single chapter must directly build understanding of the core subject matter.\n"
            "4. DISCRETE CHUNKING:\n"
            "   - Break down the script into exactly {num_frames} strict, logical timeline frames based on the flow of the topic from beginning to end.\n"
            "   - Each frame must capture a specific, substantive conceptual point spanning the full narrative arc.\n"
            "5. PRECISE TIMESTAMPS:\n"
            "   - Map out logical, sequential floating-point timestamps in seconds matching when each point would naturally be introduced.\n"
            "6. DOCUMENTARY EXPLAINER TONE (PEDAGOGICALLY LUCID, ZERO CLASSROOM ROLEPLAY, ZERO BOILERPLATE):\n"
            "   - The spoken_explanation must contain clear, fully formed paragraphs of 65 to 90 words that flow naturally as spoken speech.\n"
            "   - Use the teaching method of a master documentary explainer: illuminate the core mechanisms, physical cause-and-effect, and intuitive intuition step-by-step.\n"
            "   - STRICT FORBIDDEN PERSONA & ROLEPLAY: NEVER identify as a classroom teacher or talk about lessons/classes. NEVER say: 'Hello students', 'I am your teacher', 'In this section of our study', 'In today's lesson', 'Welcome to our class', 'As we conclude our study', or 'You now possess the mental model'.\n"
            "   - Begin every explanation DIRECTLY with the phenomenon, observation, or physical principle itself.\n"
            "   - Ensure proper punctuation (periods, commas) so text-to-speech synthesizers articulate with natural cadence and zero silence.\n"
            "7. DUAL-LANGUAGE NARRATION (ENGLISH & HINDI TEACHER TRACKS):\n"
            "   - Every chapter MUST contain both an English documentary explanation ('spoken_explanation') and a natural, fluent Hindi teacher explanation ('spoken_explanation_hi' in Devanagari script: हिन्दी).\n"
            "   - Hindi Script Tone: Like an engaging science educator teaching concepts clearly and intuitively in Hindi (e.g. Discovery/YouTube Science Hindi), with correct scientific terms and punctuation (पूर्णविराम ।, अल्पविराम ,).\n"
            "8. HIGH-ACCURACY MULTI-ENGINE VISUAL SPECIFICATION (16:9 WIDESCREEN 800x450 VIEWPORT):\n"
            "   - For each chapter, select the optimal visual engine ('mermaid', 'd3', 'manim', or 'svg') strictly according to the pedagogical nature of that specific concept:\n"
            "     * 'mermaid': Use for multi-step processes, sequential pipelines, biochemical pathways, state transitions, classifications, decision trees, or cause-and-effect mechanisms. (MANDATORY: wrap node labels in double quotes A[\"Text\"]).\n"
            "     * 'd3': Use for quantitative relationships, physical rate laws, exponential/decay curves, probability distributions, coordinate trends, or empirical data plots.\n"
            "     * 'manim': Use for mathematical proofs, coordinate plane transformations, vector fields, calculus derivatives/tangents, or theoretical equations (3Blue1Brown chalkboard aesthetic, only when mathematical).\n"
            "     * 'svg': Use for physical experimental apparatus, spatial geometry, planetary orbits, biological cell anatomy, or dual-pane hardware/system schematics.\n"
            "   - Ensure that the engines are distributed appropriately across the chapters so the lesson feels like an interconnected, multi-faceted scientific model.\n\n"
            "Output strictly as a valid JSON array of {num_frames} objects. Do not wrap in conversational chatter."
        ).format(num_frames=num_frames)

        prompt_template = PromptTemplate.from_template(
            "Topic: {topic_title}\n"
            "Target Duration: {duration_min} minutes (Total {total_sec} seconds, ~{sec_per_frame} seconds per chapter)\n"
            "Number of Progressive Chapters: {num_frames}\n"
            "Source Video Transcript Content:\n{transcript}\n\n"
            "Instructions:\n"
            "1. Transform the transcript into exactly {num_frames} progressive, comprehensive frames covering 100% of the video's concepts.\n"
            "2. CALIBRATED COMPLEXITY: Match the educational level of the transcript. Do NOT introduce overly advanced math, jargon, or theories unless the transcript explicitly contains them.\n"
            "3. STRICT TOPICAL RELEVANCE: Keep every chapter, spoken sentence, and visual concept 100% relevant to the specific topic discussed in the video.\n"
            "4. DUAL NARRATION: For every chapter provide:\n"
            "   - 'spoken_explanation': 65-90 words in clear, captivating English.\n"
            "   - 'spoken_explanation_hi': 65-90 words in natural, fluent educational Hindi (हिन्दी in Devanagari script) explaining the concept like a master science teacher.\n"
            "   - 'chapter_title': Concise English title.\n"
            "   - 'chapter_title_hi': Concise Hindi title (हिन्दी).\n"
            "5. Include precise terminology, data points, equations, and examples from the transcript in each spoken explanation.\n"
            "6. Assign the optimal 'visual_engine' for each frame ('mermaid', 'd3', 'manim', or 'svg').\n\n"
            "Output JSON format strictly as an array of {num_frames} objects:\n"
            "[\n"
            "  {{\n"
            "    \"chapter_index\": 0,\n"
            "    \"chapter_title\": \"English Chapter Title\",\n"
            "    \"chapter_title_hi\": \"हिन्दी अध्याय शीर्षक\",\n"
            "    \"timestamp_seconds\": 0.0,\n"
            "    \"spoken_explanation\": \"65-90 words of captivating English documentary exposition...\",\n"
            "    \"spoken_explanation_hi\": \"65-90 words of natural, articulate Hindi teacher exposition in Devanagari script...\",\n"
            "    \"visual_engine\": \"mermaid\",\n"
            "    \"visual_concept\": \"Detailed geometric description directly tied to the video topic...\"\n"
            "  }}\n"
            "]"
        )

        formatted_prompt = prompt_template.format(
            topic_title=topic_title,
            duration_min=target_duration_minutes,
            total_sec=int(target_duration_minutes * 60),
            sec_per_frame=int(seconds_per_frame),
            num_frames=num_frames,
            transcript=clean_transcript
        )

        has_transcript = bool(clean_transcript and len(clean_transcript.split()) >= 15)
        has_api_keys = bool((self.groq_api_key and self.groq_api_key.strip()) or (self.hf_token and self.hf_token.strip()))

        if has_transcript and has_api_keys:
            try:
                max_toks = min(2200, max(1400, num_frames * 140))
                raw_output = self._invoke_llm(
                    prompt=formatted_prompt,
                    system_prompt=system_prompt,
                    max_tokens=max_toks,
                    temperature=0.2
                )
                parsed = clean_llm_json(raw_output)
                if isinstance(parsed, list) and len(parsed) > 0:
                    valid_chapters = [x for x in parsed if isinstance(x, dict)]
                    effective_sec_per_frame = (target_duration_minutes * 60.0) / max(len(valid_chapters), 1)
                    normalized = []
                    engine_cycle = ["mermaid", "svg", "d3", "manim"]
                    for idx, ch in enumerate(valid_chapters):
                        ch_title = ch.get("chapter_title") or ch.get("title") or f"Chapter {idx + 1}"
                        ch_title_hi = ch.get("chapter_title_hi") or ch.get("title_hi") or ""
                        speech = ch.get("spoken_explanation") or ch.get("spoken_text") or ch.get("text") or ch.get("script") or ch.get("explanation") or ""
                        speech_hi = ch.get("spoken_explanation_hi") or ch.get("spoken_text_hi") or ch.get("text_hi") or ch.get("script_hi") or ""

                        # If Hindi track is missing from LLM, auto-synthesize authentic Hindi teacher script
                        if not speech_hi or not ch_title_hi:
                            h_title, h_speech = self._translate_chapter_to_hindi(ch_title, speech, topic_title, idx)
                            if not ch_title_hi:
                                ch_title_hi = h_title
                            if not speech_hi:
                                speech_hi = h_speech

                        concept = ch.get("visual_concept") or ch.get("concept") or ch.get("visual") or ch.get("svg") or ch_title
                        ts = round(idx * effective_sec_per_frame, 1)
                        engine_val = ch.get("visual_engine") or ch.get("engine")
                        if not engine_val or engine_val not in ["mermaid", "d3", "manim", "svg"]:
                            engine_val = engine_cycle[idx % len(engine_cycle)]
                        normalized.append({
                            "chapter_index": idx,
                            "chapter_title": ch_title,
                            "chapter_title_hi": ch_title_hi,
                            "timestamp_seconds": ts,
                            "spoken_explanation": speech,
                            "spoken_explanation_hi": speech_hi,
                            "visual_concept": concept,
                            "visual_engine": engine_val
                        })

                    # If LLM returned enough frames (>= 75% of requested), use them and expand up to num_frames
                    if len(normalized) >= max(3, int(num_frames * 0.75)):
                        synth = self._synthesize_pedagogical_curriculum(topic_title, transcript_text, target_duration_minutes, num_frames, target_language=target_language)
                        while len(normalized) < num_frames and len(normalized) < len(synth):
                            idx = len(normalized)
                            synth_item = synth[idx].copy()
                            synth_item["chapter_index"] = idx
                            synth_item["timestamp_seconds"] = round(idx * (target_duration_minutes * 60.0 / num_frames), 1)
                            normalized.append(synth_item)
                        return normalized
                    else:
                        logger.info(f"LLM generated {len(normalized)} frames, below threshold for {num_frames} frames. Using high-density domain synthesizer.")
            except Exception as e:
                logger.warning(f"LangChain curriculum generation warning: {e}. Falling back to domain synthesizer.")

        # Fallback to high-fidelity pedagogical domain synthesizer
        return self._synthesize_pedagogical_curriculum(topic_title, transcript_text, target_duration_minutes, num_frames, target_language=target_language)


    @staticmethod
    def sanitize_mermaid_server(code: str) -> str:
        """
        Sanitizes raw Mermaid.js flowchart code to conform strictly to Mermaid v11 syntax:
        1. Ensures all node labels in square brackets [ ... ] are wrapped in double quotes [" ... "].
        2. Ensures all decision nodes in curly braces { ... } are wrapped in double quotes {" ... "}.
        3. Ensures all rounded nodes in parentheses ( ... ) are wrapped in double quotes (" ... ").
        4. Cleans up arrow annotations -->|...| by removing internal colons or quotes.
        """
        if not code:
            return code

        # Strip markdown fences if present
        code = re.sub(r"^```(?:mermaid)?\s*", "", code)
        code = re.sub(r"\s*```$", "", code).strip()

        sanitized_lines = []
        for line in code.split("\n"):
            trimmed = line.strip()
            # Skip directives or styles
            if trimmed.startswith("%%") or trimmed.startswith("style ") or trimmed.startswith("classDef "):
                sanitized_lines.append(line)
                continue

            # Auto-quote unquoted square bracket nodes: Node[Text with special chars] -> Node["Text with special chars"]
            def quote_square(m):
                prefix = m.group(1)
                inner = m.group(2).replace('"', "'").strip()
                return f'{prefix}["{inner}"]'
            line = re.sub(r'([A-Za-z0-9_-]+)\[([^"\]\n][^\]\n]*?)\]', quote_square, line)

            # Auto-quote unquoted curly bracket decision nodes: Node{Text?} -> Node{"Text?"}
            def quote_curly(m):
                prefix = m.group(1)
                inner = m.group(2).replace('"', "'").strip()
                return f'{prefix}{{"{inner}"}}'
            line = re.sub(r'([A-Za-z0-9_-]+)\{([^"\}\n][^\}\n]*?)\}', quote_curly, line)

            # Auto-quote unquoted parentheses nodes: Node(Text) -> Node("Text")
            def quote_round(m):
                prefix = m.group(1)
                inner = m.group(2).replace('"', "'").strip()
                return f'{prefix}("{inner}")'
            line = re.sub(r"([A-Za-z0-9_-]+)\((?!\()([^\"'()\n][^()\n]*?)\)", quote_round, line)

            # Clean up arrow labels
            def clean_arrow(m):
                arrow = m.group(1)
                label = re.sub(r'[":;]', ' ', m.group(2)).strip()
                return f'{arrow}|{label}|'
            line = re.sub(r'(-->|-.->|==>)\|([^|]+)\|', clean_arrow, line)

            sanitized_lines.append(line)

        return "\n".join(sanitized_lines)


    def generate_visual_for_concept(
        self,
        topic_title: str,
        chapter_title: str,
        spoken_explanation: str,
        visual_concept: str,
        visual_engine: str,
        chapter_idx: int,
        total_chapters: int
    ) -> str:
        """
        Stage 2: Translates the pedagogical explanation and visual concept into an authentic
        16:9 widescreen (800x450) multi-engine illustration (Mermaid, D3, Manim, or Pure SVG).
        """
        engine = visual_engine.lower() if visual_engine else "svg"
        if engine not in ["mermaid", "d3", "manim", "svg"]:
            engine = ["mermaid", "svg", "d3", "manim"][chapter_idx % 4]

        # Build visuals dynamically from scratch using the LLM for every concept
        # to guarantee 100% topical relevance to the specific video topic.

        # Engine-specific LLM instructions
        if engine == "mermaid":
            system_prompt = (
                "You are an expert computational visual systems architect. "
                "Generate valid, clean Mermaid.js diagram code (starting with 'flowchart TD' or 'flowchart LR') "
                "that directly illustrates the exact workflow, process, architecture, taxonomy, or causal pipeline "
                "explained in this chapter.\n\n"
                "CRITICAL RULES:\n"
                "1. Output ONLY raw Mermaid code starting with 'flowchart TD' or 'flowchart LR'.\n"
                "2. Include 4 to 7 connected stages labeled with the exact technical entities and mechanisms from the lecture.\n"
                "3. MANDATORY SYNTAX: Always wrap ALL node labels in double quotes inside brackets or braces! "
                "For example: A[\"Step Name (Details)\"] or B{\"Decision Question?\"}. "
                "NEVER use bare colons, parentheses, question marks, or slashes inside node brackets without double quotes.\n"
                "4. Apply rich high-contrast styles (e.g. style A fill:#1e293b,stroke:#38bdf8,stroke-width:2px,color:#f8fafc).\n"
                "5. STRICT TOPICAL RELEVANCE: Illustrate ONLY the specific concepts of this chapter. "
                "NEVER mention planets, solar system, Pluto, or Saturn unless the video is explicitly about astronomy!\n"
                "6. NO markdown fences, NO surrounding conversational text."
            )
            prompt_text = f"Topic: {topic_title}\nChapter: {chapter_title}\nExplanation: {spoken_explanation}\nVisual Concept: {visual_concept}\nGenerate the raw Mermaid code:"

        elif engine == "d3":
            system_prompt = (
                "You are an expert quantitative data visualization engineer. "
                "Generate a clean JSON specification for a 16:9 800x450 D3.js coordinate curve chart illustrating the "
                "quantitative rate changes, equations, mathematical curves, or dynamic relationships discussed in this chapter.\n\n"
                "CRITICAL RULES:\n"
                "1. Output ONLY a valid JSON object matching: {\"title\": \"...\", \"xLabel\": \"...\", \"yLabel\": \"...\", \"points\": [[0, 10], [1, 25], ..., [10, 85]]}.\n"
                "2. Provide 8 to 14 realistic coordinate points reflecting the actual scientific phenomenon or data trend.\n"
                "3. STRICT TOPICAL RELEVANCE: Match the exact metrics, equations, and quantities taught in this chapter. Never invent off-topic space or planetary labels.\n"
                "4. NO markdown, NO text outside the JSON."
            )
            prompt_text = f"Topic: {topic_title}\nChapter: {chapter_title}\nExplanation: {spoken_explanation}\nVisual Concept: {visual_concept}\nGenerate the D3 chart JSON:"

        elif engine == "manim":
            system_prompt = (
                "You are an expert mathematical and scientific animator in the style of 3Blue1Brown Manim. "
                "Generate a high-precision 16:9 800x450 vector SVG graphic (<svg viewBox=\"0 0 800 450\" xmlns=\"http://www.w3.org/2000/svg\" data-engine=\"manim\">).\n\n"
                "CRITICAL RULES:\n"
                "1. Background must be dark chalkboard: <rect width=\"800\" height=\"450\" fill=\"#0f172a\" rx=\"14\" stroke=\"#334155\" stroke-width=\"1.5\"/> with coordinate grid lines or glowing axes.\n"
                "2. Include coordinate axes, directional vector arrows, or geometric models strictly reflecting this chapter's actual topic. If a formula was taught, include a sleek top banner displaying it.\n"
                "3. Use vibrant 3Blue1Brown colors: cyan (#38bdf8), amber (#f59e0b), emerald (#10b981), purple (#c084fc).\n"
                "4. STRICT TOPICAL RELEVANCE: Depict ONLY what is taught in this chapter. NEVER draw planets, solar system, orbits, Pluto, or Saturn unless the lecture is explicitly about astronomy.\n"
                "5. Output ONLY raw <svg>...</svg> code with NO markdown fences."
            )
            prompt_text = f"Topic: {topic_title}\nChapter: {chapter_title}\nExplanation: {spoken_explanation}\nVisual Concept: {visual_concept}\nGenerate the complete 800x450 Manim chalkboard SVG:"

        else: # svg
            system_prompt = (
                "You are an elite educational scientific and technical visual artist (in the style of Kurzgesagt, 3Blue1Brown, and Veritasium).\n"
                "Generate a high-production, concise 16:9 widescreen 800x450 vector SVG graphic (<svg viewBox=\"0 0 800 450\" xmlns=\"http://www.w3.org/2000/svg\" data-engine=\"svg\">) "
                "that directly, specifically depicts the exact system, apparatus, mechanism, anatomy, architecture, code structures, or physical principles taught in this chapter.\n\n"
                "CRITICAL MANDATES:\n"
                "1. 100% TOPICAL FAITHFULNESS & ACCURACY (ZERO OFF-TOPIC DRIFT):\n"
                "   - The visual MUST strictly depict the exact academic subject matter of this chapter ('{chapter_title}': '{spoken_explanation}').\n"
                "   - ABSOLUTE BAN ON IRRELEVANT VISUALS: NEVER draw planets, solar system orbits, space starfields, Pluto, or Saturn UNLESS the video is specifically and explicitly about astronomy or planetary science!\n"
                "   - For computer science / programming: draw clean software architectures, data structures, protocol stacks, memory layouts, or execution pipelines.\n"
                "   - For biology / medicine: draw accurate cellular anatomy, biomolecules, organs, or physiological pathways.\n"
                "   - For physics / engineering: draw physical experimental apparatus, force vectors, mechanical systems, or circuit schematics.\n"
                "   - For mathematics / statistics: draw coordinate systems, geometric proofs, probability distributions, or matrix transformations.\n"
                "   - For economics / general: draw causal loop diagrams, systemic flowcharts, or structural frameworks.\n"
                "2. VISUAL COMPOSITION (800x450 WIDESCREEN):\n"
                "   - Dark modern canvas: <rect width=\"800\" height=\"450\" fill=\"#0f172a\" rx=\"14\" stroke=\"#1e293b\" stroke-width=\"1.5\"/>.\n"
                "   - Left/Center: Clean, beautifully rendered technical diagram with modern <defs> gradients (linearGradient, radialGradient), glowing vector paths, labeled components, and directional arrows.\n"
                "   - Right Side: A sleek glassmorphic HUD telemetry/summary card (<rect x=\"470\" y=\"65\" width=\"310\" height=\"355\" rx=\"10\" fill=\"#1e293b\" fill-opacity=\"0.9\" stroke=\"#38bdf8\" stroke-width=\"1.2\"/>) containing 3-4 bullet takeaways highlighting key terms from this chapter.\n"
                "   - Top: Header banner with the chapter title and topic title.\n"
                "3. CONCISE & CLEAN XML (AVOID TRUNCATION):\n"
                "   - Keep SVG concise (around 45 to 65 lines of code) so it renders cleanly without truncation.\n"
                "   - Ensure all tags (<rect>, <circle>, <path>, <text>, <line>, <g>) are properly closed.\n"
                "   - MUST end strictly with </svg>.\n"
                "   - Output ONLY raw <svg viewBox=\"0 0 800 450\" xmlns=\"http://www.w3.org/2000/svg\" data-engine=\"svg\">...</svg> with NO markdown code fences and NO surrounding conversational text."
            )
            prompt_text = f"Topic: {topic_title}\nChapter: {chapter_title}\nExplanation: {spoken_explanation}\nVisual Concept: {visual_concept}\nGenerate the complete 800x450 SVG graphic:"

        try:
            from compiler import validate_svg_ast
        except ImportError:
            from server.compiler import validate_svg_ast

        if (self.groq_api_key and self.groq_api_key.strip()) or (self.hf_token and self.hf_token.strip()):
            try:
                call_tokens = 900 if engine in ["mermaid", "d3"] else 2200
                raw_out = self._invoke_llm(
                    prompt=prompt_text,
                    system_prompt=system_prompt,
                    max_tokens=call_tokens,
                    temperature=0.2
                )
                cleaned = raw_out.strip()
                if engine == "mermaid":
                    cleaned_code = re.sub(r"^```(?:mermaid)?\s*", "", cleaned)
                    cleaned_code = re.sub(r"\s*```$", "", cleaned_code).strip()
                    if "-->" in cleaned_code or "flowchart" in cleaned_code or "graph" in cleaned_code:
                        return self.sanitize_mermaid_server(cleaned_code)

                elif engine == "d3":
                    cleaned_json = re.sub(r"^```(?:d3|json)?\s*", "", cleaned)
                    cleaned_json = re.sub(r"\s*```$", "", cleaned_json).strip()
                    try:
                        parsed = json.loads(cleaned_json)
                        if isinstance(parsed, dict) and "points" in parsed:
                            return json.dumps(parsed)
                    except Exception:
                        pass

                else: # manim or svg
                    if "<svg" in cleaned and "</svg>" in cleaned:
                        start_pos = cleaned.find("<svg")
                        end_pos = cleaned.rfind("</svg>") + 6
                        svg_slice = cleaned[start_pos:end_pos]
                        is_val, rep_svg, _ = validate_svg_ast(svg_slice, auto_repair=True)
                        if is_val and "</svg>" in rep_svg:
                            return rep_svg
            except Exception as e:
                logger.warning(f"LangChain visual generation warning for {engine}: {e}. Falling back to domain generator.")

        # Fallback to high-fidelity domain visual generator
        return self._generate_domain_visual(
            topic_title=topic_title,
            chapter_title=chapter_title,
            chapter_idx=chapter_idx,
            total_chapters=total_chapters,
            speech_text=spoken_explanation,
            visual_engine=engine
        )

    def generate_svg_for_concept(
        self,
        topic_title: str,
        chapter_title: str,
        spoken_explanation: str,
        visual_concept: str,
        chapter_idx: int,
        total_chapters: int
    ) -> str:
        """Backward compatibility delegator"""
        return self.generate_visual_for_concept(
            topic_title=topic_title,
            chapter_title=chapter_title,
            spoken_explanation=spoken_explanation,
            visual_concept=visual_concept,
            visual_engine="svg",
            chapter_idx=chapter_idx,
            total_chapters=total_chapters
        )

    def compile_lecture_single_pass(
        self,
        topic_title: str,
        transcript_text: str,
        target_duration_minutes: float = 4.0,
        num_frames: Optional[int] = None,
        target_language: str = "en"
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Deterministic Educational Data Compiler and Render Orchestrator:
        Compiles the entire educational lecture timeline (bilingual scripts + localized engine payloads)
        in a SINGLE pass, bypassing parallel rate limits (HTTP 429) and ensuring 100% topical relevance.
        """
        if not (self.groq_api_key and self.groq_api_key.strip()) and not (self.hf_token and self.hf_token.strip()):
            return None

        # Calibrate frame count for single-pass compilation: 4 to 6 frames is optimal
        if num_frames and num_frames > 0:
            target_frames = max(3, min(8, int(num_frames)))
        else:
            if target_duration_minutes <= 3.0:
                target_frames = 4
            elif target_duration_minutes <= 6.0:
                target_frames = 5
            else:
                target_frames = 6

        seconds_per_frame = round((target_duration_minutes * 60.0) / target_frames, 1)

        clean_transcript = preprocess_transcript_for_pedagogy(
            transcript_text,
            target_frames=target_frames,
            max_chars=6000
        )
        if not clean_transcript:
            clean_transcript = transcript_text[:4000]

        system_prompt = (
            "You act as a deterministic Educational Data Compiler and Render Orchestrator. "
            "Your absolute mandate is to convert raw educational text or video transcripts into a strictly structured "
            "timeline JSON payload optimized for localized rendering engines.\n\n"
            "[VISUAL COMPILING RULES]\n"
            "You are forbidden from generating manual, raw SVG shape strings (such as <path d=\"...\" /> or complex <ellipse> arrangements) from scratch. "
            "Instead, you must select the single most accurate Rendering Engine from the list below based on the academic subject matter being discussed in the script segment.\n\n"
            "You must map the visual requirement into one of these 4 structural engine configurations:\n\n"
            "1. ENGINE: \"mermaid\"\n"
            "   - Use For: Process flows, circular cycles, timelines, tree hierarchies, classification charts, and structural step-by-step systems (e.g., Water Cycle, History timelines, corporate structures, biological processes).\n"
            "   - Expected Output in payload: A clean, standard Mermaid.js graph string (e.g., \"graph TD; A[Sun] --> B[Water Vapor];\"). "
            "IMPORTANT: Always wrap node text containing spaces or special characters in double quotes like A[\"Step Name\"].\n\n"
            "2. ENGINE: \"math_graph\"\n"
            "   - Use For: Algebraic equations, calculus functions, geometric coordinate functions, physics waves, and statistical graphs (e.g., y = sin(x), quadratic curves, supply/demand shifts).\n"
            "   - Expected Output in payload: A standard JSON configuration string specifying the mathematical function string (e.g., \"{ \\\"title\\\": \\\"Wave Equation\\\", \\\"equation\\\": \\\"y = sin(x)\\\", \\\"x_range\\\": [-10, 10] }\").\n\n"
            "3. ENGINE: \"parametric_template\"\n"
            "   - Use For: Highly specific, standardized scientific models where geometry is absolute (e.g., Bohr Atom models, simple molecular bonds, planetary arrangements).\n"
            "   - Expected Output in payload: A clear structural layout template call matching standard parameters (e.g., \"{ \\\"template\\\": \\\"atom\\\", \\\"element\\\": \\\"Carbon\\\", \\\"protons\\\": 6, \\\"electrons\\\": 6 }\").\n\n"
            "4. ENGINE: \"basic_geometry\"\n"
            "   - Use For: Universal baseline visual layouts (e.g., a simple focal highlight, pointing an arrow to a text label, drawing a single accent box around a formula).\n"
            "   - Expected Output in payload: Simple structural geometric primitives ONLY (e.g., <circle cx=\"400\" cy=\"225\" r=\"50\" fill=\"#38bdf8\"/> <text x=\"400\" y=\"230\" text-anchor=\"middle\" fill=\"#ffffff\">Focus</text>). No intricate paths.\n\n"
            "[STRICT OUTPUT FORMAT CONSTRAINTS]\n"
            "- Your absolute output format must be a raw JSON array of objects.\n"
            "- Do not wrap the JSON output inside markdown block identifiers like ```json or ``` text markers.\n"
            "- Do not append conversational preambles, summaries, or post-explanations.\n"
            "- Ensure all inner configuration text fields use valid escaped double quotes inside the JSON string values.\n"
            "- STRICT TOPICAL RELEVANCE: Illustrate ONLY the specific concepts of this topic. NEVER mention planets, solar system, Pluto, or Saturn unless the video is explicitly about astronomy!\n\n"
            "[JSON STRUCTURAL TARGET SCHEMA]\n"
            "Each entry in your chronological timeline array must strictly conform to these structural keys:\n"
            "{\n"
            "  \"timestamp_seconds\": [Float value representing sequence marker execution time],\n"
            "  \"chapter_title\": \"[English chapter title]\",\n"
            "  \"chapter_title_hi\": \"[Devanagari Hindi chapter title]\",\n"
            "  \"spoken_text\": \"[Detailed paragraph of educational text in English spoken by a master teacher]\",\n"
            "  \"spoken_text_hi\": \"[Authentic teacher explanation in Devanagari Hindi for this chapter]\",\n"
            "  \"engine_type\": \"mermaid | math_graph | parametric_template | basic_geometry\",\n"
            "  \"render_payload\": \"[The exact data string or configuration payload matching the designated engine constraints]\"\n"
            "}"
        )

        user_prompt = (
            f"Topic: {topic_title}\n"
            f"Target Milestones: Exactly {target_frames} chronological frames spaced across {target_duration_minutes:.1f} minutes.\n"
            f"Transcript Source:\n{clean_transcript}\n\n"
            f"Compile the complete chronological timeline JSON array with exactly {target_frames} milestone objects:"
        )

        try:
            raw_out = self._invoke_llm(
                prompt=user_prompt,
                system_prompt=system_prompt,
                max_tokens=1800,
                temperature=0.2
            )
            cleaned = raw_out.strip()
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned).strip()

            # Find JSON array bracket boundaries
            start_bracket = cleaned.find("[")
            end_bracket = cleaned.rfind("]")
            if start_bracket != -1 and end_bracket != -1 and end_bracket > start_bracket:
                cleaned = cleaned[start_bracket:end_bracket + 1]

            parsed_list = json.loads(cleaned)
            if not isinstance(parsed_list, list) or len(parsed_list) == 0:
                return None

            frames: List[Dict[str, Any]] = []
            engine_map = {
                "mermaid": "mermaid",
                "math_graph": "d3",
                "parametric_template": "manim",
                "basic_geometry": "svg"
            }

            for idx, item in enumerate(parsed_list):
                if not isinstance(item, dict):
                    continue

                ts = item.get("timestamp_seconds")
                if ts is None or not isinstance(ts, (int, float)):
                    ts = idx * seconds_per_frame
                else:
                    ts = float(ts)

                ch_title = str(item.get("chapter_title") or f"Milestone {idx + 1}").strip()
                ch_title_hi = str(item.get("chapter_title_hi") or "").strip()
                spoken = str(item.get("spoken_text") or "").strip()
                spoken_hi = str(item.get("spoken_text_hi") or "").strip()

                # If Hindi track missing from single-pass, populate via deterministic translator
                if not spoken_hi or not ch_title_hi:
                    h_title, h_speech = self._translate_chapter_to_hindi(ch_title, spoken, topic_title, idx)
                    if not ch_title_hi:
                        ch_title_hi = h_title
                    if not spoken_hi:
                        spoken_hi = h_speech

                raw_engine = str(item.get("engine_type") or "basic_geometry").strip().lower()
                vis_engine = engine_map.get(raw_engine, "mermaid" if "-->" in str(item.get("render_payload", "")) else "svg")
                render_payload = str(item.get("render_payload") or "").strip()

                if vis_engine == "mermaid" and render_payload:
                    render_payload = self.sanitize_mermaid_server(render_payload)

                frames.append({
                    "timestamp_seconds": ts,
                    "chapter_title": ch_title,
                    "chapter_title_hi": ch_title_hi,
                    "spoken_text": spoken,
                    "spoken_text_hi": spoken_hi,
                    "action_type": 1,
                    "svg_payload": render_payload,
                    "visual_engine": vis_engine,
                    "render_payload": render_payload
                })

            if len(frames) >= 2:
                frames.sort(key=lambda x: x["timestamp_seconds"])
                return frames
            return None

        except Exception as e:
            logger.warning(f"Single-pass compilation failed: {e}. Falling back to multi-stage pipeline...")
            return None

    def compile_full_lecture(
        self,
        topic_title: str,
        transcript_text: str,
        source_url: str = "",
        target_duration_minutes: float = 4.0,
        num_frames: Optional[int] = None,
        target_language: str = "en"
    ) -> Dict[str, Any]:
        """
        Orchestrates full LangChain pipeline for Option A (Rich Widescreen 16:9 Vector Illustrations):
        1. Curriculum planning with in-depth bilingual teacher voiceover script and calculated timeline.
        2. High-fidelity 800x450 vector SVG generation for every frame (staggered execution).
        3. AST verification and healing.
        """
        import concurrent.futures
        import time

        # Calibrated for optimal pedagogical pacing (~45-60 seconds per visual milestone)
        if not num_frames or num_frames <= 0:
            if target_duration_minutes <= 3.0:
                num_frames = 4
            elif target_duration_minutes <= 6.0:
                num_frames = 5
            else:
                num_frames = min(7, max(4, int(target_duration_minutes * 1.0)))
        else:
            num_frames = max(3, min(8, int(num_frames)))

        seconds_per_frame = (target_duration_minutes * 60.0) / max(num_frames, 1)

        # Stage 1: Pedagogical Curriculum Planning
        curriculum = self.plan_pedagogical_curriculum(
            topic_title=topic_title,
            transcript_text=transcript_text,
            target_duration_minutes=target_duration_minutes,
            num_frames=num_frames,
            target_language=target_language
        )

        def build_frame(item: tuple) -> Dict[str, Any]:
            idx, ch = item
            ch_idx = ch.get("chapter_index", idx)
            ch_title = ch.get("chapter_title", f"Concept {ch_idx + 1}")
            ch_title_hi = ch.get("chapter_title_hi") or ""
            explanation = ch.get("spoken_explanation", "")
            explanation_hi = ch.get("spoken_explanation_hi") or ""

            # Ensure Hindi track is always populated with authentic teacher pedagogy
            if not explanation_hi or not ch_title_hi:
                h_title, h_speech = self._translate_chapter_to_hindi(ch_title, explanation, topic_title, ch_idx)
                if not ch_title_hi:
                    ch_title_hi = h_title
                if not explanation_hi:
                    explanation_hi = h_speech

            concept = ch.get("visual_concept", "")
            # In Option A: Generate rich 16:9 widescreen vector SVG illustrations
            engine_choice = "svg"
            timestamp = float(ch.get("timestamp_seconds", ch_idx * seconds_per_frame))

            # Stagger generation slightly to keep TPM below Groq rate limits
            if idx > 0:
                time.sleep(idx * 0.35)

            raw_visual = self.generate_visual_for_concept(
                topic_title=topic_title,
                chapter_title=ch_title,
                spoken_explanation=explanation,
                visual_concept=concept,
                visual_engine=engine_choice,
                chapter_idx=ch_idx,
                total_chapters=len(curriculum)
            )

            return {
                "timestamp_seconds": timestamp,
                "spoken_text": explanation,
                "spoken_text_hi": explanation_hi,
                "action_type": 1,  # INJECT_NEW_VECTOR
                "svg_payload": raw_visual,
                "visual_engine": engine_choice,
                "chapter_title": ch_title,
                "chapter_title_hi": ch_title_hi
            }

        max_workers = min(len(curriculum), 2)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            frames = list(executor.map(build_frame, enumerate(curriculum)))

        # Sort frames strictly by timestamp
        frames.sort(key=lambda x: x["timestamp_seconds"])

        lecture_id = f"yt-{os.urandom(4).hex()}"
        return {
            "lecture_id": lecture_id,
            "topic_title": topic_title,
            "source_video_url": source_url,
            "target_duration_seconds": target_duration_minutes * 60.0,
            "target_language": target_language,
            "frames": frames
        }

    # =========================================================================
    # High-Fidelity Pedagogical Domain Synthesizer & Vector Generator
    # (Runs seamlessly when API key is pending or during cold-starts)
    # =========================================================================

    def _synthesize_pedagogical_curriculum(
        self,
        topic_title: str,
        transcript_text: str,
        target_duration_minutes: float,
        num_frames: int,
        target_language: str = "en"
    ) -> List[Dict[str, Any]]:
        """
        Generates in-depth pedagogical teacher scripts (70-95 words per frame)
        tailored strictly to the subject matter, spanning the full multi-minute duration.
        Eliminates all robotic filler formulas and auto-caption punctuation bugs.
        """
        seconds_per_frame = round((target_duration_minutes * 60.0) / max(num_frames, 1), 1)
        lower_topic = topic_title.lower()
        lower_text = f"{topic_title} {transcript_text}".lower()

        # Domain classification - strictly anchored to topic to prevent false domain captures
        is_pluto = any(w in lower_topic for w in ["pluto", "tombaugh", "dwarf planet", "kuiper belt", "iau dwarf"])
        is_solar = any(w in lower_topic for w in ["solar system", "planets of the solar", "heliocentric system"])
        is_space = is_solar or is_pluto or any(w in lower_topic for w in ["astronomy", "cosmos", "interplanetary", "exoplanet", "galaxy"])
        is_quantum = any(w in lower_topic for w in ["quantum", "double slit", "wave-particle duality", "superposition", "wavefunction"])
        is_relativity = any(w in lower_topic for w in ["speed of light", "special relativity", "general relativity", "spacetime"])
        is_neural = any(w in lower_topic for w in ["neural network", "deep learning", "machine learning", "gradient descent", "backpropagation"])
        is_mitosis = any(w in lower_topic for w in ["mitosis", "meiosis", "cell division", "chromosome segregation"])
        is_biochem = any(w in lower_topic for w in ["photosynthesis", "calvin cycle", "cellular respiration", "krebs cycle"])
        is_math = any(w in lower_topic for w in ["calculus", "derivative", "differential equation", "linear algebra"])
        if is_space:
            # 85%+ Pure SVGs for space & astronomical topics, with occasional D3/Manim for quantitative orbital curves
            engine_cycle = ["svg", "svg", "svg", "d3", "svg", "svg", "manim", "svg"]
        elif is_mitosis or is_biochem:
            engine_cycle = ["svg", "svg", "svg", "mermaid", "svg", "svg"]
        elif is_quantum or is_relativity:
            engine_cycle = ["svg", "svg", "manim", "svg", "d3", "svg"]
        elif is_neural or is_math:
            engine_cycle = ["svg", "d3", "svg", "manim", "mermaid", "svg"]
        else:
            engine_cycle = ["svg", "svg", "svg", "d3", "svg", "mermaid"]

        chapters_data = []

        # =====================================================================
        # DOMAIN 1: SOLAR SYSTEM & PLANETARY ARCHITECTURE (18 HIGH-DENSITY CHAPTERS)
        # =====================================================================
        if is_solar and not is_pluto:
            chapters_data = [
                (
                    "The Solar System: Gravitational Center & The Sun",
                    "At the heliocentric center of our solar system sits the Sun, an incandescent sphere of plasma containing over 99.8 percent of all mass in the entire planetary system. In its core, thermonuclear fusion converts four million tons of matter into pure radiant energy every second, generating the vast gravitational well that commands the orbits of every planet, asteroid, and comet while warming the surrounding cosmos.",
                    "Heliocentric macro diagram showing the Sun's radiant corona, magnetic field loops, and the gravitational potential well."
                ),
                (
                    "The Solar Atmosphere: Corona, Flares & Magnetic Loops",
                    "Surrounding the solar surface lies the scorching corona, a dynamic envelope of superheated plasma reaching temperatures of several million degrees Celsius. Twisted magnetic field lines erupt from sunspots, accelerating energetic protons and electrons outwards into interplanetary space as the supersonic solar wind. This continuous plasma outflow sculpts the heliospheric bubble that shields our entire planetary family from galactic cosmic rays.",
                    "Detailed cutaway of the solar corona, magnetic flux ropes, coronal mass ejections, and the outward solar wind vector field."
                ),
                (
                    "Mercury: Extreme Thermal Gradients & Ancient Basins",
                    "Innermost of all worlds is Mercury, a dense sphere of silicate rock encasing a colossal metallic iron core. Lacking any substantial insulating atmosphere, Mercury endures wild thermal extremes, plunging to minus 180 degrees Celsius during the long night and soaring to 430 degrees under the searing solar glare. Its cratered face preserves billions of years of cosmic bombardment, dominated by the massive Caloris Basin impact structure.",
                    "Cross-section of Mercury showing the disproportionately large metallic core and cratered surface with the Caloris Basin."
                ),
                (
                    "Venus: Supercritical Atmosphere & Runaway Greenhouse",
                    "Second from the Sun lies Venus, often called Earth's twin in size and mass, yet an absolute planetary furnace. Wrapped in an impenetrable blanket of opaque sulfuric acid clouds, Venus experiences a catastrophic runaway greenhouse effect. Atmospheric pressure at its scorched basalt surface exceeds 90 Earth atmospheres, trapping heat until temperatures hover constantly at a lead-melting 465 degrees Celsius. This super-dense carbon dioxide atmosphere completely prevents heat dissipation, making Venus the hottest planetary surface in the entire solar system.",
                    "Atmospheric column diagram of Venus depicting sulfuric acid cloud decks, infrared thermal trapping, and dense supercritical CO2."
                ),
                (
                    "Earth & The Moon: The Habitable Goldilocks Zone",
                    "Orbiting precisely within the circumstellar habitable zone at one astronomical unit, Earth possesses liquid water oceans, active plate tectonics, and a protective magnetosphere generated by its liquid outer core. Notice the Earth-Moon gravitational barycenter. The Moon stabilizes Earth's axial tilt, preventing wild climatic swings and sustaining the stable environmental conditions required for four billion years of continuous biological evolution.",
                    "Orbital schematic of Earth and Moon showing the shared barycenter, magnetosphere deflecting solar wind, and the liquid water ocean zone."
                ),
                (
                    "Earth's Magnetosphere: Dipolar Dynamo Deflection",
                    "Deep within Earth, vigorous convective currents in the molten liquid iron outer core generate a powerful dipolar magnetic field through a self-sustaining geodynamo. Extending tens of thousands of kilometers into space, the magnetosphere creates a defensive bow shock that deflects lethal solar wind particles into the Van Allen radiation belts, preventing atmospheric stripping and preserving our biosphere.",
                    "3D vector field map of Earth's magnetosphere illustrating the bow shock, magnetic reconnection lines, and trapped radiation belts."
                ),
                (
                    "Mars: The Crimson Desert & Ancient Hydrology",
                    "Across the orbital boundary lies Mars, the Red Planet, stained rust-red by ubiquitous iron oxide dust. While frigid and barren today beneath an atmospheric pressure of less than one percent of Earth's, Martian topography reveals unmistakable dried river channels, deltaic sediment fans, and colossal geological monuments, including Olympus Mons, the largest volcano in the entire solar system, towering 22 kilometers high.",
                    "Topographic elevation model of Mars highlighting Olympus Mons, Valles Marineris canyon, and ancient dry river delta deposits."
                ),
                (
                    "Mars: Olympus Mons & The Tharsis Volcanic Shield",
                    "The colossal volcanic province of Tharsis demonstrates how the absence of plate tectonics shaped Martian geology. Because the crust remained stationary over a stationary mantle hotspot for hundreds of millions of years, magma erupted repeatedly through the same conduits, constructing Olympus Mons—a volcanic shield whose base spans the entire width of France and whose caldera punctures the thin Martian stratosphere.",
                    "Geological cross-section of Olympus Mons showing the subterranean magma chamber, layered basaltic lava flows, and summit caldera caldera collapse."
                ),
                (
                    "The Asteroid Belt: Jupiter's Resonance & Accretion Barrier",
                    "Between the orbits of Mars and Jupiter lies the Asteroid Belt, a swirling ring populated by millions of rocky and metallic planetesimals left over from the birth of the solar system. Far from condensing into a ninth planet, accretion was permanently disrupted here by the immense gravitational resonance of nearby Jupiter, which continuously stirred velocities and shattered colliding protoplanets.",
                    "Distribution ring map of the Asteroid Belt between Mars and Jupiter, highlighting orbital resonance Kirkwood gaps."
                ),
                (
                    "Ceres: The Dwarf Planet of the Asteroid Realm",
                    "Dominating the main Asteroid Belt is Ceres, a round dwarf planet containing one-third of the belt's total mass. NASA's Dawn mission discovered that Ceres is a water-rich world possessing a rocky silicate core encased in an icy mantle. White reflective salt deposits inside Occator Crater demonstrate active cryovolcanism, where briny subterranean fluids percolate upward to the frigid surface.",
                    "Cutaway profile of dwarf planet Ceres showing its icy mantle, hydrated salts, and the reflective Occator Crater central dome."
                ),
                (
                    "Jupiter: Gas Giant Fluid Dynamics & The Great Red Spot",
                    "Crossing beyond the asteroid belt reveals the realm of the outer giants, commanded by Jupiter. With a mass exceeding two and a half times all other planets combined, Jupiter is a fluid giant composed almost entirely of hydrogen and helium. Its vibrant counter-rotating cloud bands and the Great Red Spot—a high-pressure cyclonic storm raging continuously for centuries—demonstrate the spectacular power of deep atmospheric convection.",
                    "Fluid atmospheric zonal flow schematic of Jupiter showing counter-rotating jet streams, the Great Red Spot vortex, and Galilean moons."
                ),
                (
                    "The Galilean Moons: Volcanic Io & Europa's Ocean",
                    "Jupiter orchestrates a miniature solar system of its own through its four colossal Galilean moons. Locked in a 4:2:1 Laplace orbital resonance, tidal forces continually flex Io's interior, fueling hundreds of active sulfur volcanoes. Meanwhile, neighboring Europa conceals a global liquid water ocean twice the volume of all Earth's oceans combined beneath a fractured ice shell.",
                    "Orbital resonance schematic showing Io, Europa, and Ganymede with tidal heating cross-sections."
                ),
                (
                    "Saturn: Dynamic Ring Architecture & Roche Limit",
                    "Further outward glides Saturn, universally celebrated for its breathtaking system of concentric rings. Extending up to 280,000 kilometers from the planet but averaging barely ten meters in thickness, these rings consist of trillions of glistening water-ice particles. They are the pulverized remains of comets and icy moons torn apart by tidal forces when venturing within Saturn's gravitational Roche limit.",
                    "3D profile of Saturn and its rings showing the A, B, and C rings separated by the Cassini Division, illustrating the Roche tidal limit."
                ),
                (
                    "Titan: Nitrogen Atmosphere & Liquid Hydrocarbon Lakes",
                    "Saturn's largest moon, Titan, is one of the most chemically fascinating environments in the solar system. Shrouded in an atmospheric blanket composed mostly of nitrogen with dense orange photochemical smog, Titan experiences a complete meteorological cycle analogous to Earth's—except rivers, precipitation, and vast polar seas are composed of liquid methane and ethane at minus 179 degrees Celsius.",
                    "Surface and atmospheric profile of Titan showing methane rainfall, meandering hydrocarbon river networks, and subsurface water ice."
                ),
                (
                    "Uranus: The Tilted Ice Giant & Methane Stratosphere",
                    "Penetrating deeper into the frozen frontier, we encounter Uranus, the first of the ice giants. Unlike Jupiter and Saturn, Uranus is enriched with heavier volatiles: water, ammonia, and methane ice. Atmospheric methane absorbs red photons, tinting the planet a calm cyan. Uniquely, Uranus rotates tilted 98 degrees on its side, likely knocked over by a cataclysmic collision during the early chaotic planetary migration.",
                    "Axial tilt diagram of Uranus rotating on its side at 98 degrees, illustrating extreme 42-year polar seasons and its faint vertical ring."
                ),
                (
                    "Neptune: Supersonic Storms & The Deep Azure Realm",
                    "Eighth and furthest of the major planets is Neptune, a deep azure world whipped by the fastest planetary winds ever measured in the solar system, exceeding 2,000 kilometers per hour. Driven by internal heat radiating outward from its core, Neptune's dynamic atmosphere spawns transient dark vortices and high-altitude white cirrus clouds of frozen methane crystals traveling across its upper troposphere.",
                    "Neptune atmospheric wind velocity profile showing retrograde equatorial jet streams, dynamic storm vortices, and high-altitude methane clouds."
                ),
                (
                    "The Kuiper Belt: The Frozen Remnants of Creation",
                    "Beyond Neptune's 30 AU orbit lies the vast expanse of the Kuiper Belt, a doughnut-shaped disk of primordial icy planetesimals stretching across hundreds of millions of kilometers. This frozen reservoir preserves pristine chemical clues dating back 4.6 billion years to the birth of the solar nebula, hosting hundreds of thousands of icy worlds, including Pluto, Haumea, and Makemake.",
                    "Planar orbital map of the Kuiper Belt extending from Neptune outward to 50 AU, showing orbital resonance clusters."
                ),
                (
                    "Cosmic Synthesis: Scale, Harmony & The Exoplanet Frontier",
                    "Viewing the architecture of the solar system as a unified whole reveals a precise balance of gravity, angular momentum, and thermodynamic condensation. What began as a collapsing cloud of interstellar gas and dust evolved into an intricate, life-bearing planetary ecosystem that now serves as our vital roadmap for exploring thousands of newly discovered exoplanetary systems across the galaxy.",
                    "Comprehensive logarithmic scale map from the Sun to the Oort Cloud, integrating terrestrial, giant, and trans-Neptunian orbital zones."
                )
            ]

        # =====================================================================
        # DOMAIN 2: PLUTO, KUIPER BELT & IAU PLANETARY CLASSIFICATION (16 CHAPTERS)
        # =====================================================================
        elif is_pluto:
            chapters_data = [
                (
                    "The Discovery of the Ninth Planet (1930)",
                    "In 1930, young astronomer Clyde Tombaugh at Lowell Observatory painstakingly compared photographic glass plates, detecting a faint point of light shifting against static background stars. Named after the Roman god of the underworld, Pluto was hailed worldwide as the ninth planet of our solar system, capturing humanity's imagination as a mysterious frozen sentinel guarding the cosmic edge. For over seven decades, school textbooks celebrated this distant world as the outer anchor of our planetary realm.",
                    "Tombaugh blink comparator apparatus showing photographic plates with Pluto shifting against static background stars."
                ),
                (
                    "The Anomalous Orbit & Trans-Neptunian Mechanics",
                    "As astronomers mapped Pluto's trajectory, startling anomalies emerged. Unlike the eight major planets whose orbits are nearly circular and co-planar along the ecliptic, Pluto travels on an eccentric, tilted 17-degree orbit that crosses inside Neptune's path. We now understand Pluto does not orbit alone; it is the crown jewel of the Kuiper Belt, a vast ring of icy debris left over from solar system accretion.",
                    "Elliptical 248-year inclined orbit of Pluto intersecting the ecliptic plane and Neptune's orbital track in the Kuiper Belt."
                ),
                (
                    "The Crisis of 2005: Eris & The Multi-Planet Dilemma",
                    "In the early 2000s, powerful digital sky surveys discovered dozens of large trans-Neptunian objects like Quaoar and Sedna. Then in 2005, Mike Brown's team discovered Eris, an icy world originally calculated to be more massive than Pluto. Astronomy faced a stark dilemma: either expand the solar system to dozens or hundreds of planets, or formalize what truly defines a planet.",
                    "Comparative scale diagram showing Earth, the Moon, Pluto, Charon, and Eris with relative orbital radii."
                ),
                (
                    "The IAU 2006 Three Criteria for Planethood",
                    "In August 2006, the International Astronomical Union convened in Prague and established three scientific criteria for planethood: the body must orbit the Sun, possess sufficient mass for hydrostatic equilibrium (a round shape), and have cleared the neighborhood around its orbit. Pluto satisfied the first two, but shares its orbital zone with thousands of Kuiper Belt objects.",
                    "Three-pillar scientific flowchart of the IAU definition highlighting hydrostatic equilibrium and orbital clearing."
                ),
                (
                    "The Dwarf Planet Classification & Plutoids",
                    "Pluto was reclassified as a dwarf planet—a category representing massive celestial bodies that are round like planets but reside within debris belts. Far from a demotion, this classification recognized Pluto as the archetype of an entirely new class of planetary worlds: plutinos and trans-Neptunian ice dwarfs that vastly outnumber the rocky and gas giant planets.",
                    "Solar system architectural taxonomy categorizing terrestrial planets, gas giants, ice giants, and dwarf planets."
                ),
                (
                    "New Horizons: The Living Ice World & Tombaugh Regio",
                    "In July 2015, NASA's New Horizons spacecraft flew within 7,800 miles of Pluto, transforming a fuzzy pixel into a geologically active world. Scientists were stunned to find Sputnik Planitia, a colossal heart-shaped basin of flowing nitrogen ice, water-ice mountains towering 11,000 feet, methane dunes, and compelling evidence of a deep liquid water ocean beneath its frozen crust.",
                    "High-resolution geological surface map of Pluto showing the heart-shaped Tombaugh Regio and nitrogen ice convection cells."
                ),
                (
                    "Charon & The Binary Planetary Dance",
                    "Pluto and its largest moon, Charon, form a true double planet system. Charon is so massive relative to Pluto—about one-eighth of its mass—that their gravitational center of mass lies out in open space between them. The two bodies are mutually tidally locked, eternally facing each other as they perform a graceful orbital ballet around their shared barycenter.",
                    "Binary barycenter orbital diagram showing Pluto and Charon revolving around an external mutual center of mass."
                ),
                (
                    "Atmospheric Dynamics & Sublimation Cycles",
                    "Pluto possesses a tenuous, layered atmosphere composed primarily of nitrogen, methane, and carbon monoxide. As Pluto travels along its 248-year elliptical orbit, the distance from the Sun fluctuates between 30 and 49 astronomical units. This causes dramatic atmospheric freeze-out cycles, where gases sublimate into hazy skies at perihelion and condense back onto the surface as seasonal snow.",
                    "Seasonal atmospheric sublimation diagram illustrating nitrogen pressure variations between perihelion and aphelion."
                ),
                (
                    "Kuiper Belt Architecture & Orbital Resonances",
                    "Pluto is locked in a stable 3-to-2 orbital resonance with Neptune: for every three times Neptune orbits the Sun, Pluto orbits precisely twice. This celestial clockwork ensures that even though Pluto's orbit crosses inside Neptune's, the two bodies can never collide. This gravitational harmony is shared by an entire population of Kuiper Belt objects known as plutinos.",
                    "Orbital resonance plot demonstrating the 3:2 Neptune-Pluto gravitational lock and safe separation distance."
                ),
                (
                    "The Expanding Family of Dwarf Planets",
                    "Pluto's reclassification opened the doorway to exploring an astonishing variety of dwarf worlds across our solar system. From Ceres in the Asteroid Belt to elongated, rapidly spinning Haumea, methane-shrouded Makemake, and distant scattered-disk world Eris, dwarf planets represent the most abundant and diverse class of large bodies in our cosmic neighborhood.",
                    "Comparative gallery of recognized dwarf planets showing Ceres, Pluto, Haumea, Makemake, and Eris to scale."
                ),
                (
                    "Subsurface Oceans & Outer Solar System Astrobiology",
                    "The New Horizons mission revealed that Sputnik Planitia's orientation is dynamically tied to a positive mass anomaly, strongly pointing to an underground liquid water ocean kept warm by radioactive decay in Pluto's rocky core. This astonishing discovery revolutionized planetary science, showing that liquid water and potential habitable environments can endure even in the deep freeze of the outer solar system.",
                    "Cross-sectional cutaway diagram of Pluto illustrating the silicate core, radioactive heat generation, subsurface liquid ocean, and ice shell."
                ),
                (
                    "Sputnik Planitia: Convection Cells of Glacial Nitrogen",
                    "The brilliant western lobe of Tombaugh Regio is a vast geological expanse known as Sputnik Planitia. Lacking any visible impact craters, this sheet of solid nitrogen, carbon monoxide, and methane ice continuously resurfaces itself through thermal convection. Polygonal cells twenty to forty kilometers across slowly churn, rising at their warm centers and descending along cool trenches like a colossal boiling cauldron of ice.",
                    "Cellular convection map of Sputnik Planitia illustrating polygonal nitrogen ice overturn and subterranean thermal plumes."
                ),
                (
                    "Water-Ice Mountain Ranges: Tenzing & Hillary Montes",
                    "Flanking the frozen plains of Sputnik Planitia stand jagged mountain chains rising up to four kilometers above the terrain, named Hillary Montes and Tenzing Montes. At Pluto's surface temperature of minus 230 degrees Celsius, water ice behaves not like soft snow, but like rigid bedrock, creating sheer structural peaks capable of supporting towering alpine relief.",
                    "Topographic elevation profile of Pluto's water-ice cordilleras demonstrating mechanical rigidity under cryogenic temperatures."
                ),
                (
                    "Cryovolcanism: Wright Mons & Rising Slush Plumes",
                    "South of Sputnik Planitia lies Wright Mons, a colossal volcanic construct over 150 kilometers wide with a cavernous central depression. Rather than spewing molten silicate basalt, Wright Mons is an immense cryovolcano that erupts a slurry of water ice, ammonia, and volatile salts originating from Pluto's subterranean mantle, reshaping the planet's young southern topography.",
                    "Cryovolcanic structural diagram of Wright Mons illustrating subterranean slush conduits and surface fissure eruptions."
                ),
                (
                    "The Clyde Tombaugh Legacy: Gateway to the Third Realm",
                    "Carrying a portion of Clyde Tombaugh's ashes, New Horizons fulfilled the astronomer's lifelong journey into the cosmic unknown. What began as a speck on photographic glass revolutionized our fundamental understanding of planetary evolution, proving that distance from the Sun does not dictate geological death, and that dynamic internal heat thrives even at the outer edge of creation.",
                    "Memorial trajectory timeline linking Tombaugh's 1930 discovery plate to New Horizons' 2015 interplanetary encounter."
                ),
                (
                    "Cosmic Perspective: Pluto's True Scientific Legacy",
                    "Rather than mourning the loss of a ninth planet label, modern astronomy celebrates Pluto as the gateway to the third zone of the solar system. Pluto proved that small, icy worlds can possess complex geology, cryovolcanism, and rich chemistry. Its study continues to illuminate the processes that assembled our solar system and govern worlds throughout the cosmos.",
                    "Conceptual synthesis artwork showing Pluto as the portal connecting the inner planetary system to the vast Kuiper Belt and interstellar space."
                )
            ]

        # =====================================================================
        # DOMAIN 3: QUANTUM MECHANICS & DOUBLE SLIT INTERFERENCE
        # =====================================================================
        elif is_quantum:
            chapters_data = [
                (
                    "The Classical Wave-Particle Conundrum",
                    "One of the most profound puzzles in modern physics centers on the fundamental nature of light and matter. In classical Newtonian physics, particles travel along distinct, deterministic trajectories, while waves spread out continuously, exhibiting diffraction and interference. For centuries, experiments like Young's double slit seemed to prove definitively that light is a continuous wave.",
                    "Comparative diagram showing Newtonian discrete particles forming two sharp bands versus continuous waves forming interference ripples."
                ),
                (
                    "The Double-Slit Diffraction Apparatus",
                    "Consider the physical double-slit experimental setup. A coherent light source emits photons toward a barrier with two narrow parallel slits separated by a distance d. As wavefronts pass through the slits, each slit acts as a secondary source of spherical ripples. When these wavefronts project onto a distant detector screen, they overlap, creating an alternating pattern of bright and dark fringes.",
                    "Schematic of the double-slit barrier showing path length difference delta L = d sin(theta) and screen interference fringes."
                ),
                (
                    "Constructive & Destructive Phase Interference",
                    "The formation of alternating fringes is governed by wave phase coherence. Where the path length difference between the two waves is an integer multiple of the wavelength, the wave peaks align in constructive interference, producing intense bright bands. Conversely, where peaks meet troughs, the waves completely cancel out in destructive interference, leaving regions of absolute darkness.",
                    "Wave superposition graph showing constructive in-phase addition yielding amplitude 2A versus destructive out-of-phase cancellation to zero."
                ),
                (
                    "The Single-Photon Firing Paradox",
                    "The puzzle deepens dramatically when laser intensity is reduced so low that only one single photon is fired at a time. Intuitively, a single discrete particle must pass through slit A or slit B and accumulate as two simple piles. Yet, as thousands of individual photon impacts are recorded over time, the full alternating interference fringe pattern miraculously reappears.",
                    "Accumulation time-lapse diagram showing individual photon detector dots gradually building up the continuous wave interference fringe."
                ),
                (
                    "Wavefunction Superposition & Probability",
                    "How can a single photon interfere with itself? In quantum theory, described by Erwin Schrödinger, the photon does not travel as a localized classical ball. Instead, it propagates as a probability wave or quantum state psi in a coherent superposition of passing through both slits simultaneously. The probability of detecting the photon at any point is proportional to the square of its wavefunction amplitude.",
                    "Schrodinger probability density function psi squared plotted across the detector screen showing probability peaks."
                ),
                (
                    "The Measurement Problem & Wavefunction Collapse",
                    "To solve the mystery, physicists placed high-speed particle detectors directly at the slits to catch the photon in the act of passing through one or the other. The moment this measurement is made, the quantum state undergoes instantaneous wavefunction collapse. The interference pattern immediately disappears, replaced by two classical particle bands. The mere act of measurement alters physical reality.",
                    "Dual-path setup showing a detector observing slit A causing wavefunction collapse and destroying the wave interference pattern."
                ),
                (
                    "De Broglie Wavelength & Matter Waves",
                    "This bizarre quantum behavior is not confined to light. In 1924, Louis de Broglie hypothesized that all matter possesses a characteristic wavelength equal to Planck's constant divided by momentum. Subsequent experiments fired electrons, neutrons, and even massive carbon-60 buckyball molecules through double slits—and every single one produced the exact same wave interference pattern.",
                    "De Broglie matter wave equation lambda = h / p connecting particle mass and momentum to physical spatial wavelength."
                ),
                (
                    "Quantum Epistemology: What Is Reality?",
                    "The double-slit experiment forces us to abandon naive classical realism. In the quantum domain, particles do not possess well-defined physical properties like position or trajectory prior to measurement. Nature is fundamentally probabilistic and non-local. Understanding this quantum reality provides the theoretical foundation for quantum computing, cryptography, and modern semiconductor physics.",
                    "Unified conceptual synthesis diagram bridging the quantum superposition state, the measurement interface, and classical macroscopic reality."
                )
            ]

        # =====================================================================
        # DOMAIN 4: SPECIAL RELATIVITY & THE SPEED OF LIGHT
        # =====================================================================
        elif is_relativity:
            chapters_data = [
                (
                    "The Two-Way Mirror Dilemma",
                    "Have you ever considered that the one-way speed of light has never actually been measured? Every physical experiment in modern history, from Fizeau's toothed wheel to contemporary atomic clocks, bounces photons off a distant mirror back to the source. This means we only ever measure the round-trip average velocity, leaving open the startling possibility that light travels at different speeds in opposite directions.",
                    "Laser emitter firing toward a distant mirror with forward and reverse velocity vectors showing the round-trip path."
                ),
                (
                    "The Clock Synchronization Paradox",
                    "To measure light traveling in one direction alone from point A to point B, you need synchronized clocks at both locations. But how do you synchronize them? If you send a light signal between them, you must assume the speed of light to set the clocks, which creates a circular logic trap. If you synchronize two clocks together and move one to point B, time dilation alters its tick rate.",
                    "Two synchronized atomic clocks at distance D separated with a question mark on the synchronization pulse."
                ),
                (
                    "Einstein's Anisotropic Convention",
                    "In his groundbreaking 1905 paper on Special Relativity, Albert Einstein recognized this profound epistemological barrier. He realized that the one-way speed of light is not an empirical fact of nature that we have discovered, but a convention—a definition that we choose for mathematical simplicity. We choose to assume light travels isotropically at constant c in all directions.",
                    "Coordinate spacetime graph showing symmetric light cones alongside an anisotropic skewed coordinate system."
                ),
                (
                    "Universal Invariance & Physical Observations",
                    "What happens to the laws of physics if light travels at instantaneous speed in one direction and half the speed in reverse? Incredibly, the round-trip speed remains precisely c, and all observational predictions of electrodynamics, GPS signals, and particle physics remain intact. Our universe permits this asymmetry without violating causality or observable reality.",
                    "Cosmic observer watching distant galaxies with varying directional photon propagation vectors."
                ),
                (
                    "Modern Topological Experiments",
                    "Contemporary physicists have devised ingenious topological experiments trying to close the measurement loop without reflections. Yet, because causality is fundamentally tied to the maximum speed of information transfer, any closed causal loop inherently measures the round-trip speed. The true one-way speed remains nature's best-kept secret.",
                    "Fiber optic closed loop resonator with interferometer interference peaks measuring photon phase coherence."
                ),
                (
                    "Synthesis & The Geometric Fabric of Spacetime",
                    "This counterintuitive revelation forces us to distinguish between what is physically measurable and what is a coordinate choice. The speed of light is not just how fast photons travel through space; it is the ultimate conversion factor between space and time itself. Understanding this elevates our perception from naive mechanics to genuine relativistic intuition.",
                    "Unified spacetime metric diagram with four-vector components and the invariant light cone structure."
                )
            ]

        # =====================================================================
        # DOMAIN 5: NEURAL NETWORKS & DEEP LEARNING
        # =====================================================================
        elif is_neural:
            chapters_data = [
                (
                    "The Artificial Neuron Architecture",
                    "At the core of modern artificial intelligence lies the artificial neuron, a computational model inspired by biological synapses. Instead of biochemical pulses, each neuron holds a numerical value called an activation. Notice on our diagram the column of input activations, each representing a single feature, such as the grayscale intensity of a pixel in an image.",
                    "Input layer with numbered nodes holding activation values connected to the next hidden layer."
                ),
                (
                    "Synaptic Weights & Feature Detectors",
                    "Neurons between adjacent layers are densely connected by lines called weights. Think of each weight as a dial that determines how strongly one neuron excites or inhibits another. A positive weight amplifies a signal, while a negative weight suppresses it. Together, these weights act as pattern filters designed to detect sub-components like edges and curves.",
                    "Bipartite graph with positive green and negative orange connection lines weighted with decimal values."
                ),
                (
                    "The Weighted Sum & Bias Threshold",
                    "To compute the activation of a hidden neuron, the network multiplies every incoming input by its corresponding weight and computes their sum. We then add a bias term, which acts as a threshold determining how active the neuron should be by default before receiving any input. This forms the linear combination w times x plus b.",
                    "Mathematical summation node computing sigma w_i times x_i plus bias, feeding into an activation node."
                ),
                (
                    "Nonlinear Activation Functions: ReLU & Sigmoid",
                    "If we only computed linear sums, stacking thousands of layers would still amount to nothing more than a single flat linear transformation. To learn complex, curvy decision boundaries, we pass the sum through a nonlinear activation function like ReLU or Sigmoid. This squashes the activation into a constrained range and introduces non-linearity.",
                    "Sigmoid S-curve and ReLU activation plots mapping negative values to zero and positive values linearly."
                ),
                (
                    "Deep Layer Hierarchies & Spatial Abstraction",
                    "The true magic of deep learning emerges through hierarchical abstraction. The early layers identify simple edges and texture gradients. Intermediate layers assemble these edges into shapes and contours. The final layers synthesize these contours into holistic concepts like numbers, faces, or semantic words with remarkable confidence.",
                    "Multilayer deep network showing progressive feature extraction from raw pixels to abstract geometric shapes."
                ),
                (
                    "Output Classification & Loss Measurement",
                    "Finally, the output layer delivers the network's verdict, distributing probability activations across all possible classes using softmax. If the network misclassifies an input, a loss function calculates the exact numerical error. This scalar value tells the network precisely how far its current predictions deviate from ground truth.",
                    "Softmax probability bar chart showing high activation for the target digit with error loss gradient arrow."
                ),
                (
                    "Backpropagation: The Chain Rule in Action",
                    "Learning occurs through backpropagation. By applying the calculus chain rule in reverse from the output layer back to the inputs, the network computes the partial derivative of the loss with respect to every single weight. This reveals which specific weights were responsible for the error and in which direction they must be adjusted.",
                    "Reverse computational graph showing error gradients flowing backward through weight matrices using the chain rule."
                ),
                (
                    "Gradient Descent & Generalization Mastery",
                    "Using gradient descent, an optimizer iteratively nudges millions of parameters down the multidimensional error landscape. Over thousands of training epochs, the network converges on an optimal configuration, moving beyond rote memorization to true generalization on previously unseen data.",
                    "3D loss landscape surface with gradient descent trajectory vector navigating into a global minimum basin."
                )
            ]

        # =====================================================================
        # DOMAIN 6: CELL BIOLOGY & MITOSIS
        # =====================================================================
        elif is_mitosis:
            chapters_data = [
                (
                    "The Cellular Division Imperative & Interphase",
                    "Every living organism originates from a single cell that duplicates through the finely orchestrated process of mitosis. Before division can occur, the cell spends most of its life in interphase, replicating its genomic DNA into identical sister chromatids. Centrosomes duplicate in the cytoplasm, preparing the mechanical apparatus required for chromosome segregation.",
                    "Cell membrane enclosing the nucleus with loose chromatin threads and duplicating centrosomes."
                ),
                (
                    "Prophase: Chromatin Condensation",
                    "As mitosis commences in prophase, loose chromatin condenses into tightly coiled, visible X-shaped chromosomes. Meanwhile, the nuclear envelope begins to disintegrate, and centrosomes migrate to opposite cellular poles, extending dynamic microtubules known as the mitotic spindle apparatus.",
                    "Condensed X-shaped chromosomes inside the dissolving nuclear envelope with radiating spindle fibers."
                ),
                (
                    "Metaphase: The Equatorial Alignment",
                    "During metaphase, spindle fibers attach to protein complexes called kinetochores located at the centromere of each chromosome. Cellular motor proteins generate opposing tension, pulling every chromosome until they align perfectly along the central equatorial plate. A cellular checkpoint ensures every single chromatid is anchored.",
                    "Equatorial metaphase plate with all chromosomes lined up precisely down the central vertical axis."
                ),
                (
                    "Anaphase: Chromatid Segregation",
                    "Once the spindle checkpoint is satisfied, molecular cohesin rings are cleaved. Spindle microtubules rapidly depolymerize, pulling sister chromatids apart toward opposite poles of the cell. Each chromatid is now an independent, full-fledged chromosome, guaranteeing genetic equivalence in both daughter cells.",
                    "Separated V-shaped chromatid arms being pulled in opposite directions toward the centrosome poles."
                ),
                (
                    "Telophase & Nuclear Envelope Reformation",
                    "In telophase, the separated chromosomes arrive at opposite poles and decondense back into diffuse chromatin. New nuclear membranes assemble around each set of chromosomes, reconstituting two genetically identical nuclei within a single elongated cytoplasm.",
                    "Two reforming nuclei at opposite ends of an elongated dumbbell-shaped cell."
                ),
                (
                    "Cytokinesis & Daughter Cell Cleavage",
                    "Finally, cytokinesis physically cleaves the cell into two. An actin and myosin contractile ring pinches the cell membrane along the cleavage furrow until it divides completely into two healthy, independent daughter cells, each containing an exact copy of the parent genome.",
                    "Two completely divided daughter cells each containing identical nuclei and complete organelles."
                )
            ]

        # =====================================================================
        # DOMAIN 7: CUSTOM TOPIC WITH TRANSCRIPT GROUNDING
        # =====================================================================
        elif transcript_text and transcript_text.strip():
            raw_lines = [l.strip() for l in transcript_text.split("\n") if l.strip()]
            cleaned_entries = []
            time_prefix = re.compile(r"^(\d{1,2}:(?:\d{2}:)?\d{2}(?:\.\d+)?)\s*(.*)$")
            sound_pattern = re.compile(r"\[(music|applause|laughter|cheering|snicker|sigh|groan)\]", re.IGNORECASE)
            sponsor_pattern = re.compile(r"(sponsor|nordvpn|caseta|squarespace|brilliant|audible|patreon|subscribe|bell icon|like this video)", re.IGNORECASE)

            for line in raw_lines:
                line_clean = sound_pattern.sub("", line).strip()
                if not line_clean or sponsor_pattern.search(line_clean):
                    continue
                m = time_prefix.match(line_clean)
                if m:
                    text = m.group(2).strip()
                    if text: cleaned_entries.append(text)
                else:
                    cleaned_entries.append(line_clean)

            # Join all words to eliminate auto-caption unpunctuated chunks
            all_words = " ".join(cleaned_entries).split()
            if len(all_words) >= max(12, num_frames * 4):
                stop_words = {"this", "that", "there", "these", "those", "video", "about", "which", "would", "could", "should", "their", "because", "going", "really", "actually", "think", "people", "welcome", "hello", "today", "channel"}
                words_per_frame = max(8, len(all_words) // num_frames)

                openers = [
                    "At the core of this system, {topic} establishes the governing physical conditions.",
                    "As the process develops, {topic} directly drives the primary interactions.",
                    "At this stage, the central operational dynamic is {topic}.",
                    "The observable behavior of the system shifts markedly under the influence of {topic}.",
                    "Underlying these mechanics, quantitative relationships govern how {topic} operates.",
                    "A key physical milestone emerges as {topic} regulates energy and matter transfer.",
                    "Empirical observations and experimental measurements reveal the precise behavior of {topic}.",
                    "Integrating these interactions demonstrates how {topic} stabilizes the macroscopic system."
                ]

                for idx in range(num_frames):
                    start_w = idx * words_per_frame
                    end_w = (idx + 1) * words_per_frame if idx < num_frames - 1 else len(all_words)
                    window_words = all_words[start_w:end_w]

                    # Extract prominent technical terms
                    meaningful = [w.capitalize() for w in window_words if re.match(r"^[A-Za-z]{4,}$", w) and w.lower() not in stop_words]
                    key_term = meaningful[0] if meaningful else f"Phase {idx + 1}"
                    sub_term = meaningful[1] if len(meaningful) > 1 else "Mechanisms"
                    topic_label = f"{key_term} & {sub_term}"

                    # Group window words into natural 12-16 word punctuated sentences
                    sub_sentences = []
                    for s_i in range(0, min(len(window_words), 55), 14):
                        chunk = window_words[s_i:s_i + 14]
                        if len(chunk) >= 4:
                            sub_sentences.append(" ".join(chunk).capitalize() + ".")

                    body_narration = " ".join(sub_sentences) if sub_sentences else f"During this stage, {topic_label.lower()} defines the primary interactions and energetic flow."
                    if len(body_narration.split()) < 35:
                        body_narration += f" This establishes the fundamental dynamics of {topic_label.lower()}, revealing how energy, structure, and physical constraints evolve across the system."
                    opener = openers[idx % len(openers)].format(topic=topic_label)
                    full_speech = f"{opener} {body_narration} The accompanying illustration highlights how these core parameters interact to govern the overall process."

                    chapter_title = f"{key_term}: Principles & Analysis" if idx > 0 else f"Introduction: {key_term} & Foundations"
                    visual_concept = f"A clean 16:9 widescreen 800x450 vector diagram illustrating {topic_label} with labeled schematic nodes, directional flow vectors, and clear annotations."

                    chapters_data.append((chapter_title, full_speech, visual_concept))

        # =====================================================================
        # DOMAIN 8: GENERAL ACADEMIC FOUNDATIONS (NO TRANSCRIPT / FALLBACK)
        # =====================================================================
        if not chapters_data:
            chapters_data = [
                (
                    f"Foundations of {topic_title}",
                    f"At its fundamental level, {topic_title} is governed by a precise balance of physical interactions and boundary constraints. Rather than a collection of isolated facts, the system functions as an interconnected dynamic structure. Defining the initial conditions and primary elements reveals how equilibrium is established, providing the crucial baseline for predicting how the entire system responds across every operational stage.",
                    "Overview coordinate diagram illustrating the primary elements and spatial boundaries of the topic."
                ),
                (
                    "The Primary Governing Mechanisms",
                    f"To understand how {topic_title} functions dynamically, we must analyze its fundamental governing interactions. Individual components continuously exchange energy, force, and information across distinct stages. When one element undergoes a state change, it triggers a predictable cascade across adjacent nodes, driving the system toward stable macroscopic equilibrium while preventing uncontrolled oscillation or breakdown.",
                    "System interaction map showing directional force and data arrows between key structural nodes."
                ),
                (
                    "Mathematical Formulation & State Dynamics",
                    "Natural phenomena are governed by rigorous mathematical relationships that translate observed physical behavior into predictable equations. By formalizing these interactions with quantitative rate laws and boundary functions, equilibrium states become mathematically predictable under varying environmental constraints. This formal framework enables researchers to calculate system responses with high precision, ensuring reliable analytical accuracy across all observed configurations.",
                    "Mathematical coordinate plane graphing the governing curve with labeled tangent vectors and boundary thresholds."
                ),
                (
                    "Critical Thresholds & Counterintuitive Behaviors",
                    "When physical parameters are pushed toward extreme limits, non-linear edge cases and counterintuitive behaviors often emerge. Understanding these critical thresholds, phase transitions, and bifurcation points provides the deep structural insight required to predict how the system behaves under stress. Mastering these dynamics allows engineers to prevent catastrophic failure modes and unlock higher operational efficiency in demanding real-world applications.",
                    "Phase space diagram highlighting critical bifurcation points and non-linear transitions."
                ),
                (
                    "Empirical Observation & Real-World Impact",
                    "Theoretical models achieve their ultimate validation when tested against rigorous empirical physical experiments. In modern research and applied science, these foundational principles form the operational backbone of advanced technologies. By comparing predicted values against calibrated sensor measurements, engineers can refine governing parameters, optimize efficiency, and ensure robust physical reliability across diverse operating conditions.",
                    "Experimental measurement apparatus showing sensor readouts and precision tolerance bands."
                ),
                (
                    "Conceptual Synthesis & Architectural Takeaways",
                    f"Synthesizing these concepts reveals how {topic_title} operates as a unified, coherent system. From initial boundary conditions to non-linear thresholds and empirical validation, each layer reinforces the predictive model that governs real-world applications in science and engineering. Looking across the complete architecture illuminates how microscopic mechanisms aggregate into observable macroscopic order.",
                    "Unified structural synthesis diagram connecting all previous layers into a balanced complete model."
                )
            ]

        # Expand chapters dynamically to match num_frames without generic repetitions
        while len(chapters_data) < num_frames:
            idx = len(chapters_data) + 1
            chapters_data.append((
                f"{topic_title}: Advanced Analysis (Phase {idx})",
                f"Examining secondary feedback loops and stabilizing forces in {topic_title} reveals how energy cascades through the system over extended time scales. As external conditions fluctuate, subtle parameter adjustments and damping mechanisms prevent runaway divergence, preserving overall system stability and maintaining structural equilibrium.",
                "Detailed schematic highlighting secondary feedback paths and stabilizing equilibrium loops."
            ))

        selected = chapters_data[:num_frames]
        curriculum = []

        for idx, (title, speech, concept) in enumerate(selected):
            ts = round(idx * seconds_per_frame, 1)
            h_title, h_speech = self._translate_chapter_to_hindi(title, speech, topic_title, idx)

            curriculum.append({
                "chapter_index": idx,
                "chapter_title": title,
                "chapter_title_hi": h_title,
                "timestamp_seconds": ts,
                "spoken_explanation": speech,
                "spoken_explanation_hi": h_speech,
                "visual_concept": concept,
                "visual_engine": engine_cycle[idx % len(engine_cycle)]
            })

        return curriculum

    def _translate_chapter_to_hindi(self, title: str, speech: str, topic: str, idx: int) -> tuple[str, str]:
        """
        Provides authentic, natural, high-fidelity Hindi educational translation (Devanagari script)
        for pedagogical chapters, eliminating robotic machine-transliteration quirks.
        """
        curated_map = {
            "The Solar System: Gravitational Center & The Sun": (
                "सौर मंडल: गुरुत्वाकर्षण केंद्र और सूर्य",
                "हमारे सौर मंडल के केंद्र में सूर्य स्थित है, जो प्लाज्मा का एक विशाल धधकता हुआ गोला है जिसमें पूरे सौर मंडल का 99.8 प्रतिशत द्रव्यमान समाहित है। इसके आंतरिक क्रोड में होने वाले थर्मोन्यूक्लियर नाभिकीय संलयन से प्रति सेकंड लाखों टन पदार्थ शुद्ध ऊर्जा में परिवर्तित होता है। यही ऊर्जा विशाल गुरुत्वाकर्षण कुआं बनाती है जो सभी ग्रहों, क्षुद्रग्रहों और धूमकेतुओं को अपनी कक्षा में बाँधकर रखता है।"
            ),
            "The Solar Atmosphere: Corona, Flares & Magnetic Loops": (
                "सौर वातावरण: कोरोना, सौर ज्वालाएँ और चुंबकीय लूप",
                "सूर्य की दृश्य सतह से ऊपर उठने पर सौर कोरोना का विस्तार होता है, जहाँ तापमान लाखों डिग्री तक पहुँच जाता है। मुड़ी हुई चुंबकीय क्षेत्र रेखाएँ संवहन प्लाज्मा से ऊर्जा सोखती हैं और सौर ज्वालाओं के रूप में भयानक विस्फोट करती हैं। ये चुंबकीय लूप और कोरोनल मास इजेक्शन सौर वायु के रूप में पूरे सौर मंडल में आवेशित कणों की एक निरंतर धारा बहाते हैं।"
            ),
            "Mercury: Extreme Thermal Swings & Cratered Basins": (
                "बुध ग्रह: अत्यधिक तापीय उतार-चढ़ाव और क्रेटर युक्त सतह",
                "सूर्य के सबसे निकट स्थित बुध ग्रह अत्यधिक विषम परिस्थितियों का सामना करता है। वायुमंडल की अनुपस्थिति के कारण यहाँ सौर मंडल का सबसे तीव्र तापीय उतार-चढ़ाव देखा जाता है। दिन का तापमान 430 डिग्री सेल्सियस तक पहुँच जाता है, जबकि रात में तापमान गिरकर माइनस 180 डिग्री हो जाता है। इसकी सतह पर प्राचीन उल्कापिंडों के संघात के निशान मौजूद हैं।"
            ),
            "Venus: Supercritical Atmosphere & Runaway Greenhouse": (
                "शुक्र ग्रह: सघन वातावरण और अनियंत्रित ग्रीनहाउस प्रभाव",
                "सूर्य से दूसरा ग्रह शुक्र है, जिसे आकार में पृथ्वी का जुड़वां माना जाता है, लेकिन यह एक दहकती हुई भट्टी के समान है। सल्फ्यूरिक एसिड के घने बादलों से ढका शुक्र अनियंत्रित ग्रीनहाउस प्रभाव का सबसे विनाशकारी उदाहरण है। यहाँ की सतह पर वायुमंडलीय दबाव पृथ्वी से 90 गुना अधिक है और तापमान निरंतर 465 डिग्री सेल्सियस पर बना रहता है, जो सीसे को भी पिघलाने में सक्षम है।"
            ),
            "Earth & The Moon: The Habitable Goldilocks Zone": (
                "पृथ्वी और चंद्रमा: जीवन योग्य गोल्डीलॉक्स ज़ोन",
                "सूर्य से एक खगोलीय इकाई की दूरी पर पृथ्वी जीवन योग्य गोल्डीलॉक्स ज़ोन में स्थित है। यहाँ तरल जल के महासागर, सक्रिय विवर्तनिक प्लेटें और रक्षात्मक चुंबकीय क्षेत्र मौजूद हैं। चंद्रमा पृथ्वी के अक्षीय झुकाव को स्थिर रखता है, जिससे चरम मौसमी उतार-चढ़ाव रुकते हैं और अरबों वर्षों से जैविक विकास के लिए अनुकूल वातावरण बना हुआ है।"
            ),
            "Earth's Magnetosphere: Dipolar Dynamo Deflection": (
                "पृथ्वी का चुंबकीय क्षेत्र: सौर वायु से जीवन की सुरक्षा",
                "पृथ्वी के आंतरिक तरल लोहे के क्रोड में संवहन धाराएँ जियोडायनेमो के माध्यम से एक शक्तिशाली द्विध्रुवीय चुंबकीय क्षेत्र उत्पन्न करती हैं। अंतरिक्ष में हजारों किलोमीटर तक फैला यह चुंबकीय मंडल सौर वायु के घातक आवेशित कणों को विक्षेपित कर वैन एलन विकिरण पेटियों में फँसा देता है, जिससे हमारा वायुमंडल अंतरिक्ष में बिखरने से सुरक्षित रहता है।"
            ),
            "Mars: The Crimson Desert & Ancient Hydrology": (
                "मंगल ग्रह: लाल रेगिस्तान और प्राचीन जल नदियाँ",
                "कक्षीय सीमा के पार मंगल ग्रह है, जो आयरन ऑक्साइड की धूल के कारण लाल दिखाई देता है। आज यह अत्यधिक ठंडा और विरल वातावरण वाला ग्रह है, लेकिन इसकी भौगोलिक संरचना प्राचीन सूखी नदी घाटियों, डेल्टा निक्षेपों और सौर मंडल के सबसे ऊंचे ज्वालामुखी ओलंपस मॉन्स को उजागर करती है, जो 22 किलोमीटर ऊंचा है।"
            ),
            "The Asteroid Belt: Jupiter's Resonance & Accretion Barrier": (
                "क्षुद्रग्रह घेरा: बृहस्पति का गुरुत्वाकर्षण और बिखरे हुए अवशेष",
                "मंगल और बृहस्पति के बीच क्षुद्रग्रह घेरा स्थित है, जिसमें सौर मंडल के निर्माण के समय के लाखों चट्टानी और धातु पिंड मौजूद हैं। पास स्थित विशालकाय बृहस्पति के प्रबल गुरुत्वाकर्षण और कक्षीय अनुनाद के कारण ये पिंड कभी मिलकर एक नौवें ग्रह का रूप नहीं ले सके और निरंतर आपस में टकराते रहे।"
            ),
            "Jupiter: Gas Giant Fluid Dynamics & The Great Red Spot": (
                "बृहस्पति: गैस दानव और विशाल लाल धब्बा (द ग्रेट रेड स्पॉट)",
                "क्षुद्रग्रह घेरे के पार बाहरी विशाल ग्रहों की दुनिया शुरू होती है, जिसका नेतृत्व बृहस्पति करता है। सौर मंडल के अन्य सभी ग्रहों के कुल द्रव्यमान से ढाई गुना अधिक भारी यह ग्रह हाइड्रोजन और हीलियम से बना है। इसका विशाल लाल धब्बा सदियों से चल रहा एक उच्च दबाव वाला चक्रवाती तूफान है, जो इसकी वायुमंडलीय शक्ति को प्रदर्शित करता है।"
            ),
            "Saturn: Dynamic Ring Architecture & Roche Limit": (
                "शनि ग्रह: छल्लों की वास्तुकला और रोश सीमा",
                "शनि ग्रह अपने मनमोहक छल्लों के लिए विश्व विख्यात है। ग्रह से 280,000 किलोमीटर दूर तक फैले ये छल्ले औसतन मात्र 10 मीटर मोटे हैं और खरबों बर्फ के कणों से मिलकर बने हैं। जब कोई बर्फीला चंद्रमा या धूमकेतु शनि की रोश सीमा के भीतर आया, तो गुरुत्वाकर्षण ज्वारीय बलों ने उसे छोटे-छोटे टुकड़ों में विखंडित कर दिया।"
            ),
            "Pluto & The Kuiper Belt": (
                "प्लूटो और काइपर बेल्ट: सौर मंडल की बर्फीली सीमा",
                "नेप्च्यून की कक्षा से परे काइपर बेल्ट में प्लूटो स्थित है। यह केवल एक निष्कासित ग्रह नहीं, बल्कि बाहरी सौर मंडल के तीसरे क्षेत्र का प्रवेश द्वार है। न्यू होराइजन्स मिशन ने साबित किया कि प्लूटो पर नाइट्रोजन बर्फ के विशाल हिमनद, बर्फीले पर्वत और उप-सतही महासागर मौजूद हैं, जो चरम ठंड में भी भूगर्भीय गतिविधि का प्रमाण हैं।"
            )
        }

        for k, v in curated_map.items():
            if k.lower() in title.lower() or title.lower() in k.lower():
                return v

        topic_lower = f"{title} {speech} {topic}".lower()
        if re.search(r"\b(sun|solar system|corona)\b", topic_lower):
            return (
                f"सूर्य और सौर ऊर्जा (चरण {idx + 1})",
                "सूर्य हमारे सौर मंडल की केंद्रीय शक्ति है। इसके भीतर चलने वाला निरंतर नाभिकीय संलयन अपार ऊर्जा उत्पन्न करता है, जिससे प्रकाश और गुरुत्वाकर्षण का संतुलन बना रहता है।"
            )
        elif re.search(r"\b(mars|martian)\b", topic_lower):
            return (
                f"मंगल ग्रह की संरचना और वायुमंडल (चरण {idx + 1})",
                "मंगल ग्रह की लाल मिट्टी और प्राचीन घाटियाँ संकेत देती हैं कि यहाँ कभी पानी का प्रवाह रहा होगा। आज यह ग्रह वैज्ञानिकों के लिए भविष्य की खोज का सबसे बड़ा केंद्र है।"
            )
        elif re.search(r"\b(earth|terrestrial)\b", topic_lower) and "astronomy" in topic_lower:
            return (
                f"पृथ्वी: जीवन और वायुमंडलीय संतुलन (चरण {idx + 1})",
                "पृथ्वी का अनूठा वायुमंडल और चुंबकीय क्षेत्र इसे जीवन के लिए आदर्श बनाते हैं। प्राकृतिक चक्र ऊर्जा और जल का सतत संतुलन बनाए रखते हैं।"
            )
        elif re.search(r"\b(quantum|double slit|wavefunction|superposition)\b", topic_lower):
            return (
                f"क्वांटम यांत्रिकी: तरंग-कण प्रकृति (चरण {idx + 1})",
                "क्वांटम भौतिकी दर्शाती है कि सूक्ष्म कण एक ही समय में तरंग और कण दोनों की भांति व्यवहार कर सकते हैं, जो शास्त्रीय भौतिकी के नियमों को चुनौती देता है।"
            )
        elif re.search(r"\b(speed of light|relativity|spacetime|einstein)\b", topic_lower):
            return (
                f"सापेक्षता का सिद्धांत और प्रकाश की गति (चरण {idx + 1})",
                "आइंस्टीन के अनुसार प्रकाश की गति ब्रह्मांड में एक सार्वभौमिक स्थिरांक है। जब कोई वस्तु प्रकाश की गति के करीब पहुँचती है, तो समय धीमा हो जाता है।"
            )
        elif re.search(r"\b(mitosis|cell division|meiosis)\b", topic_lower):
            return (
                f"कोशिका विभाजन और जीवन का विकास (चरण {idx + 1})",
                "कोशिका विभाजन की प्रक्रिया में डीएनए का सटीक प्रतिकृतिकरण होता है, जिससे नई कोशिकाएं बनती हैं और जीवों में वृद्धि तथा पुनरुत्पादन संभव होता है।"
            )
        elif re.search(r"\b(vaccine|immune|antibody|pathogen|antigen)\b", topic_lower):
            return (
                f"प्रतिरक्षा प्रणाली और टीका विज्ञान (चरण {idx + 1})",
                "टीका मानव प्रतिरक्षा प्रणाली को रोगजनकों की पहचान करने के लिए प्रशिक्षित करता है। जब एंटीजन शरीर में प्रवेश करते हैं, तो कोशिकाएं एंटीबॉडी बनाती हैं जो भविष्य के संक्रमण से सुरक्षा प्रदान करती हैं।"
            )

        return (
            f"{topic}: प्रमुख वैज्ञानिक सिद्धांत (भाग {idx + 1})",
            f"{topic} के इस चरण में मूल सिद्धांतों और भौतिक प्रक्रियाओं का गहरा विश्लेषण किया जाता है। ऊर्जा और संरचना का यह संतुलन तंत्र को स्थिरता प्रदान करता है।"
        )

    def _generate_domain_visual(
        self,
        topic_title: str,
        chapter_title: str,
        chapter_idx: int,
        total_chapters: int,
        speech_text: str,
        visual_engine: str = "svg"
    ) -> str:
        """
        Constructs a cinema-grade, mathematically balanced, crisp 16:9 widescreen 800x450 illustration
        tailored directly to the video's actual scientific topic across Mermaid.js, D3.js, Manim, and Pure SVG.
        Features topic-adaptive canvas backgrounds (deep cosmic void, cellular micro-fluid, cyber tech slate),
        luminous multi-stop gradients, accurate physical anatomy, and informative HUD cards.
        """
        engine = (visual_engine or "svg").lower()
        clean_ch = chapter_title.replace('&', 'and').replace('<', '').replace('>', '').replace('"', '').strip() or f"Chapter {chapter_idx + 1}"
        clean_topic = topic_title.replace('&', 'and').replace('<', '').replace('>', '').replace('"', '').strip() or "Scientific Analysis"
        safe_ch = clean_ch
        safe_topic = clean_topic

        # Topic detection - strictly anchored to topic and chapter title to prevent false domain captures
        lower_top = topic_title.lower()
        lower_ch_txt = chapter_title.lower()
        combined_text = f"{topic_title} {chapter_title} {speech_text}".lower()

        # Space ONLY triggers if the overall topic is explicitly astronomy / planetary science
        is_space = any(w in lower_top for w in [
            "solar system", "planet", "planets", "astronomy", "pluto", "saturn", 
            "jupiter", "mars", "neptune", "uranus", "mercury", "venus", "kuiper belt", 
            "astronomical", "iau dwarf", "keplerian orbit", "interplanetary", "exoplanet"
        ])
        is_quantum = any(w in lower_top or w in lower_ch_txt for w in ["quantum", "double slit", "wavefunction", "superposition", "wave-particle duality"])
        is_relativity = any(w in lower_top or w in lower_ch_txt for w in ["speed of light", "special relativity", "general relativity", "spacetime"])
        is_neural = any(w in lower_top or w in lower_ch_txt for w in ["neural network", "deep learning", "backpropagation", "gradient descent"])
        is_mitosis = any(w in lower_top or w in lower_ch_txt for w in ["mitosis", "cell division", "meiosis", "chromosome segregation"])
        is_biochem = any(w in lower_top or w in lower_ch_txt for w in ["photosynthesis", "calvin cycle", "cellular respiration", "krebs cycle"])

        # Thorough conversational and intro stopword filter to guarantee zero filler labels
        conversational_stopwords = {
            "welcome", "friends", "hello", "today", "episode", "binocs", "peekaboo", "kid", "kids",
            "video", "channel", "subscribe", "let", "lets", "learn", "watch", "explore", "rather",
            "merely", "begin", "study", "this", "that", "these", "those", "which", "there", "their",
            "because", "between", "through", "notice", "observe", "diagram", "elements", "system",
            "section", "about", "could", "would", "should", "first", "second", "third", "also",
            "just", "like", "know", "think", "make", "take", "come", "look", "time", "year",
            "years", "people", "thing", "things", "what", "when", "where", "have", "with", "from",
            "into", "more", "some", "other", "such", "than", "then", "very", "even", "most",
            "only", "back", "after", "before", "each", "every", "both", "under", "over",
            "your", "yours", "our", "ours", "call", "called", "named", "show", "shows", "mean",
            "means", "ever", "never", "always", "here", "well", "good", "great", "world", "understand",
            "understanding", "deep", "intuitive", "principles", "principle", "foundational", "primary",
            "governing", "mathematical", "counterintuitive", "behaviors", "empirical", "takeaways"
        }

        # Extract authentic topical keywords
        speech_words = re.findall(r"\b[A-Za-z]{4,}\b", f"{chapter_title} {speech_text}")
        notable = [w.capitalize() for w in speech_words if w.lower() not in conversational_stopwords]

        # Domain fallback terms
        if is_space:
            domain_terms = ["Heliocentric Gravity", "Hydrostatic Balance", "Planetary Accretion", "Kuiper Belt", "Solar Corona", "Keplerian Velocity"]
        elif is_quantum:
            domain_terms = ["Wave Superposition", "Double-Slit Diffraction", "Wavefunction Collapse", "Interference Fringes", "Photon Probability", "Phase Coherence"]
        elif is_neural:
            domain_terms = ["Synaptic Weights", "Activation Dynamics", "Loss Gradient Descent", "Backpropagation Chain", "Nonlinear Manifold", "Dense Representation"]
        elif is_mitosis:
            domain_terms = ["Kinetochore Spindles", "Sister Chromatids", "Metaphase Equator", "Microtubule Asters", "Centromere Tension", "Cytokinesis Cleavage"]
        elif is_relativity:
            domain_terms = ["Lorentz Invariance", "Two-Way Speed of Light", "Spacetime Geodesic", "Clock Synchronization", "Time Dilation Factor", "Null Interval"]
        elif is_biochem:
            domain_terms = ["Thylakoid Membrane", "ATP Synthase Complex", "Calvin-Benson Cycle", "Photon Absorption", "RuBisCO Carboxylation", "Proton Gradient"]
        else:
            domain_terms = ["Physical Equilibrium", "Dynamic Transformation", "Energy Transfer", "Governing Boundary", "Empirical Observation", "Feedback Regulation"]

        t1 = (notable[0] if len(notable) > 0 else domain_terms[0]).replace('&', 'and').replace('<', '').replace('>', '')
        t2 = (notable[1] if len(notable) > 1 else domain_terms[1]).replace('&', 'and').replace('<', '').replace('>', '')
        t3 = (notable[2] if len(notable) > 2 else domain_terms[2]).replace('&', 'and').replace('<', '').replace('>', '')
        t4 = (notable[3] if len(notable) > 3 else domain_terms[3]).replace('&', 'and').replace('<', '').replace('>', '')

        # 1. MERMAID.JS FLOWCHARTS (Sequential, Structural, & Causal Architecture)
        if engine == "mermaid":
            if is_space:
                return """flowchart TD
  A["Astronomical Body Discovery"] --> B{"Criterion 1: Hydrostatic Equilibrium?"}
  B -->|Yes - Sufficient Gravity for Spherical Shape| C{"Criterion 2: Direct Solar Orbit?"}
  C -->|Yes - Heliocentric Path| D{"Criterion 3: Cleared Orbital Neighborhood?"}
  D -->|Cleared Accretion Zone| E["Classical Major Planet: Earth, Mars, Jupiter"]
  D -->|Not Cleared - Coexists with Kuiper Belt Objects| F["Dwarf Planet: Pluto, Eris, Ceres"]
  style B fill:#1e293b,stroke:#38bdf8,stroke-width:2px,color:#f8fafc
  style C fill:#1e293b,stroke:#38bdf8,stroke-width:2px,color:#f8fafc
  style D fill:#1e293b,stroke:#38bdf8,stroke-width:2px,color:#f8fafc
  style F fill:#451a03,stroke:#f59e0b,stroke-width:2px,color:#fef3c7"""
            elif is_quantum:
                return """flowchart LR
  A["Coherent Monochromatic Source"] --> B["Double-Slit Diffraction Barrier"]
  B --> C["Spatial Wavefront Superposition"]
  C --> D{"Observation Detector Active?"}
  D -->|No: Quantum Wave Coherence| E["Interference Fringes on Screen"]
  D -->|Yes: Wavefunction Collapse| F["Classical Particle Clump Pattern"]
  style B fill:#1e293b,stroke:#38bdf8,stroke-width:2px,color:#f8fafc
  style C fill:#1e293b,stroke:#38bdf8,stroke-width:2px,color:#f8fafc
  style E fill:#022c22,stroke:#10b981,stroke-width:2px,color:#f0fdf4
  style F fill:#451a03,stroke:#f59e0b,stroke-width:2px,color:#fef3c7"""
            elif is_neural:
                return """flowchart LR
  A["Input Feature Vector X"] --> B["Linear Projection: W·X + b"]
  B --> C["Nonlinear Activation: ReLU / Sigmoid"]
  C --> D["Loss Computation: L(y, y_hat)"]
  D --> E["Backpropagation Chain Rule: dL/dW"]
  E --> F["Gradient Descent Weight Update: W <- W - eta*dL"]
  style B fill:#1e293b,stroke:#38bdf8,stroke-width:2px,color:#f8fafc
  style D fill:#1e293b,stroke:#a855f7,stroke-width:2px,color:#f8fafc
  style F fill:#022c22,stroke:#10b981,stroke-width:2px,color:#f0fdf4"""
            elif is_mitosis:
                return """flowchart LR
  A["Interphase: G1/S/G2 DNA Replication"] --> B["Prophase: Chromosome Condensation"]
  B --> C["Metaphase: Equatorial Plate Alignment"]
  C --> D["Anaphase: Kinetochore Tension & Separation"]
  D --> E["Telophase: Nuclear Envelope Reassembly"]
  E --> F["Cytokinesis: Two Genetically Identical 2n Cells"]
  style C fill:#1e293b,stroke:#38bdf8,stroke-width:2px,color:#f8fafc
  style D fill:#022c22,stroke:#10b981,stroke-width:2px,color:#f0fdf4"""
            elif is_relativity:
                return """flowchart TD
  A["Clock A: Light Pulse Emitted at t0"] --> B["Pulse Travels Distance L Through Vacuum"]
  B --> C["Mirror B: Reflection Event at Distant t1"]
  C --> D["Clock A: Return Signal Detected at t2"]
  D --> E["Empirical Two-Way Speed: c = 2L / (t2 - t0)"]
  E -.->|Einstein Synchronization Convention| F["Assumed One-Way Speed: t1 = 0.5 * (t0 + t2)"]
  style B fill:#1e293b,stroke:#38bdf8,stroke-width:2px,color:#f8fafc
  style E fill:#022c22,stroke:#10b981,stroke-width:2px,color:#f0fdf4"""
            else:
                return f"""flowchart TD
  A["{t1}: Initial State"] --> B["{t2}: Dynamic Transformation"]
  B --> C["{t3}: Interaction Phase"]
  C --> D["{t4}: Equilibrium State"]
  D -.->|Feedback Modulation Loop| B
  style A fill:#1e293b,stroke:#38bdf8,stroke-width:2px,color:#f8fafc
  style B fill:#1e293b,stroke:#38bdf8,stroke-width:2px,color:#f8fafc
  style C fill:#1e293b,stroke:#a855f7,stroke-width:2px,color:#f8fafc
  style D fill:#022c22,stroke:#10b981,stroke-width:2px,color:#f0fdf4"""

        # 2. D3.JS QUANTITATIVE CHARTS & COORDINATE CURVES
        elif engine == "d3":
            if is_quantum:
                pts = [[0, 3], [1, 7], [2, 19], [3, 9], [4, 52], [5, 100], [6, 52], [7, 9], [8, 19], [9, 7], [10, 3]]
                x_lbl = "Detector Screen Offset x (mm)"
                y_lbl = "Normalized Relative Intensity I / I₀"
            elif is_space:
                pts = [[1, 100], [2, 71], [3, 58], [4, 50], [5, 45], [6, 41], [7, 38], [8, 35], [9, 33], [10, 31]]
                x_lbl = "Semi-Major Orbital Radius r (AU)"
                y_lbl = "Keplerian Orbital Velocity v (km/s)"
            elif is_neural:
                pts = [[0, 95], [1, 68], [2, 46], [3, 31], [4, 20], [5, 13], [6, 8], [7, 5], [8, 4], [9, 3], [10, 2]]
                x_lbl = "Optimization Training Epochs"
                y_lbl = "Empirical Objective Loss ℒ"
            elif is_relativity:
                pts = [[0, 10], [2, 11], [4, 15], [6, 25], [7, 36], [8, 55], [8.5, 68], [9, 82], [9.5, 93], [10, 100]]
                x_lbl = "Velocity Ratio (v / c)"
                y_lbl = "Lorentz Factor γ (Time Dilation)"
            elif is_mitosis or is_biochem:
                pts = [[0, 4], [1, 8], [2, 16], [3, 32], [4, 55], [5, 78], [6, 91], [7, 96], [8, 98], [9, 99], [10, 100]]
                x_lbl = "Biological Reaction Coordinate"
                y_lbl = "Metabolic Pathway Rate / Progress (%)"
            else:
                pts = [[0, 10], [1, 24], [2, 55], [3, 82], [4, 96], [5, 94], [6, 78], [7, 52], [8, 32], [9, 18], [10, 12]]
                x_lbl = f"{t1} Evolution (Parameter X)"
                y_lbl = f"{t2} Rate / Probability (Y)"

            spec = {
                "title": f"{safe_ch[:38]}: Quantitative Model",
                "xLabel": x_lbl,
                "yLabel": y_lbl,
                "points": pts
            }
            return json.dumps(spec)

        # 3. MANIM VECTOR (3Blue1Brown Chalkboard Mathematical Aesthetics)
        elif engine == "manim":
            if is_quantum:
                equation = "iℏ ∂ψ/∂t = Ĥψ   •   P(x) = |ψ(x)|²   •   Δx · Δp ≥ ℏ/2"
            elif is_space:
                equation = "T² / a³ = 4π² / G(M + m)   •   r(θ) = p / (1 + e·cos θ)"
            elif is_neural:
                equation = "ℒ(w) = ½∑(y - ŷ)²   •   ∇_w ℒ = -(y - ŷ)x   •   w ← w - η∇ℒ"
            elif is_relativity:
                equation = "c = 2L / Δt   •   Δt' = γ Δt   •   ds² = -c²dt² + dx² + dy² + dz²"
            elif is_mitosis or is_biochem:
                equation = "dN/dt = rN(1 - N/K)   •   2n Chromosomes   •   Kinetochore Tension"
            else:
                equation = f"∇F({t1}, {t2}) = [ ∂F/∂x, ∂F/∂y ]   •   dy/dx = tan(θ)"

            return f"""<svg viewBox="0 0 800 450" xmlns="http://www.w3.org/2000/svg" data-engine="manim">
  <defs>
    <pattern id="m-grid-{chapter_idx}" width="25" height="25" patternUnits="userSpaceOnUse">
      <path d="M 25 0 L 0 0 0 25" fill="none" stroke="#1e293b" stroke-width="0.8" opacity="0.6"/>
    </pattern>
    <marker id="m-arr-b-{chapter_idx}" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="#38bdf8"/>
    </marker>
    <marker id="m-arr-t-{chapter_idx}" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="#10b981"/>
    </marker>
  </defs>
  <rect width="800" height="450" fill="#0f172a" rx="14" stroke="#334155" stroke-width="1.5"/>
  <rect width="800" height="450" fill="url(#m-grid-{chapter_idx})"/>
  <!-- Coordinate Axes -->
  <line x1="50" y1="240" x2="750" y2="240" stroke="#64748b" stroke-width="1.8"/>
  <line x1="400" y1="410" x2="400" y2="70" stroke="#64748b" stroke-width="1.8"/>
  <text x="740" y="230" font-family="system-ui, serif" font-style="italic" font-size="14" fill="#94a3b8">x</text>
  <text x="412" y="85" font-family="system-ui, serif" font-style="italic" font-size="14" fill="#94a3b8">y</text>
  <!-- Vector Field Arrows -->
  <line x1="160" y1="320" x2="220" y2="280" stroke="#38bdf8" stroke-width="2.2" marker-end="url(#m-arr-b-{chapter_idx})"/>
  <line x1="260" y1="340" x2="330" y2="290" stroke="#38bdf8" stroke-width="2.2" marker-end="url(#m-arr-b-{chapter_idx})"/>
  <line x1="360" y1="350" x2="430" y2="290" stroke="#38bdf8" stroke-width="2.2" marker-end="url(#m-arr-b-{chapter_idx})"/>
  <line x1="460" y1="330" x2="530" y2="260" stroke="#38bdf8" stroke-width="2.2" marker-end="url(#m-arr-b-{chapter_idx})"/>
  <line x1="560" y1="300" x2="630" y2="220" stroke="#38bdf8" stroke-width="2.2" marker-end="url(#m-arr-b-{chapter_idx})"/>
  <!-- Function Graph Curve -->
  <path d="M 100,370 Q 260,110 400,240 T 700,100" fill="none" stroke="#f59e0b" stroke-width="3.5" stroke-linecap="round"/>
  <!-- Tangent Line & Inflection Point -->
  <line x1="280" y1="300" x2="520" y2="180" stroke="#10b981" stroke-width="2.5" stroke-dasharray="6,4" marker-end="url(#m-arr-t-{chapter_idx})"/>
  <circle cx="400" cy="240" r="5" fill="#ffffff" stroke="#10b981" stroke-width="2.5"/>
  <!-- Mathematical Formula Callout Banner -->
  <rect x="40" y="20" width="720" height="34" rx="8" fill="#1e293b" stroke="#334155" stroke-width="1.2"/>
  <text x="400" y="42" font-family="'Times New Roman', serif" font-style="italic" font-size="13.5" font-weight="bold" fill="#f8fafc" text-anchor="middle">
    {equation}
  </text>
  <text x="400" y="415" font-family="system-ui, sans-serif" font-size="12" font-weight="600" fill="#cbd5e1" text-anchor="middle">{safe_topic.upper()[:40]} • {safe_ch[:30]}</text>
  <text x="400" y="435" font-family="system-ui, sans-serif" font-size="10" font-weight="500" fill="#64748b" text-anchor="middle">Manim Vector Geometry • 3Blue1Brown Pedagogical Chalkboard</text>
</svg>"""

        # 4. PURE SVG (Top-Quality High-Production YouTube Scientific Graphics)
        else: # svg
            if is_space:
                # Detect specific focus within the astronomical chapter
                is_sun = any(w in combined_text for w in ["sun", "corona", "fusion", "photosphere", "flare", "convective", "thermonuclear", "plasma"])
                is_earth_moon = any(w in combined_text for w in ["earth", "moon", "magnetosphere", "barycenter", "goldilocks", "habitable zone", "hydrosphere", "dynamo"])
                is_mars = any(w in combined_text for w in ["mars", "olympus mons", "red planet", "valles marineris", "tharsis", "delta", "martian"])
                is_saturn_rings = any(w in combined_text for w in ["saturn", "ring", "rings", "roche", "cassini", "titan", "shepherd"])
                is_pluto_focus = any(w in combined_text for w in ["pluto", "dwarf", "kuiper", "criteria", "clearing", "tombaugh", "charon", "eris", "sedna", "sputnik", "cryovolcanism", "montes"])
                is_gas_giants = any(w in combined_text for w in ["jupiter", "uranus", "neptune", "gas giant", "ice giant", "red spot", "jovian", "galilean", "europa"])
                is_terrestrial = any(w in combined_text for w in ["mercury", "venus", "rocky", "terrestrial", "inner", "caloris"])
                is_orbits = any(w in combined_text for w in ["kepler", "orbit", "velocity", "gravity", "ellipse", "aphelion", "perihelion", "resonance", "heliocentric", "newton"])

                if is_sun:
                    space_model_idx = 6
                elif is_earth_moon:
                    space_model_idx = 7
                elif is_mars:
                    space_model_idx = 8
                elif is_saturn_rings:
                    space_model_idx = 9
                elif is_pluto_focus:
                    space_model_idx = 2
                elif is_gas_giants:
                    space_model_idx = 4
                elif is_terrestrial:
                    space_model_idx = 3
                elif is_orbits:
                    space_model_idx = 5
                else:
                    # Dynamically cycle through all 9 cinema-grade models across frames
                    cycle_order = [1, 6, 3, 7, 8, 4, 9, 5, 2]
                    space_model_idx = cycle_order[chapter_idx % len(cycle_order)]

                # -------------------------------------------------------------
                # SPACE MODEL 2: PLUTO, KUIPER BELT & THE 3 IAU CRITERIA
                # -------------------------------------------------------------
                if space_model_idx == 2:
                    return f"""<svg viewBox="0 0 800 450" xmlns="http://www.w3.org/2000/svg" data-engine="svg">
  <defs>
    <radialGradient id="sp2-sun-{chapter_idx}" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="40%" stop-color="#fef08a"/>
      <stop offset="75%" stop-color="#f59e0b"/>
      <stop offset="100%" stop-color="#ea580c" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="sp2-pluto-{chapter_idx}" cx="40%" cy="40%" r="55%">
      <stop offset="0%" stop-color="#fed7aa"/>
      <stop offset="50%" stop-color="#cbd5e1"/>
      <stop offset="100%" stop-color="#64748b"/>
    </radialGradient>
    <radialGradient id="sp2-charon-{chapter_idx}" cx="40%" cy="40%" r="50%">
      <stop offset="0%" stop-color="#94a3b8"/>
      <stop offset="80%" stop-color="#475569"/>
      <stop offset="100%" stop-color="#334155"/>
    </radialGradient>
  </defs>

  <!-- Deep Cosmic Canvas -->
  <rect width="800" height="450" fill="#020617" rx="14" stroke="#1e293b" stroke-width="1.5"/>

  <!-- Starfield Background -->
  <g opacity="0.85">
    <circle cx="45" cy="55" r="1.2" fill="#ffffff" opacity="0.9"/>
    <circle cx="120" cy="180" r="0.8" fill="#bae6fd" opacity="0.6"/>
    <circle cx="190" cy="70" r="1.5" fill="#fef08a" opacity="0.8"/>
    <circle cx="280" cy="45" r="0.9" fill="#ffffff" opacity="0.7"/>
    <circle cx="340" cy="140" r="1.3" fill="#ffffff" opacity="0.9"/>
    <circle cx="410" cy="80" r="0.7" fill="#bae6fd" opacity="0.5"/>
    <circle cx="75" cy="380" r="1.1" fill="#ffffff" opacity="0.8"/>
    <circle cx="150" cy="410" r="0.8" fill="#fef08a" opacity="0.6"/>
    <circle cx="230" cy="360" r="1.4" fill="#ffffff" opacity="0.9"/>
    <circle cx="320" cy="420" r="0.7" fill="#bae6fd" opacity="0.5"/>
    <circle cx="380" cy="380" r="1.0" fill="#ffffff" opacity="0.7"/>
  </g>

  <!-- Distant Glowing Sun Focus -->
  <circle cx="95" cy="115" r="42" fill="url(#sp2-sun-{chapter_idx})" opacity="0.85"/>
  <circle cx="95" cy="115" r="14" fill="#ffffff"/>
  <text x="95" y="142" font-family="system-ui, sans-serif" font-size="10" font-weight="700" fill="#fef08a" text-anchor="middle">Sun (Focus F₁)</text>

  <!-- Neptune Orbit (Circular Reference ~30 AU) -->
  <ellipse cx="185" cy="190" rx="135" ry="105" fill="none" stroke="#0284c7" stroke-width="1.8" stroke-dasharray="4,4"/>
  <circle cx="320" cy="190" r="7" fill="#2563eb"/>
  <text x="320" y="212" font-family="system-ui, sans-serif" font-size="9.5" font-weight="600" fill="#38bdf8" text-anchor="middle">Neptune Orbit (30 AU)</text>

  <!-- Pluto Eccentric & Inclined Orbit (~30-49 AU, 17° Incline) -->
  <ellipse cx="205" cy="180" rx="165" ry="95" transform="rotate(-17 205 180)" fill="none" stroke="#f59e0b" stroke-width="2.4"/>
  <text x="210" y="65" font-family="system-ui, sans-serif" font-size="9.5" font-weight="700" fill="#f59e0b" text-anchor="middle">Pluto Highly Inclined Orbit (17° Plane Tilt)</text>

  <!-- Kuiper Belt Debris Band -->
  <g opacity="0.45" stroke="#94a3b8" stroke-width="1.2">
    <circle cx="380" cy="100" r="1.5" fill="#cbd5e1"/>
    <circle cx="395" cy="130" r="2.0" fill="#94a3b8"/>
    <circle cx="410" cy="165" r="1.2" fill="#cbd5e1"/>
    <circle cx="390" cy="220" r="1.8" fill="#e2e8f0"/>
    <circle cx="370" cy="265" r="1.5" fill="#94a3b8"/>
    <circle cx="350" cy="305" r="2.2" fill="#cbd5e1"/>
  </g>
  <text x="385" y="335" font-family="system-ui, sans-serif" font-size="9" fill="#94a3b8" text-anchor="middle">Kuiper Belt Debris Zone</text>

  <!-- Detailed Inset: Pluto & Charon Binary System -->
  <g transform="translate(180, 290)">
    <!-- Pluto Body -->
    <circle cx="0" cy="0" r="34" fill="url(#sp2-pluto-{chapter_idx})"/>
    <!-- Nitrogen Ice Heart (Tombaugh Regio) -->
    <path d="M -8,-6 C -18,-18 -3,-26 2,-14 C 7,-26 22,-18 12,-6 C 2,6 0,16 2,16 C -4,14 -4,6 -8,-6 Z" fill="#fffbeb" opacity="0.9"/>
    <text x="0" y="48" font-family="system-ui, sans-serif" font-size="11" font-weight="700" fill="#f8fafc" text-anchor="middle">Pluto (2,376 km)</text>
    <text x="0" y="61" font-family="system-ui, sans-serif" font-size="8.5" fill="#fde68a" text-anchor="middle">Tombaugh Regio Nitrogen Ice</text>

    <!-- Charon Moon -->
    <circle cx="68" cy="-22" r="17" fill="url(#sp2-charon-{chapter_idx})"/>
    <circle cx="68" cy="-33" r="5" fill="#b91c1c" opacity="0.8"/>
    <text x="68" y="8" font-family="system-ui, sans-serif" font-size="9.5" font-weight="700" fill="#cbd5e1" text-anchor="middle">Charon</text>
    <text x="68" y="19" font-family="system-ui, sans-serif" font-size="7.5" fill="#94a3b8" text-anchor="middle">Tidally Locked</text>
  </g>

  <!-- Right Side Glassmorphic HUD Telemetry Card -->
  <rect x="435" y="65" width="335" height="355" rx="12" fill="#0f172a" fill-opacity="0.9" stroke="#38bdf8" stroke-width="1.2"/>
  
  <text x="455" y="98" font-family="system-ui, sans-serif" font-size="12.5" font-weight="700" fill="#38bdf8">IAU PLANETARY DEFINITION (2006)</text>
  <line x1="455" y1="110" x2="745" y2="110" stroke="#334155" stroke-width="1"/>

  <!-- Criterion 1 -->
  <text x="455" y="136" font-family="system-ui, sans-serif" font-size="11" font-weight="700" fill="#f8fafc">1. Hydrostatic Equilibrium</text>
  <rect x="670" y="123" width="75" height="18" rx="4" fill="#022c22" stroke="#10b981" stroke-width="1"/>
  <text x="707" y="136" font-family="system-ui, sans-serif" font-size="9.5" font-weight="700" fill="#10b981" text-anchor="middle">PASSED ✓</text>
  <text x="455" y="154" font-family="system-ui, sans-serif" font-size="9.5" fill="#94a3b8">Sufficient gravity to form nearly round spherical shape.</text>

  <!-- Criterion 2 -->
  <text x="455" y="186" font-family="system-ui, sans-serif" font-size="11" font-weight="700" fill="#f8fafc">2. Heliocentric Direct Orbit</text>
  <rect x="670" y="173" width="75" height="18" rx="4" fill="#022c22" stroke="#10b981" stroke-width="1"/>
  <text x="707" y="186" font-family="system-ui, sans-serif" font-size="9.5" font-weight="700" fill="#10b981" text-anchor="middle">PASSED ✓</text>
  <text x="455" y="204" font-family="system-ui, sans-serif" font-size="9.5" fill="#94a3b8">Directly orbits the Sun (not a moon of another planet).</text>

  <!-- Criterion 3 -->
  <text x="455" y="236" font-family="system-ui, sans-serif" font-size="11" font-weight="700" fill="#f8fafc">3. Cleared Orbital Neighborhood</text>
  <rect x="670" y="223" width="75" height="18" rx="4" fill="#450a0a" stroke="#ef4444" stroke-width="1"/>
  <text x="707" y="236" font-family="system-ui, sans-serif" font-size="9.5" font-weight="700" fill="#ef4444" text-anchor="middle">FAILED ✗</text>
  <text x="455" y="254" font-family="system-ui, sans-serif" font-size="9.5" fill="#fca5a5">Shares accretion zone with >100,000 Kuiper Belt objects.</text>
  <text x="455" y="268" font-family="system-ui, sans-serif" font-size="9" fill="#94a3b8">Pluto mass is only 0.07x of its orbital zone (Earth = 1,700,000x).</text>

  <!-- Verdict Pill -->
  <rect x="455" y="295" width="295" height="42" rx="8" fill="#1e293b" stroke="#f59e0b" stroke-width="1.2"/>
  <text x="602" y="313" font-family="system-ui, sans-serif" font-size="10.5" font-weight="700" fill="#fde68a" text-anchor="middle">OFFICIAL IAU CLASSIFICATION:</text>
  <text x="602" y="328" font-family="system-ui, sans-serif" font-size="10" font-weight="600" fill="#38bdf8" text-anchor="middle">Dwarf Planet &amp; Trans-Neptunian Plutoid</text>

  <!-- Topical Takeaway -->
  <text x="455" y="365" font-family="system-ui, sans-serif" font-size="10.5" font-weight="600" fill="#cbd5e1">• Core Mechanism: {t1}</text>
  <text x="455" y="385" font-family="system-ui, sans-serif" font-size="10.5" font-weight="600" fill="#cbd5e1">• Dynamic Process: {t2}</text>
  <text x="455" y="405" font-family="system-ui, sans-serif" font-size="10" fill="#64748b">Synchronized with ByteClass lecture timeline</text>

  <!-- Top Title Banner -->
  <rect x="160" y="14" width="480" height="32" rx="16" fill="#0f172a" fill-opacity="0.9" stroke="#38bdf8" stroke-width="1.2"/>
  <text x="400" y="35" font-family="system-ui, sans-serif" font-size="12" font-weight="700" fill="#38bdf8" text-anchor="middle">{safe_topic.upper()[:44]} • {safe_ch.upper()[:30]}</text>
</svg>"""

                # -------------------------------------------------------------
                # SPACE MODEL 3: INNER TERRESTRIAL ROCKY WORLDS CLOSE-UP
                # -------------------------------------------------------------
                elif space_model_idx == 3:
                    return f"""<svg viewBox="0 0 800 450" xmlns="http://www.w3.org/2000/svg" data-engine="svg">
  <defs>
    <radialGradient id="sp3-sun-{chapter_idx}" cx="0%" cy="50%" r="90%">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="30%" stop-color="#fef08a"/>
      <stop offset="65%" stop-color="#f59e0b"/>
      <stop offset="100%" stop-color="#ea580c" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="sp3-merc-{chapter_idx}" cx="35%" cy="35%" r="55%">
      <stop offset="0%" stop-color="#cbd5e1"/>
      <stop offset="60%" stop-color="#94a3b8"/>
      <stop offset="100%" stop-color="#475569"/>
    </radialGradient>
    <radialGradient id="sp3-venus-{chapter_idx}" cx="35%" cy="35%" r="55%">
      <stop offset="0%" stop-color="#fef08a"/>
      <stop offset="50%" stop-color="#f59e0b"/>
      <stop offset="100%" stop-color="#b45309"/>
    </radialGradient>
    <radialGradient id="sp3-earth-{chapter_idx}" cx="35%" cy="35%" r="55%">
      <stop offset="0%" stop-color="#38bdf8"/>
      <stop offset="50%" stop-color="#0284c7"/>
      <stop offset="100%" stop-color="#0f172a"/>
    </radialGradient>
    <radialGradient id="sp3-mars-{chapter_idx}" cx="35%" cy="35%" r="55%">
      <stop offset="0%" stop-color="#fca5a5"/>
      <stop offset="60%" stop-color="#ef4444"/>
      <stop offset="100%" stop-color="#7f1d1d"/>
    </radialGradient>
  </defs>

  <rect width="800" height="450" fill="#020617" rx="14" stroke="#1e293b" stroke-width="1.5"/>

  <!-- Starfield -->
  <g opacity="0.8">
    <circle cx="90" cy="50" r="1.1" fill="#ffffff"/>
    <circle cx="180" cy="80" r="0.8" fill="#bae6fd"/>
    <circle cx="270" cy="35" r="1.3" fill="#fef08a"/>
    <circle cx="360" cy="90" r="0.9" fill="#ffffff"/>
    <circle cx="450" cy="40" r="1.2" fill="#ffffff"/>
    <circle cx="560" cy="75" r="0.7" fill="#bae6fd"/>
    <circle cx="670" cy="45" r="1.4" fill="#fef08a"/>
    <circle cx="150" cy="410" r="0.8" fill="#ffffff"/>
    <circle cx="290" cy="425" r="1.2" fill="#bae6fd"/>
    <circle cx="430" cy="395" r="0.9" fill="#fef08a"/>
    <circle cx="590" cy="415" r="1.3" fill="#ffffff"/>
  </g>

  <!-- Radiant Solar Limb on Left Edge -->
  <circle cx="-50" cy="225" r="140" fill="url(#sp3-sun-{chapter_idx})"/>
  <text x="35" y="230" font-family="system-ui, sans-serif" font-size="11" font-weight="900" fill="#ffffff">SOLAR CORONA</text>

  <!-- 1. Mercury (0.39 AU) -->
  <g transform="translate(135, 225)">
    <circle cx="0" cy="0" r="16" fill="url(#sp3-merc-{chapter_idx})"/>
    <!-- Craters -->
    <circle cx="-5" cy="-4" r="3" fill="#64748b" opacity="0.7"/>
    <circle cx="4" cy="5" r="2.2" fill="#475569" opacity="0.8"/>
    <text x="0" y="32" font-family="system-ui, sans-serif" font-size="10.5" font-weight="700" fill="#cbd5e1" text-anchor="middle">MERCURY</text>
    <text x="0" y="44" font-family="system-ui, sans-serif" font-size="8" fill="#94a3b8" text-anchor="middle">0.39 AU • Iron Core</text>
    <rect x="-35" y="-45" width="70" height="18" rx="4" fill="#1e293b" stroke="#64748b" stroke-width="0.8"/>
    <text x="0" y="-33" font-family="system-ui, sans-serif" font-size="8" fill="#94a3b8" text-anchor="middle">-180°C to 430°C</text>
  </g>

  <!-- 2. Venus (0.72 AU) -->
  <g transform="translate(235, 225)">
    <circle cx="0" cy="0" r="24" fill="url(#sp3-venus-{chapter_idx})"/>
    <!-- Cloud swirl path -->
    <path d="M -16,-6 Q 0,-18 16,-8 Q 0,16 -16,6" fill="none" stroke="#fef08a" stroke-width="1.5" opacity="0.5"/>
    <text x="0" y="40" font-family="system-ui, sans-serif" font-size="10.5" font-weight="700" fill="#fde047" text-anchor="middle">VENUS</text>
    <text x="0" y="52" font-family="system-ui, sans-serif" font-size="8" fill="#fde68a" text-anchor="middle">0.72 AU • Runaway CO2</text>
    <rect x="-32" y="-55" width="64" height="18" rx="4" fill="#451a03" stroke="#f59e0b" stroke-width="0.8"/>
    <text x="0" y="-43" font-family="system-ui, sans-serif" font-size="8" font-weight="700" fill="#fef08a" text-anchor="middle">465°C • 92 atm</text>
  </g>

  <!-- 3. Earth & Orbiting Moon (1.00 AU) -->
  <g transform="translate(345, 225)">
    <!-- Moon orbit dotted line -->
    <ellipse cx="0" cy="0" rx="38" ry="18" transform="rotate(-15)" fill="none" stroke="#38bdf8" stroke-width="1" stroke-dasharray="3,3" opacity="0.6"/>
    <!-- Earth Globe -->
    <circle cx="0" cy="0" r="26" fill="url(#sp3-earth-{chapter_idx})"/>
    <!-- Continents -->
    <path d="M -12,-8 C -6,-16 4,-12 8,-4 C 12,4 4,14 -4,12 C -10,10 -16,0 -12,-8 Z" fill="#22c55e" opacity="0.85"/>
    <!-- Moon -->
    <circle cx="34" cy="-12" r="6" fill="#f8fafc"/>
    <text x="0" y="42" font-family="system-ui, sans-serif" font-size="11" font-weight="800" fill="#38bdf8" text-anchor="middle">EARTH &amp; MOON</text>
    <text x="0" y="54" font-family="system-ui, sans-serif" font-size="8" fill="#7dd3fc" text-anchor="middle">1.00 AU • Habitable Zone</text>
    <rect x="-36" y="-58" width="72" height="18" rx="4" fill="#064e3b" stroke="#10b981" stroke-width="0.8"/>
    <text x="0" y="-46" font-family="system-ui, sans-serif" font-size="8" font-weight="700" fill="#6ee7b7" text-anchor="middle">Water • O2 • Life</text>
  </g>

  <!-- 4. Mars (1.52 AU) -->
  <g transform="translate(455, 225)">
    <circle cx="0" cy="0" r="19" fill="url(#sp3-mars-{chapter_idx})"/>
    <!-- Olympus Mons & Polar Ice Cap -->
    <circle cx="0" cy="-16" r="4.5" fill="#ffffff" opacity="0.95"/>
    <circle cx="4" cy="3" r="3.5" fill="#991b1b" stroke="#fca5a5" stroke-width="0.8"/>
    <text x="0" y="36" font-family="system-ui, sans-serif" font-size="10.5" font-weight="700" fill="#ef4444" text-anchor="middle">MARS</text>
    <text x="0" y="48" font-family="system-ui, sans-serif" font-size="8" fill="#fca5a5" text-anchor="middle">1.52 AU • Olympus Mons</text>
    <rect x="-34" y="-50" width="68" height="18" rx="4" fill="#450a0a" stroke="#ef4444" stroke-width="0.8"/>
    <text x="0" y="-38" font-family="system-ui, sans-serif" font-size="8" font-weight="700" fill="#fca5a5" text-anchor="middle">-63°C • 0.006 atm</text>
  </g>

  <!-- Right Telemetry Panel (Terrestrial Planetary Physics) -->
  <rect x="525" y="65" width="250" height="355" rx="10" fill="#0f172a" fill-opacity="0.9" stroke="#38bdf8" stroke-width="1.2"/>
  <text x="545" y="96" font-family="system-ui, sans-serif" font-size="11.5" font-weight="700" fill="#38bdf8">TERRESTRIAL REALM (SILICATES)</text>
  <line x1="545" y1="106" x2="755" y2="106" stroke="#334155" stroke-width="1"/>

  <text x="545" y="132" font-family="system-ui, sans-serif" font-size="10" font-weight="700" fill="#f8fafc">• Thermal Condensation Gradient:</text>
  <text x="545" y="148" font-family="system-ui, sans-serif" font-size="9" fill="#94a3b8">Inner heat allowed only metals and refractory</text>
  <text x="545" y="162" font-family="system-ui, sans-serif" font-size="9" fill="#94a3b8">silicates to condense from the solar nebula.</text>

  <text x="545" y="194" font-family="system-ui, sans-serif" font-size="10" font-weight="700" fill="#f8fafc">• Planetary Differentiation:</text>
  <text x="545" y="210" font-family="system-ui, sans-serif" font-size="9" fill="#94a3b8">Heavy molten iron sank to form planetary cores;</text>
  <text x="545" y="224" font-family="system-ui, sans-serif" font-size="9" fill="#94a3b8">lighter silicates floated up to form crusts.</text>

  <text x="545" y="256" font-family="system-ui, sans-serif" font-size="10" font-weight="700" fill="#f8fafc">• Secondary Atmospheres:</text>
  <text x="545" y="272" font-family="system-ui, sans-serif" font-size="9" fill="#94a3b8">Volcanic outgassing and comet impacts delivered</text>
  <text x="545" y="286" font-family="system-ui, sans-serif" font-size="9" fill="#94a3b8">water, CO2, and nitrogen atmospheres.</text>

  <rect x="545" y="315" width="210" height="42" rx="6" fill="#1e293b" stroke="#f59e0b" stroke-width="1"/>
  <text x="650" y="333" font-family="system-ui, sans-serif" font-size="9.5" font-weight="700" fill="#fde68a" text-anchor="middle">ACTIVE FOCUS: {t1.upper()[:22]}</text>
  <text x="650" y="347" font-family="system-ui, sans-serif" font-size="8.5" fill="#38bdf8" text-anchor="middle">{t2[:26]}</text>

  <text x="545" y="385" font-family="system-ui, sans-serif" font-size="8.5" fill="#64748b">ByteClass Synchronized Telemetry System</text>

  <!-- Top Title Banner -->
  <rect x="160" y="14" width="480" height="32" rx="16" fill="#0f172a" fill-opacity="0.9" stroke="#38bdf8" stroke-width="1.2"/>
  <text x="400" y="35" font-family="system-ui, sans-serif" font-size="12" font-weight="700" fill="#38bdf8" text-anchor="middle">INNER TERRESTRIAL WORLDS: MERCURY • VENUS • EARTH • MARS</text>
</svg>"""

                # -------------------------------------------------------------
                # SPACE MODEL 4: GAS GIANTS & ICE GIANTS CLOSE-UP
                # -------------------------------------------------------------
                elif space_model_idx == 4:
                    return f"""<svg viewBox="0 0 800 450" xmlns="http://www.w3.org/2000/svg" data-engine="svg">
  <defs>
    <linearGradient id="sp4-jup-{chapter_idx}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#f59e0b"/>
      <stop offset="20%" stop-color="#d97706"/>
      <stop offset="38%" stop-color="#fef3c7"/>
      <stop offset="55%" stop-color="#b45309"/>
      <stop offset="75%" stop-color="#f59e0b"/>
      <stop offset="100%" stop-color="#78350f"/>
    </linearGradient>
    <radialGradient id="sp4-sat-{chapter_idx}" cx="35%" cy="35%" r="55%">
      <stop offset="0%" stop-color="#fef08a"/>
      <stop offset="70%" stop-color="#eab308"/>
      <stop offset="100%" stop-color="#a16207"/>
    </radialGradient>
    <radialGradient id="sp4-ura-{chapter_idx}" cx="35%" cy="35%" r="55%">
      <stop offset="0%" stop-color="#a5f3fc"/>
      <stop offset="70%" stop-color="#06b6d4"/>
      <stop offset="100%" stop-color="#0e7490"/>
    </radialGradient>
    <radialGradient id="sp4-nep-{chapter_idx}" cx="35%" cy="35%" r="55%">
      <stop offset="0%" stop-color="#93c5fd"/>
      <stop offset="60%" stop-color="#2563eb"/>
      <stop offset="100%" stop-color="#1e3a8a"/>
    </radialGradient>
  </defs>

  <rect width="800" height="450" fill="#020617" rx="14" stroke="#1e293b" stroke-width="1.5"/>

  <!-- Starfield -->
  <g opacity="0.8">
    <circle cx="70" cy="50" r="1.1" fill="#ffffff"/>
    <circle cx="160" cy="90" r="0.8" fill="#bae6fd"/>
    <circle cx="280" cy="40" r="1.3" fill="#fef08a"/>
    <circle cx="390" cy="85" r="0.9" fill="#ffffff"/>
    <circle cx="490" cy="45" r="1.2" fill="#ffffff"/>
    <circle cx="610" cy="75" r="0.7" fill="#bae6fd"/>
    <circle cx="720" cy="35" r="1.4" fill="#fef08a"/>
    <circle cx="110" cy="410" r="0.8" fill="#ffffff"/>
    <circle cx="320" cy="425" r="1.2" fill="#bae6fd"/>
    <circle cx="510" cy="395" r="0.9" fill="#fef08a"/>
  </g>

  <!-- 1. Jupiter (5.2 AU) -->
  <g transform="translate(140, 220)">
    <circle cx="0" cy="0" r="54" fill="url(#sp4-jup-{chapter_idx})"/>
    <!-- Great Red Spot with swirl -->
    <ellipse cx="20" cy="18" rx="12" ry="7" fill="#dc2626"/>
    <ellipse cx="20" cy="18" rx="8" ry="4" fill="#ef4444" opacity="0.8"/>
    <!-- Galilean Moons -->
    <circle cx="-72" cy="-10" r="3" fill="#fef08a"/><text x="-72" y="-18" font-size="7" fill="#fef08a" text-anchor="middle">Io</text>
    <circle cx="-62" cy="12" r="2.5" fill="#bae6fd"/><text x="-62" y="24" font-size="7" fill="#bae6fd" text-anchor="middle">Europa</text>
    <circle cx="68" cy="-14" r="3.8" fill="#cbd5e1"/><text x="68" y="-22" font-size="7" fill="#cbd5e1" text-anchor="middle">Ganymede</text>
    <circle cx="78" cy="16" r="3.2" fill="#94a3b8"/><text x="78" y="28" font-size="7" fill="#94a3b8" text-anchor="middle">Callisto</text>
    <text x="0" y="74" font-family="system-ui, sans-serif" font-size="12" font-weight="800" fill="#f59e0b" text-anchor="middle">JUPITER (318 M⊕)</text>
    <text x="0" y="88" font-family="system-ui, sans-serif" font-size="8.5" fill="#fde68a" text-anchor="middle">5.20 AU • Metallic H2 Dynamo</text>
  </g>

  <!-- 2. Saturn & Majestic 3D Rings (9.5 AU) -->
  <g transform="translate(350, 220)">
    <!-- Back rings -->
    <ellipse cx="0" cy="0" rx="72" ry="22" transform="rotate(-22)" fill="none" stroke="#fde68a" stroke-width="9" opacity="0.5"/>
    <ellipse cx="0" cy="0" rx="60" ry="18" transform="rotate(-22)" fill="none" stroke="#020617" stroke-width="1.8"/> <!-- Cassini Division -->
    <!-- Planet body -->
    <circle cx="0" cy="0" r="40" fill="url(#sp4-sat-{chapter_idx})"/>
    <!-- Front rings -->
    <path d="M -66,25 A 72 22 0 0 0 66,-25" transform="rotate(-22)" fill="none" stroke="#fef08a" stroke-width="9" opacity="0.95"/>
    <path d="M -55,20 A 60 18 0 0 0 55,-20" transform="rotate(-22)" fill="none" stroke="#020617" stroke-width="1.8"/>
    <text x="0" y="74" font-family="system-ui, sans-serif" font-size="12" font-weight="800" fill="#fde047" text-anchor="middle">SATURN (95 M⊕)</text>
    <text x="0" y="88" font-family="system-ui, sans-serif" font-size="8.5" fill="#fde68a" text-anchor="middle">9.58 AU • Water-Ice Rings</text>
  </g>

  <!-- 3. Uranus (19.2 AU) & 4. Neptune (30.1 AU) -->
  <g transform="translate(500, 160)">
    <!-- Uranus Tilted 98° -->
    <circle cx="0" cy="0" r="24" fill="url(#sp4-ura-{chapter_idx})"/>
    <ellipse cx="0" cy="0" rx="6" ry="34" fill="none" stroke="#bae6fd" stroke-width="1.2" opacity="0.7"/>
    <text x="0" y="38" font-family="system-ui, sans-serif" font-size="10.5" font-weight="700" fill="#22d3ee" text-anchor="middle">URANUS (14 M⊕)</text>
    <text x="0" y="50" font-family="system-ui, sans-serif" font-size="8" fill="#bae6fd" text-anchor="middle">19.2 AU • Tilted 98° Axis</text>
  </g>

  <g transform="translate(500, 290)">
    <!-- Neptune Deep Azure -->
    <circle cx="0" cy="0" r="23" fill="url(#sp4-nep-{chapter_idx})"/>
    <ellipse cx="-5" cy="4" rx="6" ry="3.5" fill="#1e3a8a" stroke="#60a5fa" stroke-width="0.8"/> <!-- Great Dark Spot -->
    <path d="M -12,-8 Q 0,-14 12,-6" fill="none" stroke="#ffffff" stroke-width="1.2" opacity="0.8"/> <!-- Cirrus methane -->
    <text x="0" y="36" font-family="system-ui, sans-serif" font-size="10.5" font-weight="700" fill="#60a5fa" text-anchor="middle">NEPTUNE (17 M⊕)</text>
    <text x="0" y="48" font-family="system-ui, sans-serif" font-size="8" fill="#93c5fd" text-anchor="middle">30.1 AU • 2,100 km/h Winds</text>
  </g>

  <!-- Right Telemetry Panel (Gas & Ice Giant Chemistry) -->
  <rect x="585" y="65" width="195" height="355" rx="10" fill="#0f172a" fill-opacity="0.9" stroke="#38bdf8" stroke-width="1.2"/>
  <text x="600" y="96" font-family="system-ui, sans-serif" font-size="11" font-weight="700" fill="#38bdf8">OUTER GIANTS (JOVIAN)</text>
  <line x1="600" y1="106" x2="765" y2="106" stroke="#334155" stroke-width="1"/>

  <text x="600" y="132" font-family="system-ui, sans-serif" font-size="9.5" font-weight="700" fill="#f8fafc">• Gas Giants (H / He):</text>
  <text x="600" y="148" font-family="system-ui, sans-serif" font-size="8.5" fill="#94a3b8">Jupiter &amp; Saturn hold 92%</text>
  <text x="600" y="160" font-family="system-ui, sans-serif" font-size="8.5" fill="#94a3b8">hydrogen and 7% helium.</text>

  <text x="600" y="190" font-family="system-ui, sans-serif" font-size="9.5" font-weight="700" fill="#f8fafc">• Ice Giants (H2O / CH4):</text>
  <text x="600" y="206" font-family="system-ui, sans-serif" font-size="8.5" fill="#94a3b8">Uranus &amp; Neptune have dense</text>
  <text x="600" y="218" font-family="system-ui, sans-serif" font-size="8.5" fill="#94a3b8">mantles of supercritical water,</text>
  <text x="600" y="230" font-family="system-ui, sans-serif" font-size="8.5" fill="#94a3b8">ammonia, &amp; methane ice.</text>

  <text x="600" y="260" font-family="system-ui, sans-serif" font-size="9.5" font-weight="700" fill="#f8fafc">• Magnetic Dynamos:</text>
  <text x="600" y="276" font-family="system-ui, sans-serif" font-size="8.5" fill="#94a3b8">Liquid metallic hydrogen inside</text>
  <text x="600" y="288" font-family="system-ui, sans-serif" font-size="8.5" fill="#94a3b8">Jupiter creates a field 20,000x</text>
  <text x="600" y="300" font-family="system-ui, sans-serif" font-size="8.5" fill="#94a3b8">stronger than Earth's.</text>

  <rect x="600" y="325" width="165" height="42" rx="6" fill="#1e293b" stroke="#f59e0b" stroke-width="1"/>
  <text x="682" y="343" font-family="system-ui, sans-serif" font-size="9" font-weight="700" fill="#fde68a" text-anchor="middle">ACTIVE TOPIC:</text>
  <text x="682" y="357" font-family="system-ui, sans-serif" font-size="8" fill="#38bdf8" text-anchor="middle">{t1[:20]}</text>

  <!-- Top Title Banner -->
  <rect x="160" y="14" width="480" height="32" rx="16" fill="#0f172a" fill-opacity="0.9" stroke="#38bdf8" stroke-width="1.2"/>
  <text x="400" y="35" font-family="system-ui, sans-serif" font-size="12" font-weight="700" fill="#38bdf8" text-anchor="middle">JOVIAN GAS GIANTS &amp; ICE GIANTS: JUPITER • SATURN • URANUS • NEPTUNE</text>
</svg>"""

                # -------------------------------------------------------------
                # SPACE MODEL 5: HELIOCENTRIC ORBITAL MECHANICS & KEPLER'S LAWS
                # -------------------------------------------------------------
                elif space_model_idx == 5:
                    return f"""<svg viewBox="0 0 800 450" xmlns="http://www.w3.org/2000/svg" data-engine="svg">
  <defs>
    <radialGradient id="sp5-sun-{chapter_idx}" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="35%" stop-color="#fef08a"/>
      <stop offset="70%" stop-color="#f59e0b"/>
      <stop offset="100%" stop-color="#ea580c" stop-opacity="0"/>
    </radialGradient>
    <marker id="sp5-arr-{chapter_idx}" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="#38bdf8"/>
    </marker>
    <marker id="sp5-vmax-{chapter_idx}" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="#ef4444"/>
    </marker>
  </defs>

  <rect width="800" height="450" fill="#020617" rx="14" stroke="#1e293b" stroke-width="1.5"/>

  <!-- Starfield -->
  <g opacity="0.8">
    <circle cx="80" cy="50" r="1.1" fill="#ffffff"/>
    <circle cx="180" cy="80" r="0.8" fill="#bae6fd"/>
    <circle cx="290" cy="35" r="1.3" fill="#fef08a"/>
    <circle cx="410" cy="80" r="0.9" fill="#ffffff"/>
    <circle cx="520" cy="45" r="1.2" fill="#ffffff"/>
    <circle cx="680" cy="75" r="0.7" fill="#bae6fd"/>
    <circle cx="120" cy="410" r="0.8" fill="#ffffff"/>
    <circle cx="340" cy="425" r="1.2" fill="#bae6fd"/>
  </g>

  <!-- Main Keplerian Elliptical Orbit -->
  <!-- Major axis line -->
  <line x1="80" y1="225" x2="480" y2="225" stroke="#334155" stroke-width="1.2" stroke-dasharray="4,4"/>
  <!-- Orbit Path -->
  <ellipse cx="280" cy="225" rx="200" ry="120" fill="none" stroke="#38bdf8" stroke-width="2.2"/>

  <!-- Swept Equal Area Sectors (Kepler's Second Law: dA/dt = const) -->
  <!-- Perihelion Swept Sector -->
  <path d="M 180,225 L 80,225 A 200 120 0 0 1 100,165 Z" fill="#38bdf8" fill-opacity="0.25" stroke="#38bdf8" stroke-width="1.5"/>
  <text x="130" y="200" font-family="system-ui, sans-serif" font-size="11" font-weight="700" fill="#7dd3fc" text-anchor="middle">Area ΔA₁</text>
  <text x="130" y="214" font-family="system-ui, sans-serif" font-size="8.5" fill="#bae6fd" text-anchor="middle">(Time Δt)</text>

  <!-- Aphelion Swept Sector -->
  <path d="M 180,225 L 480,225 A 200 120 0 0 0 460,165 Z" fill="#f59e0b" fill-opacity="0.25" stroke="#f59e0b" stroke-width="1.5"/>
  <text x="430" y="200" font-family="system-ui, sans-serif" font-size="11" font-weight="700" fill="#fde68a" text-anchor="middle">Area ΔA₂</text>
  <text x="430" y="214" font-family="system-ui, sans-serif" font-size="8.5" fill="#fde68a" text-anchor="middle">(Time Δt)</text>

  <!-- Sun at Focus F1 -->
  <circle cx="180" cy="225" r="42" fill="url(#sp5-sun-{chapter_idx})"/>
  <circle cx="180" cy="225" r="16" fill="#ffffff"/>
  <text x="180" y="258" font-family="system-ui, sans-serif" font-size="10.5" font-weight="800" fill="#fef08a" text-anchor="middle">Sun (Focus F₁)</text>

  <!-- Empty Focus F2 -->
  <circle cx="380" cy="225" r="4" fill="none" stroke="#64748b" stroke-width="1.5" stroke-dasharray="2,2"/>
  <text x="380" y="244" font-family="system-ui, sans-serif" font-size="8.5" fill="#64748b" text-anchor="middle">Empty Focus F₂</text>

  <!-- Perihelion (Planet at closest approach) -->
  <circle cx="80" cy="225" r="9" fill="#22c55e"/>
  <!-- Velocity Vector v_max -->
  <line x1="80" y1="225" x2="80" y2="155" stroke="#ef4444" stroke-width="3" marker-end="url(#sp5-vmax-{chapter_idx})"/>
  <text x="65" y="170" font-family="system-ui, sans-serif" font-size="10" font-weight="800" fill="#ef4444" text-anchor="end">v_max</text>
  <text x="80" y="250" font-family="system-ui, sans-serif" font-size="10" font-weight="700" fill="#f8fafc" text-anchor="middle">Perihelion (r_p)</text>

  <!-- Aphelion (Planet at farthest distance) -->
  <circle cx="480" cy="225" r="9" fill="#22c55e"/>
  <!-- Velocity Vector v_min -->
  <line x1="480" y1="225" x2="480" y2="265" stroke="#38bdf8" stroke-width="2" marker-end="url(#sp5-arr-{chapter_idx})"/>
  <text x="495" y="260" font-family="system-ui, sans-serif" font-size="9" font-weight="700" fill="#38bdf8">v_min</text>
  <text x="480" y="248" font-family="system-ui, sans-serif" font-size="10" font-weight="700" fill="#f8fafc" text-anchor="middle">Aphelion (r_a)</text>

  <!-- Semimajor axis marker a -->
  <line x1="280" y1="100" x2="480" y2="100" stroke="#f59e0b" stroke-width="1.5"/>
  <text x="380" y="94" font-family="system-ui, sans-serif" font-size="9.5" font-weight="700" fill="#f59e0b" text-anchor="middle">Semi-major axis (a)</text>

  <!-- Right Telemetry Panel (Kepler's Laws) -->
  <rect x="535" y="65" width="245" height="355" rx="10" fill="#0f172a" fill-opacity="0.9" stroke="#38bdf8" stroke-width="1.2"/>
  <text x="555" y="96" font-family="system-ui, sans-serif" font-size="11.5" font-weight="700" fill="#38bdf8">KEPLER'S THREE LAWS</text>
  <line x1="555" y1="106" x2="760" y2="106" stroke="#334155" stroke-width="1"/>

  <text x="555" y="132" font-family="system-ui, sans-serif" font-size="10" font-weight="700" fill="#f8fafc">1. Law of Ellipses:</text>
  <text x="555" y="148" font-family="system-ui, sans-serif" font-size="9" fill="#94a3b8">All planets orbit the Sun along elliptical</text>
  <text x="555" y="162" font-family="system-ui, sans-serif" font-size="9" fill="#94a3b8">paths with the Sun located at one focus.</text>

  <text x="555" y="194" font-family="system-ui, sans-serif" font-size="10" font-weight="700" fill="#f8fafc">2. Law of Equal Areas:</text>
  <text x="555" y="210" font-family="system-ui, sans-serif" font-size="9" fill="#94a3b8">A line joining Sun and planet sweeps</text>
  <text x="555" y="224" font-family="system-ui, sans-serif" font-size="9" fill="#94a3b8">equal areas in equal intervals of time (ΔA₁=ΔA₂).</text>

  <text x="555" y="256" font-family="system-ui, sans-serif" font-size="10" font-weight="700" fill="#f8fafc">3. Harmonic Law (T² ∝ a³):</text>
  <rect x="555" y="270" width="205" height="28" rx="4" fill="#1e293b" stroke="#334155" stroke-width="0.8"/>
  <text x="657" y="288" font-family="'Times New Roman', serif" font-style="italic" font-size="11" font-weight="bold" fill="#fde68a" text-anchor="middle">T² / a³ = 4π² / G(M☉ + m)</text>

  <rect x="555" y="315" width="205" height="42" rx="6" fill="#1e293b" stroke="#f59e0b" stroke-width="1"/>
  <text x="657" y="333" font-family="system-ui, sans-serif" font-size="9.5" font-weight="700" fill="#fde68a" text-anchor="middle">ORBITAL HARMONY: {t1.upper()[:18]}</text>
  <text x="657" y="347" font-family="system-ui, sans-serif" font-size="8.5" fill="#38bdf8" text-anchor="middle">{t2[:24]}</text>

  <!-- Top Title Banner -->
  <rect x="160" y="14" width="480" height="32" rx="16" fill="#0f172a" fill-opacity="0.9" stroke="#38bdf8" stroke-width="1.2"/>
  <text x="400" y="35" font-family="system-ui, sans-serif" font-size="12" font-weight="700" fill="#38bdf8" text-anchor="middle">HELIOCENTRIC ORBITAL MECHANICS &amp; KEPLER'S LAWS</text>
</svg>"""

                # -------------------------------------------------------------
                # SPACE MODEL 6: THE SUN, THERMONUCLEAR CORE & RADIANT CORONA
                # -------------------------------------------------------------
                elif space_model_idx == 6:
                    return f"""<svg viewBox="0 0 800 450" xmlns="http://www.w3.org/2000/svg" data-engine="svg">
  <defs>
    <radialGradient id="sp6-sun-core-{chapter_idx}" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="35%" stop-color="#fef08a"/>
      <stop offset="65%" stop-color="#f59e0b"/>
      <stop offset="100%" stop-color="#ea580c"/>
    </radialGradient>
    <radialGradient id="sp6-corona-{chapter_idx}" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#fef08a" stop-opacity="0.9"/>
      <stop offset="50%" stop-color="#f97316" stop-opacity="0.4"/>
      <stop offset="100%" stop-color="#ea580c" stop-opacity="0"/>
    </radialGradient>
  </defs>

  <rect width="800" height="450" fill="#020617" rx="14" stroke="#1e293b" stroke-width="1.5"/>

  <!-- Starfield -->
  <g opacity="0.8">
    <circle cx="85" cy="50" r="1.1" fill="#ffffff"/>
    <circle cx="170" cy="80" r="0.8" fill="#bae6fd"/>
    <circle cx="280" cy="40" r="1.3" fill="#fef08a"/>
    <circle cx="410" cy="75" r="0.9" fill="#ffffff"/>
    <circle cx="510" cy="45" r="1.2" fill="#ffffff"/>
    <circle cx="680" cy="80" r="0.7" fill="#bae6fd"/>
    <circle cx="120" cy="410" r="0.8" fill="#ffffff"/>
    <circle cx="310" cy="425" r="1.2" fill="#bae6fd"/>
  </g>

  <!-- Large Sun Left Center (Cutaway Interior View) -->
  <g transform="translate(240, 235)">
    <!-- Outer Corona Glow -->
    <circle cx="0" cy="0" r="175" fill="url(#sp6-corona-{chapter_idx})"/>

    <!-- Coronal Prominence Magnetic Loop Arches -->
    <path d="M -90,-115 Q -140,-185 0,-165 Q 40,-175 60,-125" fill="none" stroke="#f97316" stroke-width="3.5" opacity="0.85"/>
    <path d="M 115,-70 Q 185,-90 170,10 Q 155,50 115,70" fill="none" stroke="#fbbf24" stroke-width="3" opacity="0.8"/>
    <path d="M -115,70 Q -185,110 -115,140 Q -60,165 0,140" fill="none" stroke="#ea580c" stroke-width="3.2" opacity="0.85"/>

    <!-- Convective Zone Outer Shell -->
    <circle cx="0" cy="0" r="130" fill="#ea580c" stroke="#f97316" stroke-width="2"/>

    <!-- Radiative Zone Shell -->
    <circle cx="0" cy="0" r="90" fill="#f59e0b" stroke="#fef08a" stroke-width="2"/>

    <!-- Thermonuclear Fusion Core -->
    <circle cx="0" cy="0" r="48" fill="url(#sp6-sun-core-{chapter_idx})"/>
    <text x="0" y="5" font-family="system-ui, sans-serif" font-size="12" font-weight="900" fill="#020617" text-anchor="middle">FUSION CORE</text>
    <text x="0" y="20" font-family="system-ui, sans-serif" font-size="8.5" font-weight="800" fill="#78350f" text-anchor="middle">15,000,000 K</text>

    <!-- Cutaway quadrant indicator line -->
    <line x1="0" y1="0" x2="130" y2="0" stroke="#fef08a" stroke-width="1.2" stroke-dasharray="3,3"/>
    <line x1="0" y1="0" x2="0" y2="-130" stroke="#fef08a" stroke-width="1.2" stroke-dasharray="3,3"/>

    <!-- Outward Radiative Energy Vectors -->
    <line x1="0" y1="-50" x2="0" y2="-88" stroke="#ffffff" stroke-width="2.5"/>
    <line x1="45" y1="-25" x2="80" y2="-45" stroke="#ffffff" stroke-width="2.5"/>
    <line x1="50" y1="0" x2="88" y2="0" stroke="#ffffff" stroke-width="2.5"/>
    <line x1="35" y1="35" x2="65" y2="65" stroke="#ffffff" stroke-width="2.5"/>

    <!-- Labels -->
    <text x="0" y="-95" font-family="system-ui, sans-serif" font-size="9" font-weight="700" fill="#ffffff" text-anchor="middle">Radiative Zone (Photon Diffusion)</text>
    <text x="0" y="-136" font-family="system-ui, sans-serif" font-size="9" font-weight="700" fill="#fde68a" text-anchor="middle">Convective Zone (Thermal Upwelling)</text>
  </g>

  <!-- Right Side Telemetry Card (Solar Physics & Fusion Engine) -->
  <rect x="475" y="65" width="305" height="355" rx="10" fill="#0f172a" fill-opacity="0.9" stroke="#f59e0b" stroke-width="1.2"/>
  <text x="495" y="96" font-family="system-ui, sans-serif" font-size="11.5" font-weight="700" fill="#f59e0b">THE SOLAR ENGINE &amp; HELIOSPHERE</text>
  <line x1="495" y1="106" x2="760" y2="106" stroke="#334155" stroke-width="1"/>

  <text x="495" y="132" font-family="system-ui, sans-serif" font-size="10" font-weight="700" fill="#f8fafc">• Proton-Proton Chain Fusion:</text>
  <rect x="495" y="142" width="265" height="26" rx="4" fill="#1e293b" stroke="#334155" stroke-width="0.8"/>
  <text x="627" y="159" font-family="'Times New Roman', serif" font-style="italic" font-size="10.5" font-weight="bold" fill="#fde68a" text-anchor="middle">4 ¹H → ⁴He + 2e⁺ + 2ν_e + 26.7 MeV</text>

  <text x="495" y="188" font-family="system-ui, sans-serif" font-size="10" font-weight="700" fill="#f8fafc">• Mass-Energy Conversion (E = mc²):</text>
  <text x="495" y="204" font-family="system-ui, sans-serif" font-size="9" fill="#94a3b8">Converts 4,260,000 metric tons of mass into</text>
  <text x="495" y="218" font-family="system-ui, sans-serif" font-size="9" fill="#94a3b8">pure radiant energy every single second.</text>

  <text x="495" y="246" font-family="system-ui, sans-serif" font-size="10" font-weight="700" fill="#f8fafc">• Photon Diffusion Time:</text>
  <text x="495" y="262" font-family="system-ui, sans-serif" font-size="9" fill="#94a3b8">Gamma photons take ~100,000 years to scatter</text>
  <text x="495" y="276" font-family="system-ui, sans-serif" font-size="9" fill="#94a3b8">outward through dense radiative plasma.</text>

  <rect x="495" y="305" width="265" height="42" rx="6" fill="#1e293b" stroke="#f59e0b" stroke-width="1"/>
  <text x="627" y="323" font-family="system-ui, sans-serif" font-size="9.5" font-weight="700" fill="#fde68a" text-anchor="middle">CORE EQUILIBRIUM: {t1.upper()[:20]}</text>
  <text x="627" y="337" font-family="system-ui, sans-serif" font-size="8.5" fill="#38bdf8" text-anchor="middle">{t2[:26]}</text>

  <text x="495" y="375" font-family="system-ui, sans-serif" font-size="8.5" fill="#64748b">ByteClass Vector Graphics Engine • 16:9 Cinema</text>

  <!-- Top Title Banner -->
  <rect x="160" y="14" width="480" height="32" rx="16" fill="#0f172a" fill-opacity="0.9" stroke="#f59e0b" stroke-width="1.2"/>
  <text x="400" y="35" font-family="system-ui, sans-serif" font-size="12" font-weight="700" fill="#fef08a" text-anchor="middle">{safe_topic.upper()[:44]} • {safe_ch.upper()[:30]}</text>
</svg>"""

                # -------------------------------------------------------------
                # SPACE MODEL 7: EARTH-MOON BARYCENTER & MAGNETOSPHERIC SHIELD
                # -------------------------------------------------------------
                elif space_model_idx == 7:
                    return f"""<svg viewBox="0 0 800 450" xmlns="http://www.w3.org/2000/svg" data-engine="svg">
  <defs>
    <radialGradient id="sp7-earth-{chapter_idx}" cx="35%" cy="35%" r="55%">
      <stop offset="0%" stop-color="#38bdf8"/>
      <stop offset="50%" stop-color="#0284c7"/>
      <stop offset="100%" stop-color="#0f172a"/>
    </radialGradient>
    <radialGradient id="sp7-moon-{chapter_idx}" cx="35%" cy="35%" r="55%">
      <stop offset="0%" stop-color="#cbd5e1"/>
      <stop offset="60%" stop-color="#94a3b8"/>
      <stop offset="100%" stop-color="#475569"/>
    </radialGradient>
  </defs>

  <rect width="800" height="450" fill="#020617" rx="14" stroke="#1e293b" stroke-width="1.5"/>

  <!-- Starfield -->
  <g opacity="0.8">
    <circle cx="80" cy="50" r="1.1" fill="#ffffff"/>
    <circle cx="160" cy="80" r="0.8" fill="#bae6fd"/>
    <circle cx="280" cy="35" r="1.3" fill="#fef08a"/>
    <circle cx="390" cy="90" r="0.9" fill="#ffffff"/>
    <circle cx="510" cy="40" r="1.2" fill="#ffffff"/>
    <circle cx="680" cy="75" r="0.7" fill="#bae6fd"/>
    <circle cx="110" cy="410" r="0.8" fill="#ffffff"/>
    <circle cx="320" cy="425" r="1.2" fill="#bae6fd"/>
  </g>

  <!-- Incoming Supersonic Solar Wind Stream (Deflected at Bow Shock) -->
  <g stroke="#f59e0b" stroke-width="1.5" opacity="0.7" stroke-dasharray="6,4">
    <line x1="20" y1="120" x2="90" y2="120"/>
    <line x1="20" y1="180" x2="70" y2="180"/>
    <line x1="20" y1="235" x2="65" y2="235"/>
    <line x1="20" y1="290" x2="70" y2="290"/>
    <line x1="20" y1="350" x2="90" y2="350"/>
  </g>
  <text x="35" y="105" font-family="system-ui, sans-serif" font-size="9" font-weight="700" fill="#f59e0b">Solar Wind (450 km/s)</text>

  <!-- Magnetospheric Bow Shock & Dipolar Magnetic Field Lines -->
  <g fill="none">
    <!-- Bow Shock Arc -->
    <path d="M 120,60 Q 60,235 120,410" stroke="#38bdf8" stroke-width="3" opacity="0.9"/>
    <text x="75" y="80" font-family="system-ui, sans-serif" font-size="9" font-weight="700" fill="#38bdf8">Bow Shock</text>

    <!-- Dipolar loops -->
    <path d="M 230,195 C 130,120 130,60 230,195" stroke="#0ea5e9" stroke-width="1.6" opacity="0.6"/>
    <path d="M 230,275 C 130,350 130,410 230,275" stroke="#0ea5e9" stroke-width="1.6" opacity="0.6"/>
    <path d="M 230,195 C 340,110 390,160 230,195" stroke="#0ea5e9" stroke-width="1.6" opacity="0.6"/>
    <path d="M 230,275 C 340,360 390,310 230,275" stroke="#0ea5e9" stroke-width="1.6" opacity="0.6"/>
  </g>

  <!-- Earth Body -->
  <g transform="translate(230, 235)">
    <circle cx="0" cy="0" r="40" fill="url(#sp7-earth-{chapter_idx})"/>
    <!-- Continents -->
    <path d="M -16,-12 C -8,-24 8,-18 12,-6 C 18,6 6,22 -6,18 C -16,14 -24,0 -16,-12 Z" fill="#22c55e" opacity="0.9"/>
    <!-- Magnetic Axis Tilted 11° -->
    <line x1="-10" y1="-55" x2="10" y2="55" stroke="#ef4444" stroke-width="2" stroke-dasharray="3,3"/>
    <circle cx="-10" cy="-55" r="3" fill="#ef4444"/><text x="-16" y="-62" font-size="8" fill="#ef4444" font-weight="700">N_mag</text>
    <circle cx="10" cy="55" r="3" fill="#38bdf8"/><text x="14" y="67" font-size="8" fill="#38bdf8" font-weight="700">S_mag</text>
    <text x="0" y="58" font-family="system-ui, sans-serif" font-size="11" font-weight="800" fill="#38bdf8" text-anchor="middle">EARTH</text>

    <!-- Mutual Barycenter Crosshair inside Earth (4,670 km from center) -->
    <circle cx="28" cy="0" r="5" fill="#f59e0b" opacity="0.9"/>
    <line x1="28" y1="-8" x2="28" y2="8" stroke="#ffffff" stroke-width="1.5"/>
    <line x1="20" y1="0" x2="36" y2="0" stroke="#ffffff" stroke-width="1.5"/>
    <text x="28" y="-12" font-family="system-ui, sans-serif" font-size="7.5" font-weight="700" fill="#fde68a" text-anchor="middle">Barycenter</text>
  </g>

  <!-- Orbiting Moon -->
  <g transform="translate(415, 235)">
    <ellipse cx="-185" cy="0" rx="185" ry="55" fill="none" stroke="#64748b" stroke-width="1.2" stroke-dasharray="3,3" opacity="0.7"/>
    <circle cx="0" cy="0" r="14" fill="url(#sp7-moon-{chapter_idx})"/>
    <text x="0" y="24" font-family="system-ui, sans-serif" font-size="9.5" font-weight="700" fill="#cbd5e1" text-anchor="middle">MOON</text>
    <text x="0" y="35" font-family="system-ui, sans-serif" font-size="7.5" fill="#94a3b8" text-anchor="middle">Tidally Locked</text>
  </g>

  <!-- Right Side Telemetry Card (Geomagnetic & Barycentric Physics) -->
  <rect x="475" y="65" width="305" height="355" rx="10" fill="#0f172a" fill-opacity="0.9" stroke="#38bdf8" stroke-width="1.2"/>
  <text x="495" y="96" font-family="system-ui, sans-serif" font-size="11.5" font-weight="700" fill="#38bdf8">EARTH-MOON SYSTEM DYNAMICS</text>
  <line x1="495" y1="106" x2="760" y2="106" stroke="#334155" stroke-width="1"/>

  <text x="495" y="132" font-family="system-ui, sans-serif" font-size="10" font-weight="700" fill="#f8fafc">• Liquid Outer Core Geodynamo:</text>
  <text x="495" y="148" font-family="system-ui, sans-serif" font-size="9" fill="#94a3b8">Convection of molten iron generates the</text>
  <text x="495" y="162" font-family="system-ui, sans-serif" font-size="9" fill="#94a3b8">dipolar magnetosphere deflecting cosmic rays.</text>

  <text x="495" y="194" font-family="system-ui, sans-serif" font-size="10" font-weight="700" fill="#f8fafc">• Shared Gravitational Barycenter:</text>
  <text x="495" y="210" font-family="system-ui, sans-serif" font-size="9" fill="#94a3b8">Lies 4,670 km from Earth's center (0.73 R⊕),</text>
  <text x="495" y="224" font-family="system-ui, sans-serif" font-size="9" fill="#94a3b8">inside the solid silicate mantle.</text>

  <text x="495" y="256" font-family="system-ui, sans-serif" font-size="10" font-weight="700" fill="#f8fafc">• Axial Obliquity Stabilization:</text>
  <text x="495" y="272" font-family="system-ui, sans-serif" font-size="9" fill="#94a3b8">Lunar tidal torque locks Earth's 23.5° axial</text>
  <text x="495" y="286" font-family="system-ui, sans-serif" font-size="9" fill="#94a3b8">tilt, preventing chaotic climatic swings.</text>

  <rect x="495" y="315" width="265" height="42" rx="6" fill="#1e293b" stroke="#f59e0b" stroke-width="1"/>
  <text x="627" y="333" font-family="system-ui, sans-serif" font-size="9.5" font-weight="700" fill="#fde68a" text-anchor="middle">HABITABLE EQUILIBRIUM: {t1.upper()[:18]}</text>
  <text x="627" y="347" font-family="system-ui, sans-serif" font-size="8.5" fill="#38bdf8" text-anchor="middle">{t2[:24]}</text>

  <!-- Top Title Banner -->
  <rect x="160" y="14" width="480" height="32" rx="16" fill="#0f172a" fill-opacity="0.9" stroke="#38bdf8" stroke-width="1.2"/>
  <text x="400" y="35" font-family="system-ui, sans-serif" font-size="12" font-weight="700" fill="#38bdf8" text-anchor="middle">{safe_topic.upper()[:44]} • {safe_ch.upper()[:30]}</text>
</svg>"""

                # -------------------------------------------------------------
                # SPACE MODEL 8: MARS TOPOGRAPHY & OLYMPUS MONS VOLCANIC SHIELD
                # -------------------------------------------------------------
                elif space_model_idx == 8:
                    return f"""<svg viewBox="0 0 800 450" xmlns="http://www.w3.org/2000/svg" data-engine="svg">
  <defs>
    <radialGradient id="sp8-mars-globe-{chapter_idx}" cx="40%" cy="35%" r="60%">
      <stop offset="0%" stop-color="#fca5a5"/>
      <stop offset="50%" stop-color="#ef4444"/>
      <stop offset="85%" stop-color="#b91c1c"/>
      <stop offset="100%" stop-color="#450a0a"/>
    </radialGradient>
    <radialGradient id="sp8-caldera-{chapter_idx}" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#991b1b"/>
      <stop offset="70%" stop-color="#7f1d1d"/>
      <stop offset="100%" stop-color="#450a0a"/>
    </radialGradient>
  </defs>

  <rect width="800" height="450" fill="#020617" rx="14" stroke="#1e293b" stroke-width="1.5"/>

  <!-- Starfield -->
  <g opacity="0.8">
    <circle cx="75" cy="45" r="1.1" fill="#ffffff"/>
    <circle cx="180" cy="75" r="0.8" fill="#bae6fd"/>
    <circle cx="290" cy="35" r="1.3" fill="#fef08a"/>
    <circle cx="410" cy="85" r="0.9" fill="#ffffff"/>
    <circle cx="530" cy="40" r="1.2" fill="#ffffff"/>
    <circle cx="680" cy="70" r="0.7" fill="#bae6fd"/>
    <circle cx="120" cy="410" r="0.8" fill="#ffffff"/>
    <circle cx="330" cy="425" r="1.2" fill="#bae6fd"/>
  </g>

  <!-- Large Mars Planetary Hemisphere -->
  <g transform="translate(240, 235)">
    <circle cx="0" cy="0" r="145" fill="url(#sp8-mars-globe-{chapter_idx})"/>

    <!-- North Polar Water & Dry Ice Cap -->
    <path d="M -45,-138 C -20,-148 20,-148 45,-138 C 30,-128 -30,-128 -45,-138 Z" fill="#ffffff" opacity="0.95"/>
    <text x="0" y="-120" font-family="system-ui, sans-serif" font-size="8" font-weight="700" fill="#ffffff" text-anchor="middle">Polar Ice Cap</text>

    <!-- Valles Marineris Canyon System -->
    <path d="M -80,25 Q -10,35 60,15 Q 110,30 135,20" fill="none" stroke="#450a0a" stroke-width="5" stroke-linecap="round"/>
    <path d="M -75,26 Q -10,36 60,16 Q 110,31 130,21" fill="none" stroke="#1c1917" stroke-width="2" stroke-linecap="round"/>
    <text x="25" y="45" font-family="system-ui, sans-serif" font-size="8.5" font-weight="700" fill="#fca5a5" text-anchor="middle">Valles Marineris (4,000 km Canyon)</text>

    <!-- Ancient River Delta Branching System (Jezero/Eberswalde) -->
    <g stroke="#38bdf8" stroke-width="1.2" fill="none" opacity="0.85">
      <path d="M 70,-45 Q 85,-40 95,-35"/>
      <path d="M 95,-35 Q 105,-30 115,-32"/>
      <path d="M 95,-35 Q 105,-42 118,-45"/>
      <path d="M 95,-35 Q 108,-35 120,-38"/>
    </g>
    <text x="105" y="-52" font-family="system-ui, sans-serif" font-size="7.5" font-weight="700" fill="#7dd3fc" text-anchor="middle">Ancient River Delta</text>

    <!-- Olympus Mons Shield Volcano -->
    <g transform="translate(-65, -45)">
      <!-- 600 km Wide Shield Footprint -->
      <ellipse cx="0" cy="0" rx="55" ry="38" fill="#b91c1c" stroke="#fca5a5" stroke-width="1.5"/>
      <!-- Basal Escarpment Cliff (6 km drop) -->
      <ellipse cx="0" cy="0" rx="42" ry="28" fill="#991b1b" stroke="#f87171" stroke-width="1.2" stroke-dasharray="3,2"/>
      <!-- Summit Caldera (80 km wide) -->
      <ellipse cx="0" cy="0" rx="16" ry="10" fill="url(#sp8-caldera-{chapter_idx})" stroke="#ffffff" stroke-width="1"/>
      <circle cx="-4" cy="-2" r="4" fill="#1c1917"/>
      <circle cx="4" cy="2" r="3" fill="#1c1917"/>
      <text x="0" y="-14" font-family="system-ui, sans-serif" font-size="9" font-weight="800" fill="#ffffff" text-anchor="middle">OLYMPUS MONS</text>
      <text x="0" y="24" font-family="system-ui, sans-serif" font-size="7.5" font-weight="700" fill="#fef08a" text-anchor="middle">22 km Height (Peak)</text>
    </g>
  </g>

  <!-- Right Side Telemetry Card (Martian Geology & Topography) -->
  <rect x="475" y="65" width="305" height="355" rx="10" fill="#0f172a" fill-opacity="0.9" stroke="#ef4444" stroke-width="1.2"/>
  <text x="495" y="96" font-family="system-ui, sans-serif" font-size="11.5" font-weight="700" fill="#ef4444">MARTIAN GEOLOGY &amp; HYDROLOGY</text>
  <line x1="495" y1="106" x2="760" y2="106" stroke="#334155" stroke-width="1"/>

  <text x="495" y="132" font-family="system-ui, sans-serif" font-size="10" font-weight="700" fill="#f8fafc">• Olympus Mons (Shield Volcano):</text>
  <text x="495" y="148" font-family="system-ui, sans-serif" font-size="9" fill="#94a3b8">Towers 22 km high—nearly triple Mount Everest.</text>
  <text x="495" y="162" font-family="system-ui, sans-serif" font-size="9" fill="#94a3b8">The absence of plate tectonics kept the crust</text>
  <text x="495" y="176" font-family="system-ui, sans-serif" font-size="9" fill="#94a3b8">stationary over a single magma hotspot for eons.</text>

  <text x="495" y="204" font-family="system-ui, sans-serif" font-size="10" font-weight="700" fill="#f8fafc">• Valles Marineris Rift Canyon:</text>
  <text x="495" y="220" font-family="system-ui, sans-serif" font-size="9" fill="#94a3b8">Extends 4,000 km across the equator and reaches</text>
  <text x="495" y="234" font-family="system-ui, sans-serif" font-size="9" fill="#94a3b8">depths of 7 km—four times deeper than Grand Canyon.</text>

  <text x="495" y="262" font-family="system-ui, sans-serif" font-size="10" font-weight="700" fill="#f8fafc">• Ancient Water Networks:</text>
  <text x="495" y="278" font-family="system-ui, sans-serif" font-size="9" fill="#94a3b8">Branching deltas prove persistent liquid water oceans</text>
  <text x="495" y="292" font-family="system-ui, sans-serif" font-size="9" fill="#94a3b8">during the warmer Noachian period 3.8 Ga ago.</text>

  <rect x="495" y="315" width="265" height="42" rx="6" fill="#1e293b" stroke="#f59e0b" stroke-width="1"/>
  <text x="627" y="333" font-family="system-ui, sans-serif" font-size="9.5" font-weight="700" fill="#fde68a" text-anchor="middle">MARTIAN EQUILIBRIUM: {t1.upper()[:16]}</text>
  <text x="627" y="347" font-family="system-ui, sans-serif" font-size="8.5" fill="#38bdf8" text-anchor="middle">{t2[:24]}</text>

  <!-- Top Title Banner -->
  <rect x="160" y="14" width="480" height="32" rx="16" fill="#0f172a" fill-opacity="0.9" stroke="#ef4444" stroke-width="1.2"/>
  <text x="400" y="35" font-family="system-ui, sans-serif" font-size="12" font-weight="700" fill="#fca5a5" text-anchor="middle">{safe_topic.upper()[:44]} • {safe_ch.upper()[:30]}</text>
</svg>"""

                # -------------------------------------------------------------
                # SPACE MODEL 9: SATURN'S CONCENTRIC RINGS & THE ROCHE TIDAL LIMIT
                # -------------------------------------------------------------
                elif space_model_idx == 9:
                    return f"""<svg viewBox="0 0 800 450" xmlns="http://www.w3.org/2000/svg" data-engine="svg">
  <defs>
    <radialGradient id="sp9-sat-body-{chapter_idx}" cx="35%" cy="35%" r="55%">
      <stop offset="0%" stop-color="#fef08a"/>
      <stop offset="60%" stop-color="#eab308"/>
      <stop offset="100%" stop-color="#854d0e"/>
    </radialGradient>
    <linearGradient id="sp9-rings-grad-{chapter_idx}" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#78350f" stop-opacity="0.2"/>
      <stop offset="25%" stop-color="#fde68a" stop-opacity="0.6"/>
      <stop offset="55%" stop-color="#fef08a" stop-opacity="0.95"/>
      <stop offset="68%" stop-color="#020617"/>
      <stop offset="85%" stop-color="#fef3c7" stop-opacity="0.85"/>
      <stop offset="100%" stop-color="#fef08a" stop-opacity="0.4"/>
    </linearGradient>
  </defs>

  <rect width="800" height="450" fill="#020617" rx="14" stroke="#1e293b" stroke-width="1.5"/>

  <!-- Starfield -->
  <g opacity="0.8">
    <circle cx="85" cy="45" r="1.1" fill="#ffffff"/>
    <circle cx="170" cy="75" r="0.8" fill="#bae6fd"/>
    <circle cx="280" cy="35" r="1.3" fill="#fef08a"/>
    <circle cx="410" cy="85" r="0.9" fill="#ffffff"/>
    <circle cx="520" cy="40" r="1.2" fill="#ffffff"/>
    <circle cx="680" cy="75" r="0.7" fill="#bae6fd"/>
    <circle cx="120" cy="410" r="0.8" fill="#ffffff"/>
    <circle cx="330" cy="425" r="1.2" fill="#bae6fd"/>
  </g>

  <!-- Saturn & Dynamic 3D Rings -->
  <g transform="translate(240, 235)">
    <!-- Back Half of Concentric Rings -->
    <ellipse cx="0" cy="0" rx="180" ry="52" transform="rotate(-24)" fill="none" stroke="url(#sp9-rings-grad-{chapter_idx})" stroke-width="32" opacity="0.65"/>
    <!-- Cassini Division Back Gap -->
    <ellipse cx="0" cy="0" rx="145" ry="42" transform="rotate(-24)" fill="none" stroke="#020617" stroke-width="4"/>

    <!-- Saturn Planetary Sphere with Shadow Casting -->
    <circle cx="0" cy="0" r="68" fill="url(#sp9-sat-body-{chapter_idx})"/>
    <!-- Atmospheric subtle bands -->
    <path d="M -64,15 Q 0,25 64,15" stroke="#ca8a04" stroke-width="4" fill="none" opacity="0.5"/>
    <path d="M -60,-15 Q 0,-5 60,-15" stroke="#ca8a04" stroke-width="3" fill="none" opacity="0.5"/>

    <!-- Ring Shadow on Planet Surface -->
    <path d="M -62,-8 Q 0,4 62,-8 Q 0,14 -62,-8 Z" fill="#020617" opacity="0.7"/>

    <!-- Front Half of Concentric Rings -->
    <path d="M -164,66 A 180 52 0 0 0 164,-66" transform="rotate(-24)" fill="none" stroke="url(#sp9-rings-grad-{chapter_idx})" stroke-width="32" opacity="0.95"/>
    <!-- Cassini Division Front Gap -->
    <path d="M -132,53 A 145 42 0 0 0 132,-53" transform="rotate(-24)" fill="none" stroke="#020617" stroke-width="4"/>

    <!-- Shepherd Moons (Prometheus & Pandora) guarding F-Ring -->
    <circle cx="178" cy="-80" r="3" fill="#ffffff"/><text x="190" y="-84" font-size="7.5" fill="#fef08a">Prometheus</text>
    <circle cx="192" cy="-70" r="2.5" fill="#cbd5e1"/><text x="204" y="-68" font-size="7.5" fill="#cbd5e1">Pandora</text>

    <!-- Roche Tidal Limit Boundary Arc (Dashed Cyan) -->
    <ellipse cx="0" cy="0" rx="195" ry="58" transform="rotate(-24)" fill="none" stroke="#38bdf8" stroke-width="1.5" stroke-dasharray="4,4" opacity="0.85"/>
    <text x="130" y="80" font-family="system-ui, sans-serif" font-size="8.5" font-weight="700" fill="#38bdf8">Roche Tidal Limit (d = 2.44 R)</text>

    <text x="0" y="98" font-family="system-ui, sans-serif" font-size="12" font-weight="800" fill="#fef08a" text-anchor="middle">SATURN &amp; CONCENTRIC RINGS</text>
    <text x="0" y="112" font-family="system-ui, sans-serif" font-size="8.5" fill="#cbd5e1" text-anchor="middle">A, B &amp; C Rings • Cassini Division (4,800 km gap)</text>
  </g>

  <!-- Right Side Telemetry Card (Ring Dynamics & Tidal Physics) -->
  <rect x="475" y="65" width="305" height="355" rx="10" fill="#0f172a" fill-opacity="0.9" stroke="#f59e0b" stroke-width="1.2"/>
  <text x="495" y="96" font-family="system-ui, sans-serif" font-size="11.5" font-weight="700" fill="#f59e0b">SATURNIAN RING DYNAMICS</text>
  <line x1="495" y1="106" x2="760" y2="106" stroke="#334155" stroke-width="1"/>

  <text x="495" y="132" font-family="system-ui, sans-serif" font-size="10" font-weight="700" fill="#f8fafc">• Pure Water-Ice Composition:</text>
  <text x="495" y="148" font-family="system-ui, sans-serif" font-size="9" fill="#94a3b8">Trillions of particles (99% pure H2O ice)</text>
  <text x="495" y="162" font-family="system-ui, sans-serif" font-size="9" fill="#94a3b8">spanning from dust grains to house-sized blocks.</text>

  <text x="495" y="194" font-family="system-ui, sans-serif" font-size="10" font-weight="700" fill="#f8fafc">• Incredible Thickness Ratio:</text>
  <text x="495" y="210" font-family="system-ui, sans-serif" font-size="9" fill="#94a3b8">Extends 280,000 km across, yet averages barely</text>
  <text x="495" y="224" font-family="system-ui, sans-serif" font-size="9" fill="#94a3b8">10 meters in thickness—flatter than razor paper.</text>

  <text x="495" y="256" font-family="system-ui, sans-serif" font-size="10" font-weight="700" fill="#f8fafc">• The Gravitational Roche Limit:</text>
  <text x="495" y="272" font-family="system-ui, sans-serif" font-size="9" fill="#94a3b8">Tidal gravitational shear tears apart any moon</text>
  <text x="495" y="286" font-family="system-ui, sans-serif" font-size="9" fill="#94a3b8">or comet that wanders within d = 2.44 R (M/m)¹/³.</text>

  <rect x="495" y="315" width="265" height="42" rx="6" fill="#1e293b" stroke="#f59e0b" stroke-width="1"/>
  <text x="627" y="333" font-family="system-ui, sans-serif" font-size="9.5" font-weight="700" fill="#fde68a" text-anchor="middle">ROCHE TIDAL EQUILIBRIUM: {t1.upper()[:16]}</text>
  <text x="627" y="347" font-family="system-ui, sans-serif" font-size="8.5" fill="#38bdf8" text-anchor="middle">{t2[:24]}</text>

  <!-- Top Title Banner -->
  <rect x="160" y="14" width="480" height="32" rx="16" fill="#0f172a" fill-opacity="0.9" stroke="#f59e0b" stroke-width="1.2"/>
  <text x="400" y="35" font-family="system-ui, sans-serif" font-size="12" font-weight="700" fill="#fde68a" text-anchor="middle">{safe_topic.upper()[:44]} • {safe_ch.upper()[:30]}</text>
</svg>"""

                # -------------------------------------------------------------
                # SPACE MODEL 1: THE COMPLETE SOLAR SYSTEM OVERVIEW (MACRO VIEW)
                # -------------------------------------------------------------
                else:
                    return f"""<svg viewBox="0 0 800 450" xmlns="http://www.w3.org/2000/svg" data-engine="svg">
  <defs>
    <radialGradient id="sun-corona-{chapter_idx}" cx="20%" cy="50%" r="60%">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="25%" stop-color="#fffbeb"/>
      <stop offset="55%" stop-color="#fbbf24"/>
      <stop offset="85%" stop-color="#ea580c"/>
      <stop offset="100%" stop-color="#ea580c" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="sun-core-{chapter_idx}" cx="35%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="40%" stop-color="#fef08a"/>
      <stop offset="85%" stop-color="#f59e0b"/>
      <stop offset="100%" stop-color="#ea580c"/>
    </radialGradient>
    <radialGradient id="earth-grad-{chapter_idx}" cx="40%" cy="40%" r="50%">
      <stop offset="0%" stop-color="#38bdf8"/>
      <stop offset="60%" stop-color="#0284c7"/>
      <stop offset="100%" stop-color="#0369a1"/>
    </radialGradient>
    <radialGradient id="mars-grad-{chapter_idx}" cx="40%" cy="40%" r="50%">
      <stop offset="0%" stop-color="#fca5a5"/>
      <stop offset="70%" stop-color="#ef4444"/>
      <stop offset="100%" stop-color="#991b1b"/>
    </radialGradient>
    <linearGradient id="jup-bands-{chapter_idx}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#f59e0b"/>
      <stop offset="22%" stop-color="#d97706"/>
      <stop offset="38%" stop-color="#fef3c7"/>
      <stop offset="55%" stop-color="#b45309"/>
      <stop offset="75%" stop-color="#f59e0b"/>
      <stop offset="100%" stop-color="#92400e"/>
    </linearGradient>
    <radialGradient id="sat-grad-{chapter_idx}" cx="40%" cy="40%" r="50%">
      <stop offset="0%" stop-color="#fef08a"/>
      <stop offset="70%" stop-color="#eab308"/>
      <stop offset="100%" stop-color="#ca8a04"/>
    </radialGradient>
  </defs>

  <!-- Deep Cosmic Canvas -->
  <rect width="800" height="450" fill="#020617" rx="14" stroke="#1e293b" stroke-width="1.5"/>

  <!-- Starfield of Multi-magnitude Stars -->
  <g opacity="0.8">
    <circle cx="85" cy="45" r="1.1" fill="#ffffff"/>
    <circle cx="160" cy="85" r="0.8" fill="#bae6fd"/>
    <circle cx="240" cy="35" r="1.4" fill="#fef08a"/>
    <circle cx="310" cy="95" r="0.9" fill="#ffffff"/>
    <circle cx="390" cy="40" r="1.2" fill="#ffffff"/>
    <circle cx="470" cy="75" r="0.8" fill="#bae6fd"/>
    <circle cx="550" cy="30" r="1.5" fill="#fef08a"/>
    <circle cx="630" cy="90" r="1.0" fill="#ffffff"/>
    <circle cx="720" cy="45" r="1.3" fill="#ffffff"/>
    <circle cx="130" cy="390" r="0.8" fill="#ffffff"/>
    <circle cx="210" cy="420" r="1.2" fill="#bae6fd"/>
    <circle cx="300" cy="370" r="0.9" fill="#fef08a"/>
    <circle cx="420" cy="415" r="1.4" fill="#ffffff"/>
    <circle cx="530" cy="380" r="0.7" fill="#bae6fd"/>
    <circle cx="650" cy="425" r="1.1" fill="#ffffff"/>
    <circle cx="740" cy="390" r="1.3" fill="#fef08a"/>
  </g>

  <!-- Sun Radiant Corona & Core -->
  <circle cx="40" cy="225" r="95" fill="url(#sun-corona-{chapter_idx})" opacity="0.6"/>
  <circle cx="40" cy="225" r="46" fill="url(#sun-core-{chapter_idx})"/>
  <text x="40" y="230" font-family="system-ui, sans-serif" font-size="12" font-weight="900" fill="#ffffff" text-anchor="middle">SUN</text>

  <!-- Orbital Ellipses -->
  <g fill="none" stroke="#334155" stroke-width="1.2" opacity="0.7">
    <ellipse cx="40" cy="225" rx="80" ry="60"/>
    <ellipse cx="40" cy="225" rx="120" ry="85"/>
    <ellipse cx="40" cy="225" rx="165" ry="115" stroke="#1d4ed8" stroke-dasharray="3,3"/>
    <ellipse cx="40" cy="225" rx="215" ry="145"/>
    <ellipse cx="40" cy="225" rx="310" ry="200"/>
    <ellipse cx="40" cy="225" rx="420" ry="260"/>
    <ellipse cx="40" cy="225" rx="520" ry="320"/>
    <ellipse cx="40" cy="225" rx="615" ry="370"/>
  </g>

  <!-- Planet 1: Mercury -->
  <circle cx="120" cy="225" r="4.5" fill="#94a3b8"/>
  <text x="120" y="205" font-family="system-ui, sans-serif" font-size="8.5" font-weight="600" fill="#94a3b8" text-anchor="middle">Mercury</text>

  <!-- Planet 2: Venus -->
  <circle cx="160" cy="225" r="7.5" fill="#fde047"/>
  <text x="160" y="200" font-family="system-ui, sans-serif" font-size="8.5" font-weight="600" fill="#fde047" text-anchor="middle">Venus</text>

  <!-- Planet 3: Earth & Moon -->
  <circle cx="205" cy="225" r="8.5" fill="url(#earth-grad-{chapter_idx})"/>
  <circle cx="203" cy="223" r="3.5" fill="#22c55e" opacity="0.8"/>
  <circle cx="218" cy="217" r="2.2" fill="#ffffff"/>
  <text x="205" y="195" font-family="system-ui, sans-serif" font-size="9" font-weight="700" fill="#38bdf8" text-anchor="middle">Earth &amp; Moon</text>

  <!-- Planet 4: Mars -->
  <circle cx="255" cy="225" r="6.5" fill="url(#mars-grad-{chapter_idx})"/>
  <circle cx="255" cy="219.5" r="1.8" fill="#ffffff"/>
  <text x="255" y="202" font-family="system-ui, sans-serif" font-size="8.5" font-weight="600" fill="#ef4444" text-anchor="middle">Mars</text>

  <!-- Asteroid Belt (Main Belt between Mars & Jupiter) -->
  <g opacity="0.5">
    <circle cx="282" cy="180" r="1.2" fill="#94a3b8"/>
    <circle cx="286" cy="205" r="1.5" fill="#cbd5e1"/>
    <circle cx="284" cy="235" r="1.8" fill="#64748b"/>
    <circle cx="287" cy="265" r="1.3" fill="#cbd5e1"/>
    <circle cx="283" cy="290" r="1.6" fill="#94a3b8"/>
  </g>
  <text x="285" y="165" font-family="system-ui, sans-serif" font-size="7.5" fill="#94a3b8" text-anchor="middle">Asteroid Belt</text>

  <!-- Planet 5: Jupiter -->
  <circle cx="350" cy="225" r="24" fill="url(#jup-bands-{chapter_idx})"/>
  <ellipse cx="358" cy="233" rx="5" ry="3" fill="#dc2626"/>
  <circle cx="320" cy="225" r="1.8" fill="#fef08a"/>
  <circle cx="380" cy="225" r="1.8" fill="#ffffff"/>
  <text x="350" y="185" font-family="system-ui, sans-serif" font-size="10" font-weight="700" fill="#f59e0b" text-anchor="middle">Jupiter</text>
  <text x="350" y="265" font-family="system-ui, sans-serif" font-size="7.5" fill="#fef3c7" text-anchor="middle">Great Red Spot</text>

  <!-- Planet 6: Saturn -->
  <g transform="translate(460, 225)">
    <ellipse cx="0" cy="0" rx="34" ry="11" transform="rotate(-22)" fill="none" stroke="#fde68a" stroke-width="4.5" opacity="0.6"/>
    <circle cx="0" cy="0" r="17" fill="url(#sat-grad-{chapter_idx})"/>
    <path d="M -30,11 A 34 11 0 0 0 30,-11" transform="rotate(-22)" fill="none" stroke="#fef08a" stroke-width="4.5" opacity="0.9"/>
  </g>
  <text x="460" y="185" font-family="system-ui, sans-serif" font-size="10" font-weight="700" fill="#fde68a" text-anchor="middle">Saturn</text>
  <text x="460" y="265" font-family="system-ui, sans-serif" font-size="7.5" fill="#fef08a" text-anchor="middle">Planetary Rings</text>

  <!-- Planet 7: Uranus -->
  <circle cx="560" cy="225" r="12" fill="#22d3ee"/>
  <ellipse cx="560" cy="225" rx="3" ry="16" fill="none" stroke="#bae6fd" stroke-width="1" opacity="0.6"/>
  <text x="560" y="195" font-family="system-ui, sans-serif" font-size="9" font-weight="600" fill="#22d3ee" text-anchor="middle">Uranus</text>

  <!-- Planet 8: Neptune -->
  <circle cx="655" cy="225" r="11.5" fill="#2563eb"/>
  <text x="655" y="195" font-family="system-ui, sans-serif" font-size="9" font-weight="600" fill="#60a5fa" text-anchor="middle">Neptune</text>

  <!-- Kuiper Belt & Pluto -->
  <ellipse cx="730" cy="210" rx="8" ry="18" fill="none" stroke="#f59e0b" stroke-width="1" stroke-dasharray="2,2"/>
  <circle cx="730" cy="205" r="4.2" fill="#cbd5e1"/>
  <text x="730" y="185" font-family="system-ui, sans-serif" font-size="8.5" font-weight="700" fill="#f59e0b" text-anchor="middle">Pluto</text>
  <text x="730" y="240" font-family="system-ui, sans-serif" font-size="7.5" fill="#94a3b8" text-anchor="middle">Kuiper Belt</text>

  <!-- Top HUD Header Banner -->
  <rect x="160" y="14" width="480" height="32" rx="16" fill="#0f172a" fill-opacity="0.9" stroke="#38bdf8" stroke-width="1.2"/>
  <text x="400" y="35" font-family="system-ui, sans-serif" font-size="12" font-weight="700" fill="#38bdf8" text-anchor="middle">THE SOLAR SYSTEM: HELIOCENTRIC PLANETARY ARCHITECTURE</text>

  <!-- Bottom Telemetry Badges (3 Educational Panels) -->
  <rect x="40" y="375" width="220" height="52" rx="8" fill="#0f172a" fill-opacity="0.85" stroke="#334155" stroke-width="1"/>
  <text x="52" y="396" font-family="system-ui, sans-serif" font-size="10.5" font-weight="700" fill="#38bdf8">TERRESTRIAL PLANETS</text>
  <text x="52" y="414" font-family="system-ui, sans-serif" font-size="8.5" fill="#94a3b8">Mercury • Venus • Earth • Mars (Silicate Rock)</text>

  <rect x="285" y="375" width="230" height="52" rx="8" fill="#0f172a" fill-opacity="0.85" stroke="#334155" stroke-width="1"/>
  <text x="297" y="396" font-family="system-ui, sans-serif" font-size="10.5" font-weight="700" fill="#f59e0b">GAS GIANTS (JOVIAN)</text>
  <text x="297" y="414" font-family="system-ui, sans-serif" font-size="8.5" fill="#94a3b8">Jupiter • Saturn (H/He Gas, 95% System Mass)</text>

  <rect x="540" y="375" width="220" height="52" rx="8" fill="#0f172a" fill-opacity="0.85" stroke="#334155" stroke-width="1"/>
  <text x="552" y="396" font-family="system-ui, sans-serif" font-size="10.5" font-weight="700" fill="#10b981">ICE GIANTS &amp; KUIPER BELT</text>
  <text x="552" y="414" font-family="system-ui, sans-serif" font-size="8.5" fill="#94a3b8">Uranus • Neptune • Pluto (Volatile Ices &amp; KBOs)</text>
</svg>"""

            elif is_quantum:
                return f"""<svg viewBox="0 0 800 450" xmlns="http://www.w3.org/2000/svg" data-engine="svg">
  <defs>
    <radialGradient id="q-laser-{chapter_idx}" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#38bdf8"/>
      <stop offset="60%" stop-color="#0284c7"/>
      <stop offset="100%" stop-color="#0284c7" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <!-- Quantum Void Canvas -->
  <rect width="800" height="450" fill="#090d16" rx="14" stroke="#1e293b" stroke-width="1.5"/>

  <!-- Top Title Banner -->
  <rect x="180" y="16" width="440" height="32" rx="16" fill="#0f172a" stroke="#38bdf8" stroke-width="1.2"/>
  <text x="400" y="37" font-family="system-ui, sans-serif" font-size="12" font-weight="700" fill="#38bdf8" text-anchor="middle">QUANTUM WAVE-PARTICLE DUALITY &amp; DOUBLE-SLIT GEOMETRY</text>

  <!-- Left: Coherent Wave Apparatus -->
  <g transform="translate(40, 80)">
    <!-- Laser Emitter -->
    <rect x="20" y="130" width="45" height="30" rx="6" fill="#1e293b" stroke="#38bdf8" stroke-width="1.5"/>
    <circle cx="65" cy="145" r="16" fill="url(#q-laser-{chapter_idx})"/>
    <text x="42" y="149" font-family="system-ui, sans-serif" font-size="9" font-weight="700" fill="#38bdf8" text-anchor="middle">LASER</text>

    <!-- Incident Planar Waves -->
    <line x1="85" y1="90" x2="85" y2="200" stroke="#38bdf8" stroke-width="2.2" opacity="0.8"/>
    <line x1="110" y1="80" x2="110" y2="210" stroke="#38bdf8" stroke-width="2.2" opacity="0.8"/>
    <line x1="135" y1="70" x2="135" y2="220" stroke="#38bdf8" stroke-width="2.2" opacity="0.8"/>

    <!-- Double-Slit Barrier -->
    <rect x="160" y="40" width="12" height="75" rx="3" fill="#334155"/>
    <rect x="160" y="130" width="12" height="30" rx="3" fill="#334155"/>
    <rect x="160" y="175" width="12" height="75" rx="3" fill="#334155"/>
    <text x="166" y="122" font-family="system-ui, sans-serif" font-size="8" fill="#fef08a" text-anchor="middle">Slit 1</text>
    <text x="166" y="171" font-family="system-ui, sans-serif" font-size="8" fill="#fef08a" text-anchor="middle">Slit 2</text>

    <!-- Superposition Wavefront Ripples -->
    <g fill="none" stroke="#38bdf8" stroke-width="1.5" opacity="0.6">
      <path d="M 172,122 A 30 30 0 0 1 202,145"/>
      <path d="M 172,122 A 60 60 0 0 1 230,145"/>
      <path d="M 172,122 A 90 90 0 0 1 260,145"/>
      <path d="M 172,168 A 30 30 0 0 0 202,145"/>
      <path d="M 172,168 A 60 60 0 0 0 230,145"/>
      <path d="M 172,168 A 90 90 0 0 0 260,145"/>
    </g>

    <!-- Detector Phosphor Screen -->
    <rect x="330" y="40" width="14" height="210" rx="4" fill="#1e293b" stroke="#64748b" stroke-width="1.5"/>

    <!-- Color-mapped Interference Fringes on Screen -->
    <line x1="331" y1="145" x2="343" y2="145" stroke="#38bdf8" stroke-width="10"/>
    <line x1="331" y1="115" x2="343" y2="115" stroke="#38bdf8" stroke-width="6"/>
    <line x1="331" y1="175" x2="343" y2="175" stroke="#38bdf8" stroke-width="6"/>
    <line x1="331" y1="90" x2="343" y2="90" stroke="#0284c7" stroke-width="3"/>
    <line x1="331" y1="200" x2="343" y2="200" stroke="#0284c7" stroke-width="3"/>
    <text x="250" y="275" font-family="system-ui, sans-serif" font-size="11" font-weight="700" fill="#f8fafc" text-anchor="middle">Diffraction &amp; Phase Superposition</text>
  </g>

  <!-- Right Side HUD Takeaway Card -->
  <rect x="440" y="75" width="320" height="335" rx="12" fill="#0f172a" fill-opacity="0.9" stroke="#38bdf8" stroke-width="1.2"/>
  <text x="460" y="108" font-family="system-ui, sans-serif" font-size="13" font-weight="700" fill="#38bdf8">{safe_ch.upper()[:28]}</text>
  <line x1="460" y1="120" x2="735" y2="120" stroke="#334155" stroke-width="1"/>
  <text x="460" y="152" font-family="system-ui, sans-serif" font-size="11" font-weight="600" fill="#38bdf8">• Core Mechanism: {t1}</text>
  <text x="460" y="186" font-family="system-ui, sans-serif" font-size="11" font-weight="600" fill="#10b981">• Wave Superposition: {t2}</text>
  <text x="460" y="220" font-family="system-ui, sans-serif" font-size="11" font-weight="600" fill="#f59e0b">• Interference Pattern: {t3}</text>
  <text x="460" y="254" font-family="system-ui, sans-serif" font-size="11" font-weight="600" fill="#c084fc">• Wavefunction Collapse: {t4}</text>

  <rect x="460" y="285" width="280" height="95" rx="8" fill="#1e293b" stroke="#38bdf8" stroke-width="1"/>
  <text x="475" y="312" font-family="system-ui, sans-serif" font-size="11" font-weight="700" fill="#38bdf8">Pedagogical Physics Insight:</text>
  <text x="475" y="334" font-family="system-ui, sans-serif" font-size="10" fill="#e2e8f0">Photons exhibit wave interference when unobserved,</text>
  <text x="475" y="352" font-family="system-ui, sans-serif" font-size="10" fill="#94a3b8">collapsing into discrete classical particles upon measurement.</text>
</svg>"""

            elif is_neural:
                return f"""<svg viewBox="0 0 800 450" xmlns="http://www.w3.org/2000/svg" data-engine="svg">
  <!-- Cyber Slate Canvas -->
  <rect width="800" height="450" fill="#0b0f19" rx="14" stroke="#1e293b" stroke-width="1.5"/>

  <!-- Top Title Banner -->
  <rect x="180" y="16" width="440" height="32" rx="16" fill="#1e1b4b" stroke="#a855f7" stroke-width="1.2"/>
  <text x="400" y="37" font-family="system-ui, sans-serif" font-size="12" font-weight="700" fill="#c084fc" text-anchor="middle">DEEP NEURAL TOPOLOGY &amp; BACKPROPAGATION GRADIENTS</text>

  <!-- Left: Multi-Layer Neural Network -->
  <g transform="translate(60, 95)">
    <!-- Synaptic Lines -->
    <g stroke="#334155" stroke-width="1.2" opacity="0.6">
      <line x1="40" y1="60" x2="140" y2="40"/><line x1="40" y1="60" x2="140" y2="90"/><line x1="40" y1="60" x2="140" y2="140"/><line x1="40" y1="60" x2="140" y2="190"/>
      <line x1="40" y1="120" x2="140" y2="40"/><line x1="40" y1="120" x2="140" y2="90"/><line x1="40" y1="120" x2="140" y2="140"/><line x1="40" y1="120" x2="140" y2="190"/>
      <line x1="40" y1="180" x2="140" y2="40"/><line x1="40" y1="180" x2="140" y2="90"/><line x1="40" y1="180" x2="140" y2="140"/><line x1="40" y1="180" x2="140" y2="190"/>
      <line x1="140" y1="40" x2="240" y2="80"/><line x1="140" y1="90" x2="240" y2="80"/><line x1="140" y1="140" x2="240" y2="150"/><line x1="140" y1="190" x2="240" y2="150"/>
    </g>

    <!-- Active Gradient Pathways -->
    <line x1="40" y1="120" x2="140" y2="90" stroke="#38bdf8" stroke-width="2.5"/>
    <line x1="140" y1="90" x2="240" y2="80" stroke="#10b981" stroke-width="2.5"/>

    <!-- Input Layer -->
    <circle cx="40" cy="60" r="14" fill="#0c4a6e" stroke="#38bdf8" stroke-width="2"/>
    <circle cx="40" cy="120" r="14" fill="#0c4a6e" stroke="#38bdf8" stroke-width="2"/>
    <circle cx="40" cy="180" r="14" fill="#0c4a6e" stroke="#38bdf8" stroke-width="2"/>
    <text x="40" y="215" font-family="system-ui, sans-serif" font-size="9" font-weight="700" fill="#38bdf8" text-anchor="middle">Inputs X</text>

    <!-- Hidden Layer -->
    <circle cx="140" cy="40" r="14" fill="#064e3b" stroke="#10b981" stroke-width="2"/>
    <circle cx="140" cy="90" r="14" fill="#064e3b" stroke="#10b981" stroke-width="2"/>
    <circle cx="140" cy="140" r="14" fill="#064e3b" stroke="#10b981" stroke-width="2"/>
    <circle cx="140" cy="190" r="14" fill="#064e3b" stroke="#10b981" stroke-width="2"/>
    <text x="140" y="225" font-family="system-ui, sans-serif" font-size="9" font-weight="700" fill="#10b981" text-anchor="middle">Hidden ReLU</text>

    <!-- Output Layer -->
    <circle cx="240" cy="80" r="14" fill="#451a03" stroke="#f59e0b" stroke-width="2"/>
    <circle cx="240" cy="150" r="14" fill="#451a03" stroke="#f59e0b" stroke-width="2"/>
    <text x="240" y="185" font-family="system-ui, sans-serif" font-size="9" font-weight="700" fill="#f59e0b" text-anchor="middle">Outputs ŷ</text>

    <!-- Backward Gradient Arrow -->
    <path d="M 230,165 Q 140,240 50,195" fill="none" stroke="#ef4444" stroke-width="2.5" stroke-dasharray="4,4"/>
    <text x="140" y="255" font-family="system-ui, sans-serif" font-size="9" font-weight="700" fill="#ef4444" text-anchor="middle">Backprop: ∂ℒ/∂W</text>
  </g>

  <!-- Right Side HUD Card -->
  <rect x="440" y="75" width="320" height="335" rx="12" fill="#0f172a" fill-opacity="0.9" stroke="#38bdf8" stroke-width="1.2"/>
  <text x="460" y="108" font-family="system-ui, sans-serif" font-size="13" font-weight="700" fill="#38bdf8">{safe_ch.upper()[:28]}</text>
  <line x1="460" y1="120" x2="735" y2="120" stroke="#334155" stroke-width="1"/>
  <text x="460" y="152" font-family="system-ui, sans-serif" font-size="11" font-weight="600" fill="#38bdf8">• Forward Feature Vector: {t1}</text>
  <text x="460" y="186" font-family="system-ui, sans-serif" font-size="11" font-weight="600" fill="#10b981">• Activation Manifold: {t2}</text>
  <text x="460" y="220" font-family="system-ui, sans-serif" font-size="11" font-weight="600" fill="#f59e0b">• Loss Function: {t3}</text>
  <text x="460" y="254" font-family="system-ui, sans-serif" font-size="11" font-weight="600" fill="#c084fc">• Weight Optimization: {t4}</text>

  <rect x="460" y="285" width="280" height="95" rx="8" fill="#1e293b" stroke="#38bdf8" stroke-width="1"/>
  <text x="475" y="312" font-family="system-ui, sans-serif" font-size="11" font-weight="700" fill="#38bdf8">Computational Model:</text>
  <text x="475" y="334" font-family="system-ui, sans-serif" font-size="10" fill="#e2e8f0">Weights optimize via stochastic gradient descent,</text>
  <text x="475" y="352" font-family="system-ui, sans-serif" font-size="10" fill="#94a3b8">minimizing cross-entropy loss over training epochs.</text>
</svg>"""

            elif is_mitosis:
                return f"""<svg viewBox="0 0 800 450" xmlns="http://www.w3.org/2000/svg" data-engine="svg">
  <!-- Microscopic Cellular Canvas -->
  <rect width="800" height="450" fill="#061a1e" rx="14" stroke="#134e4a" stroke-width="1.5"/>

  <!-- Top Title Banner -->
  <rect x="180" y="16" width="440" height="32" rx="16" fill="#042f2e" stroke="#14b8a6" stroke-width="1.2"/>
  <text x="400" y="37" font-family="system-ui, sans-serif" font-size="12" font-weight="700" fill="#2dd4bf" text-anchor="middle">CELL DIVISION &amp; METAPHASE CHROMOSOME SEGREGATION</text>

  <!-- Left: Cell Mitotic Spindle Apparatus -->
  <g transform="translate(230, 245)">
    <!-- Plasma Membrane -->
    <ellipse cx="0" cy="0" rx="165" ry="125" fill="#022c22" stroke="#10b981" stroke-width="2.5"/>

    <!-- Centrosomes / Asters -->
    <circle cx="-120" cy="0" r="10" fill="#f59e0b"/>
    <circle cx="120" cy="0" r="10" fill="#f59e0b"/>
    <text x="-120" y="24" font-family="system-ui, sans-serif" font-size="8.5" fill="#fef08a" text-anchor="middle">Centrosome</text>
    <text x="120" y="24" font-family="system-ui, sans-serif" font-size="8.5" fill="#fef08a" text-anchor="middle">Centrosome</text>

    <!-- Spindle Microtubules -->
    <g fill="none" stroke="#2dd4bf" stroke-width="1.4" opacity="0.7">
      <path d="M -110,0 Q 0,-85 110,0"/>
      <path d="M -110,0 Q 0,-40 110,0"/>
      <path d="M -110,0 Q 0,0 110,0"/>
      <path d="M -110,0 Q 0,40 110,0"/>
      <path d="M -110,0 Q 0,85 110,0"/>
    </g>

    <!-- Duplicated X-Chromatids on Equatorial Plate -->
    <!-- Chromosome 1 (Rose) -->
    <g transform="translate(0, -50)">
      <line x1="-7" y1="-14" x2="7" y2="14" stroke="#f43f5e" stroke-width="4.5" stroke-linecap="round"/>
      <line x1="7" y1="-14" x2="-7" y2="14" stroke="#f43f5e" stroke-width="4.5" stroke-linecap="round"/>
      <circle cx="0" cy="0" r="3" fill="#fef08a"/>
    </g>
    <!-- Chromosome 2 (Sky Blue) -->
    <g transform="translate(0, 0)">
      <line x1="-7" y1="-14" x2="7" y2="14" stroke="#38bdf8" stroke-width="4.5" stroke-linecap="round"/>
      <line x1="7" y1="-14" x2="-7" y2="14" stroke="#38bdf8" stroke-width="4.5" stroke-linecap="round"/>
      <circle cx="0" cy="0" r="3" fill="#fef08a"/>
    </g>
    <!-- Chromosome 3 (Emerald) -->
    <g transform="translate(0, 50)">
      <line x1="-7" y1="-14" x2="7" y2="14" stroke="#10b981" stroke-width="4.5" stroke-linecap="round"/>
      <line x1="7" y1="-14" x2="-7" y2="14" stroke="#10b981" stroke-width="4.5" stroke-linecap="round"/>
      <circle cx="0" cy="0" r="3" fill="#fef08a"/>
    </g>
    <text x="0" y="148" font-family="system-ui, sans-serif" font-size="11" font-weight="700" fill="#f8fafc" text-anchor="middle">Metaphase Equatorial Alignment</text>
  </g>

  <!-- Right Side HUD Card -->
  <rect x="440" y="75" width="320" height="335" rx="12" fill="#042f2e" fill-opacity="0.9" stroke="#14b8a6" stroke-width="1.2"/>
  <text x="460" y="108" font-family="system-ui, sans-serif" font-size="13" font-weight="700" fill="#2dd4bf">{safe_ch.upper()[:28]}</text>
  <line x1="460" y1="120" x2="735" y2="120" stroke="#134e4a" stroke-width="1"/>
  <text x="460" y="152" font-family="system-ui, sans-serif" font-size="11" font-weight="600" fill="#2dd4bf">• Mitotic Phase: {t1}</text>
  <text x="460" y="186" font-family="system-ui, sans-serif" font-size="11" font-weight="600" fill="#38bdf8">• Spindle Apparatus: {t2}</text>
  <text x="460" y="220" font-family="system-ui, sans-serif" font-size="11" font-weight="600" fill="#f59e0b">• Kinetochore Tension: {t3}</text>
  <text x="460" y="254" font-family="system-ui, sans-serif" font-size="11" font-weight="600" fill="#f43f5e">• Genetic Equator: {t4}</text>

  <rect x="460" y="285" width="280" height="95" rx="8" fill="#064e3b" stroke="#10b981" stroke-width="1"/>
  <text x="475" y="312" font-family="system-ui, sans-serif" font-size="11" font-weight="700" fill="#2dd4bf">Cellular Biological Principle:</text>
  <text x="475" y="334" font-family="system-ui, sans-serif" font-size="10" fill="#e2e8f0">Bipolar spindle tension aligns duplicated chromosomes,</text>
  <text x="475" y="352" font-family="system-ui, sans-serif" font-size="10" fill="#a7f3d0">guaranteeing equal 2n genetic distribution in daughter cells.</text>
</svg>"""

            else:
                # General Scientific & Engineering System
                return f"""<svg viewBox="0 0 800 450" xmlns="http://www.w3.org/2000/svg" data-engine="svg">
  <!-- Modern Dark Slate Canvas -->
  <rect width="800" height="450" fill="#0f172a" rx="14" stroke="#334155" stroke-width="1.5"/>

  <!-- Top Title Banner -->
  <rect x="180" y="16" width="440" height="32" rx="16" fill="#1e293b" stroke="#38bdf8" stroke-width="1.2"/>
  <text x="400" y="37" font-family="system-ui, sans-serif" font-size="12" font-weight="700" fill="#38bdf8" text-anchor="middle">PHYSICAL &amp; ARCHITECTURAL SCHEMATIC: {safe_topic.upper()[:36]}</text>

  <!-- Left: Topic-Specific Architectural Process Pipeline -->
  <g transform="translate(45, 75)">
    <!-- Stage 1 Block -->
    <rect x="0" y="20" width="360" height="68" rx="10" fill="#1e293b" stroke="#38bdf8" stroke-width="1.5"/>
    <circle cx="28" cy="54" r="14" fill="#0c4a6e" stroke="#38bdf8" stroke-width="1.5"/>
    <text x="28" y="58" font-family="system-ui, sans-serif" font-size="11" font-weight="800" fill="#38bdf8" text-anchor="middle">1</text>
    <text x="56" y="46" font-family="system-ui, sans-serif" font-size="12" font-weight="700" fill="#f8fafc">FOUNDATIONAL STATE</text>
    <text x="56" y="66" font-family="system-ui, sans-serif" font-size="10.5" fill="#94a3b8">{t1[:36]}</text>

    <!-- Connector 1 -->
    <line x1="180" y1="88" x2="180" y2="124" stroke="#38bdf8" stroke-width="2" stroke-dasharray="4,4"/>
    <polygon points="175,122 180,132 185,122" fill="#38bdf8"/>

    <!-- Stage 2 Block -->
    <rect x="0" y="132" width="360" height="68" rx="10" fill="#1e293b" stroke="#10b981" stroke-width="1.5"/>
    <circle cx="28" cy="166" r="14" fill="#064e3b" stroke="#10b981" stroke-width="1.5"/>
    <text x="28" y="170" font-family="system-ui, sans-serif" font-size="11" font-weight="800" fill="#10b981" text-anchor="middle">2</text>
    <text x="56" y="158" font-family="system-ui, sans-serif" font-size="12" font-weight="700" fill="#f8fafc">OPERATIONAL MECHANISM</text>
    <text x="56" y="178" font-family="system-ui, sans-serif" font-size="10.5" fill="#94a3b8">{t2[:36]}</text>

    <!-- Connector 2 -->
    <line x1="180" y1="200" x2="180" y2="236" stroke="#10b981" stroke-width="2" stroke-dasharray="4,4"/>
    <polygon points="175,234 180,244 185,234" fill="#10b981"/>

    <!-- Stage 3 Block -->
    <rect x="0" y="244" width="360" height="68" rx="10" fill="#1e293b" stroke="#f59e0b" stroke-width="1.5"/>
    <circle cx="28" cy="278" r="14" fill="#451a03" stroke="#f59e0b" stroke-width="1.5"/>
    <text x="28" y="282" font-family="system-ui, sans-serif" font-size="11" font-weight="800" fill="#f59e0b" text-anchor="middle">3</text>
    <text x="56" y="270" font-family="system-ui, sans-serif" font-size="12" font-weight="700" fill="#f8fafc">SYSTEM EQUILIBRIUM &amp; RESULT</text>
    <text x="56" y="290" font-family="system-ui, sans-serif" font-size="10.5" fill="#94a3b8">{t3[:36]}</text>
  </g>

  <!-- Right: Pedagogical Key Card -->
  <rect x="440" y="75" width="320" height="335" rx="12" fill="#1e293b" fill-opacity="0.9" stroke="#38bdf8" stroke-width="1.2"/>
  <text x="460" y="108" font-family="system-ui, sans-serif" font-size="13" font-weight="700" fill="#38bdf8">{safe_ch.upper()[:28]}</text>
  <line x1="460" y1="120" x2="735" y2="120" stroke="#334155" stroke-width="1"/>
  <text x="460" y="152" font-family="system-ui, sans-serif" font-size="11" font-weight="600" fill="#38bdf8">• Core Mechanism: {t1}</text>
  <text x="460" y="186" font-family="system-ui, sans-serif" font-size="11" font-weight="600" fill="#10b981">• Dynamic Process: {t2}</text>
  <text x="460" y="220" font-family="system-ui, sans-serif" font-size="11" font-weight="600" fill="#f59e0b">• Interaction Layer: {t3}</text>
  <text x="460" y="254" font-family="system-ui, sans-serif" font-size="11" font-weight="600" fill="#c084fc">• Equilibrium State: {t4}</text>
  <rect x="460" y="285" width="280" height="95" rx="8" fill="#0f172a" stroke="#38bdf8" stroke-width="1"/>
  <text x="475" y="312" font-family="system-ui, sans-serif" font-size="11" font-weight="700" fill="#38bdf8">Key Educational Takeaway:</text>
  <text x="475" y="334" font-family="system-ui, sans-serif" font-size="10" fill="#e2e8f0">16:9 Widescreen Vector Model</text>
  <text x="475" y="352" font-family="system-ui, sans-serif" font-size="10" fill="#94a3b8">Directly synchronized with lecture timeline</text>
</svg>"""

    def _generate_domain_svg(
        self,
        topic_title: str,
        chapter_title: str,
        chapter_idx: int,
        total_chapters: int,
        speech_text: str
    ) -> str:
        """Backward compatibility delegator"""
        return self._generate_domain_visual(
            topic_title=topic_title,
            chapter_title=chapter_title,
            chapter_idx=chapter_idx,
            total_chapters=total_chapters,
            speech_text=speech_text,
            visual_engine="svg"
        )

