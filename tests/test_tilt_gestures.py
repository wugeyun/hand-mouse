from dataclasses import replace

import pytest

from hand_mouse.detectors import LeftPalmTiltScrollDetector, is_emergency_fist


def arm(detector, hand, now=0.0):
    assert detector.update([hand], now) == 0
    assert detector.update([hand], now + 0.15) == 0
    assert detector.update([hand], now + 0.31) == 0


@pytest.mark.parametrize("angle, direction", [(32, -1), (-32, 1)])
def test_tilt_scrolls_once_and_return_to_center_does_not_scroll(standing_hand, angle, direction):
    detector = LeftPalmTiltScrollDetector()
    arm(detector, standing_hand())
    assert detector.update([standing_hand(angle=angle)], 0.4) == direction
    assert detector.update([standing_hand(angle=angle)], 0.5) == 0
    assert detector.update([standing_hand()], 0.6) == 0
    assert detector.update([standing_hand(angle=-angle)], 0.65) == 0
    assert detector.update([standing_hand(angle=-angle)], 0.8) == 0


def test_center_hold_rearms_for_another_tilt(standing_hand):
    detector = LeftPalmTiltScrollDetector()
    arm(detector, standing_hand())
    assert detector.update([standing_hand(angle=35)], 0.4) == -1
    assert detector.update([standing_hand()], 0.5) == 0
    assert detector.update([standing_hand()], 0.65) == 0
    assert detector.update([standing_hand()], 0.81) == 0
    assert detector.update([standing_hand(angle=-35)], 0.9) == 1
    assert detector.update([standing_hand(angle=-35)], 1.0) == 0


def test_short_center_pass_does_not_rearm(standing_hand):
    detector = LeftPalmTiltScrollDetector()
    arm(detector, standing_hand())
    assert detector.update([standing_hand(angle=35)], 0.4) == -1
    assert detector.update([standing_hand(angle=5)], 0.5) == 0
    assert detector.update([standing_hand(angle=-35)], 0.55) == 0
    assert detector.update([standing_hand(angle=-35)], 0.9) == 0


@pytest.mark.parametrize("angle", [-19.9, -15, -5, 0, 5, 15, 19.9])
def test_small_tilt_does_not_scroll(standing_hand, angle):
    detector = LeftPalmTiltScrollDetector()
    arm(detector, standing_hand())
    assert detector.update([standing_hand(angle=angle)], 0.4) == 0


@pytest.mark.parametrize("angle, direction", [(20, -1), (-20, 1)])
@pytest.mark.parametrize("hold", [0.099, 0.1])
def test_twenty_degrees_triggers_only_after_100ms_upright(standing_hand, angle, direction, hold):
    detector = LeftPalmTiltScrollDetector()
    assert detector.update([standing_hand()], 0) == 0
    assert detector.update([standing_hand()], hold) == 0
    assert detector.update([standing_hand(angle=angle)], hold + 0.01) == (direction if hold >= 0.1 else 0)


def test_return_to_center_rearms_at_exactly_100ms(standing_hand):
    detector = LeftPalmTiltScrollDetector()
    assert detector.update([standing_hand()], 0) == 0
    assert detector.update([standing_hand()], 0.1) == 0
    assert detector.update([standing_hand(angle=20)], 0.2) == -1
    assert detector.update([standing_hand()], 0.5) == 0
    assert detector.update([standing_hand()], 0.6) == 0
    assert detector.update([standing_hand(angle=-20)], 0.61) == 1


def test_translation_with_upright_palm_is_not_tilt(standing_hand):
    detector = LeftPalmTiltScrollDetector()
    arm(detector, standing_hand())
    for now, shift in ((0.4, (0.2, 0)), (0.5, (-0.2, 0)), (0.6, (0, -0.2))):
        assert detector.update([standing_hand(shift=shift)], now) == 0


@pytest.mark.parametrize("aspect_ratio", [0.75, 16 / 9, 2.0])
def test_tilt_angle_accounts_for_camera_aspect_ratio(standing_hand, aspect_ratio):
    detector = LeftPalmTiltScrollDetector()
    arm(detector, standing_hand())
    hand = standing_hand(angle=32)
    points = hand.points.copy()
    points[:, 0] = 0.5 + (points[:, 0] - 0.5) / aspect_ratio
    assert detector.update([replace(hand, points=points)], 0.4, frame_aspect_ratio=aspect_ratio) == -1


@pytest.mark.parametrize("angle", [35, -35, 90, 180])
def test_must_start_with_upright_palm(standing_hand, angle):
    detector = LeftPalmTiltScrollDetector()
    assert detector.update([standing_hand(angle=angle)], 0) == 0
    assert detector.update([standing_hand(angle=angle)], 0.31) == 0
    assert detector.update([standing_hand(angle=angle)], 0.4) == 0


@pytest.mark.parametrize("gap, direction", [(0.08, -1), (0.4, 0)])
def test_short_tracking_loss_preserves_readiness_long_loss_cancels_it(standing_hand, gap, direction):
    detector = LeftPalmTiltScrollDetector()
    arm(detector, standing_hand())
    assert detector.update([], 0.33) == 0
    assert detector.update([standing_hand(angle=35)], 0.33 + gap) == direction


def test_right_hand_tilt_does_not_scroll(standing_hand):
    detector = LeftPalmTiltScrollDetector()
    arm(detector, standing_hand(side="right"))
    assert detector.update([standing_hand(side="right", angle=35)], 0.4) == 0


@pytest.mark.parametrize("side", ["left", "right"])
def test_fist_still_stops_and_cancels_readiness(standing_hand, side):
    detector = LeftPalmTiltScrollDetector()
    arm(detector, standing_hand())
    fist = standing_hand(side=side, tips=())
    assert is_emergency_fist(fist)
    assert detector.update([fist, standing_hand(angle=35)], 0.4) == 0
    assert detector.update([standing_hand(angle=35)], 0.5) == 0


@pytest.mark.parametrize("tips", [(), (8,), (8, 12)])
def test_fist_single_finger_and_v_sign_do_not_prepare_scroll(standing_hand, tips):
    detector = LeftPalmTiltScrollDetector()
    assert detector.update([standing_hand(tips=tips)], 0) == 0
    assert detector.update([standing_hand(tips=tips)], 0.31) == 0
    assert detector.update([standing_hand(angle=35, tips=tips)], 0.4) == 0
