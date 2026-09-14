from hand_mouse.cli import strictly_increasing_timestamp


def test_timestamp_advances_when_frames_share_a_millisecond() -> None:
    assert strictly_increasing_timestamp(0, -1) == 0
    assert strictly_increasing_timestamp(0, 0) == 1
    assert strictly_increasing_timestamp(0, 1) == 2


def test_timestamp_catches_up_to_elapsed_time() -> None:
    assert strictly_increasing_timestamp(10, 2) == 10
