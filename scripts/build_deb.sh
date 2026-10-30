#!/usr/bin/env bash
set -euo pipefail

VERSION="1.0.0"
PKG_DIR="portsnip_${VERSION}-1_all"

echo "==> Building Debian package for portsnip v${VERSION}..."

rm -rf "${PKG_DIR}"
mkdir -p "${PKG_DIR}/DEBIAN"
mkdir -p "${PKG_DIR}/usr/local/bin"
mkdir -p "${PKG_DIR}/usr/local/lib/portsnip"

cat << EOF > "${PKG_DIR}/DEBIAN/control"
Package: portsnip
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: all
Maintainer: portsnip maintainers <maintainers@example.com>
Depends: python3 (>= 3.10), python3-psutil, python3-rich
Description: Instant port and process terminator for developers.
 portsnip traces open ports to their originating process and safely
 terminates them using POSIX signals.
EOF

# Copy source code into package lib directory
cp -r src/portsnip "${PKG_DIR}/usr/local/lib/"

# Create executable entrypoint wrapper
cat << 'EOF' > "${PKG_DIR}/usr/local/bin/portsnip"
#!/usr/bin/env python3
import sys
import os

# Add local package path if installed as standalone package
sys.path.insert(0, "/usr/local/lib")

from portsnip.cli import main

if __name__ == "__main__":
    sys.exit(main())
EOF

chmod +x "${PKG_DIR}/usr/local/bin/portsnip"

# Build package with dpkg-deb if available
if command -v dpkg-deb &> /dev/null; then
    dpkg-deb --build "${PKG_DIR}"
    echo "==> Package built: ${PKG_DIR}.deb"
else
    echo "==> Directory structure prepared at ${PKG_DIR}/ (dpkg-deb not found)."
fi
