# FastAPI Service

一个面向实际项目的轻量 FastAPI 骨架，包含配置管理、API 版本、统一异常响应、
请求 ID、日志、健康检查、测试与 Docker 支持。

## 快速开始

要求 Python 3.9+。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
uvicorn app.main:app --reload
```

启动后可访问：

- Swagger UI: <http://127.0.0.1:8000/docs>
- 健康检查: <http://127.0.0.1:8000/health>
- 示例接口: <http://127.0.0.1:8000/api/v1/examples/ping>

生产环境默认关闭 Swagger、ReDoc 与 OpenAPI 地址。如需临时开启，可设置
`APP_DEBUG=true`。

## 常用命令

```bash
# 测试
pytest

# 静态检查
ruff check .
ruff format --check .

# Docker
docker build -t fastapi-service .
docker run --rm -p 8000:8000 --env-file .env fastapi-service
```

## 目录结构

```text
app/
├── api/                 # 路由与 API 版本
├── core/                # 配置、日志、中间件、异常
├── schemas/             # Pydantic 请求/响应模型
└── main.py              # 应用工厂与 FastAPI 实例
tests/                   # pytest 测试
```

新增业务模块时，建议将业务逻辑放到 `app/services/`，数据访问放到
`app/repositories/`，路由函数只负责 HTTP 参数转换与调用编排。

## Windows EXE

Windows 用户无需安装 Python。双击生成的 `FastAPI-Service.exe` 后，程序会：

1. 在本机随机可用端口启动服务；
2. 自动打开默认浏览器中的 Swagger 页面；
3. 显示一个包含“打开浏览器”和“退出”按钮的小窗口。

在 Windows 10/11 构建机中双击 `build_windows.bat`，完成后文件位于：

```text
dist\FastAPI-Service.exe
```

也可以将项目推送到 GitHub，然后手动运行 `Build Windows executable` 工作流。
构建产物会作为 `FastAPI-Service-windows-x64` Artifact 提供下载。

PyInstaller 不是跨平台编译器，因此 Windows `.exe` 必须在 Windows 环境中构建。
应用运行日志保存在：

```text
%LOCALAPPDATA%\FastAPI-Service\logs\app.log
```

如果 `FastAPI-Service.exe` 同目录存在 `.env`，程序会自动读取它。

构建完成后，在 PowerShell 中运行自动冒烟测试：

```powershell
powershell -ExecutionPolicy Bypass -File .\verify_windows.ps1
```

脚本会启动 EXE、验证 `/health` 和 `/api/v1/examples/ping`，然后自动结束测试进程。

## macOS 测试应用

macOS 不使用 `.exe`，对应的交付物是可双击运行的 `FastAPI-Service.app`。
应用已经包含 Python 解释器和全部依赖，因此目标 Mac 不需要安装 Python。

### 在当前 Mac 构建

```bash
chmod +x build_macos.sh verify_macos.sh
./build_macos.sh
```

脚本会运行单元测试、构建应用、执行打包后的接口冒烟测试，并生成与当前
Mac 芯片架构对应的 ZIP：

```text
dist/FastAPI-Service-macos-arm64.zip
```

Intel Mac 上的文件名为：

```text
dist/FastAPI-Service-macos-x86_64.zip
```

也可以将项目推送到 GitHub，手动运行 `Build macOS applications` 工作流。
工作流会同时生成两个 Artifact：

- `FastAPI-Service-macos-arm64`：Apple 芯片（M1/M2/M3/M4 等）
- `FastAPI-Service-macos-x86_64`：Intel 芯片

GitHub 当前为这两个构建分别使用 arm64 和 Intel macOS 运行器。

### 在没有 Python 的 Mac 上验证

1. 在目标 Mac 的“关于本机”中确认芯片类型，并复制对应的 ZIP 文件；
2. 解压 ZIP，得到 `FastAPI-Service.app`；
3. 第一次运行时右键应用并选择“打开”，然后确认“打开”；
4. 应用会自动启动本地服务并打开 Swagger 页面；
5. 访问 `/health`，确认返回的 `status` 为 `ok`；
6. 在窗口中点击“退出”，确认服务随应用一起关闭。

如果系统仍然拦截未公证应用，可前往“系统设置 → 隐私与安全性”，在安全提示中
选择“仍要打开”。测试版本采用临时签名；正式对外发布时应使用 Apple Developer ID
证书签名并提交 Apple 公证。

应用日志位于：

```text
~/Library/Logs/FastAPI-Service/app.log
```

若需自动验证当前已构建的 `.app`，可运行：

```bash
./verify_macos.sh
```

PyInstaller 不是跨平台编译器；macOS `.app` 必须在对应架构的 Mac 或 GitHub macOS
运行器上构建。
