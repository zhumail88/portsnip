#!/usr/bin/env bash
set -euo pipefail

APP_NAME="portsnip"
INSTALL_DIR="/usr/local/bin"

echo "==> Installing ${APP_NAME}..."

# Verify Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed." >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Check root / sudo
if [ "$EUID" -ne 0 ]; then
    echo "Error: Please run as root (or with sudo) to install to ${INSTALL_DIR}." >&2
    exit 1
fi

# If installing from a cloned repository
if [ -f "${REPO_ROOT}/pyproject.toml" ]; then
    echo "==> Installing from local source..."
    python3 -m pip install "${REPO_ROOT}" --upgrade
else
    echo "==> Installing requirements..."
    python3 -m pip install psutil rich --quiet
fi

# Ensure executable wrapper is in INSTALL_DIR if pip didn't place it there
if ! command -v "${APP_NAME}" &> /dev/null; then
    cat << 'EOF' > "${INSTALL_DIR}/${APP_NAME}"
#!/usr/bin/env python3
import sys
from portsnip.cli import main

if __name__ == "__main__":
    sys.exit(main())
EOF
    chmod +x "${INSTALL_DIR}/${APP_NAME}"
fi

echo "==> ${APP_NAME} installed successfully."
echo "==> Run '${APP_NAME} --help' to get started."
