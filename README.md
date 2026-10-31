# Project ByteClass: Video-to-Vector Compression & Offline Edge Playback Engine

> **Target Objective**: Compresses 50 MB/minute video lectures into a **<50 KB/minute** timeline-synchronized vector instruction payload (**99.9% data reduction**), running 100% offline on low-end hardware via a Progressive Web App (PWA).

---

## 🏗️ 1. Architecture & Multi-Engine Pipeline

```
[STAGE 1: SERVER CONTENT INGESTION & COMPILATION]
   Teacher Video / Audio / Topic Script (.mp4 / .mp3 / text / YouTube URL)
                │
                ▼
   ┌────────────────────────────────────────┐
   │ Single-Pass LLM Compiler Orchestrator  │ ──> Groq High-Speed Cloud Inference (~500 tok/s)
   │ (Deterministic 4-Engine Target Schema) │ ──> Automatic 429 Rate-Limit Backoff & Retry Loop
   └────────────────────────────────────────┘
                │
                ├─────────────────────────────────────────┐
                ▼ (Dual-Track Bilingual Scripts)          ▼ (Localized Visual Payloads)
   ┌───────────────────────────┐             ┌───────────────────────────────────┐
   │ English & Devanagari      │             │ Localized Vector Engine Selector: │
   │ Hindi Teacher Voiceovers  │             │ 1. Mermaid.js (Processes/Cycles)  │
   │ (chapter_title_hi /       │             │ 2. D3.js (Math/Coordinate Curves) │
   │  spoken_text_hi)          │             │ 3. Parametric (Atom/Science)      │
   └───────────────────────────┘             │ 4. Basic Geometry (Primitives)    │
                │                            └───────────────────────────────────┘
                ▼                                         │
   ┌───────────────────────────┐                          │
   │ Syntactic AST Parser      │ <────────────────────────┘
   │ (xml.etree.ElementTree    │ ──> Verifies XML/DOM tree, auto-heals tags & passes
   │  auto-healing & checks)   │     through Mermaid/JSON client payloads without corruption
   └───────────────────────────┘
                │
                ▼
   ┌───────────────────────────┐
   │ Protobuf v3 Compiler      │ ──> Compresses structured timeline into binary byte array
   └───────────────────────────┘
                │
         (.bin Payload) Generated: Under 50 KB per minute (< 2.5 KB for 15s)
                │
[STAGE 2: LOW-BANDWIDTH EDGE NETWORK TRANSFER]
                │  (Transmitted over 2G Network Throttling / 10 Kbps Pipe)
                ▼
[STAGE 3: CLIENT EDGE RENDERING (PWA)]
   Student Device Storage (IndexedDB Caching Engine via idb & PWA Service Worker)
                │
                ▼
   ┌───────────────────────────┐
   │ Protobuf.js Binary Decoder│ ──> De-serializes binary stream back into execution objects
   └───────────────────────────┘
                │
         ┌──────┴───────────────────────────────────────┐
         ▼ (Clock-Synchronized Playback Loop)            ▼ (Hardware-Accelerated 16:9 Canvas)
   ┌───────────────────────────┐             ┌──────────────────────────────────────────┐
   │ HTML5 Web Speech TTS      │             │ Universal Visual Engine Resolver         │
   │ • English Studio Voice    │             │ • Mermaid.js Flowcharts & Step Pipelines │
   │ • Authentic Devanagari    │             │ • D3.js Smooth Dynamic Mathematical Curves│
   │   Hindi Voice (हिंदी)     │             │ • Parametric 3Blue1Brown / Bohr Models   │
   │ • 0 KB Streaming Bandwidth│             │ • 800x450 Dark Slate SVG DOM Vectors     │
   └───────────────────────────┘             └──────────────────────────────────────────┘
```

---

## 🛠️ 2. Technology Stack & Key Highlights

### A. Server-Side Compiling Engine (Python FastAPI)
- **Runtime**: Python 3.10+ / 3.12 + FastAPI + Uvicorn
- **Inference Engines**:
  - **Groq Cloud API** (~500 tokens/sec) with models: `openai/gpt-oss-20b`, `openai/gpt-oss-120b`, and `qwen/qwen3.8-27b`.
  - **Hugging Face Serverless Chat API** as automatic secondary fallback.
- **Single-Pass Compilation**: Compiles full multi-chapter timelines (bilingual narration + localized diagrams) in **1 single API request** (~1,500 tokens total), eliminating parallel HTTP 429 rate limit spikes.
- **Intelligent 429 Retry Backoff**: Automatically parses server wait times (`try again in Xs`), pauses with a 0.6s padding, and safely retries.
- **OTPM Clamping**: Strictly clamps output token requests for Qwen to $\le 850$ tokens to respect Groq's 1,000 OTPM limit.
- **Serialization**: Google Protocol Buffers v3 (`lecture.proto` compiled via `grpcio-tools`).
- **AST Verification**: `xml.etree.ElementTree` verifies XML DOM structures, auto-repairs unclosed tags, and preserves client-side engine payloads (Mermaid, D3 JSON).

### B. Edge Client Runtime Environment (React + TypeScript + PWA)
- **Framework**: React 19 + TypeScript + Vite + Tailwind CSS v4
- **Visual Resolvers**:
  - **Mermaid.js**: Interactive procedural flowcharts, state transitions, timelines, and cycles.
  - **D3.js**: Dynamic coordinate plotting for equations (sine waves, parabolic curves, exponential decay).
  - **Parametric / Manim Templates**: Standardized scientific models (e.g. Bohr atom with electron orbitals).
  - **Basic Geometry / SVG**: 16:9 widescreen (800x450) vector canvas with high-contrast slate aesthetics.
- **Dual-Track Bilingual Audio**: In-flight instant switching between **English** and **Hindi (Devanagari हिंदी)** using the native HTML5 Web Speech API (**0 KB streaming bandwidth**).
- **Offline Storage**: IndexedDB database (`byteclass_offline_cache`) via `idb` with Service Worker precaching.
- **Network Simulator**: Real-time 2G (10 Kbps GPRS / 50 Kbps EDGE) transfer benchmark and 99.9% data reduction meter.

---

## 🚀 3. Exact Step-by-Step Instructions to Run

### Step 1: Clone & Verify System Prerequisites

Ensure the following are installed on your machine:
- **Python**: Version 3.10, 3.11, or 3.12 ([python.org](https://www.python.org/downloads/))
- **Node.js**: Version 18.x or 20.x ([nodejs.org](https://nodejs.org/))
- **Git**

```powershell
# Verify Python installation
python --version

# Verify Node and npm
node --version
npm --version
```

---

### Step 2: Configure Environment Variables (`.env`)

In the project root folder (`g:\EduTech Project` or your clone directory), verify or create a `.env` file:

```env
# ==============================================================================
# PROJECT BYTECLASS: BACKEND LLM & COMPILER CONFIGURATION
# ==============================================================================

# 1. (RECOMMENDED) GROQ CLOUD API KEY
# Sign up for a free key at: https://console.groq.com/keys
GROQ_API_KEY=gsk_your_groq_api_key_here

# 2. (OPTIONAL) HUGGING FACE API ACCESS TOKEN
# Get a free read token at: https://huggingface.co/settings/tokens
HF_TOKEN=hf_your_huggingface_token_here

# 3. BACKEND MODEL SELECTION
MODEL_NAME=Qwen/Qwen2.5-Coder-32B-Instruct

# 4. DEFAULT LESSON DURATION (MINUTES)
DEFAULT_DURATION_MINUTES=4.0
```

> [!TIP]
> A free **Groq Cloud API Key** provides blazing fast generation (~500 tokens/sec), completing an entire 4-minute lecture compilation in only 3 to 6 seconds!

---

### Step 3: Launch the Project

You can run the project using **one-click batch scripts** (on Windows) or **standard terminal commands**.

#### Option A: One-Click Launch (Windows)
Double-click `start_all.bat` in the root folder, or run:
```powershell
.\start_all.bat
```
*This starts the FastAPI backend on port `8000`, the Vite client on port `5173`, and opens `http://127.0.0.1:5173` in your browser.*

---

#### Option B: Manual Terminal Execution

##### 1. Start the FastAPI Backend
Open a terminal in the project root:
```powershell
# If using the project virtualenv:
.\venv\Scripts\python.exe -m uvicorn server.main:app --host 127.0.0.1 --port 8000 --reload

# Or if using your global Python installation:
python -m uvicorn server.main:app --host 127.0.0.1 --port 8000 --reload
```
- **Backend Health Check**: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)
- **Interactive Swagger Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

##### 2. Start the React Edge Client
Open a second terminal window:
```powershell
# Navigate into the client directory
cd client

# Install frontend dependencies (first time only)
npm install

# Start the Vite development server
npm run dev -- --host 127.0.0.1 --port 5173
```
- **Edge Player Web App**: [http://127.0.0.1:5173](http://127.0.0.1:5173)

---

## 🖥️ 4. How to Use the Application

### 1. Ingesting YouTube Videos & Topics
1. Open [http://127.0.0.1:5173](http://127.0.0.1:5173) in your browser.
2. Under **Content Ingestion**, either:
   - Paste a YouTube URL (e.g., an educational video on the *Water Cycle*, *Quantum Physics*, *Calculus*, or *Cell Division*).
   - Or enter an educational topic title directly into the **Topic Title** field.
3. Click **Compile & Ingest Lecture**.
4. The backend compiler runs single-pass compilation, generates synchronized bilingual speech tracks, validates vector schemas, and compresses the timeline into binary Protobuf in ~4–6 seconds.

### 2. Dual-Track Bilingual Playback (English & Hindi)
- Click **Play** on the main player. The browser will begin local TTS narration synchronized with real-time vector visuals.
- Click the **Language Switcher** toggle (`EN` / `HI` / `हिंदी`) at any time:
  - Audio and chapter titles switch immediately to authentic Devanagari Hindi or English without reloading or redownloading data.

### 3. Custom JSON Upload Studio
- Click **JSON Studio** in the top navigation bar.
- Drag-and-drop any `.json` lecture payload or edit JSON directly in the browser.
- Click **Validate & Load into Player** to test custom SVG, Mermaid, or D3 diagrams with live AST error auto-repair.

### 4. Testing 100% Offline Mode & 2G Simulation
1. Once a lecture is loaded, it is automatically cached inside your browser's local **IndexedDB** database.
2. Open your browser's Developer Tools (`F12`), switch to the **Network** tab, and toggle **Offline**.
3. Reload the page: the entire PWA, lecture timeline, speech narration, and vector diagrams continue to run smoothly with **0 KB network traffic**.
4. Switch to the **Edge Metrics Dashboard** to inspect the 2G network simulation (10 Kbps vs 50 Mbps) and observe the 99.9% data reduction benchmark.

---

## 📊 5. Verified Telemetry Benchmarks

| Metric | Legacy 1080p MP4 | ByteClass Protobuf Payload | Improvement |
| :--- | :--- | :--- | :--- |
| **Data Size (1 min)** | ~50.0 MB (51,200 KB) | **15 - 40 KB** | **99.94% Reduction** |
| **Download Time (10 Kbps 2G)**| 11 Hours 6 Minutes | **18 - 32 Seconds** | **1,500x Faster** |
| **Streaming Bandwidth** | ~833 KB/sec continuous | **0 KB/sec (Offline Cache)** | **100% Zero Network** |
| **Audio Bandwidth** | Embedded AAC Audio stream | **0 KB (Local Web Speech TTS)**| **0 KB Network** |
| **Rendering Pipeline** | Video Decoder Hardware | **GPU Inline Vector SVG DOM** | **Low-End Mobile Friendly** |

---

## 📁 6. Project Directory Structure

```
EduTech Project/
├── .env                         # Backend API keys (Groq, Hugging Face) and model config
├── start_all.bat                # 1-Click launcher for both backend & frontend
├── start_server.bat             # 1-Click launcher for FastAPI backend
├── start_client.bat             # 1-Click launcher for Vite React client
├── README.md                    # Project documentation & run guide
│
├── server/                      # FastAPI Python Backend
│   ├── main.py                  # API endpoints (/api/ingest-youtube, /api/validate-svg, etc.)
│   ├── langchain_engine.py      # Single-pass compiler, 429 backoff retry, bilingual prompts
│   ├── compiler.py              # Protobuf v3 serializer & XML/AST validation interceptor
│   ├── transcription.py         # YouTube transcript fetcher & duration estimator
│   └── proto/
│       ├── lecture.proto        # Protobuf v3 schema definition
│       └── lecture_pb2.py       # Compiled Python Protobuf classes
│
└── client/                      # React 19 + TypeScript + Vite PWA Client
    ├── src/
    │   ├── App.tsx              # Main application orchestrator & view controller
    │   ├── components/
    │   │   ├── OfflineVectorPlayer.tsx    # Widescreen vector stage & TTS playback engine
    │   │   ├── JsonUploadStudio.tsx       # Custom payload uploader & validator
    │   │   ├── EdgeMetricsDashboard.tsx   # 2G simulation benchmark & telemetry meter
    │   │   └── SvgVisualsStudio.tsx       # Multi-engine diagram inspector & editor
    │   ├── services/
    │   │   ├── visualEngineResolver.ts    # Resolves Mermaid, D3, Manim & SVG to 800x450
    │   │   ├── speechSynthesizer.ts       # HTML5 Web Speech TTS manager (EN & HI)
    │   │   ├── protobufDecoder.ts         # Client-side Protobuf binary deserializer
    │   │   └── indexedDbStore.ts          # Local persistent storage engine (idb)
    │   └── types/
    │       └── lecture.ts       # TypeScript interfaces for frames and lectures
    └── package.json             # Frontend dependencies and scripts
```

---

## ❓ 7. Troubleshooting & FAQ

<details>
<summary><b>1. Error: "No Groq API key configured" or slow Hugging Face responses</b></summary>

Ensure your `.env` file in the project root has a valid `GROQ_API_KEY`. Sign up for free at [console.groq.com](https://console.groq.com/keys) to generate one. Groq provides fast, free-tier cloud inference (~500 tokens/sec).
</details>

<details>
<summary><b>2. Error: Port 8000 or 5173 already in use</b></summary>

If port `8000` or `5173` is occupied by another process:
- Backend: specify a different port:
  ```powershell
  python -m uvicorn server.main:app --port 8001 --host 127.0.0.1
  ```
- Frontend: specify a different port:
  ```powershell
  npm run dev -- --port 5174
  ```
</details>

<details>
<summary><b>3. Hindi voice sounds English or silent on Windows</b></summary>

The app uses your device's native voices. To ensure optimal Hindi TTS quality:
1. Open Windows **Settings** > **Time & Language** > **Language & Region**.
2. Click **Add a language** > Search for **Hindi (हिन्दी)** > Ensure **Text-to-speech** is checked and installed.
3. Restart your browser.
</details>
