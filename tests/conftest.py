from types import SimpleNamespace

import numpy as np
import pytest

from hand_mouse.detectors import make_pose


@pytest.fixture
def standing_hand():
    def pose(angle=0.0, shift=(0.0, 0.0), side="left", tips=(8, 12, 16, 20)):
        points = np.zeros((21, 3), dtype=np.float32)
        points[0, :2] = (0.5, 0.85)
        points[3, :2], points[4, :2] = (0.42, 0.72), (0.46, 0.74)
        for x, mcp, pip, dip, tip in (
            (0.4, 5, 6, 7, 8), (0.5, 9, 10, 11, 12),
            (0.6, 13, 14, 15, 16), (0.7, 17, 18, 19, 20),
        ):
            points[mcp, :2] = (x, 0.6)
            points[pip, :2] = (x, 0.45 if tip in tips else 0.52)
            points[dip, :2] = (x, 0.32 if tip in tips else 0.66)
            points[tip, :2] = (x, 0.22 if tip in tips else 0.72)
        radians = np.deg2rad(angle)
        rotation = np.array(((np.cos(radians), -np.sin(radians)), (np.sin(radians), np.cos(radians))))
        wrist = points[0, :2].copy()
        points[:, :2] = (points[:, :2] - wrist) @ rotation.T + wrist + shift
        return make_pose([SimpleNamespace(x=x, y=y, z=z) for x, y, z in points], side)

    return pose
