# Hand Mouse

A coarse webcam gesture input controller for general desktop applications. It intentionally recognizes large movements instead of fine-grained finger poses, so a small set of gestures can replace common wheel and left-click actions.

[中文 README](README.md) | [Development Guide](DEVELOPMENT.en.md) | [Contributing](CONTRIBUTING.en.md)

## Status

This is a runnable MVP intended for camera, lighting, and gesture-distance tuning before real use. The code is split into testable gesture detectors, an input-event layer, and a command-line entry point. It is not packaged as a desktop installer yet.

## Gestures

| Gesture | Output | Notes |
| --- | --- | --- |
| Hold the left palm open | Continuously scroll page up | Starts after about 1000ms and repeats while held |
| Hold the right palm open | Continuously scroll page down | Starts after about 1000ms and repeats while held |
| Extend the right thumb sideways | Left click | Other fingers folded; fires once after about 500ms |
| Point the right index finger up | Fine mouse movement | Arms after about 500ms; the index controls the cursor |
| Make a fist with the left hand | Stop mouse movement immediately | No delay; locks the current cursor position |

Scroll direction no longer depends on vertical movement. The left palm always scrolls up and the right palm always scrolls down. Scrolling starts after 1000ms of stability and repeats while the palm is held open; closing the hand or removing it from the frame stops scrolling immediately.

Pointing the right index finger up arms fine cursor movement. A detected left fist immediately freezes the cursor and exits pointer mode. After the fist is released, the right index must remain stable for another 500ms before movement resumes.

Events are sent to the currently focused application. Any target that responds to standard mouse events can use the controller, including browsers, macOS Finder, Windows File Explorer, PPT viewers, image viewers, and office software. The project does not determine whether an application supports a particular action, so the final behavior depends on that application's own mouse handling.

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

On the first start, the program downloads `hand_landmarker.task` from the official MediaPipe model endpoint and caches it in the user cache directory. The model is used for local hand-landmark detection; if the machine cannot reach that endpoint, download the model manually and pass it with `--model PATH`.

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

- Hold the left palm open for about 1000ms; it should keep printing `scroll up`.
- Hold the right palm open for about 1000ms; it should keep printing `scroll down`.
- Hold the right thumb sideways for about 500ms; the terminal should print one `left click`. Holding it must not repeat the click.
- Hold the right index finger up for about 500ms; the preview `POINTER` state should become `fine`.
- Make a left fist while moving; `LEFT FIST` should become `True` and `POINTER` should immediately become `idle`.

Only continue to live input after dry-run output is stable.

### 6. Test live input

Prepare a safe target application such as a normal browser page, a temporary folder in macOS Finder or Windows File Explorer, or a non-important image. Then run:

```bash
python run_hand_mouse.py --live --no-preview
```

Switch to the target application after the process starts and make sure its window is focused before testing scroll and left clicks. Events are sent to the focused window; the project does not determine whether the target supports a particular action.

Return to the terminal and press `Ctrl+C` when testing is finished.

### 7. Permissions and troubleshooting

- macOS: in System Settings -> Privacy & Security, grant Camera and Accessibility permissions to the terminal or application running the controller.
- Windows: allow Python or the terminal to access the camera; use `py --list` to inspect installed versions.
- `No module named cv2` or `mediapipe`: confirm that `.venv` is active and run `python -m pip install -e .`; do not use another Python's `pip`.
- Model download failure: prepare `hand_landmarker.task` manually and run `python run_hand_mouse.py --model PATH`.
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
  --scroll-amount 4 \
  --scroll-stable-time 1.00 \
  --scroll-repeat-interval 0.25 \
  --click-stable-time 0.50 \
  --pointer-stable-time 0.50 \
  --fine-sensitivity 0.35
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
