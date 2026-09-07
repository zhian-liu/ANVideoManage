# 视频监控管理平台

统一接入各厂家家庭摄像机的 Web 管理平台。支持 **实时预览（多画面宫格）**、**录像存储与回放**、**云台 PTZ 控制**。

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.11+ · FastAPI · SQLAlchemy(async) · SQLite |
| 前端 | React 18 · TypeScript · Vite · Ant Design 5 · mpegts.js |
| 流媒体 | ZLMediaKit（拉流 / 转码 / MP4 录像） |
| 摄像机接入 | RTSP/ONVIF（已实现）+ 厂商云 API / 私有 SDK（预留适配器） |

## 编译环境

Windows 开发和打包建议使用 64 位环境：

| 工具 | 版本要求 | 用途 |
|------|----------|------|
| Git | 2.x 或更高 | 获取项目代码和 ZLMediaKit 子模块 |
| Python | 3.11 或更高 | 后端运行、语法检查和 PyInstaller 打包 |
| Node.js | 18 LTS 或更高 | 前端依赖安装和 Vite 构建 |
| npm | 随 Node.js 安装 | 安装前端依赖 |
| CMake | 3.20 或更高 | 生成 ZLMediaKit 工程 |
| Visual Studio | 2019/2022，安装“使用 C++ 的桌面开发” | 编译 Windows 版 ZLMediaKit |
| Inno Setup | 6.x（仅打包需要） | 生成 `VideoManageSetup.exe` |

ZLMediaKit 的 CMake 文件最低声明为 3.1.3，但 Windows 编译建议使用较新的 CMake 和 Visual Studio 2022。抓拍的后端回退方案还需要 FFmpeg；普通浏览器画面抓拍不依赖 FFmpeg。

首次准备代码时执行：

```powershell
git clone https://github.com/zhian-liu/ANVideoManage.git
cd ANVideoManage

# ZLMediaKit 不随主仓库提交，需要单独放到该目录
git clone https://github.com/ZLMediaKit/ZLMediaKit.git backend\ZLMediaKit
git -C backend\ZLMediaKit submodule update --init --recursive
```

如果 ZLMediaKit 已经存在，只需执行：

```powershell
git -C backend\ZLMediaKit submodule update --init --recursive
```

## 架构

```
浏览器(React) ──HTTP REST──▶ FastAPI ──REST API──▶ ZLMediaKit ──RTSP拉流──▶ 摄像机
      │                          │                        │
      └──HTTP-TS/HTTP-FLV/HLS────┘                        └──MP4录像 + WebHook回调──▶ 录像索引
```

## 目录结构

```
backend/            FastAPI 后端
  app/
    api/            auth / devices / streams / recordings / ptz / settings / zlm_hook
    adapters/       摄像机适配器（onvif 已实现，cloud/sdk 为模板）
    core/           JWT / 鉴权依赖
    models/         User / Device / Recording / AppSetting
    services/       ZLMediaKit 客户端、流代理同步、文件存储
    main.py         入口
frontend/           React 前端
config/             ZLMediaKit 配置
```

## 启动步骤

### 1. 编译并启动 ZLMediaKit

如果已有 ZLMediaKit Windows 预编译包，可以跳过编译，直接把 `MediaServer.exe` 放入 `backend\ZLMediaKit\release\windows\Debug\Release`。需要自行编译时，在项目根目录执行：

```powershell
cd backend\ZLMediaKit
git submodule update --init --recursive

# 生成 Visual Studio 2022 x64 工程
cmake -S . -B build -G "Visual Studio 17 2022" -A x64 `
  -DENABLE_API=ON `
  -DENABLE_HLS=ON `
  -DENABLE_MP4=ON `
  -DENABLE_RTPPROXY=ON `
  -DENABLE_WEBRTC=ON `
  -DENABLE_TESTS=OFF

# 编译 Release 配置
cmake --build build --config Release --parallel
cd ..\..
```

当前工程的 CMake 输出目录由 ZLMediaKit 自身配置决定，通常可执行文件位于 `backend\ZLMediaKit\release\windows\Debug\Release\MediaServer.exe`。复制配置并启动：

```powershell
Copy-Item config\zlmediakit.config.ini backend\ZLMediaKit\release\windows\Debug\Release\config.ini -Force
cd backend\ZLMediaKit\release\windows\Debug\Release
.\MediaServer.exe
```

也可以使用 ZLMediaKit 目录中已有的 `build.bat`，它会初始化子模块、生成 VS2022 工程并编译 Release 配置。首次启动前，确认配置中的 WebHook 地址、HTTP `8080`、RTSP `554` 和 RTMP `1935` 端口与本机环境一致。

### 2. 启动后端

```powershell
cd backend
py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env  # 按需修改，尤其是 ZLM_API_BASE / ZLM_API_SECRET
python run.py
```

不使用激活脚本时，可以直接调用虚拟环境解释器：

```powershell
backend\venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

> 首次启动会自动创建 SQLite 数据库并种子默认管理员 `admin / admin123`（见 `.env`）。
> 验证：浏览器打开 http://127.0.0.1:8000/docs 可见接口文档，`/api/health` 返回 ok。

### 3. 启动前端

```powershell
cd frontend
npm ci
npm run dev
```

浏览器打开 http://localhost:5173 ，使用 `admin / admin123` 登录。

### 4. 单独编译前端

前端生产构建会生成 `frontend\dist`，后端打包和 FastAPI 静态托管都会使用该目录：

```powershell
cd frontend
npm ci
npm run build
```

构建完成后可以用 Vite 预览生产文件：

```powershell
npm run preview
```

### 5. 检查后端

后端是 Python 服务，不需要单独生成二进制即可运行。提交前可执行语法检查和接口启动检查：

```powershell
cd backend
venv\Scripts\python.exe -m compileall -q app
venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

启动后访问 `http://127.0.0.1:8000/api/health`，应返回 `{"status":"ok"}`。需要停止服务时，在运行窗口按 `Ctrl+C`。

### 6. Windows 打包

在项目根目录双击 `packaging/package_windows.bat`，或执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\package_windows.ps1
```

脚本会依次执行 `npm run build`、安装 `packaging\requirements-build.txt`、使用 PyInstaller 将后端冻结为 `VideoManageBackend.exe`，复制 ZLMediaKit 运行文件，最后调用 Inno Setup 生成 `release\VideoManageSetup.exe`。构建机器需要已经准备好 `backend\ZLMediaKit\release\windows\Debug\Release\MediaServer.exe`。目标机器不需要安装 Python 或 Node.js，安装后通过桌面快捷方式启动即可。

也可以双击：

```text
packaging\package_windows.bat
```

主要产物：

```text
frontend\dist\                         前端生产文件
release\pyinstaller-dist\              PyInstaller 后端目录
release\installer-staging\             安装包临时目录
release\VideoManageSetup.exe            Inno Setup 安装程序
```

## 使用说明

1. **添加设备**：进入「设备管理」→「添加设备」，填写名称，选择接入方式：
   - **RTSP/ONVIF**：填写 IP / RTSP 端口 / ONVIF 端口 / 用户名 / 密码；若已知 RTSP 地址可直接填入「RTSP 地址」列（优先使用）。
   - 厂商云 API / 私有 SDK 为预留，当前会提示未实现。
2. **实时预览**：进入「实时预览」查看多画面宫格。每个窗口支持暂停、关闭、抓拍和开始/停止 MP4 录像；点击某一格放大并（若启用云台）显示云台控制。
3. **录像回放**：进入「录像回放」选择设备与时间范围查询，点击列表项回放。
4. **云台 PTZ**：在实时预览放大视图中，长按方向/变焦按钮控制，松手即停。

## 关键说明

- **流地址**：后端把摄像机流以 `device_{id}` 为 stream 名交给 ZLMediaKit 拉流，前端优先通过
  `http://<ZLM主机>:8080/live/device_{id}.live.ts`（HTTP-MPEG-TS）由 `mpegts.js` 播放，
  TS 请求失败时自动回退到 HTTP-FLV。
- **H.265 浏览器限制**：`mpegts.js` 负责 TS 解封装和 MSE 写入，H.265 解码仍由浏览器/Windows
  HEVC 组件提供。未安装 HEVC 扩展或硬件/系统不支持时，当前版本不会进行 FFmpeg 转码，页面无法播放该 H.265 流。
- **录像**：ZLMediaKit 按 `mp4_max_second`（默认 5 分钟）切段录制，录制完成触发 `on_record_mp4`
  WebHook，后端据此写入录像索引，回放时直接由后端以 `video/mp4` 提供（支持拖动）。
- **抓拍**：实时预览窗口优先直接从当前播放画面生成 JPEG 并下载，不依赖摄像机的抓图接口；
  后端 API 仍会优先尝试 ONVIF `GetSnapshotUri`，失败后回退到 ZLMediaKit `getSnap`。
  使用 ZLMediaKit 回退方案时，需要在其配置的 `ffmpeg.bin` 位置提供 FFmpeg。
- **手动录像**：开始/停止按钮调用 ZLMediaKit 的 `startRecord` / `stopRecord`（MP4 类型），
  不会删除共享的流代理，因此不会影响其他窗口播放。
- **状态**：设备在线状态由 `on_stream_changed` WebHook 更新，列表接口也会实时比对在线流。
- **摄像机密码**：为连接摄像机，设备密码以明文存储于本地数据库（家庭内网场景可接受，生产建议加密）。

## 常见问题

- **预览一直显示「离线」**：确认 ZLMediaKit 已启动、`ZLM_API_BASE` 端口正确、摄像机 RTSP 地址可达；
  若摄像机未填写 RTSP 地址，请确认其支持 ONVIF 且用户名密码正确。
- **录像没有生成**：确认设备「启用录像」开启，且 ZLMediaKit 的 `protocol.enable_mp4` 与后端逐路控制兼容
  （旧版本可设为 `enable_mp4=1` 全局录像）；等待一个分片时长后刷新回放页。
- **抓拍失败**：先确认视频窗口已经正常播放，窗口抓拍会直接读取当前画面；若调用后端抓拍 API，
  请确认 ONVIF 端口、用户名和密码正确，或在 ZLMediaKit 的 `ffmpeg.bin` 位置安装 FFmpeg，
  并确保纯 RTSP 设备填写的地址包含可用认证信息。
- **浏览器无法播放**：确认 ZLMediaKit 配置 `http.allow_cross_domains=1`；HTTPS 部署时需改用 WebRTC/HLS。

## 后续扩展（预留）

- 多用户 + RBAC（`User.role` 字段与 `require_roles` 依赖已就位）
- 厂商云 API / 私有 SDK 适配器（继承 `CameraAdapter` 并在 `registry` 注册即可）
- 移动侦测告警、WebRTC 低延迟播放、数据库切换 PostgreSQL
