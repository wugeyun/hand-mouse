# Hand Mouse

一个面向通用桌面软件的粗粒度摄像头手势输入控制器。项目只识别幅度较大的动作，不做精细的逐指手势分类，目标是用少量动作替代常用的滚轮和鼠标点击。

[English README](README.en.md) | [开发文档](DEVELOPMENT.md) | [贡献指南](CONTRIBUTING.md)

## 当前状态

这是一个可运行的 MVP，适合在真实使用前进行摄像头、光线和手势距离调试。当前功能已经拆成可测试的手势检测器、输入事件层和命令行入口，但还没有打包成桌面安装程序。

## 手势

| 手势 | 输出动作 | 说明 |
| --- | --- | --- |
| 左手掌张开并保持 | 页面持续向上滚动 | 稳定约 1000ms 后开始，保持手掌继续滚动 |
| 右手掌张开并保持 | 页面持续向下滚动 | 稳定约 1000ms 后开始，保持手掌继续滚动 |
| 右手拇指横向伸出 | 鼠标左键单击 | 其他手指收起，稳定约 500ms 后触发一次 |
| 右手比耶 | 鼠标右键单击 | 食指和中指伸直、其他长手指收起，稳定约 500ms 后触发一次 |
| 右手拇指和食指捏合 | 精细鼠标移动 | 稳定约 500ms 后进入，捏合中点控制光标；分开后停止 |
| 任意一只手握拳 | 全局急停 | 立即停止滚动、点击和鼠标移动 |

滚动动作不再依赖上下挥动方向，而是根据左右手固定目标方向。手掌稳定 1000ms 后开始连续滚动，手掌收起或离开画面后立即停止。

右手拇指和食指捏合并保持约 500ms 后进入精细鼠标移动模式，两个指尖的中点就是鼠标指针；分开后立即停止。捏合开始时保留当前鼠标位置，MediaPipe 暂时丢失整只手后会尝试继续追踪两个指尖。

鼠标移动会把捏合中点的归一化位置映射到当前鼠标所在显示器的完整范围，包含菜单栏和 Dock/任务栏，因此捏合点移动到摄像头边缘时鼠标也能到达屏幕边缘。进入精细模式时保留当前鼠标位置，并用短暂平滑过渡消除初始偏差，避免识别瞬间跳动。多显示器在每次进入精细模式时按鼠标所在的显示器计算，当前模式不会自动跨屏；快速移动仍会提高目标跟随速度，静止时的小幅抖动会被死区过滤。

任意一只手握拳都会触发全局急停，立即停止滚动、点击、捏合移动和局部指尖追踪。拳头释放后，所有手势都必须重新满足各自的稳定时间。

输出事件会发送给当前获得焦点的应用。只要目标应用能够响应对应的标准鼠标事件，浏览器、macOS 访达、Windows 文件管理器、PPT、图片查看器和各种办公软件都可以使用；项目不会判断当前应用是否支持某个动作，最终效果取决于目标应用自己的鼠标行为。

## 运行条件与安装

运行顺序是：确认运行条件、获取项目、选择正确的 Python、创建虚拟环境、安装依赖、先 dry-run、再真实测试。

项目要求 Python 3.10 或更高版本，推荐 Python 3.12。不要只看 `python3` 这个命令名，必须先确认它实际对应的版本。

本文档统一使用 `.venv312` 作为虚拟环境目录名。你可以根据实际 Python 版本和个人习惯改成其他名称，但后续命令中的目录名必须保持一致。

### 1. 获取项目

克隆正式仓库：

```bash
git clone https://github.com/wugeyun/hand-mouse.git
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
python3.12 -m venv .venv312
source .venv312/bin/activate
```

如果确认 `python3` 本身已经是 3.10+，也可以使用：

```bash
python3 -m venv .venv312
source .venv312/bin/activate
```

激活后再次确认，确保没有误用系统 Python：

```bash
python --version
python -c "import sys; print(sys.executable)"
```

输出应为 Python 3.10+，解释器路径应位于项目的 `.venv312` 目录下。

### 3. Windows PowerShell：检查并选择 Python

```powershell
py --list
py -3.12 --version
```

使用 Python 3.12 创建并激活虚拟环境：

```powershell
py -3.12 -m venv .venv312
.\.venv312\Scripts\Activate.ps1
python --version
python -c "import sys; print(sys.executable)"
```

如果 PowerShell 禁止执行激活脚本，可以直接使用 `.venv312` 中的 Python，或按系统提示调整当前用户的执行策略。不要因此改用未确认版本的全局 `python`。

### 4. 安装依赖和确认模型

确认虚拟环境已经激活后执行：

```bash
python -m pip install --upgrade pip
python -m pip install -e .
python -m hand_mouse --version
```

仓库已经包含 `src/hand_mouse/models/hand_landmarker.task`，因此正常克隆后不需要再次下载模型。程序会按以下顺序寻找模型：命令行 `--model PATH`、仓库内置模型、用户缓存目录，最后才尝试从 MediaPipe 官方地址下载。模型只用于本地手部关键点检测，摄像头画面不会上传。

确认仓库内模型存在：

macOS：

```bash
test -s src/hand_mouse/models/hand_landmarker.task && echo "model is ready"
```

Windows PowerShell：

```powershell
Test-Path .\src\hand_mouse\models\hand_landmarker.task
```

维护代码或运行测试时，安装开发依赖：

```bash
python -m pip install -e ".[dev]"
```

### 5. macOS：先运行 dry-run

dry-run 只打开摄像头并打印识别到的动作，不会移动真实鼠标：

```bash
python run_hand_mouse.py
```

依次测试：

- 左手掌张开保持约 1000ms，随后终端应持续显示 `scroll up`。
- 右手掌张开保持约 1000ms，随后终端应持续显示 `scroll down`。
- 右手拇指横向伸出保持约 500ms，终端应显示一次 `left click`；保持该姿态不会连续点击。
- 右手比耶保持约 500ms，终端应显示一次 `right click`；保持该姿态不会连续触发。
- 右手拇指和食指捏合保持约 500ms，预览中的 `POINTER` 应变为 `fine`；分开后应停止移动。
- 精细模式下将捏合点移动到摄像头画面的四个边缘，鼠标应在当前显示器的对应边缘停止。
- 左手或右手握拳，预览中的 `FIST STOP` 应变为 `True`，所有动作应立即停止。

只有 dry-run 的输出稳定后，才进行真实输入测试。

### 6. Windows：先运行 dry-run

在已激活的 PowerShell 中，从仓库根目录执行：

```powershell
python run_hand_mouse.py
```

确认 dry-run 稳定后，再打开真实输入：

```powershell
python run_hand_mouse.py --live --no-preview
```

如果 PowerShell 不允许激活脚本，可以不激活虚拟环境，直接使用虚拟环境中的解释器：

```powershell
.\.venv312\Scripts\python.exe run_hand_mouse.py
.\.venv312\Scripts\python.exe run_hand_mouse.py --live --no-preview
```

测试完成后在 PowerShell 中按 `Ctrl+C` 停止程序。

### 7. macOS：真实输入测试

先准备一个安全的目标应用，例如浏览器普通网页、macOS 访达中的临时文件夹，或一张不重要的图片。然后运行：

```bash
python run_hand_mouse.py --live --no-preview
```

程序启动后切换到目标应用，确保目标窗口获得焦点，再测试滚动、左键和右键单击。所有事件都会发送给当前焦点窗口，项目不会判断目标应用是否支持某个动作。

测试完成后切回终端按 `Ctrl+C` 停止程序。

### 8. Windows：真实输入测试

先准备一个安全的目标应用，例如浏览器普通网页、Windows 文件管理器中的临时目录，或一张不重要的图片。然后运行：

```powershell
python run_hand_mouse.py --live --no-preview
```

程序启动后切换到目标应用，确保目标窗口获得焦点，再测试滚动、左键和右键单击。测试完成后切回 PowerShell 按 `Ctrl+C` 停止程序。

### 9. 权限和常见问题

- macOS：在“系统设置 -> 隐私与安全性”中给运行程序的终端或应用授予“相机”和“辅助功能”权限。
- Windows：允许 Python 或终端访问摄像头；PowerShell 可以用 `py --list` 检查已安装版本。
- `No module named cv2` 或 `mediapipe`：确认已经激活 `.venv312`，并使用 `python -m pip install -e .` 安装，不要使用另一个 Python 的 `pip`。
- 模型文件被删除或克隆不完整：确认 `src/hand_mouse/models/hand_landmarker.task` 存在；也可以手动准备模型后使用 `python run_hand_mouse.py --model PATH`。
- `Cannot open camera 0`：确认摄像头权限，或尝试 `--camera 1`、`--camera 2`。
- dry-run 正常但 live 没反应：优先检查 macOS“辅助功能”权限和当前焦点窗口。

## 一键部署和运行

仓库根目录提供两个平台脚本。脚本会自动检查 Python、选择或创建虚拟环境、安装项目和测试依赖、确认内置模型、运行测试，然后在确认后启动正式鼠标控制。

macOS：双击 `run_macos.command`。如果系统提示没有执行权限，在终端中从项目根目录执行一次：

```bash
chmod +x run_macos.command
open run_macos.command
```

Windows：双击 `run_windows.bat`。也可以在 PowerShell 中运行：

```powershell
.\run_windows.bat
```

首次运行时，脚本会优先查找 Python 3.12、3.11、3.10；如果没有符合要求的版本，会提供版本选择。macOS 使用 Homebrew 安装，Windows 使用 `winget` 安装；如果对应工具不可用，脚本会打开 Python 官方下载页面并提示重新运行。虚拟环境目录默认是 `.venv312`，在提示处直接按回车即可，也可以输入自定义名称。

首次部署完成后，脚本会保存当前平台的本地环境配置。以后再次双击时，确认跳过部署即可直接进入“运行测试”和“正式启动”两步；测试失败时不会启动真实鼠标事件。正式启动使用 `--live --no-preview`，运行期间按 `Ctrl+C` 停止。

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
  --scroll-amount 4 \
  --scroll-stable-time 1.00 \
  --scroll-repeat-interval 0.25 \
  --click-stable-time 0.50 \
  --pinch-stable-time 0.50 \
  --fine-sensitivity 0.35 \
  --cursor-max-gain 3.00 \
  --cursor-acceleration-speed 1.00 \
  --cursor-deadzone 0.0015
```

也可以直接运行源码入口：

```bash
python run_hand_mouse.py --help
```

## 权限和平台说明

- macOS：需要给运行程序的终端或应用授予“相机”和“辅助功能”权限。
- Windows：需要允许应用访问摄像头。
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
