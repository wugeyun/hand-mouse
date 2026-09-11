# Hand Mouse

A coarse webcam gesture input controller for general desktop applications. It intentionally recognizes large movements instead of fine-grained finger poses, so a small set of gestures can replace common wheel, zoom, and mouse-click actions.

[中文 README](README.md) | [Development Guide](DEVELOPMENT.en.md) | [Contributing](CONTRIBUTING.en.md)

## Status

This is a runnable MVP intended for camera, lighting, and gesture-distance tuning before real use. The code is split into testable gesture detectors, an input-event layer, and a command-line entry point. It is not packaged as a desktop installer yet.

## Gestures

| Gesture | Output | Notes |
| --- | --- | --- |
| Move both hands apart | Zoom in | Sends `Ctrl/Command + mouse wheel up` by default |
| Move both hands together | Zoom out | Sends `Ctrl/Command + mouse wheel down` by default |
| Swipe one hand up | Mouse wheel up | One event per clear swipe |
| Swipe one hand down | Mouse wheel down | One event per clear swipe |
| Move a fist toward and away from the camera twice | Left click | Must happen within a short counting window |
| Move a fist toward and away from the camera three times | Right click | Must happen within a short counting window |

In this project, a “fist tap” means that the fist becomes visibly larger in the camera image and then returns to its previous size. It is a forward/backward motion relative to the camera, not a physical collision. A single pulse is ignored to reduce accidental clicks during use.

Events are sent to the currently focused application. Any target that responds to the corresponding standard mouse or keyboard events can use the controller, including browsers, macOS Finder, Windows File Explorer, PPT viewers, image viewers, and office software. The project does not determine whether an application supports a particular action, so the final behavior depends on that application's own mouse and shortcut handling. Use `--zoom-mode keys` for applications that use `Ctrl/Command +` and `Ctrl/Command -`.

## Requirements And Installation

Follow this order: confirm the requirements, get the project, select the correct Python interpreter, create a virtual environment, install dependencies, run dry-run, then test live input.

The project requires Python 3.10 or newer; Python 3.12 is recommended. Do not rely on the command name `python3` alone. Always confirm the version it resolves to.

### 1. Get the project

Replace `YOUR_GITHUB_USERNAME` with the actual repository owner:

```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/hand-mouse.git
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
python3.12 -m venv .venv
source .venv/bin/activate
```

If you confirmed that `python3` itself is 3.10+, you may use:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Verify again after activation so the system interpreter is not accidentally used:

```bash
python --version
python -c "import sys; print(sys.executable)"
```

The output must be Python 3.10+ and the executable path should be inside the project's `.venv` directory.

### 3. Windows PowerShell: check and select Python

```powershell
py --list
py -3.12 --version
```

Create and activate a Python 3.12 virtual environment:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python --version
python -c "import sys; print(sys.executable)"
```

If PowerShell blocks activation scripts, you can call the Python executable inside `.venv` directly or follow the system prompt to adjust the current-user execution policy. Do not switch to an unverified global `python`.

### 4. Install dependencies

With the virtual environment active:

```bash
python -m pip install --upgrade pip
python -m pip install -e .
python -m hand_mouse --version
```

For maintenance work or tests, install development dependencies:

```bash
python -m pip install -e ".[dev]"
```

### 5. Run dry-run first

Dry-run opens the camera and prints detected actions without moving the real mouse:

```bash
python run_hand_mouse.py
```

Test these actions in order:

- Move both hands apart or together; the terminal should print `zoom in` or `zoom out`.
- Swipe one hand up or down; it should print `scroll up` or `scroll down`.
- Move a fist toward and away from the camera twice; after the counting window it should print `left click`.
- Move a fist toward and away from the camera three times; it should print `right click`.

Only continue to live input after dry-run output is stable.

### 6. Test live input

Prepare a safe target application such as a normal browser page, a temporary folder in macOS Finder or Windows File Explorer, or a non-important image. Then run:

```bash
python run_hand_mouse.py --live --no-preview
```

Switch to the target application after the process starts and make sure its window is focused before testing scroll, zoom, and clicks. Events are sent to the focused window; the project does not determine whether the target supports a particular action.

Return to the terminal and press `Ctrl+C` when testing is finished. If zoom does not work, try:

```bash
python run_hand_mouse.py --live --no-preview --zoom-mode keys
```

### 7. Permissions and troubleshooting

- macOS: in System Settings -> Privacy & Security, grant Camera and Accessibility permissions to the terminal or application running the controller.
- Windows: allow Python or the terminal to access the camera; use `py --list` to inspect installed versions.
- `No module named cv2` or `mediapipe`: confirm that `.venv` is active and run `python -m pip install -e .`; do not use another Python's `pip`.
- `Cannot open camera 0`: check camera permissions or try `--camera 1` or `--camera 2`.
- Dry-run works but live input does not: check macOS Accessibility permissions and the focused target window first.

## Run

After installation, you can also start dry-run with:

```bash
python -m hand_mouse
```

Enable real mouse events after the gestures look stable:

```bash
python -m hand_mouse --live
```

For full-screen work or when the preview should not interfere with the active application, hide the preview window and stop with `Ctrl+C`:

```bash
python -m hand_mouse --live --no-preview
```

Useful tuning options:

```bash
python -m hand_mouse --live \
  --zoom-mode keys \
  --scroll-amount 4 \
  --zoom-amount 1 \
  --swipe-distance 0.20 \
  --pulse-threshold 0.16
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
