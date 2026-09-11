# 开发文档

本文档面向维护者和贡献者。用户安装与运行说明见 [README.md](README.md)，英文同步版本见 [DEVELOPMENT.en.md](DEVELOPMENT.en.md)。

## 设计目标

项目服务于通用桌面交互，优先考虑低认知负担、低误触发和可解释性：

- 不训练用户专属手势模型。
- 不识别复杂的逐指动作。
- 用手之间的距离、手掌中心位移和拳头投影大小变化完成检测。
- 检测器只产生抽象动作，系统输入事件集中在单独的控制层。
- 默认 dry-run，只有显式传入 `--live` 才会操作当前电脑。

## 代码结构

```text
src/hand_mouse/
  cli.py         # 摄像头循环、MediaPipe 适配和命令行参数
  controller.py  # PyAutoGUI 输入事件和平台修饰键
  detectors.py   # 纯几何/时序手势检测器
tests/
  test_detectors.py
run_hand_mouse.py # 未安装项目时的源码入口
```

数据流为：

```text
摄像头帧 -> MediaPipe 关键点 -> HandPose -> 手势检测器 -> 抽象动作 -> PyAutoGUI
```

## 动作契约

- `ZoomDetector.update(hands, now)`：返回 `1` 表示双手分开、放大；返回 `-1` 表示双手靠近、缩小；返回 `0` 表示没有动作。
- `SwipeDetector.update(center, now)`：返回 `1` 表示向上滚动；返回 `-1` 表示向下滚动；返回 `0` 表示没有动作。
- `FistTapDetector.update(pose, now)`：返回 `left_click` 或 `right_click` 字符串列表。两次脉冲会在计数窗口结束后确认左键，三次脉冲会立即确认右键。
- `InputController` 是唯一负责发送真实输入事件的类。检测器和单元测试不能直接调用 PyAutoGUI。

## 本地开发

```bash
python3 -m venv .venv
source .venv/bin/activate
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

- `--zoom-threshold`：双手距离变化阈值。
- `--swipe-distance`：挥手的最小垂直位移。
- `--swipe-speed`：挥手的最小速度。
- `--pulse-threshold`：拳头投影大小相对基线的变化阈值。
- `--tap-window`：两次或三次拳头脉冲的最大间隔。

使用距离变远时，优先降低 `--swipe-distance` 和 `--pulse-threshold`；误触发时反向调高，并增加光照或扩大摄像头取景区域。

## 新增输入后端

如果需要替换 PyAutoGUI：

1. 在 `controller.py` 中实现相同的 `scroll`、`zoom`、`left_click` 和 `right_click` 方法。
2. 保持 `--live` 作为真实输入的唯一开关。
3. 在没有桌面环境的 CI 中保持可导入、可测试。
4. 为平台权限、焦点窗口和失败恢复补充文档。

## 发布检查清单

- 更新 `pyproject.toml`、`src/hand_mouse/__init__.py` 和 `CHANGELOG.md` 版本。
- 运行 `ruff check .` 和 `pytest`。
- 在至少一个目标平台上完成 dry-run 摄像头测试。
- 在目标浏览器、文件管理器、办公软件或其他桌面应用中分别验证滚动、缩放、左键和右键。
- 验证没有 `--live` 时不会发送系统输入事件。
- 检查依赖和新增文件的许可证。
- 创建 Git tag，并在 GitHub Release 中记录已验证的平台和已知限制。
