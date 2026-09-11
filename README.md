# Hand Mouse

一个面向通用桌面软件的粗粒度摄像头手势输入控制器。项目只识别幅度较大的动作，不做精细的逐指手势分类，目标是用少量动作替代常用的滚轮、缩放和鼠标点击。

[English README](README.en.md) | [开发文档](DEVELOPMENT.md) | [贡献指南](CONTRIBUTING.md)

## 当前状态

这是一个可运行的 MVP，适合在真实使用前进行摄像头、光线和手势距离调试。当前功能已经拆成可测试的手势检测器、输入事件层和命令行入口，但还没有打包成桌面安装程序。

## 手势

| 手势 | 输出动作 | 说明 |
| --- | --- | --- |
| 双手向外 | 放大 | 默认发送 `Ctrl/Command + 鼠标滚轮向上` |
| 双手向内 | 缩小 | 默认发送 `Ctrl/Command + 鼠标滚轮向下` |
| 单手向上挥 | 鼠标向上滚动 | 每次明显挥动只触发一次 |
| 单手向下挥 | 鼠标向下滚动 | 每次明显挥动只触发一次 |
| 拳头向摄像头靠近再离开 2 次 | 鼠标左键 | 需要在短时间窗口内完成 |
| 拳头向摄像头靠近再离开 3 次 | 鼠标右键 | 需要在短时间窗口内完成 |

“拳头敲击”在本项目中定义为拳头在画面中的投影明显变大再恢复，也就是相对摄像头前后移动；不是识别真实的碰撞。单次拳头脉冲不会触发动作，避免使用过程中误点击。

输出事件会发送给当前获得焦点的应用。只要目标应用能够响应对应的标准鼠标或键盘事件，浏览器、macOS 访达、Windows 文件管理器、PPT、图片查看器和各种办公软件都可以使用；项目不会判断当前应用是否支持某个动作，最终效果取决于目标应用自己的鼠标/快捷键行为。对于使用 `Ctrl/Command +` 和 `Ctrl/Command -` 的应用，可以使用 `--zoom-mode keys`。

## 运行条件与安装

运行顺序是：确认运行条件、获取项目、选择正确的 Python、创建虚拟环境、安装依赖、先 dry-run、再真实测试。

项目要求 Python 3.10 或更高版本，推荐 Python 3.12。不要只看 `python3` 这个命令名，必须先确认它实际对应的版本。

### 1. 获取项目

把下面的 `YOUR_GITHUB_USERNAME` 替换成实际仓库所有者：

```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/hand-mouse.git
cd hand-mouse
```

### 2. macOS：检查并选择 Python

```bash
command -v python3
python3 --version
command -v python3.12
python3.12 --version
```

选择规则：

- 如果 `python3 --version` 已经是 3.10 或更高，可以使用 `python3`。
- 如果 `python3` 是 3.9 或更低，但 `python3.12` 存在，使用 `python3.12`。
- 如果没有任何 3.10+ 解释器，先安装 Python 3.10+，再回到这一步确认。

例如使用 Python 3.12 创建虚拟环境：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

如果确认 `python3` 本身已经是 3.10+，也可以使用：

```bash
python3 -m venv .venv
source .venv/bin/activate
```

激活后再次确认，确保没有误用系统 Python：

```bash
python --version
python -c "import sys; print(sys.executable)"
```

输出应为 Python 3.10+，解释器路径应位于项目的 `.venv` 目录下。

### 3. Windows PowerShell：检查并选择 Python

```powershell
py --list
py -3.12 --version
```

使用 Python 3.12 创建并激活虚拟环境：

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python --version
python -c "import sys; print(sys.executable)"
```

如果 PowerShell 禁止执行激活脚本，可以直接使用虚拟环境中的 Python，或按系统提示调整当前用户的执行策略。不要因此改用未确认版本的全局 `python`。

### 4. 安装依赖

确认虚拟环境已经激活后执行：

```bash
python -m pip install --upgrade pip
python -m pip install -e .
python -m hand_mouse --version
```

维护代码或运行测试时，安装开发依赖：

```bash
python -m pip install -e ".[dev]"
```

### 5. 先运行 dry-run

dry-run 只打开摄像头并打印识别到的动作，不会移动真实鼠标：

```bash
python run_hand_mouse.py
```

依次测试：

- 双手向外或向内，终端应显示 `zoom in` 或 `zoom out`。
- 单手向上或向下挥，终端应显示 `scroll up` 或 `scroll down`。
- 拳头向摄像头靠近再离开两次，计数窗口结束后应显示 `left click`。
- 拳头向摄像头靠近再离开三次，应显示 `right click`。

只有 dry-run 的输出稳定后，才进行真实输入测试。

### 6. 真实输入测试

先准备一个安全的目标应用，例如浏览器普通网页、macOS 访达中的临时文件夹、Windows 文件管理器中的临时目录，或一张不重要的图片。然后运行：

```bash
python run_hand_mouse.py --live --no-preview
```

程序启动后切换到目标应用，确保目标窗口获得焦点，再测试滚动、缩放和点击。所有事件都会发送给当前焦点窗口，项目不会判断目标应用是否支持某个动作。

测试完成后切回终端按 `Ctrl+C` 停止程序。缩放不生效时，可改用：

```bash
python run_hand_mouse.py --live --no-preview --zoom-mode keys
```

### 7. 权限和常见问题

- macOS：在“系统设置 -> 隐私与安全性”中给运行程序的终端或应用授予“相机”和“辅助功能”权限。
- Windows：允许 Python 或终端访问摄像头；PowerShell 可以用 `py --list` 检查已安装版本。
- `No module named cv2` 或 `mediapipe`：确认已经激活 `.venv`，并使用 `python -m pip install -e .` 安装，不要使用另一个 Python 的 `pip`。
- `Cannot open camera 0`：确认摄像头权限，或尝试 `--camera 1`、`--camera 2`。
- dry-run 正常但 live 没反应：优先检查 macOS“辅助功能”权限和当前焦点窗口。

## 运行

安装完成后，也可以使用下面的命令启动 dry-run：

```bash
python -m hand_mouse
```

确认识别稳定后，使用 `--live` 开启真实鼠标事件：

```bash
python -m hand_mouse --live
```

全屏工作或不希望预览窗口干扰当前应用时，可以关闭预览窗口，使用 `Ctrl+C` 停止：

```bash
python -m hand_mouse --live --no-preview
```

常用调节项：

```bash
python -m hand_mouse --live \
  --zoom-mode keys \
  --scroll-amount 4 \
  --zoom-amount 1 \
  --swipe-distance 0.20 \
  --pulse-threshold 0.16
```

也可以直接运行源码入口：

```bash
python run_hand_mouse.py --help
```

## 权限和平台说明

- macOS：需要给运行程序的终端或应用授予“相机”和“辅助功能”权限。
- Windows：需要允许应用访问摄像头；不同应用对 `Ctrl + 滚轮` 的支持不同。
- 摄像头画面默认在本机处理，不上传视频；依赖库仍应按各自许可证和隐私说明使用。

## 开发

项目结构、检测器状态机、测试命令和发布检查见 [DEVELOPMENT.md](DEVELOPMENT.md)。

```bash
python -m pip install -e ".[dev]"
ruff check .
pytest
```

测试不需要摄像头，也不会发送真实鼠标事件。真实摄像头、系统权限和具体目标应用需要在目标机器上单独验收。

## 许可证

本项目使用 [MIT License](LICENSE)。
