# 贡献指南

欢迎提交问题、改进建议和代码。英文同步版本见 [CONTRIBUTING.en.md](CONTRIBUTING.en.md)。

## 提交 Issue 前

- 搜索已有 Issue，避免重复报告。
- 记录操作系统、Python 版本、摄像头位置、光照和运行命令。
- 不要上传包含人脸、屏幕内容或其他隐私信息的摄像头截图。
- 区分 dry-run 中的识别错误和 `--live` 下的系统输入权限问题。

## 提交代码

```bash
python -m pip install -e ".[dev]"
ruff check .
pytest
```

新检测逻辑需要有不依赖摄像头的单元测试。真实鼠标事件只能通过 `InputController` 发送，测试默认不得开启 `--live`。

提交信息建议使用简短、明确的动词开头，例如 `fix: reduce fist tap false positives`。

## 行为和许可证

请保持尊重和可复现的讨论。提交代码即表示你同意代码按本项目 [MIT License](LICENSE) 发布。
