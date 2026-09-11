# Contributing

Bug reports, improvement ideas, and code contributions are welcome. The Chinese primary version is [CONTRIBUTING.md](CONTRIBUTING.md).

## Before opening an issue

- Search existing issues first.
- Include the OS, Python version, camera position, lighting, and command used.
- Do not upload camera screenshots containing faces, screen content, or other private information.
- Distinguish detector failures in dry-run from OS input-permission failures with `--live`.

## Before submitting code

```bash
python -m pip install -e ".[dev]"
ruff check .
pytest
```

New detector logic must include camera-free unit tests. Real mouse events may only be sent through `InputController`; tests must not enable `--live` by default.

Use short, imperative commit messages such as `fix: reduce fist tap false positives`.

## Conduct and license

Keep discussions respectful and reproducible. By submitting code, you agree that it is released under this project's [MIT License](LICENSE).
