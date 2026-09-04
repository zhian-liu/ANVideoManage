# 视频监控管理平台

统一接入各厂家家庭摄像机的 Web 管理平台。支持 **实时预览（多画面宫格）**、**录像存储与回放**、**云台 PTZ 控制**。

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.11+ · FastAPI · SQLAlchemy(async) · SQLite |
| 前端 | React 18 · TypeScript · Vite · Ant Design 5 |
| 流媒体 | ZLMediaKit（拉流 / 转码 / MP4 录像） |
| 摄像机接入 | RTSP/ONVIF（已实现）+ 厂商云 API / 私有 SDK（预留适配器） |

## 架构

```
浏览器(React) ──HTTP REST──▶ FastAPI ──REST API──▶ ZLMediaKit ──RTSP拉流──▶ 摄像机
      │                          │                        │
      └──HTTP-FLV/HLS────────────┘                        └──MP4录像 + WebHook回调──▶ 录像索引
```

## 目录结构

```
backend/            FastAPI 后端
  app/
    api/            auth / devices / streams / recordings / ptz / zlm_hook
    adapters/       摄像机适配器（onvif 已实现，cloud/sdk 为模板）
    core/           JWT / 鉴权依赖
    models/         User / Device / Recording
    services/       ZLMediaKit 客户端、流代理同步
    main.py         入口
frontend/           React 前端
config/             ZLMediaKit 配置
```

## 启动步骤

### 1. 启动 ZLMediaKit

1. 到 [ZLMediaKit 发布页](https://github.com/ZLMediaKit/ZLMediaKit/releases) 下载 Windows 预编译包并解压；
2. 将 `config/zlmediakit.config.ini` 覆盖/合并到其运行目录的 `config.ini`（注意修改其中的 WebHook 地址与端口以匹配后端）；
3. 启动 ZLMediaKit（运行 `MediaServer.exe`），确认 HTTP 端口 `8080` 可访问。

### 2. 启动后端

```bash
cd backend
python -m venv .venv
# Windows 激活：.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # 按需修改，尤其是 ZLM_API_BASE / ZLM_API_SECRET
uvicorn app.main:app --reload --port 8000
```

> 首次启动会自动创建 SQLite 数据库并种子默认管理员 `admin / admin123`（见 `.env`）。
> 验证：浏览器打开 http://127.0.0.1:8000/docs 可见接口文档，`/api/health` 返回 ok。

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 http://localhost:5173 ，使用 `admin / admin123` 登录。

### 4. Windows 打包

在项目根目录双击 `packaging/package_windows.bat`，或执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\package_windows.ps1
```

脚本会使用 PyInstaller 将后端冻结为 `VideoManageBackend.exe`，再调用 Inno Setup
生成 `release/VideoManageSetup.exe`。目标机器不需要安装 Python 或 Node.js，安装后
通过桌面快捷方式启动即可。构建机器需要 Python 3.11+、Node.js 和 Inno Setup 6。

## 使用说明

1. **添加设备**：进入「设备管理」→「添加设备」，填写名称，选择接入方式：
   - **RTSP/ONVIF**：填写 IP / RTSP 端口 / ONVIF 端口 / 用户名 / 密码；若已知 RTSP 地址可直接填入「RTSP 地址」列（优先使用）。
   - 厂商云 API / 私有 SDK 为预留，当前会提示未实现。
2. **实时预览**：进入「实时预览」查看多画面宫格。每个窗口支持暂停、关闭、抓拍和开始/停止 MP4 录像；点击某一格放大并（若启用云台）显示云台控制。
3. **录像回放**：进入「录像回放」选择设备与时间范围查询，点击列表项回放。
4. **云台 PTZ**：在实时预览放大视图中，长按方向/变焦按钮控制，松手即停。

## 关键说明

- **流地址**：后端把摄像机流以 `device_{id}` 为 stream 名交给 ZLMediaKit 拉流，前端通过
  `http://<ZLM主机>:8080/live/device_{id}.live.flv`（HTTP-FLV）播放。
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
