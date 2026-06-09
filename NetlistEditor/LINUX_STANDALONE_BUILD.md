# NetlistEditor Standalone Linux Build

This document describes the Linux standalone build work for the CRIMSON
NetlistEditor / CRIMSON Boundary Condition Toolbox application.

## What Changed

The NetlistEditor app already had a standalone executable target named
`CRIMSONBCT`. The build was updated so it can be configured and built outside
the larger CRIMSON GUI tree.

Main changes:

- Added a local `FindQwt.cmake` compatibility finder so CMake can find Qwt from
  Ubuntu packages or a manually installed Qwt build.
- Switched the bundled QtPropertyBrowser dependency to use the local source copy
  under `src/gui/qtsolutions/qtpropertyeditor`.
- Added Qt 5 / Qt 6 selection through `NETLISTEDITOR_USE_QT6`.
- Added Qt 6 compatibility fixes for removed or changed APIs, including
  `QRegExp`, `QRegExpValidator`, `QPalette::Background`, `QSignalMapper`,
  `QStyleOptionViewItemV3`, `QList::toSet`, `QColorDialog::getRgba`, and stricter
  `QFlags` conversion.
- Added a default dark theme for the Qt Widgets UI.
- Kept the schematic canvas readable by forcing canvas text items to black on
  the white canvas.

The Qt 5 build remains the default. The Qt 6 build is opt-in.

## Linux Dependencies

Install common build tools:

```bash
sudo apt update
sudo apt install build-essential cmake pkg-config wget
```

Install Qt 5 dependencies for the default build:

```bash
sudo apt install qtbase5-dev qtbase5-dev-tools libqt5svg5-dev libqwt-qt5-dev
```

Install Qt 6 dependencies for the Qt 6 build:

```bash
sudo apt install qt6-base-dev qt6-base-dev-tools qt6-svg-dev libgl1-mesa-dev
```

Ubuntu 24.04 did not provide a `libqwt-qt6-dev` package in this setup, so Qwt
for Qt 6 was built manually.

## Build Qwt For Qt 6

Download and build Qwt 6.3.0 with `qmake6`:

```bash
cd /tmp
wget https://sourceforge.net/projects/qwt/files/qwt/6.3.0/qwt-6.3.0.tar.bz2
tar xf qwt-6.3.0.tar.bz2
cd qwt-6.3.0
qmake6 qwt.pro
make -j
sudo make install
```

Expected install location:

```text
/usr/local/qwt-6.3.0
```

Verify the Qt 6 Qwt install:

```bash
find /usr/local/qwt-6.3.0 -type f \( -name 'qwt_plot.h' -o -name 'libqwt*.so*' \)
ldd /usr/local/qwt-6.3.0/lib/libqwt.so | grep Qt
```

The `ldd` output should show Qt 6 libraries, for example:

```text
libQt6Widgets.so.6
libQt6Gui.so.6
libQt6Core.so.6
```

## Build NetlistEditor With Qt 5

From the NetlistEditor directory:

```bash
cd /home/sadid/crimson/cr_gui/crimson_gui_private/Apps/NetlistEditor
cmake -S . -B build-linux
cmake --build build-linux -j
```

Run:

```bash
./build-linux/bin/CRIMSONBCT
```

## Build NetlistEditor With Qt 6

From the NetlistEditor directory:

```bash
cd /home/sadid/starfish/NetlistEditor
cmake -S . -B build-qt6-linux-starfish \
  -DNETLISTEDITOR_USE_QT6=ON \
  -DCMAKE_PREFIX_PATH=/usr/local/qwt-6.3.0
cmake --build build-qt6-linux-starfish -j
```

Run:

```bash
./build-qt6-linux-starfish/bin/CRIMSONBCT
```

Verify Qt 6 linkage:

```bash
ldd build-qt6-linux-starfish/bin/CRIMSONBCT | grep -E 'Qt6|qwt'
```

Expected output includes:

```text
libQt6Widgets.so.6
libQt6Gui.so.6
libQt6Core.so.6
libqwt.so.6.3 => /usr/local/qwt-6.3.0/lib/libqwt.so.6.3
```

## Running In WSL

On Windows 11 with WSLg, run the binary directly from WSL:

```bash
./build-qt6-linux/bin/CRIMSONBCT
```

WSL may print Mesa/EGL warnings such as:

```text
libEGL warning
MESA: error: ZINK
```

If the window opens and renders, those warnings are usually not blocking.

If Qt platform plugin issues occur, try:

```bash
QT_QPA_PLATFORM=xcb ./build-qt6-linux/bin/CRIMSONBCT
```

## Notes

- Qt 5 is still the default build path.
- Qt 6 requires the manually installed Qwt build unless the system provides a
  Qt 6 Qwt development package.
- The executable target is named `CRIMSONBCT`.
- The Linux standalone binaries are produced at:

```text
build-linux/bin/CRIMSONBCT
build-qt6-linux/bin/CRIMSONBCT
```

