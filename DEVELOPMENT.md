# 开发文档

本文档面向维护者和贡献者。用户安装与运行说明见 [README.md](README.md)，英文同步版本见 [DEVELOPMENT.en.md](DEVELOPMENT.en.md)。

## 设计目标

项目服务于通用桌面交互，优先考虑低认知负担、低误触发和可解释性：

- 不训练用户专属手势模型。
- 不识别复杂的逐指动作。
- 用左右手标签、手掌是否张开和拇指姿态完成检测。
- 检测器只产生抽象动作，系统输入事件集中在单独的控制层。
- 默认 dry-run，只有显式传入 `--live` 才会操作当前电脑。

## 代码结构

```text
src/hand_mouse/
  cli.py         # 摄像头循环和命令行参数
  controller.py  # PyAutoGUI 输入事件、显示器边界和平台修饰键
  detectors.py   # 纯几何/时序手势检测器
  tracker.py     # MediaPipe Tasks API 和模型选择/缓存
  models/        # 随仓库分发的 hand_landmarker.task
tests/
  test_detectors.py
run_hand_mouse.py # 未安装项目时的源码入口
```

数据流为：

```text
摄像头帧 -> MediaPipe Tasks 关键点 -> HandPose -> 手势检测器 -> 抽象动作 -> PyAutoGUI
```

`tracker.py` 默认优先使用 `models/hand_landmarker.task`，因此源码克隆和 editable 安装都不依赖首次联网下载。仓库模型缺失时才回退到用户缓存和官方模型地址；发布或同步仓库时应保留该二进制文件。

## 动作契约

- `OpenPalmScrollDetector.update(finger_count, handedness, now)`：左手张开稳定 500ms 后返回 `1` 并按间隔持续返回，右手张开稳定 500ms 后返回 `-1` 并按间隔持续返回；手掌收起后停止。
- `HorizontalThumbClickDetector.update(thumb_horizontal, now)`：右手拇指横向姿态稳定达到 `--click-stable-time` 后返回 `True`，保持该状态或其他状态返回 `False`；离开该姿态后再次进入才会重新触发。
- `PeaceSignClickDetector.update(peace_sign, now)`：右手比耶姿态稳定达到 `--click-stable-time` 后返回 `True`，保持该状态或其他状态返回 `False`；松开后再次进入才会重新触发右键。
- `PinchPointerDetector.update(hands, now)`：右手拇指和食指捏合稳定后进入精细模式；分开后退出；整只右手暂时丢失时保留状态，由局部指尖追踪器决定是否继续。
- `PinchPointTracker`：捏合时保存最近的可靠帧和关键点，整只手关键点暂时丢失后才启动拇指尖和食指尖局部追踪，并输出两个指尖的中点；恢复识别后重新保存参考帧。
- `CursorMapper`：将捏合中点的归一化摄像头坐标映射到进入精细模式时鼠标所在显示器的完整边界；进入时保留当前鼠标位置并平滑消除初始偏差，当前模式不会自动切换显示器；死区以累计位移判断，停手后继续平滑收敛到最后有效目标。
- 任意一只手的拳头都会触发全局急停，重置滚动、点击、捏合状态和局部追踪器。
- `InputController` 是唯一负责发送真实输入事件的类，提供左键和右键发送方法。检测器和单元测试不能直接调用 PyAutoGUI。

## 本地开发

```bash
python3 -m venv .venv312
source .venv312/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

运行检查：

```bash
ruff check .
pytest
python -m hand_mouse --help
```

测试不需要摄像头、MediaPipe 模型或桌面权限。摄像头联调先使用默认 dry-run：

```bash
python -m hand_mouse
```

只有确认检测结果稳定后才使用：

```bash
python -m hand_mouse --live
```

## 阈值调节

参数都以归一化摄像头坐标或相对投影大小表示，避免绑定固定分辨率：

- `--scroll-stable-time`：张开手掌持续多久后确认滚动。
- `--scroll-repeat-interval`：连续滚动事件之间的间隔。
- `--click-stable-time`：右手拇指横向姿态持续多久后确认左键。
- `--pointer-stable-time` / `--pinch-stable-time`：右手拇指和食指捏合持续多久后进入鼠标模式，默认 300ms。
- `--cursor-smoothing`：摄像头绝对目标位置的平滑系数。
- `--fine-sensitivity`：低速时鼠标跟随目标的基础比例。
- `--cursor-max-gain`：高速时鼠标跟随目标的最大比例。
- `--cursor-acceleration-speed`：达到最大增益时的归一化手部速度。
- `--cursor-deadzone`：忽略静止抖动的最小归一化位移。

跟随比例使用平方曲线：`base_gain + (max_gain - base_gain) * speed_ratio^2`，并限制在 `0..1`。进入精细模式时，映射器记录当前鼠标位置与手指绝对目标之间的偏差，在短暂过渡期内逐步消除该偏差，因此不会在识别瞬间跳到目标位置。显示器边界来自完整显示器范围，而不是排除菜单栏、Dock 或任务栏后的工作区。

误触发时提高 `--scroll-stable-time`，并增加光照或扩大摄像头取景区域。

## 新增输入后端

如果需要替换 PyAutoGUI：

1. 在 `controller.py` 中实现相同的 `scroll`、`left_click` 和 `right_click` 方法。
2. 保持 `--live` 作为真实输入的唯一开关。
3. 在没有桌面环境的 CI 中保持可导入、可测试。
4. 为平台权限、焦点窗口和失败恢复补充文档。

## 发布检查清单

- 更新 `pyproject.toml`、`src/hand_mouse/__init__.py` 和 `CHANGELOG.md` 版本。
- 运行 `ruff check .` 和 `pytest`。
- 在至少一个目标平台上完成 dry-run 摄像头测试。
- 在目标浏览器、文件管理器、办公软件或其他桌面应用中分别验证滚动、左键单击和右键单击。
- 验证没有 `--live` 时不会发送系统输入事件。
- 检查依赖和新增文件的许可证。
- 创建 Git tag，并在 GitHub Release 中记录已验证的平台和已知限制。
