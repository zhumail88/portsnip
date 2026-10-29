# Packaging and Distribution Guide

`portsnip` should be distributed the way a standard Linux system utility is, rather than through a bare `python main.py` invocation. This guide covers Debian packaging, a universal installer script, and the release strategy.

---

## 1. Debian Package (`.deb`)

A Debian package can be built directly with the standard `dpkg-deb` utility. No build server is required.

### Directory Structure

```text
portsnip_1.0.0-1_all/
├── DEBIAN/
│   └── control
└── usr/
    └── local/
        └── bin/
            └── portsnip
```

### `DEBIAN/control`

```text
Package: portsnip
Version: 1.0.0
Section: utils
Priority: optional
Architecture: all
Maintainer: Your Name <your.email@example.com>
Depends: python3 (>= 3.8), python3-psutil
Description: Instant port and process terminator for developers.
 portsnip traces open ports to their originating process and safely
 terminates them using POSIX signals.
```

### Build Command

```bash
dpkg-deb --build portsnip_1.0.0-1_all
# Output: portsnip_1.0.0-1_all.deb
```

---

## 2. Universal Bash Installer (`scripts/install.sh`)

```bash
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

# Install dependencies
python3 -m pip install --upgrade pip --quiet
python3 -m pip install psutil rich --quiet

# Install executable wrapper
cat << 'EOF' > "${INSTALL_DIR}/${APP_NAME}"
#!/usr/bin/env python3
import sys
from portsnip.cli import main

if __name__ == "__main__":
    sys.exit(main())
EOF

chmod +x "${INSTALL_DIR}/${APP_NAME}"

echo "==> ${APP_NAME} installed successfully to ${INSTALL_DIR}/${APP_NAME}."
echo "==> Run '${APP_NAME} --help' to get started."
```

---

## 3. GitHub Releases Strategy

Each published release should include:

1. The source code archive (zip and tarball).
2. The generated `.deb` package for Debian and Ubuntu users.
3. A standalone binary built with PyInstaller or Nuitka, so the tool can run without a Python installation.