# Hand Mouse

A coarse webcam gesture input controller for general desktop applications. It intentionally recognizes large movements instead of fine-grained finger poses, so a small set of gestures can replace common wheel and mouse-click actions.

[中文 README](README.md) | [Development Guide](DEVELOPMENT.en.md) | [Contributing](CONTRIBUTING.en.md)

## Status

This is a runnable MVP intended for camera, lighting, and gesture-distance tuning before real use. The code is split into testable gesture detectors, an input-event layer, and a command-line entry point. It is not packaged as a desktop installer yet.

## Gestures

| Gesture | Output | Notes |
| --- | --- | --- |
| Hold the left palm upright, then tilt left | Scroll page up once | Keep the wrist roughly still; return upright and pause before another tilt |
| Hold the left palm upright, then tilt right | Scroll page down once | Keep fingers naturally straight; holding the tilt never repeats |
| Extend the right thumb sideways | Left click | Other fingers folded; fires once after about 300ms |
| Make a V sign with the right hand | Right click | Index and middle extended, other long fingers folded; fires once after about 300ms |
| Open all five right-hand fingers | Mouse movement | Arms after about 300ms; the index-finger base controls the cursor; closing stops it |
| Make a fist with either hand | Global emergency stop | Immediately stops scrolling, clicks, and movement; fists never scroll |

Hold the left palm upright with naturally straight fingers for about 100ms. Keep the wrist roughly still and tilt the palm about 20 degrees right to scroll down once, or left to scroll up once. Directions follow the onscreen skeleton; the thumb need not be stretched out. Holding the tilt never repeats. Return near upright and pause for about 100ms before another scroll; a quick return or crossing directly to the other side does not trigger. Translating the whole hand, vertical movement, and small jitter do not scroll. Hand loss longer than about 200ms or a fist clears readiness, requiring another upright hold. Left-hand tilts work while the right palm moves the cursor.

Holding the right hand open for about 300ms starts cursor movement. The control point is the index-finger base where the finger meets the palm, following hand movement and rotation. Closing any fingers or losing the right hand stops movement immediately. Pinching no longer moves the cursor.

The normalized index-base point maps to the full bounds of the display containing the mouse, including the menu bar and Dock/taskbar. Starting movement preserves the cursor position and smoothly removes the initial offset. Each activation selects the display under the cursor; movement does not switch displays automatically. Fast motion increases following speed, and a deadzone filters stationary jitter.

A fist with either hand immediately stops scrolling, clicks, and movement, taking priority over left-hand tilts. Fists never scroll. After a stop, pointer and click gestures must satisfy their stability periods again, and the left palm must return upright and pause before scrolling. The original sideways-thumb left click and V-sign right click still fire once after about 300ms.

Events are sent to the currently focused application. Any target that responds to standard mouse events can use the controller, including browsers, macOS Finder, Windows File Explorer, PPT viewers, image viewers, and office software. The project does not determine whether an application supports a particular action, so the final behavior depends on that application's own mouse handling.

## Requirements And Installation

Follow this order: confirm the requirements, get the project, select the correct Python interpreter, create a virtual environment, install dependencies, run dry-run, then test live input.

The project requires Python 3.10 or newer; Python 3.12 is recommended. Do not rely on the command name `python3` alone. Always confirm the version it resolves to.

This guide consistently uses `.venv312` as the virtual-environment directory name. You may choose another name for your Python installation, but keep that name consistent in all subsequent activation and interpreter paths.

### 1. Get the project

Clone the official repository:

```bash
git clone https://github.com/wugeyun/hand-mouse.git
cd hand-mouse
```

### 2. macOS: check and select Python

```bash
command -v python3
python3 --version
command -v python3.12
python3.12 --version
```

Selection rules:

- If `python3 --version` is 3.10 or newer, you may use `python3`.
- If `python3` is 3.9 or older but `python3.12` exists, use `python3.12`.
- If no Python 3.10+ interpreter exists, install one and repeat this check.

For example, create a virtual environment with Python 3.12:

```bash
python3.12 -m venv .venv312
source .venv312/bin/activate
```

If you confirmed that `python3` itself is 3.10+, you may use:

```bash
python3 -m venv .venv312
source .venv312/bin/activate
```

Verify again after activation so the system interpreter is not accidentally used:

```bash
python --version
python -c "import sys; print(sys.executable)"
```

The output must be Python 3.10+ and the executable path should be inside the project's `.venv312` directory.

### 3. Windows PowerShell: check and select Python

```powershell
py --list
py -3.12 --version
```

Create and activate a Python 3.12 virtual environment:

```powershell
py -3.12 -m venv .venv312
.\.venv312\Scripts\Activate.ps1
python --version
python -c "import sys; print(sys.executable)"
```

If PowerShell blocks activation scripts, you can call the Python executable inside `.venv312` directly or follow the system prompt to adjust the current-user execution policy. Do not switch to an unverified global `python`.

### 4. Install dependencies and verify the model

With the virtual environment active:

```bash
python -m pip install --upgrade pip
python -m pip install -e .
python -m hand_mouse --version
```

The repository includes `src/hand_mouse/models/hand_landmarker.task`, so a normal clone does not need to download the model. The program checks, in order: `--model PATH`, the bundled repository model, the user cache, and finally the official MediaPipe download URL. The model is used only for local hand-landmark detection; camera frames are not uploaded.

Verify that the bundled model exists:

macOS:

```bash
test -s src/hand_mouse/models/hand_landmarker.task && echo "model is ready"
```

Windows PowerShell:

```powershell
Test-Path .\src\hand_mouse\models\hand_landmarker.task
```

For maintenance work or tests, install development dependencies:

```bash
python -m pip install -e ".[dev]"
```

### 5. macOS: run dry-run first

Dry-run reads the camera in the background, draws live skeleton lines on a transparent desktop overlay, and prints detected actions without moving the real mouse:

```bash
python run_hand_mouse.py
```

Test these actions in order:

- Hold the left palm upright for about 100ms, then tilt right with the wrist still. It should print `scroll down` once; holding the tilt must not repeat.
- Return the left palm upright for about 100ms, then tilt left. It should print `scroll up` once. Returning upright, translating the whole hand, and right-hand tilts must not scroll.
- Hold the right thumb sideways for about 300ms; the terminal should print one `left click`. Holding it must not repeat the click.
- Hold a right-hand V sign for about 300ms; the terminal should print one `right click`. Holding it must not repeat the click.
- Open all five right-hand fingers for about 300ms to enter pointer mode. The index-finger base aligns with the cursor; closing fingers or losing the hand stops movement.
- In live mode, move the palm toward all four camera edges and confirm the cursor reaches the matching display edges.
- Either fist immediately stops scrolling, clicks, and movement. With both hands visible, test right-hand pointer movement together with left-hand scrolling.

Only continue to live input after dry-run output is stable.

### 6. Windows: run dry-run first

From the repository root, with the virtual environment activated:

```powershell
python run_hand_mouse.py
```

After dry-run is stable, enable real input:

```powershell
python run_hand_mouse.py --live
```

If PowerShell blocks activation scripts, use the virtual-environment interpreter directly:

```powershell
.\.venv312\Scripts\python.exe run_hand_mouse.py
.\.venv312\Scripts\python.exe run_hand_mouse.py --live
```

Press `Ctrl+C` in PowerShell when testing is finished.

### 7. macOS: test live input

Prepare a safe target application such as a normal browser page, a temporary folder in macOS Finder, or a non-important image. Then run:

```bash
python run_hand_mouse.py --live
```

Switch to the target application after the process starts and make sure its window is focused before testing scroll, left clicks, and right clicks. Events are sent to the focused window; the project does not determine whether the target supports a particular action.

Return to the terminal and press `Ctrl+C` when testing is finished.

### 8. Windows: test live input

Prepare a safe target application such as a normal browser page, a temporary folder in Windows File Explorer, or a non-important image. Then run:

```powershell
python run_hand_mouse.py --live
```

Switch to the target application after the process starts and make sure its window is focused before testing scroll and clicks. Return to PowerShell and press `Ctrl+C` when testing is finished.

### 9. Permissions and troubleshooting

- macOS: in System Settings -> Privacy & Security, grant Camera and Accessibility permissions to the terminal or application running the controller.
- Windows: allow Python or the terminal to access the camera; use `py --list` to inspect installed versions.
- `No module named cv2` or `mediapipe`: confirm that `.venv312` is active and run `python -m pip install -e .`; do not use another Python's `pip`.
- Missing or incomplete clone: confirm that `src/hand_mouse/models/hand_landmarker.task` exists; you can also prepare the model manually and run `python run_hand_mouse.py --model PATH`.
- macOS exit: use `Ctrl+C`. `Ctrl+Z`, terminal closure, and normal termination also clean up and exit. Terminal hangup is monitored even if the exit signal is missed. The camera closes before the overlay and model; if native work or cleanup blocks, this program terminates about 5 seconds after the exit request. The system camera light may take a few more seconds to turn off.
- `Cannot open camera 0`: check camera permissions or try `--camera 1` or `--camera 2`.
- Dry-run works but live input does not: check macOS Accessibility permissions and the focused target window first.

## One-Click Deployment And Run

The repository provides one script for each platform. The script checks Python, selects or creates a virtual environment, installs the project and test dependencies, verifies the bundled model, runs the tests, and starts live mouse control only after confirmation.

macOS: double-click `run_macos.command`. If macOS reports that the file is not executable, run this once from the repository root:

```bash
chmod +x run_macos.command
open run_macos.command
```

Windows: double-click `run_windows.bat`. You can also run it from PowerShell:

```powershell
.\run_windows.bat
```

On the first run, the scripts look for Python 3.12, 3.11, and 3.10 in that order. If no supported version is available, they offer a version choice. macOS uses Homebrew for installation, and Windows uses `winget`; if the required tool is unavailable, the script opens the official Python download page and asks you to run it again. The default virtual-environment directory is `.venv312`; press Enter to accept it or enter a custom name.

After the first deployment, each script saves a platform-specific local configuration. On later runs, confirm the deployment-skip prompt to go directly to the test and live-start steps. Live mouse control is never started when tests fail. The live command uses `--live` and draws only live skeleton lines over the desktop: a transparent background, no camera image, landmark dots, or status text, with mouse clicks passing through and input focus preserved. Bone lines use 50% opacity. Camera coordinates fill the full bounds of the display under the cursor. While the right palm is open, the entire skeleton is translated together so the index-finger base matches the actual cursor position. Lines clear as soon as the hand disappears. Press `Ctrl+C` in the terminal to stop, or use `--no-preview` for manual startup without the skeleton overlay.

## Run

After installation, you can also start dry-run with:

```bash
python -m hand_mouse
```

Enable real mouse events after the gestures look stable:

```bash
python -m hand_mouse --live
```

To hide the desktop skeleton overlay, use `--no-preview` and stop with `Ctrl+C` in the terminal:

```bash
python -m hand_mouse --live --no-preview
```

Useful tuning options:

`--scroll-amount` is the number of logical wheel notches sent per left-hand tilt. Windows converts this to the native system wheel unit automatically; macOS keeps its native scroll units.

`--scroll-stable-time` controls the upright left-palm hold before each scroll, 100ms by default. The legacy `--scroll-repeat-interval` is accepted but no longer repeats scrolling. `--pinch-stable-time` remains an alias of `--pointer-stable-time`, controlling open-palm pointer activation.

Stability times and the deadzone may be zero. The camera index must be nonnegative; frame dimensions, scroll amount, legacy repeat interval, and gains must be positive. `--cursor-smoothing` must be in `(0, 1]`, and all numeric parameters must be finite. Invalid parameters are rejected before the camera opens.

```bash
python -m hand_mouse --live \
  --scroll-amount 4 \
  --scroll-stable-time 0.10 \
  --click-stable-time 0.30 \
  --pointer-stable-time 0.30 \
  --fine-sensitivity 0.35 \
  --cursor-max-gain 3.00 \
  --cursor-acceleration-speed 1.00 \
  --cursor-deadzone 0.0015
```

The source-checkout entry point is also available:

```bash
python run_hand_mouse.py --help
```

## Permissions and platform notes

- macOS: grant Camera and Accessibility permissions to the terminal or application that runs the controller.
- Windows: allow camera access; support for `Ctrl + wheel` varies between applications.
- Camera frames are processed locally and are not uploaded by this project. Use dependencies according to their own licenses and privacy policies.

## Development

See [DEVELOPMENT.en.md](DEVELOPMENT.en.md) for the project structure, detector state machines, test commands, and release checklist.

```bash
python -m pip install -e ".[dev]"
ruff check .
pytest
```

Tests do not require a camera and do not send real mouse events. A real camera, OS permissions, and each target application still need separate acceptance testing.

## License

This project is released under the [MIT License](LICENSE).
