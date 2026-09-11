# 安全说明 / Security

## 中文

本项目会读取摄像头，并在使用 `--live` 时向当前获得焦点的应用发送鼠标或快捷键事件。请先使用默认 dry-run，确认手势稳定后再开启真实输入。

请不要在公开 Issue 中提交摄像头画面、个人信息、屏幕内容或系统日志中的敏感数据。发现可能导致任意输入注入、依赖供应链或权限绕过的问题，请通过私下渠道联系维护者，而不是先公开细节。

## English

This project reads a webcam and, with `--live`, sends mouse or shortcut events to the currently focused application. Use the default dry-run mode first and enable live input only after the gestures are stable.

Do not include camera frames, personal information, screen content, or sensitive system logs in public issues. Report possible arbitrary-input injection, dependency-supply-chain, or permission-bypass problems privately to the maintainer before public disclosure.
