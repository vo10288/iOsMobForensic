#!/bin/bash
# ──────────────────────────────────────────────
#  iOS Forensic Acquisition Tool - Launcher
#  Per Tsurugi Linux 2026 e macOS
# ──────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TOOL="$SCRIPT_DIR/ios_forensic_acquisition.py"

# Colori
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════╗"
echo "║   📱 iOS Forensic Acquisition Tool v1.0         ║"
echo "║   Tsurugi Linux 2026 / macOS                    ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "${NC}"

# Controlla Python
PYTHON=""
if command -v python3 &>/dev/null; then
    PYTHON="python3"
elif command -v python &>/dev/null; then
    PYTHON="python"
else
    echo -e "${RED}[ERRORE] Python 3 non trovato!${NC}"
    echo "Installa Python 3.7+ per continuare."
    exit 1
fi

PYVER=$($PYTHON --version 2>&1)
echo -e "${GREEN}[OK]${NC} $PYVER"

# Controlla tkinter
$PYTHON -c "import tkinter" 2>/dev/null
if [ $? -ne 0 ]; then
    echo -e "${RED}[ERRORE] tkinter non disponibile!${NC}"
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "Installa con: sudo apt install python3-tk"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "Reinstalla Python con: brew install python-tk"
    fi
    exit 1
fi
echo -e "${GREEN}[OK]${NC} tkinter disponibile"

# Controlla libimobiledevice
TOOLS_OK=0
TOOLS_MISSING=0
for tool in idevice_id ideviceinfo idevicebackup2 idevicescreenshot idevicesyslog ideviceinstaller idevicepair; do
    if command -v "$tool" &>/dev/null; then
        ((TOOLS_OK++))
    else
        ((TOOLS_MISSING++))
        echo -e "${YELLOW}[WARN]${NC} $tool non trovato"
    fi
done

if [ $TOOLS_MISSING -gt 0 ]; then
    echo ""
    echo -e "${YELLOW}Alcuni tool libimobiledevice mancano.${NC}"
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "Installa con: sudo apt install libimobiledevice-utils ideviceinstaller"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "Installa con: brew install libimobiledevice ideviceinstaller"
    fi
    echo ""
    read -p "Continuare comunque? (s/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[SsYy]$ ]]; then
        exit 0
    fi
else
    echo -e "${GREEN}[OK]${NC} libimobiledevice tools disponibili ($TOOLS_OK tools)"
fi

# Controlla ffmpeg
if command -v ffmpeg &>/dev/null; then
    echo -e "${GREEN}[OK]${NC} ffmpeg disponibile (screen recording video)"
else
    echo -e "${YELLOW}[WARN]${NC} ffmpeg non trovato (video screen recording disabilitato)"
fi

# Controlla ifuse (AFC)
if command -v ifuse &>/dev/null; then
    echo -e "${GREEN}[OK]${NC} ifuse disponibile (accesso file AFC)"
else
    echo -e "${YELLOW}[WARN]${NC} ifuse non trovato (accesso file AFC disabilitato)"
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "       Installa con: sudo apt install ifuse"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "       Installa con: brew install ifuse && brew install --cask macfuse"
    fi
fi

# Controlla usbmuxd (Linux)
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    if systemctl is-active --quiet usbmuxd 2>/dev/null; then
        echo -e "${GREEN}[OK]${NC} usbmuxd attivo"
    else
        echo -e "${YELLOW}[WARN]${NC} usbmuxd potrebbe non essere attivo"
        echo "       Avvia con: sudo systemctl start usbmuxd"
    fi
fi

echo ""
echo -e "${CYAN}Avvio tool...${NC}"
echo ""

# Avvia
$PYTHON "$TOOL"
