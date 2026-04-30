# LocalMind

A production-grade, self-hosted AI assistant platform that runs 100% locally with zero cloud dependency. Feature parity with Claude + OpenClaw, plus extras.

## Quick Install

### Linux/macOS
```bash
chmod +x install.sh
./install.sh
```

### Windows
```powershell
# Run as Administrator
.\install.ps1
```
Or double-click `install.bat`

## Requirements

### Minimum
- RAM: 8GB (runs mistral:7b + qwen2.5:7b)
- Disk: 30GB free
- OS: Windows 10+, macOS 12+, Ubuntu 20.04+
- Python: 3.8+

### Recommended
- RAM: 16GB+ (runs deepseek-r1:14b, llama3.2-vision)
- GPU: NVIDIA 8GB+ VRAM with CUDA 11.8+ (10x faster)
- OR Apple Silicon M1/M2/M3 (Metal GPU acceleration)
- OR AMD RX 6000+ with ROCm (Linux only)
- Disk: 60GB SSD

## Feature Comparison

| Feature | LocalMind | Claude | OpenClaw | ChatGPT |
|---------|-----------|--------|----------|---------|
| Reasoning CoT | ✅ | ✅ | ✅ | ❌ |
| Vision/OCR | ✅ | ✅ | ✅ | ✅ |
| Voice I/O | ✅ | ❌ | ❌ | ✅ |
| Runs Offline | ✅ | ❌ | ❌ | ❌ |
| Free | ✅ | ❌ | ✅ | ❌ |
| Code Sandbox | ✅ | ❌ | ❌ | ❌ |
| RAG | ✅ | ❌ | ❌ | ✅ |
| Branching | ✅ | ✅ | ❌ | ❌ |
| Multi-model Compare | ✅ | ❌ | ❌ | ❌ |
| Custom Prompts | ✅ | ✅ | ❌ | ✅ |
| Export | ✅ | ✅ | ✅ | ✅ |

## Model Guide

| Model | Best For |
|-------|----------|
| deepseek-r1:8b | High reasoning, math, coding, chain-of-thought |
| llama3.2-vision:11b | Image understanding, OCR, chart reading, screenshots |
| qwen2.5:7b | Fast general-purpose, instruction-following, coding |
| mistral:7b | Ultra-fast Q&A and chat |
| nomic-embed-text | Document embeddings for RAG |

## Architecture

- **Layer 1**: Ollama (Direct API, no proxy)
- **Layer 2**: FastAPI Bridge (file uploads, persistence, health)
- **WebUI**: Vanilla HTML/CSS/JS (single file, no build step)

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+K | Command Palette |
| Ctrl+Enter | Send message |
| Ctrl+N | New conversation |
| Ctrl+E | Export chat |
| Ctrl+B | Toggle sidebar |
| Ctrl+R | Regenerate last response |
| Ctrl+. | Stop streaming |
| Ctrl+L | Clear chat |
| Ctrl+1-5 | Switch to model preset |
| Esc | Close modals / stop stream |

## Usage

1. Run the installer for your platform
2. The server starts at `http://localhost:8080`
3. Ollama runs at `http://localhost:11434`

### Manual Start (Linux/macOS)
```bash
./start.sh
```

### Manual Start (Windows)
```batch
start.bat
```

## Troubleshooting

### GPU Not Detected
- NVIDIA: Ensure CUDA drivers installed (`nvidia-smi`)
- Apple Silicon: Requires macOS 12.3+ and Ollama with Metal support
- AMD: Install ROCm (Linux only)

### CORS Issues
Ensure `OLLAMA_ORIGINS=*` is set (installer does this automatically)

### Changing Ollama Host
Edit settings in the web UI or set environment variable:
```bash
export OLLAMA_HOST=http://your-ollama-server:11434
```

### Adding Custom Models
Use the Model Manager in the sidebar or:
```bash
ollama pull model-name
```

## Project Structure

```
localmind/
├── install.sh          # Linux/macOS installer
├── install.ps1         # Windows PowerShell installer
├── install.bat         # Windows batch launcher
├── start.sh            # Linux/macOS start script
├── start.bat           # Windows start script
├── server.py           # FastAPI backend
├── webui.html          # Complete single-file WebUI
├── requirements.txt    # Python dependencies
├── localmind.db       # SQLite database (auto-created)
└── uploads/           # Temp file storage (auto-created)
```

## License

MIT License - 100% local, no telemetry, no external API calls.