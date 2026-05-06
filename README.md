# 🧠 J.A.R.V.I.S

> **Just A Rather Very Intelligent System** — A premium AI assistant with hybrid LLM architecture, real-time voice, memory, and autonomous agentic capabilities.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![License](https://img.shields.io/badge/License-MIT-green) ![Platform](https://img.shields.io/badge/Platform-Windows-blue) ![Status](https://img.shields.io/badge/Status-Active-cyan)

---

## 📌 Overview

J.A.R.V.I.S is a modular, voice-first AI assistant designed for **rapid execution** and **deep agentic workflows**. It combines a **Fast Brain** (Groq Llama 3.3‑70B) for instant commands & chat with an **Agentic Brain** (Gemini 2.0 Flash / Gemma‑4‑31B) for multi‑step tasks, research, email, WhatsApp, image generation, and workspace automation.

All interactions are logged, remembered via **ChromaDB + Gemini embeddings**, and presented through a sleek **premium terminal UI**, **system tray**, and **animated popup overlays**.

---

## ✨ Core Features

| Category | Capabilities |
|----------|---------------|
| **🧠 Hybrid LLM** | Router (Llama 3.1‑8B) → Fast Brain (Llama 3.3‑70B) / Agentic Brain (Gemini) |
| **🎤 Voice** | Wake word (“Jarvis”) via Porcupine, STT via Groq Whisper‑Large‑V3 + Google fallback, TTS via Cartesia Sonic‑3 (low‑latency) + Edge TTS fallback |
| **💾 Memory** | ChromaDB vector store with Gemini‑Embedding‑2 (768d); long‑term summary, user bio, mood tracking |
| **🔧 Tools (Agentic)** | Web search (Tavily), arXiv research, deep research (auto‑report), image generate/edit (FLUX / AI Horde), email (Gmail API), WhatsApp (Twilio), workspace manager (read/write/move/rename/list/open) |
| **⚡ Fast Commands** | Open/close apps, URLs, YouTube playback, workspace file opening, direct Hinglish conversation |
| **🖥️ UI** | Coloured terminal with premium logging, system tray icon (Pystray), agent activity panel (PyQt), STT status popup, typing popup |
| **📂 Workspace** | Auto‑indexed folders (`Creations`, `Vault`, `Temp`); rename on move; file registry; fuzzy file finder |
| **📧 Communication** | Send emails with attachments, send WhatsApp messages (with file compression), read unread emails aloud |
| **🖼️ Media** | Generate FLUX images (Together AI), edit via AI Horde, auto‑save to workspace |
| **🧪 Dev Mode** | `test_jarvis` arg → text mode, no tray, faster boot |

---

## 🏗️ Architecture Overview

```
main.py (entry point)
│
├── modules/
│   ├── terminal/        → jarvis_terminal (logging, banner), tray_manager
│   ├── processor.py     → router + fast brain + agentic loop
│   ├── executor.py      → synchronous tool execution (agent) + async (fast)
│   ├── memory.py        → ContextMemory (ChromaDB, embeddings, summarisation)
│   ├── voice/           → stt (wake word + whisper), tts (Cartesia), popups
│   ├── agent_panel.py   → PyQt panel showing agent thought & step
│   └── emailManager/    → Gmail send/delete/radar
│
├── tools/
│   ├── open_any.py      → SmartAppOpener (registry + fuzzy + cache)
│   ├── close_any.py     → kill processes
│   ├── generate_image.py→ FLUX + AI Horde
│   ├── messenger.py     → WhatsApp via Twilio (auto‑compress images)
│   ├── search_tools/    → web (Tavily), arxiv, deep_research
│   └── workspace.py     → WorkspaceManager
│
└── Data/                → jarvis_memory (chroma), RAG, contacts, icons, fonts
```

---

## 🚀 Installation

### 1. Clone & Environment

```bash
git clone https://github.com/thekaifansari01/jarvis-by-kaif-ansari.git
cd jarvis-ai-assistant

# Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate      # Windows
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

**Key packages:** `groq`, `google-genai`, `chromadb`, `pyaudio`, `PyQt5`, `pystray`, `Pillow`, `tavily-python`, `twilio`, `arxiv`, `pywhatkit`, `edge-tts`, `cartesia`, `pvporcupine`, `SpeechRecognition`, `pygame`, `markdown2`, `together`, `dotenv`, …

> ⚠️ **Windows only** (due to `winsound`, `ctypes`, `taskkill`).  
> FFmpeg required for Edge TTS fallback: place `ffplay.exe` in `C:\ffmpeg\bin\` or modify path in `tts.py`.

### 3. API Keys (.env)

Create a `.env` file in the project root:

```env
# Groq
GROQ_API_KEY = "gsk_..."

# Gemini (Google AI Studio)
GEMINI_API_KEY = "AIza..."

# Together AI (Flux image generation)
TOGETHER_AI = "..."

# Tavily (web search)
TAVILY_API_KEY = "tvly-..."

# Twilio (WhatsApp)
TWILIO_ACCOUNT_SID = "AC..."
TWILIO_AUTH_TOKEN = "..."
TWILIO_FROM_NUMBER = "whatsapp:+14155238886"

# Picovoice (wake word) – optional, default key may have limits
PICOVOICE_ACCESS_KEY = "oLxGUCx6LY/..."

# Cartesia (low-latency TTS)
CARTESIA_API_KEY = "..."

# Optional: Email OAuth2 credentials.json placed in modules/emailManager/
```

### 4. Additional Setup

- **Gmail integration**: Place `credentials.json` from Google Cloud Console into `modules/emailManager/`. First run will prompt OAuth.
- **Contacts**: Edit `Data/contacts.json` for WhatsApp recipients.
- **Fonts**: Add `Data/fonts/plain-text.ttf` for popups (optional, falls back to Segoe UI).

---

## 🎮 Usage

### Normal Mode (Voice + Tray)

```bash
python main.py
```

- Console auto‑hides → system tray icon appears.
- Say **“Jarvis”** → wake sound → speak command (Hinglish or English).
- Agent panel slides down when complex tasks run.
- STT popup shows listening / transcribed status.

### Developer Mode (Text + No Tray)

```bash
python main.py test_jarvis
```

- Stay in console, type commands directly.
- No tray icon, faster boot (no 10s delay).

### Disable System Tray

```bash
python main.py system_tray=no
```

### Exit

Say “exit”, “quit”, “stop”, or “bye” – or right‑click tray icon → Exit.

---

## 🧩 Example Commands

| Command (voice or text) | What Jarvis does |
|-------------------------|------------------|
| *“Jarvis, chrome khol de”* | Opens Google Chrome |
| *“Spotify band kar”* | Kills Spotify process |
| *“YouTube pe Arijit Singh sunao”* | Plays via `pywhatkit` |
| *“Report.md khol”* | Opens file from workspace |
| *“Kaif ko WhatsApp bhej ki main aa raha hoon”* | Sends WhatsApp via Twilio |
| *“Deep research on quantum computing 2025 ka report bana”* | Agentic loop → searches web + arXiv → writes `.md` in Creations |
| *“Image generate: cat sitting on a laptop”* | FLUX generation → saves to Creations |
| *“Edit my_dog.png: make it look like a cartoon”* | AI Horde image‑to‑image |
| *“Email bhejo Anjali ko subject meeting, body kal 2pm, attach minutes.pdf”* | Gmail with attachment |
| *“Workspace list kar”* | Shows all indexed files |
| *“Mera mood kaisa hai”* | Recalls recent mood history |

---

## ⚙️ Configuration

Edit `modules/config.py` to change:

- LLM models (router / fast / agent / embedding / summariser)
- TTS engine & voice (Cartesia / Edge)
- Whisper parameters
- Agent steps, timeout, retry limit
- Image models (FLUX, AI Horde)

Or override via environment variables (prefixed with the module name).

---

## 🧠 Memory & Persistence

- **ChromaDB**: `Data/jarvis_memory/chroma_db/` – stores conversation history and RAG file embeddings.
- **Long‑term summary**: `Data/jarvis_memory/summary.txt` – periodic compression of old chats.
- **User bio & preferences**: JSON files in memory folder.
- **Workspace registry**: `Data/Jarvis_Workspace/registry.json` – keeps track of all files with descriptions.
- **Command history**: In‑memory only (deque) – never written to disk for speed.

---

## 🔧 Troubleshooting

| Issue | Possible Fix |
|-------|---------------|
| Wake word not detected | Replace `PICOVOICE_ACCESS_KEY` with your own (free trial). Or edit `stt.py` to use a different keyword. |
| Cartesia TTS fails | Check API key, internet, or fallback to Edge TTS (auto). |
| Agent panel not showing | Ensure PyQt5 installed. Run `python modules/agent_panel.py` manually to test. |
| Image generation fails | Verify `TOGETHER_AI` key and model name in config. |
| WhatsApp attachment too large | Auto‑compression is enabled (max 1920x1920, JPEG quality 75). Still fails? Reduce image manually. |
| ChromaDB errors on startup | Delete `Data/jarvis_memory/chroma_db/` (will re‑index on next run). |

---

## 🧪 Development & Extending

### Add a new tool

1. Implement function in `tools/` (e.g., `my_tool.py`).
2. Add to `agent_schema` in `processor.py` (properties & required).
3. Add execution branch in `executor.py` → `execute_single_tool_sync()`.
4. (Optional) Add to `execute_actions` for async fast brain.

### Logging

All logs go to **rich terminal** (coloured) with filter to suppress HTTP/embedding noise.  
No persistent log file by default, but you can enable `file_handler` in `logger.py`.

---

## 📁 Project Structure (Selected)

```
Jarvis/
├── main.py
├── requirements.txt
├── .env
├── modules/
│   ├── terminal/
│   │   ├── jarvis_terminal.py
│   │   └── tray_manager.py
│   ├── voice/
│   │   ├── stt.py, stt_popup.py, stt_status.py
│   │   ├── tts.py, popup.py
│   ├── processor.py
│   ├── executor.py
│   ├── memory.py
│   ├── agent_panel.py, agent_status.py
│   ├── history.py, logger.py, utils.py, config.py
│   ├── emailManager/
│   └── workspace.py
├── tools/
│   ├── open_any.py, close_any.py
│   ├── generate_image.py, messenger.py
│   └── search_tools/
│       ├── search_hub.py, web.py, arxiv_tool.py, deep_research.py
└── Data/
    ├── contacts.json
    ├── icons/, fonts/
    ├── jarvis_memory/
    └── Jarvis_Workspace/
        ├── Creations/, Vault/, Temp/
        └── registry.json
```

---

## 🙏 Acknowledgements

- **Groq** & **Gemini** for fast / deep LLM inference
- **ChromaDB** & **Gemini Embeddings** for persistent memory
- **Cartesia** for real‑time TTS
- **Together AI** & **AI Horde** for image generation
- **Twilio** & **Gmail API** for communication
- **PyQt, Pystray, Rich, Pillow, pvporcupine**

---

## 📄 License

MIT – free to use, modify, and distribute with attribution.

---

## 👤 Author

**Kaif Ansari (Mindly)**  
Built with ❤️ for seamless voice‑first AI automation.

For issues or suggestions, open a GitHub issue or contact the maintainer.

---
