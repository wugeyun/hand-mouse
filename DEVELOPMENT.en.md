# Development Guide

This document is for maintainers and contributors. User installation and usage are documented in [README.en.md](README.en.md); the Chinese primary version is [DEVELOPMENT.md](DEVELOPMENT.md).

## Design goals

The project targets general desktop interaction, so it prioritizes low cognitive load, low accidental activation, and explainable behavior:

- No user-specific gesture training.
- No complex per-finger gesture classification.
- Detection is based on handedness, open-palm state, and thumb posture.
- Detectors emit abstract actions; OS input injection stays in a separate controller.
- Dry-run is the default. Real input requires the explicit `--live` flag.

## Code structure

```text
src/hand_mouse/
  cli.py         # camera loop and CLI arguments
  overlay.py     # transparent desktop skeleton and index-base alignment
  controller.py  # PyAutoGUI input events, display bounds, and platform modifiers
  detectors.py   # pure geometry/time-series gesture detectors
  tracker.py     # MediaPipe Tasks API and model selection/cache
  models/        # Bundled hand_landmarker.task model
tests/
  test_detectors.py
run_hand_mouse.py # source-checkout entry point
```

The data flow is:

```text
camera frame -> MediaPipe Tasks landmarks -> HandPose -> detector -> abstract action -> PyAutoGUI
```

`tracker.py` prefers `models/hand_landmarker.task`, so a source clone and editable installation do not require a first-run model download. If the bundled model is missing, it falls back to the user cache and then the official model URL; releases and repository mirrors should retain this binary file.

## Action contracts

- `LeftPalmTiltScrollDetector.update(hands, now, frame_aspect_ratio)` requires at least three extended left long fingers and derives tilt from the wrist-to-middle-knuckle vector, corrected for the actual camera aspect ratio. Holding within 12 degrees of upright for 100ms arms one event: `-1` at 20 degrees right, `1` at 20 degrees left. Another event requires another upright hold; return motion and crossing directly to the other side cannot trigger. Translation does not affect tilt, and loss over 200ms or a fist resets readiness.
- `HorizontalThumbClickDetector.update(thumb_horizontal, now)` returns `True` after `--click-stable-time` seconds of a stable right horizontal-thumb pose and `False` while the state is held or for other states. Leaving the pose is required before another click can fire.
- `PeaceSignClickDetector.update(peace_sign, now)` returns `True` after `--click-stable-time` seconds of a stable right-hand V sign and `False` while the state is held or for other states. Leaving the pose is required before another right click can fire.
- `PalmPointerDetector.update(hands, now)` arms mouse movement after 300ms with the right hand fully open. Closing fingers or losing the hand stops immediately.
- `index_base_point(points)` uses MediaPipe landmark 5, the index MCP joint where the finger meets the palm, for both cursor mapping and skeleton alignment. Pinch movement and local fingertip tracking have been removed.
- `CursorMapper` maps the normalized index-base point to the full bounds of the display containing the cursor when fine mode starts. It preserves the current cursor position, then smoothly removes the initial offset; the active mode does not switch displays automatically. The deadzone uses accumulated movement, and smoothing continues toward the last accepted target after the hand stops.
- Either fist takes stop priority and resets scrolling, clicks, and movement. Explicit pinches and horizontal-thumb poses are excluded from fist classification; click gestures retain their existing behavior.
- `SkeletonOverlay` updates a transparent topmost window on the main thread, drawing only bone connections at 50% opacity and accepting neither mouse input nor keyboard focus. Camera coordinates fill the current display; an open right-hand skeleton is translated as a whole to align the index-finger base with the actual cursor, and missing hands clear the lines. `--no-preview` disables drawing; terminal `Ctrl+C` exits.
- `_runtime_resources` cleans up in camera, overlay, then model order and continues other cleanup callbacks after an error. On macOS, a 5-second timer terminates only this application if native cleanup stalls; exceptions preserve a failure exit code. `SIGINT`, `SIGTSTP`, `SIGHUP`, and `SIGTERM` set a persistent exit flag, checked after camera reads and inference, so native callbacks cannot swallow exit exceptions. A macOS watchdog monitors the initial terminal descriptors with hangup polling and terminal validity checks, covering missed signals and bounding native blockage to five seconds after an exit request. The macOS launcher uses `exec`.
- `InputController` is the only class allowed to send real input events and provides left- and right-click methods. Detectors and unit tests must not call PyAutoGUI directly.

## Local development

```bash
python3 -m venv .venv312
source .venv312/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Run checks:

```bash
ruff check .
pytest
python -m hand_mouse --help
```

Tests do not need a camera, MediaPipe model, or desktop permissions. Start camera integration in dry-run mode:

```bash
python -m hand_mouse
```

Use live input only after the detections are stable:

```bash
python -m hand_mouse --live
```

## Tuning thresholds

Thresholds use normalized camera coordinates or relative projection sizes, so they are not tied to one resolution:

- `--scroll-stable-time`: upright left-palm preparation duration before each scroll, 100ms by default.
- `--scroll-repeat-interval`: accepted for compatibility; scrolling no longer repeats.
- `--click-stable-time`: how long the right horizontal-thumb pose must remain stable before left click.
- `--pointer-stable-time` / `--pinch-stable-time`: right open-palm duration before mouse movement; 300ms by default. The latter is a legacy alias.
- `--cursor-smoothing`: smoothing factor for the absolute camera target.
- `--fine-sensitivity`: base target-follow ratio at low hand speed.
- `--cursor-max-gain`: maximum target-follow ratio at high hand speed.
- `--cursor-acceleration-speed`: normalized hand speed that reaches maximum gain.
- `--cursor-deadzone`: minimum normalized displacement used to filter stationary jitter.

The follow ratio uses a squared curve: `base_gain + (max_gain - base_gain) * speed_ratio^2`, clamped to `0..1`. When fine mode starts, the mapper records the offset between the current cursor and the hand's absolute target, then removes that offset during a short transition instead of jumping. Display bounds use the full monitor rectangle, including system bars, rather than the work area.

For accidental activations, increase `--scroll-stable-time` and improve lighting or enlarge the camera framing area.

## Adding an input backend

To replace PyAutoGUI:

1. Implement the same `scroll`, `left_click`, and `right_click` methods in `controller.py`.
2. Keep `--live` as the only switch that enables real system input.
3. Keep the backend importable and testable in headless CI.
4. Document platform permissions, focus-window behavior, and failure recovery.

## Release checklist

- Update the version in `pyproject.toml`, `src/hand_mouse/__init__.py`, and `CHANGELOG.md`.
- Run `ruff check .` and `pytest`.
- Complete a dry-run camera test on at least one target platform.
- Verify scroll, left click, and right click in target browsers, file managers, office software, or other desktop applications.
- Verify that no system input is sent without `--live`.
- Check licenses for dependencies and new files.
- Create a Git tag and describe verified platforms and known limitations in the GitHub Release.
