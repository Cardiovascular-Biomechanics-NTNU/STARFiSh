# STARFiSh Installation Guide

This guide provides instructions to install STARFiSh and its required dependencies on Linux, including the CRIMSON flowsolver and the NetlistEditor.

## Prerequisites
- **Miniconda / Anaconda**: Required for managing Python dependencies.
- **CMake** (v3.15+): Required to build the C++ bridge module.
- C++ Compiler (e.g., GCC or Clang)

---

## Step 1: Install CRIMSON Flowsolver (Linux)

First, you need to install the CRIMSON flowsolver and its dependencies for Linux.
Please refer to the CRIMSON documentation for detailed installation instructions. Ensure you build and install the `.a` static libraries and its dependencies (e.g., PETSc, Boost, OpenBLAS, etc.).

*Note: You will need the paths to the CRIMSON root directory and its dependencies for the next step.*

## Step 2: Generate and Build the Bridge Module

The Python bridge to CRIMSON is located in the `ext/` directory.

1. Navigate to the `ext/` directory:
   ```bash
   cd ext
   ```
2. Update the `CMakeLists.txt` file to point to your CRIMSON paths. Change the following variables:
   - `CRIMSON_ROOT`: Set to your CRIMSON flowsolver root directory.
   - `CRIMSON_DEPS`: Set to your CRIMSON dependencies installation directory.
3. Build the module using CMake:
   ```bash
   mkdir build
   cd build
   cmake ..
   make
   ```
This will compile `crimson_starfish_bridge` linking against the CRIMSON static libraries.

## Step 3: Install STARFiSh Dependencies

All necessary Python modules and system dependencies can be installed using the provided script.

1. From the STARFiSh root directory, run the `ubuntu_dependencies.sh` script:
   ```bash
   ./ubuntu_dependencies.sh
   ```
   *Note: If you need to install the minimal Ubuntu desktop/runtime packages (like `build-essential`, `libgl1`, etc.), you can run `INSTALL_APT=1 ./ubuntu_dependencies.sh` with root privileges.*

2. Activate the newly created conda environment:
   ```bash
   conda activate starfish-py3
   ```

3. Ensure all Python dependencies are fully installed (including PySide6):
   ```bash
   pip install -r requirements.txt
   ```

### Dependencies List (For Other Operating Systems)
If you are building STARFiSh on another OS, ensure the following dependencies are installed in your environment (all of these have been verified to run properly under the `starfish-py3` conda environment):

- `numpy`
- `scipy`
- `h5py`
- `lxml`
- `matplotlib`
- `psutil`
- `pydot`
- `graphviz`
- `pygobject`
- `pycairo`
- `gtk3`
- `gdk-pixbuf`
- `librsvg`
- `pyopengl`
- `freeglut`
- `pyglet`
- `chaospy`
- `PySide6` (can be installed via pip)

## Step 4: Install NetlistEditor (Linux)

Finally, install the NetlistEditor for Linux. 

1. Navigate to the `NetlistEditor` directory:
   ```bash
   cd NetlistEditor
   ```
2. Refer to the `LINUX_STANDALONE_BUILD.md` and `README` files located in the `NetlistEditor` folder for detailed, standalone build instructions specific to Linux.

## Step 5: Install 3D Slicer Integration (Linux)

STARFiSh includes an automated script to download and configure 3D Slicer along with the VMTK extension. This enables the **3D Slicer Integration** tab in the GUI for extracting vessel centerlines directly from 3D models.

1. Ensure you are in the STARFiSh root directory.
2. Navigate to the `Slicer` directory and run the automated installation script:
   ```bash
   cd Slicer
   ./install_slicer_linux.sh
   ```
   *Note: This script will prompt you for your `sudo` password to install required Linux graphics and audio dependencies (such as `libglu1-mesa`, `libnss3`, `libasound2t64`, etc.).*

3. The script will automatically download the latest stable Linux release of 3D Slicer, extract it into a `Slicer/` directory within the repository, and run headlessly to install the `SlicerVMTK` extension.

Once completed, you can launch the STARFiSh Model Builder GUI and use the **3D Slicer Integration** tab to automatically open your local Slicer instance with the VMTK Centerline Extraction module ready to go.
