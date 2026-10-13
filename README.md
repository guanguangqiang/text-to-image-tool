# Script2Gif

Script2Gif 是一个本地优先的 Windows 桌面工具：用户输入剧本，程序通过
`qwen3.8-flash` 生成结构化分镜，通过 `wan2.7-image-pro` 生成关键帧，再使用本地
FFmpeg 制作运镜动画并导出 MP4 和 GIF。

程序不使用数据库，也不需要部署服务端。项目、图片和成品保存在用户选择的本地目录；
阿里云 API Key 存放在 Windows Credential Manager 中，不写入项目和配置文件。

## 当前功能

- 新建、保存和打开本地项目
- 剧本导入和可编辑分镜表格
- Qwen OpenAI 兼容接口结构化生成分镜
- Wan2.7 异步生成关键帧及任务状态持久化
- 角色参考图导入和多图参考
- 相同请求内容哈希缓存
- FFmpeg 平移、缩放、字幕、MP4 拼接和 GIF 调色板导出
- 日志轮转、密钥脱敏、缓存与临时文件自动清理
- PyInstaller Windows `onedir` 打包

## 本地开发

要求 Python 3.9+，推荐 Python 3.12。

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install -e '.[dev,build]'
python main.py
```

首次启动后打开“设置”，填写：

1. 阿里云百炼 Workspace ID；
2. 对应地域的 API Key；
3. 本地 FFmpeg 路径（没有随安装包分发时必填）。

北京地域接口地址由程序按以下格式生成：

```text
https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com
```

也可以在开发环境通过 `DASHSCOPE_API_KEY` 环境变量提供密钥。

## 项目数据

每个作品都是可迁移的独立目录：

```text
project/
├── project.json
├── script.txt
├── characters/
├── shots/
├── assets/
│   ├── references/
│   ├── keyframes/
│   ├── videos/
│   └── audio/
├── jobs/
├── temp/
├── outputs/
└── logs/
```

应用日志、缓存和临时目录位于系统的用户应用数据目录。日志单文件最大 10 MB，保留
5 份；缓存默认上限 5 GB，过期缓存默认保留 30 天。

## 测试

```bash
pytest
ruff check src tests main.py launcher.py
```

真实模型调用不会进入自动测试，需要用户自己的 API Key。

## Windows 打包

`resources/ffmpeg/` 为空时，目标机器必须安装 FFmpeg，或让用户在设置中选择
`ffmpeg.exe`。如需随软件分发，将有合法分发许可的 Windows FFmpeg 二进制放到：

```text
resources/ffmpeg/ffmpeg.exe
```

然后在 Windows 10/11 x64 构建机运行：

```bat
build_windows.bat
```

输出目录：

```text
dist\Script2Gif\Script2Gif.exe
dist\installer\Script2Gif-Setup-0.2.0.exe    # 构建机安装 Inno Setup 时生成
```

PyInstaller 不是跨平台编译器，因此 Windows EXE 必须在 Windows 或 Windows CI 中构建。

## 安全说明

- 不要将开发者自己的 API Key 写入 EXE 或源码。
- 对外分发时使用 BYOK：每位用户输入自己的百炼 API Key。
- `project.json` 和日志不会记录 API Key。
- 发布前应对安装包签名，并确认所分发 FFmpeg 构建的许可证要求。
