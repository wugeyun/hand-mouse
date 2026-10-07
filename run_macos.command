#!/bin/zsh

set -u
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR" || exit 1

DEFAULT_VENV=".venv312"
CONFIG_FILE=".hand-mouse-macos.conf"
MODEL_PATH="src/hand_mouse/models/hand_landmarker.task"
PYTHON_BIN=""
VENV_DIR=""
VENV_PY=""

python_supported() {
    "$1" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1
}

python_version() {
    "$1" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))'
}

find_python() {
    PYTHON_BIN=""
    local candidate candidate_path
    for candidate in python3.12 python3.11 python3.10 python3; do
        candidate_path="$(command -v "$candidate" 2>/dev/null || true)"
        if [[ -n "$candidate_path" ]] && python_supported "$candidate_path"; then
            PYTHON_BIN="$candidate_path"
            return 0
        fi
    done
    return 1
}

confirm_yes() {
    local answer
    printf "%s [Y/n]: " "$1"
    IFS= read -r answer
    [[ -z "$answer" || "$answer" == [Yy]* ]]
}

install_python() {
    local install_version formula
    echo "No supported Python 3.10+ interpreter was found."
    echo "Choose a Python version to install:"
    echo "  1) Python 3.12 (recommended)"
    echo "  2) Python 3.11"
    echo "  3) Python 3.10"
    printf "Choice [1]: "
    IFS= read -r install_version
    case "$install_version" in
        2) install_version="3.11" ;;
        3) install_version="3.10" ;;
        *) install_version="3.12" ;;
    esac

    if ! command -v brew >/dev/null 2>&1; then
        echo "Homebrew is not installed, so Python cannot be installed automatically."
        echo "Install Python from https://www.python.org/downloads/macos/ and run this script again."
        open "https://www.python.org/downloads/macos/" >/dev/null 2>&1 || true
        return 1
    fi

    formula="python@${install_version}"
    if ! brew list --versions "$formula" >/dev/null 2>&1; then
        if ! brew install "$formula"; then
            echo "Python installation failed."
            return 1
        fi
    fi

    PYTHON_BIN="$(brew --prefix "$formula")/bin/python${install_version}"
    if [[ ! -x "$PYTHON_BIN" ]] || ! python_supported "$PYTHON_BIN"; then
        echo "The selected Python installation could not be found."
        return 1
    fi
    return 0
}

setup_environment() {
    local requested_dir existing_python
    find_python || install_python || return 1
    echo "Using Python $(python_version "$PYTHON_BIN"): $PYTHON_BIN"

    printf "Virtual environment directory [default %s]: " "$DEFAULT_VENV"
    IFS= read -r requested_dir
    VENV_DIR="${requested_dir:-$DEFAULT_VENV}"
    VENV_PY="$VENV_DIR/bin/python"

    if [[ -x "$VENV_PY" ]] && python_supported "$VENV_PY"; then
        echo "Using existing supported virtual environment: $VENV_DIR"
    else
        if [[ -e "$VENV_DIR" ]]; then
            existing_python=""
            if [[ -x "$VENV_PY" ]]; then
                existing_python="$(python_version "$VENV_PY" 2>/dev/null || true)"
            fi
            echo "The selected environment is missing or unsupported${existing_python:+ (Python $existing_python)}."
            if ! confirm_yes "Reinitialize $VENV_DIR with Python $(python_version "$PYTHON_BIN")?"; then
                return 1
            fi
        fi
        "$PYTHON_BIN" -m venv "$VENV_DIR" || return 1
        VENV_PY="$VENV_DIR/bin/python"
    fi

    echo "Installing project and test dependencies..."
    "$VENV_PY" -m pip install --upgrade pip || return 1
    "$VENV_PY" -m pip install -e ".[dev]" || return 1

    if [[ ! -s "$MODEL_PATH" ]]; then
        echo "Bundled model is missing: $MODEL_PATH"
        return 1
    fi
    "$VENV_PY" -c 'from hand_mouse.tracker import resolve_model_path; print("Model:", resolve_model_path(None))' || return 1

    printf "%s\n" "$VENV_DIR" > "$CONFIG_FILE"
    return 0
}

if [[ -s "$CONFIG_FILE" ]]; then
    IFS= read -r VENV_DIR < "$CONFIG_FILE"
    VENV_PY="$VENV_DIR/bin/python"
    if [[ -x "$VENV_PY" ]] && python_supported "$VENV_PY"; then
        echo "A completed macOS deployment was found: $VENV_DIR"
        if confirm_yes "Skip deployment and use this environment?"; then
            :
        else
            VENV_DIR=""
            VENV_PY=""
        fi
    else
        VENV_DIR=""
        VENV_PY=""
    fi
fi

if [[ -z "$VENV_PY" ]]; then
    echo "Starting first-time deployment..."
    setup_environment || {
        echo "Deployment was not completed."
        exit 1
    }
fi

echo "Running tests..."
"$VENV_PY" -m pytest || {
    echo "Tests failed. Live mouse control will not start."
    exit 1
}

if confirm_yes "All tests passed. Start live mouse control now?"; then
    echo "Starting live mode with skeleton preview. Press q/ESC in preview or Ctrl+C in terminal to stop."
    "$VENV_PY" run_hand_mouse.py --live
else
    echo "Tests passed. Live mode was not started."
fi
