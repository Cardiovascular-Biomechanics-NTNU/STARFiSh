#!/bin/bash

# Exit on any error
set -e

echo "==================================================="
echo "   STARFiSh - Automated 3D Slicer Setup (Linux)    "
echo "==================================================="

echo ""
echo "Step 1: Installing Required System Dependencies"
echo "This requires sudo privileges."
sudo apt-get update
sudo apt-get install -y libglu1-mesa libnss3 libxcursor1 libxrender1 libxcomposite1 libasound2t64 libpulse-mainloop-glib0

echo ""
echo "Step 2: Downloading 3D Slicer (Latest Stable Release)"
# Assuming the script is run from within the Slicer directory
SLICER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TAR_FILE="$SLICER_DIR/Slicer-linux.tar.gz"

if ls "$SLICER_DIR"/Slicer-*/Slicer 1> /dev/null 2>&1; then
    echo "Warning: Slicer already appears to be installed in $SLICER_DIR. Skipping download."
else
    echo "Downloading to $TAR_FILE..."
    # The official download redirect for the latest stable linux build
    wget -O "$TAR_FILE" "https://download.slicer.org/download?os=linux&stability=release"
    
    echo ""
    echo "Step 3: Extracting Slicer..."
    tar -xzf "$TAR_FILE" -C "$SLICER_DIR"
    
    echo "Cleaning up tarball..."
    rm "$TAR_FILE"
fi

echo ""
echo "Step 4: Installing SlicerVMTK Extension"
# Find the specific Slicer executable inside the extracted folder
SLICER_EXEC=$(find "$SLICER_DIR" -maxdepth 2 -type f -name "Slicer" -executable | head -n 1)

if [ -z "$SLICER_EXEC" ]; then
    echo "Error: Could not find Slicer executable in $SLICER_DIR!"
    exit 1
fi

echo "Found Slicer executable at: $SLICER_EXEC"
echo "Running Slicer headlessly to install SlicerVMTK..."

# Run Slicer headlessly and use the Extensions Manager API to download SlicerVMTK
cat << 'EOF' > install_vmtk.py
import slicer
print('Starting SlicerVMTK Extension Installation...')
em = slicer.app.extensionsManagerModel()
em.interactive = False
success = em.downloadAndInstallExtensionByName('SlicerVMTK')
if success:
    print('SUCCESS: SlicerVMTK installed.')
else:
    print('ERROR: Failed to install SlicerVMTK.')
slicer.app.quit()
EOF

$SLICER_EXEC --no-splash --no-main-window --python-script install_vmtk.py

# Clean up
rm install_vmtk.py

echo "==================================================="
echo "Setup Complete!"
echo "You can now use the 3D Slicer Integration tab in the STARFiSh UI."
echo "Please note: you may need to install the VMTK extension manually from the Extensions Manager within Slicer if there were any issues during installation."
echo "==================================================="
