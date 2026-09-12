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
  controller.py  # PyAutoGUI 输入事件和平台修饰键
  detectors.py   # 纯几何/时序手势检测器
  tracker.py     # MediaPipe Tasks API 和模型缓存
tests/
  test_detectors.py
run_hand_mouse.py # 未安装项目时的源码入口
```

数据流为：

```text
摄像头帧 -> MediaPipe Tasks 关键点 -> HandPose -> 手势检测器 -> 抽象动作 -> PyAutoGUI
```

## 动作契约

- `OpenPalmScrollDetector.update(finger_count, handedness, now)`：左手张开稳定后返回 `1` 表示向上滚动，右手张开稳定后返回 `-1` 表示向下滚动；保持手掌张开不会重复返回动作。
- `ThumbUpClickDetector.update(thumbs_up, now)`：拇指向上稳定达到 `--click-stable-time` 后返回 `True`，保持该状态或其他状态返回 `False`；离开拇指向上后再次进入才会重新触发。
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

- `--scroll-stable-time`：张开手掌持续多久后确认滚动。
- `--click-stable-time`：拇指向上持续多久后确认左键。

误触发时提高 `--scroll-stable-time`，并增加光照或扩大摄像头取景区域。

## 新增输入后端

如果需要替换 PyAutoGUI：

1. 在 `controller.py` 中实现相同的 `scroll` 和 `left_click` 方法。
2. 保持 `--live` 作为真实输入的唯一开关。
3. 在没有桌面环境的 CI 中保持可导入、可测试。
4. 为平台权限、焦点窗口和失败恢复补充文档。

## 发布检查清单

- 更新 `pyproject.toml`、`src/hand_mouse/__init__.py` 和 `CHANGELOG.md` 版本。
- 运行 `ruff check .` 和 `pytest`。
- 在至少一个目标平台上完成 dry-run 摄像头测试。
- 在目标浏览器、文件管理器、办公软件或其他桌面应用中分别验证滚动和左键单击。
- 验证没有 `--live` 时不会发送系统输入事件。
- 检查依赖和新增文件的许可证。
- 创建 Git tag，并在 GitHub Release 中记录已验证的平台和已知限制。
