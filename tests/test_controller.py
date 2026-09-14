from hand_mouse.controller import scroll_delta


def test_scroll_delta_uses_native_windows_wheel_units() -> None:
    assert scroll_delta(1, 5, platform="win32") == 600
    assert scroll_delta(-1, 5, platform="win32") == -600


def test_scroll_delta_keeps_logical_units_on_macos() -> None:
    assert scroll_delta(1, 5, platform="darwin") == 5
    assert scroll_delta(-1, 5, platform="darwin") == -5
