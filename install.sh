#!/bin/bash

set -e

echo "
╔═══════════════════════════════════════════════════════════════╗
║                    LocalMind Installer v1.0                  ║
║              Self-Hosted AI Assistant Platform                 ║
╚═══════════════════════════════════════════════════════════════╝
"

echo "Checking system requirements..."
RAM_TOTAL=$(grep MemTotal /proc/meminfo | awk '{print $2}')
RAM_GB=$((RAM_TOTAL / 1024 / 1024))
if [ $RAM_GB -lt 8 ]; then
    echo "⚠️  Warning: Less than 8GB RAM recommended (found ${RAM_GB}GB)"
fi

DISK_FREE=$(df -BG / | tail -1 | awk '{print $4}' | sed 's/G//')
if [ $DISK_FREE -lt 30 ]; then
    echo "⚠️  Warning: Less than 30GB free disk space (found ${DISK_FREE}GB)"
fi

OS=$(uname -s)
ARCH=$(uname -m)
echo "Detected: $OS ($ARCH)"

if ! command -v python3 &> /dev/null; then
    echo "Installing Python 3..."
    if [ "$OS" = "Darwin" ]; then
        if command -v brew &> /dev/null; then
            brew install python3
        else
            echo "Error: Homebrew not found. Install from https://brew.sh"
            exit 1
        fi
    else
        sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip
    fi
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}' | cut -d. -f1)
echo "Python version: $PYTHON_VERSION"

if ! command -v ollama &> /dev/null; then
    echo "Installing Ollama..."
    if [ "$OS" = "Darwin" ]; then
        if command -v brew &> /dev/null; then
            brew install ollama
        else
            echo "Downloading Ollama for macOS..."
            curl -L https://ollama.com/download/Ollama-darwin.zip -o /tmp/ollama.zip
            unzip /tmp/ollama.zip -d /usr/local/bin/
            rm /tmp/ollama.zip
        fi
    else
        curl -fsSL https://ollama.com/install.sh | sh
    fi
else
    echo "✓ Ollama already installed"
fi

echo "Setting up Ollama environment..."
if [ "$OS" = "Darwin" ]; then
    if ! grep -q "OLLAMA_ORIGINS" ~/.zshrc 2>/dev/null; then
        echo 'export OLLAMA_ORIGINS="*"' >> ~/.zshrc
    fi
    if [ -f ~/.bash_profile ] && ! grep -q "OLLAMA_ORIGINS" ~/.bash_profile; then
        echo 'export OLLAMA_ORIGINS="*"' >> ~/.bash_profile
    fi
    export OLLAMA_ORIGINS="*"
else
    if [ ! -f /etc/environment ] || ! grep -q "OLLAMA_ORIGINS" /etc/environment; then
        echo 'OLLAMA_ORIGINS="*"' | sudo tee -a /etc/environment
    fi
    export OLLAMA_ORIGINS="*"
fi

echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Creating uploads directory..."
mkdir -p uploads

echo "Creating start script..."
cat > start.sh << 'EOF'
#!/bin/bash
source venv/bin/activate
uvicorn server:app --host 0.0.0.0 --port 8080
EOF
chmod +x start.sh

echo "
═══════════════════════════════════════════════════════════════
                    Pulling AI Models
═══════════════════════════════════════════════════════════════
"

MODELS=("deepseek-r1:8b" "llama3.2-vision:11b" "qwen2.5:7b" "mistral:7b" "nomic-embed-text")

for model in "${MODELS[@]}"; do
    echo "Pulling $model..."
    ollama pull $model
done

echo "
═══════════════════════════════════════════════════════════════
                         ✓ SUCCESS
═══════════════════════════════════════════════════════════════

✅ Ollama running at http://localhost:11434
✅ Models installed: ${MODELS[*]}
✅ Server ready at http://localhost:8080

Run './start.sh' to launch LocalMind anytime.
"

echo "Starting LocalMind..."
./start.sh