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
  controller.py  # PyAutoGUI input events and platform modifiers
  detectors.py   # pure geometry/time-series gesture detectors
  tracker.py     # MediaPipe Tasks API and model cache
tests/
  test_detectors.py
run_hand_mouse.py # source-checkout entry point
```

The data flow is:

```text
camera frame -> MediaPipe Tasks landmarks -> HandPose -> detector -> abstract action -> PyAutoGUI
```

## Action contracts

- `OpenPalmScrollDetector.update(finger_count, handedness, now)` returns `1` after 1000ms of a stable left open palm and repeats at the configured interval; it returns `-1` for a stable right open palm. Closing the palm stops scrolling.
- `ThumbUpClickDetector.update(thumbs_up, now)` returns `True` after `--click-stable-time` seconds of thumb-up stability and `False` while the state is held or for other states. Leaving thumb-up is required before another click can fire.
- `InputController` is the only class allowed to send real input events. Detectors and unit tests must not call PyAutoGUI directly.

## Local development

```bash
python3 -m venv .venv
source .venv/bin/activate
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

- `--scroll-stable-time`: how long an open palm must remain stable before scrolling.
- `--scroll-repeat-interval`: interval between continuous scroll events.
- `--click-stable-time`: how long a thumbs-up pose must remain stable before left click.

For accidental activations, increase `--scroll-stable-time` and improve lighting or enlarge the camera framing area.

## Adding an input backend

To replace PyAutoGUI:

1. Implement the same `scroll` and `left_click` methods in `controller.py`.
2. Keep `--live` as the only switch that enables real system input.
3. Keep the backend importable and testable in headless CI.
4. Document platform permissions, focus-window behavior, and failure recovery.

## Release checklist

- Update the version in `pyproject.toml`, `src/hand_mouse/__init__.py`, and `CHANGELOG.md`.
- Run `ruff check .` and `pytest`.
- Complete a dry-run camera test on at least one target platform.
- Verify scroll and left click in target browsers, file managers, office software, or other desktop applications.
- Verify that no system input is sent without `--live`.
- Check licenses for dependencies and new files.
- Create a Git tag and describe verified platforms and known limitations in the GitHub Release.
