# Jarvis: The Elite AI Assistant 🚀

> *“Bhai, main check kar raha hu…”* – Your personal, autonomous AI that runs on your machine, listens, learns, and acts.  

Jarvis is a **hybrid AI assistant** built by **Kaif Ansari** (Mindly). It combines cutting‑edge LLMs (Groq, Cohere), voice interaction, workspace management, email automation, image generation, web search, and even GUI control – all in one seamless package.  

![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)
![Groq](https://img.shields.io/badge/Groq-API-black)
![Cohere](https://img.shields.io/badge/Cohere-Embeddings-green)
![License](https://img.shields.io/badge/license-MIT-red)

---

## ✨ Features

| Category | Capabilities |
|----------|--------------|
| **🧠 Intelligent** | Two‑tier AI: Fast Brain (Llama 3.3) for speed, Deep Brain (GPT‑OSS‑120B) for reasoning, RAG, conditional logic. Remembers your preferences, bio, and mood. |
| **🎙️ Voice & Wake Word** | Always‑listening with **Porcupine** wake word (“Jarvis”). Uses Groq Whisper (multilingual) for transcription. Real‑time TTS with **edge‑tts** and a slick typing popup. |
| **📁 Workspace Manager** | Organises files in `Creations`, `Vault`, `Temp`. Auto‑detects new files, prevents overwrites, syncs registry, and auto‑cleans temp files after 24h. |
| **🖼️ Image Generation/Editing** | Creates images with **Flux** (Together AI). Edits existing images via **AI Horde** – all with prompt enhancement. |
| **🌐 Web Search & Scraping** | Uses **SerpAPI** to search, then **curl_cffi** (Chrome impersonation) + Jina Reader fallback to fetch full content. Caches results. |
| **📧 Email Manager** | Send/delete emails via Gmail API. Background scanner alerts you to new mails with smart summaries. |
| **🖱️ GUI Automation** | Type, click, scroll, press hotkeys with PyAutoGUI – perfect for repetitive tasks. |
| **🕵️ Proactive Scout** | Every 15 minutes, reads your interests from memory, searches for breaking news, and announces fresh, relevant updates – with duplicate protection. |
| **🔗 App & URL Control** | Opens/closes installed apps (Start Menu auto‑discovery) and websites with intelligent fuzzy matching. |
| **🎵 YouTube Player** | Instantly plays songs/videos using `pywhatkit`. |
| **🧠 Persistent Memory** | ChromaDB vector store for chat history and file indexing. Long‑term summaries compressed by 120B model. |
| **🧩 Modular & Extensible** | Clean separation: `tools/`, `modules/`, `main.py`. Easy to add new tools. |

---

## 🛠️ Tech Stack

- **Languages**: Python 3.10+
- **AI Models**:
  - **Groq**: Llama 3.3‑70B, GPT‑OSS‑120B, Whisper‑Large‑V3‑Turbo
  - **Cohere**: Embeddings (v3), Command R+ (fallback)
- **Voice**: Porcupine (wake word), edge‑tts (speech), PyAudio/speech_recognition
- **Vector DB**: ChromaDB
- **Web**: SerpAPI, curl_cffi (TLS fingerprint), cloudscraper, BeautifulSoup
- **Image**: Together AI (Flux), AI Horde
- **Email**: Gmail API (OAuth2)
- **UI**: PyQt5 (popup), Rich (logs)
- **Automation**: PyAutoGUI, pywhatkit

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10 or higher
- Git
- (Optional) FFmpeg for TTS streaming – place `ffplay.exe` in `C:\ffmpeg\bin\`

### 2. Clone the Repository
```bash
git clone https://github.com/kaif-ansari/jarvis-by-kaif-ansari.git
cd jarvis-by-kaif-ansari
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Set Up Environment Variables
Create a `.env` file in the project root with the following keys:

```
# Required
COHERE_API_KEY=your_cohere_api_key
GROQ_API_KEY=your_groq_api_key
SERPAPI_API_KEY=your_serpapi_key
VISION_API_KEY=your_together_ai_key   # for Flux generation

# Optional (defaults work, but you can change)
PICOVOICE_ACCESS_KEY=your_picovoice_key   # or use the provided one
USER_NAME=Kaif bhai
```

### 5. Google Email Setup
- Enable Gmail API for your account.
- Download `credentials.json` from Google Cloud Console and place it in `modules/emailManager/`.
- Run the assistant once; it will open a browser for OAuth2 authentication and save `token.json`.

### 6. Run Jarvis
**Voice Mode (Default)**
```bash
python main.py
```
Wait 10 seconds for startup, then say **“Jarvis”** and give a command.

**Text Mode (Development)**
```bash
python main.py test_jarvis
```
Type commands directly.

---

## 💬 Example Interactions

| You Say | Jarvis Does |
|---------|-------------|
| *Jarvis, time kya hai?* | “Sir, it’s 3:45 PM.” |
| *Chrome kholo* | Opens Google Chrome. |
| *Naya image generate karo: a cyberpunk city* | Creates image with Flux, saves in Workspace/Creations, shows it, and updates registry. |
| *Kal ka weather kya hai?* | Searches, fetches data, responds with weather summary. |
| *Saad ko mail karo ki main meeting mein late hoon* | Prepares and sends email to Saad (if contact exists). |
| *Yeh file Vault mein move karo* | Moves file from current location to Workspace/Vault, prevents overwrites, speaks confirmation. |
| *Type karo “Hello, how are you?”* | Uses PyAutoGUI to type the text at cursor position. |
| *Volume up karo* | Simulates media key press (if supported by your system). |
| *Mujhe coding karni hai* | Switches to “Technical” mode (Do Not Disturb for scout, shorter replies). |

---

## 📁 Project Structure

```
jarvis-by-kaif-ansari/
├── Data/                     # Logs, vector DB, user memory, registry
│   ├── jarvis_memory/        # ChromaDB, preferences, mood history
│   └── Jarvis_Workspace/     # Your files (Creations, Vault, Temp)
├── modules/                  # Core logic
│   ├── processor.py          # AI router, system prompt, JSON output
│   ├── memory.py             # ContextMemory (vector DB, embeddings)
│   ├── voice/                # stt.py, tts.py, popup.py
│   ├── emailManager/         # Gmail integration
│   ├── scout/                # Proactive news scout
│   └── workspace.py          # Workspace manager
├── tools/                    # Action modules
│   ├── open_any.py           # App & URL launcher
│   ├── close_any.py          # Process killer
│   ├── generate_image.py     # Flux + Horde
│   ├── gui_automation.py     # PyAutoGUI wrapper
│   └── perform_search.py     # SerpAPI + scraping
├── main.py                   # Entry point
├── requirements.txt
└── .env                      # Your API keys
```

---

## 🔧 Troubleshooting

- **No audio / FFmpeg not found** – Ensure FFmpeg is installed and `ffplay.exe` is in `C:\ffmpeg\bin\` (or update path in `tts.py`).
- **Wake word not detected** – Check microphone permissions. On Windows, you may need to set `PvRecorder` device index manually (change `device_index=-1` in `stt.py`).
- **Email authentication fails** – Delete `token.json` and re‑run. Make sure `credentials.json` is correct and the scope is `https://mail.google.com/`.
- **Image generation errors** – Verify `VISION_API_KEY` in `.env` and ensure Together AI account has credits.

---

## 🤝 Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you’d like to change. Feel free to extend the toolset – add new `_action` keys in `processor.py` and corresponding handlers in `executor.py`.

---

## 📜 License

MIT © [Kaif Ansari](https://github.com/kaif-ansari)

---

## ⚡ A Note from the Creator

Jarvis is designed to be **private, local, and powerful**. It’s the result of months of experimentation with LLMs, automation, and voice. If you like it, star ⭐ the repo and share your own enhancements!  

*“Bhai, main hamesha ready hoon.”*
