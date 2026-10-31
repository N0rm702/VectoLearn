import os
import sys
import re
import html
import json
import base64
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Response, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from dotenv import load_dotenv, find_dotenv
# Automatically load .env from project root or server folder
load_dotenv(find_dotenv())
load_dotenv(os.path.join(CURRENT_DIR, ".env"))
load_dotenv(os.path.join(os.path.dirname(CURRENT_DIR), ".env"))

from compiler import (
    validate_svg_ast,
    compile_to_protobuf_binary,
    deserialize_from_protobuf_binary,
    ASTValidationError,
)
from llm_engine import generate_lecture_frames, MANDATORY_SYSTEM_INSTRUCTION
from transcription import parse_youtube_transcript_to_segments, extract_youtube_info
from langchain_engine import PedagogicalLangChainService, RECOMMENDED_MODELS

app = FastAPI(
    title="Project ByteClass: Video-to-Vector Binary Compiling Engine",
    description="Compresses 50MB/min video lectures into <50KB/min timeline-synchronized vector instruction payloads.",
    version="1.0.0",
)

# Enable CORS for local Vite development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for compiled binary payloads
COMPILED_PAYLOADS_STORE: Dict[str, bytes] = {}


class IngestRequest(BaseModel):
    topic_title: str
    lecture_text: str
    lecture_id: Optional[str] = None


class SvgValidationRequest(BaseModel):
    svg_payload: str
    auto_repair: Optional[bool] = True


class YouTubeToJsonRequest(BaseModel):
    topic_title: Optional[str] = ""
    transcript_text: Optional[str] = ""
    source_url: Optional[str] = ""
    hf_token: Optional[str] = None
    model_name: Optional[str] = None
    target_duration_minutes: Optional[float] = None
    num_frames: Optional[int] = None
    target_language: Optional[str] = "en"


class LangChainGenerateRequest(BaseModel):
    topic_title: Optional[str] = ""
    transcript_text: Optional[str] = ""
    source_url: Optional[str] = ""
    hf_token: Optional[str] = None
    model_name: Optional[str] = None
    target_duration_minutes: Optional[float] = None
    num_frames: Optional[int] = None
    target_language: Optional[str] = "en"


class JsonIngestRequest(BaseModel):
    lecture_json: Dict[str, Any]


@app.get("/api/health")
def health():
    return {
        "status": "healthy",
        "service": "ByteClass Protobuf Compiler",
        "target_footprint": "< 50 KB / minute",
        "compression_target": "99.9%",
    }


@app.get("/api/prompt-template")
def get_prompt_template():
    """
    Returns the exact system prompt and instructions for users who want to use an external free LLM
    (e.g., Google AI Studio Gemini Free, ChatGPT Free, Claude, Groq) to convert YouTube transcripts into JSON.
    """
    return {
        "system_instruction": MANDATORY_SYSTEM_INSTRUCTION,
        "json_schema_example": {
            "lecture_id": "yt-lec-01",
            "topic_title": "Example Topic",
            "source_video_url": "https://www.youtube.com/watch?v=...",
            "frames": [
                {
                    "timestamp_seconds": 0.0,
                    "spoken_text": "Spoken sentence here...",
                    "action_type": 1,
                    "svg_payload": '<svg viewBox="0 0 400 400" xmlns="http://www.w3.org/2000/svg"><rect width="400" height="400" fill="#090d16" rx="16"/><circle cx="200" cy="200" r="50" fill="#10b981"/></svg>',
                }
            ],
        },
    }


@app.get("/api/recommended-models")
def get_recommended_models():
    """
    Returns the recommended open-source models for LangChain pedagogical lecturing and SVG generation.
    """
    return {
        "recommended_models": RECOMMENDED_MODELS,
        "inference_notes": {
            "huggingface": "Free serverless inference with your Hugging Face User Access Token (read permission).",
            "groq_alternative": "Groq Cloud (console.groq.com) offers ultra-fast (300+ tok/s) free API access for Llama 3.3 70B & Qwen models.",
            "top_choice_svg": "Qwen/Qwen2.5-Coder-32B-Instruct produces the highest quality SVG code and spatial mathematics.",
            "top_choice_teacher": "meta-llama/Llama-3.3-70B-Instruct produces the deepest pedagogical explanations and teaching cadence."
        }
    }


@app.get("/api/backend-config")
def get_backend_config():
    """
    Returns current active backend LLM configuration from the .env file.
    All model and API credentials are kept securely in the backend.
    """
    hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACEHUB_API_TOKEN") or ""
    masked_token = (hf_token[:4] + "..." + hf_token[-4:]) if len(hf_token) > 8 else ("Configured" if hf_token else "Not Set")
    return {
        "model_name": os.environ.get("MODEL_NAME", "Qwen/Qwen2.5-Coder-32B-Instruct"),
        "hf_token_status": masked_token,
        "is_hf_token_set": bool(hf_token.strip()),
        "default_duration_minutes": float(os.environ.get("DEFAULT_DURATION_MINUTES", "4.0")),
        "is_groq_set": bool(os.environ.get("GROQ_API_KEY", "").strip()),
    }


@app.post("/api/generate-langchain-lecture")
def generate_langchain_lecture(req: LangChainGenerateRequest):
    """
    LangChain Multi-Stage Teacher & Vector Architect Pipeline:
    Takes ONLY a YouTube link (or manual transcript) and automatically:
    1. Extracts real video title & author via oEmbed.
    2. Extracts real video transcript via youtube-transcript-api.
    3. LLM plans in-depth pedagogical curriculum and 400x400 SVGs.
    4. Compiles to Protobuf v3 binary payload.
    """
    source_url = (req.source_url or "").strip()
    topic_title = (req.topic_title or "").strip()
    transcript = (req.transcript_text or "").strip()

    # If YouTube URL is provided, automatically extract title & transcript!
    video_duration_minutes = None
    target_lang = (req.target_language or "en").lower().strip()
    if source_url:
        yt_info = extract_youtube_info(source_url, target_language=target_lang)
        if not topic_title:
            topic_title = yt_info.get("title", "")
        if not transcript:
            transcript = yt_info.get("transcript", "")
        if yt_info.get("duration_minutes") and yt_info["duration_minutes"] > 0:
            video_duration_minutes = yt_info["duration_minutes"]

    import html
    if topic_title:
        topic_title = html.unescape(topic_title)
        topic_title = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), topic_title)
        topic_title = re.sub(r'\s+', ' ', topic_title).strip()

    # Fallback title if still blank
    if not topic_title:
        topic_title = "Educational Scientific Lecture"

    # If transcript is still empty (e.g., video had no captions), use topic title as the prompt!
    if not transcript:
        transcript = f"Detailed comprehensive pedagogical lecture explaining {topic_title}. Break down core mechanisms, principles, why it occurs, and key visual models."

    # If duration wasn't obtained from YouTube oEmbed/snippets, estimate from transcript text
    if not video_duration_minutes and transcript:
        from transcription import estimate_transcript_duration
        video_duration_minutes = round(estimate_transcript_duration(transcript) / 60.0, 1)

    default_dur = float(os.environ.get("DEFAULT_DURATION_MINUTES", "4.0"))
    if req.target_duration_minutes and req.target_duration_minutes > 0:
        duration = req.target_duration_minutes
    elif video_duration_minutes and video_duration_minutes > 0:
        duration = video_duration_minutes
    else:
        duration = default_dur

    service = PedagogicalLangChainService(
        hf_token=req.hf_token,
        model_name=req.model_name
    )

    try:
        payload = service.compile_full_lecture(
            topic_title=topic_title,
            transcript_text=transcript,
            source_url=source_url,
            target_duration_minutes=duration,
            num_frames=req.num_frames,
            target_language=target_lang
        )
        # Automatically compile to Protobuf binary
        binary_bytes = compile_to_protobuf_binary(payload)
        lecture_id = payload["lecture_id"]
        COMPILED_PAYLOADS_STORE[lecture_id] = binary_bytes

        payload["binary_size_bytes"] = len(binary_bytes)
        payload["binary_base64"] = base64.b64encode(binary_bytes).decode("ascii")
        payload["download_url"] = f"/api/download-bin/{lecture_id}"
        return payload
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LangChain generation failed: {str(e)}")


@app.post("/api/youtube-to-json")
def convert_youtube_transcript_to_json(req: YouTubeToJsonRequest):
    """
    Converts YouTube video transcripts into an in-depth pedagogical lecture
    with timeline-synchronized 400x400 dark-mode SVG vector diagrams using LangChain.
    """
    source_url = (req.source_url or "").strip()
    topic_title = (req.topic_title or "").strip()
    transcript = (req.transcript_text or "").strip()

    video_duration_minutes = None
    if source_url:
        yt_info = extract_youtube_info(source_url)
        if not topic_title:
            topic_title = yt_info.get("title", "")
        if not transcript:
            transcript = yt_info.get("transcript", "")
        if yt_info.get("duration_minutes") and yt_info["duration_minutes"] > 0:
            video_duration_minutes = yt_info["duration_minutes"]

    if topic_title:
        import html
        topic_title = html.unescape(topic_title)
        topic_title = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), topic_title)
        topic_title = re.sub(r'\s+', ' ', topic_title).strip()

    if not topic_title:
        topic_title = "YouTube Educational Lecture"

    if not transcript:
        transcript = f"Detailed comprehensive pedagogical lecture explaining {topic_title}. Break down core mechanisms, principles, why it occurs, and key visual models."

    # If duration wasn't obtained from YouTube oEmbed/snippets, estimate from transcript text
    if not video_duration_minutes and transcript:
        from transcription import estimate_transcript_duration
        video_duration_minutes = round(estimate_transcript_duration(transcript) / 60.0, 1)

    default_dur = float(os.environ.get("DEFAULT_DURATION_MINUTES", "4.0"))
    if req.target_duration_minutes and req.target_duration_minutes > 0:
        duration = req.target_duration_minutes
    elif video_duration_minutes and video_duration_minutes > 0:
        duration = video_duration_minutes
    else:
        duration = default_dur

    service = PedagogicalLangChainService(
        hf_token=req.hf_token,
        model_name=req.model_name
    )

    try:
        payload = service.compile_full_lecture(
            topic_title=topic_title,
            transcript_text=transcript,
            source_url=source_url,
            target_duration_minutes=duration,
            num_frames=req.num_frames,
            target_language=target_lang
        )
        return payload
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"YouTube ingestion error: {str(e)}")


@app.post("/api/validate-svg")
def test_validate_svg(req: SvgValidationRequest):
    """
    Syntactic AST Verification Interceptor endpoint:
    Validates SVG using non-evaluating xml.etree.ElementTree parser.
    """
    is_valid, repaired_svg, message = validate_svg_ast(req.svg_payload, auto_repair=req.auto_repair or True)
    return {
        "is_valid": is_valid,
        "status_message": message,
        "repaired_svg": repaired_svg,
    }


def normalize_json_payload(data: Any) -> Dict[str, Any]:
    """
    Normalizes any user-uploaded JSON (handling both snake_case, camelCase, or raw frame arrays).
    """
    if isinstance(data, list):
        # Raw array of frames
        frames_list = data
        topic_title = "Uploaded Lecture Payload"
        lecture_id = f"upload-{os.urandom(4).hex()}"
    elif isinstance(data, dict):
        frames_list = data.get("frames", [])
        topic_title = data.get("topic_title") or data.get("topicTitle") or "Uploaded Lecture"
        lecture_id = data.get("lecture_id") or data.get("lectureId") or f"upload-{os.urandom(4).hex()}"
    else:
        raise ValueError("Invalid JSON format. Expected JSON object with 'frames' array or an array of frames.")

    normalized_frames = []
    for f in frames_list:
        ts = f.get("timestamp_seconds") if "timestamp_seconds" in f else f.get("timestampSeconds", 0.0)
        text = f.get("spoken_text") if "spoken_text" in f else f.get("spokenText", "")
        action = f.get("action_type") if "action_type" in f else f.get("actionType", 1)
        svg = f.get("svg_payload") if "svg_payload" in f else f.get("svgPayload", "")

        is_valid, clean_svg, _ = validate_svg_ast(svg, auto_repair=True)

        normalized_frames.append({
            "timestamp_seconds": float(ts),
            "spoken_text": str(text),
            "action_type": int(action),
            "svg_payload": clean_svg,
        })

    # Sort frames by timestamp
    normalized_frames.sort(key=lambda x: x["timestamp_seconds"])

    return {
        "lecture_id": lecture_id,
        "topic_title": topic_title,
        "frames": normalized_frames,
    }


@app.post("/api/ingest")
def ingest_lecture(req: IngestRequest):
    """
    STAGE 1: SERVER CONTENT INGESTION & SERIALIZATION
    """
    lecture_id = req.lecture_id or f"lec-{os.urandom(4).hex()}"
    topic_title = req.topic_title.strip() or "Untitled Lecture"
    lecture_text = req.lecture_text.strip()

    if not lecture_text:
        raise HTTPException(status_code=400, detail="Lecture text cannot be empty")

    frames = generate_lecture_frames(topic_title, lecture_text)

    validated_frames = []
    for frame in frames:
        raw_svg = frame.get("svg_payload", "")
        is_valid, clean_svg, status = validate_svg_ast(raw_svg, auto_repair=True)
        validated_frames.append({
            "timestamp_seconds": float(frame.get("timestamp_seconds", 0.0)),
            "spoken_text": str(frame.get("spoken_text", "")),
            "action_type": int(frame.get("action_type", 1)),
            "svg_payload": clean_svg,
        })

    lecture_dict = {
        "lecture_id": lecture_id,
        "topic_title": topic_title,
        "frames": validated_frames,
    }

    binary_bytes = compile_to_protobuf_binary(lecture_dict)
    COMPILED_PAYLOADS_STORE[lecture_id] = binary_bytes

    duration = max([f["timestamp_seconds"] for f in validated_frames], default=10.0) + 4.0
    mp4_bytes = int(((50 * 1024 * 1024) / 60) * duration)
    bin_size = len(binary_bytes)
    reduction_pct = round(((mp4_bytes - bin_size) / mp4_bytes) * 100, 2)

    return {
        "lecture_id": lecture_id,
        "topic_title": topic_title,
        "frames": validated_frames,
        "binary_size_bytes": bin_size,
        "mp4_equivalent_bytes": mp4_bytes,
        "footprint_reduction_percent": reduction_pct,
        "duration_seconds": duration,
        "binary_base64": base64.b64encode(binary_bytes).decode("ascii"),
        "download_url": f"/api/download-bin/{lecture_id}",
    }


@app.post("/api/ingest-json")
async def ingest_uploaded_json(request: Request):
    """
    Takes a parsed JSON file uploaded by the user, runs AST verification,
    compiles to Protobuf v3 binary, and prepares for edge playback.
    Accepts direct JSON object, wrapped {lecture_json: ...}, or raw frame arrays.
    """
    try:
        data = await request.json()
        if isinstance(data, dict) and "lecture_json" in data:
            data = data["lecture_json"]
        normalized = normalize_json_payload(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON schema: {str(e)}")

    binary_bytes = compile_to_protobuf_binary(normalized)
    lecture_id = normalized["lecture_id"]
    COMPILED_PAYLOADS_STORE[lecture_id] = binary_bytes

    duration = max([f["timestamp_seconds"] for f in normalized["frames"]], default=10.0) + 4.0
    mp4_bytes = int(((50 * 1024 * 1024) / 60) * duration)
    bin_size = len(binary_bytes)
    reduction_pct = round(((mp4_bytes - bin_size) / mp4_bytes) * 100, 2)

    return {
        "lecture_id": lecture_id,
        "topic_title": normalized["topic_title"],
        "frames": normalized["frames"],
        "binary_size_bytes": bin_size,
        "mp4_equivalent_bytes": mp4_bytes,
        "footprint_reduction_percent": reduction_pct,
        "duration_seconds": duration,
        "binary_base64": base64.b64encode(binary_bytes).decode("ascii"),
        "download_url": f"/api/download-bin/{lecture_id}",
    }


@app.get("/api/download-bin/{lecture_id}")
def download_binary_payload(lecture_id: str):
    """
    Serves the compiled .bin Protobuf payload as a binary stream.
    """
    if lecture_id not in COMPILED_PAYLOADS_STORE:
        raise HTTPException(status_code=404, detail="Lecture payload not found")

    data = COMPILED_PAYLOADS_STORE[lecture_id]
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{lecture_id}.bin"'},
    )


# In-memory cache for synthesized neural speech audio bytes
TTS_AUDIO_CACHE: Dict[str, bytes] = {}


@app.get("/api/tts")
async def generate_edge_tts(text: str, voice: str = "en-US-ChristopherNeural", rate: str = "+0%"):
    """
    Studio-grade Neural Audio generated via Edge-TTS on the backend.
    Cached in-memory to prevent repeated network overhead.
    Available voices:
    - en-US-GuyNeural (Male, documentary neutral / English default)
    - en-US-ChristopherNeural (Male, engaging educator style)
    - en-US-JennyNeural (Female, clear instructor style)
    - en-US-AriaNeural (Female, natural expressive)
    - hi-IN-MadhurNeural (Male, documentary narrator / Hindi default)
    - hi-IN-SwaraNeural (Female, clear instructor style / Hindi)
    """
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Text parameter cannot be empty")

    clean_text = text.strip()
    cache_key = f"{voice}_{rate}_{clean_text}"

    if cache_key in TTS_AUDIO_CACHE:
        return Response(
            content=TTS_AUDIO_CACHE[cache_key],
            media_type="audio/mpeg",
            headers={"Cache-Control": "public, max-age=86400"},
        )

    try:
        import edge_tts
        communicate = edge_tts.Communicate(clean_text, voice=voice, rate=rate)
        chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])

        audio_data = b"".join(chunks)
        TTS_AUDIO_CACHE[cache_key] = audio_data

        return Response(
            content=audio_data,
            media_type="audio/mpeg",
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Neural TTS generation error: {str(e)}")


# ==============================================================================
# SERVE PRODUCTION FRONTEND DIRECTLY FROM FASTAPI (FAIL-SAFE BACKUP)
# ==============================================================================
client_dist_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "client", "dist")
if os.path.isdir(client_dist_dir):
    from fastapi.staticfiles import StaticFiles
    from starlette.responses import FileResponse

    assets_dir = os.path.join(client_dist_dir, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/")
    def serve_frontend_root():
        index_file = os.path.join(client_dist_dir, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"status": "ByteClass backend ready"}
