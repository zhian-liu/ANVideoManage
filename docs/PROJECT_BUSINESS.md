# 视频监控管理平台业务与代码说明

> 本文记录当前版本的前端业务、后端业务、ZLMediaKit 业务边界，以及代码文件和接口调用关系。
> 修改代码或部署环境时，优先同步更新本文档中的目录、接口和配置说明。

## 1. 系统定位与整体架构

平台用于统一管理支持 RTSP/ONVIF 的摄像机，提供设备管理、实时预览、多画面布局、抓拍、录像、录像回放和云台控制。
厂商云 API 与私有 SDK 已预留适配器入口，但当前版本没有实现具体厂商协议。

```text
浏览器（React + mpegts.js）
        │  HTTP REST /api/*（Axios，Bearer JWT）
        ▼
FastAPI 后端（设备、流、录像、PTZ、鉴权）
        │  HTTP REST /index/api/*
        ▼
ZLMediaKit（代理、协议输出、录像、抓图）
        │  RTSP 拉流
        ▼
摄像机（RTSP/ONVIF）

ZLMediaKit ── WebHook ──> FastAPI
              on_stream_changed / on_record_mp4
```

### 1.1 一次实时播放的关键流程

1. 前端进入实时预览页，调用 `GET /api/devices` 获取设备列表。
2. 对启用设备调用 `GET /api/streams/{device_id}`。如果 ZLMediaKit 中没有对应流，后端会解析设备 RTSP 地址并调用 `addStreamProxy`。
3. 后端返回 HTTP-TS、HTTP-FLV 和 HLS 地址。前端 `VideoPlayer` 优先使用 HTTP-TS，通过 `mpegts.js` 写入 MSE；播放出错时回退到 HTTP-FLV。
4. ZLMediaKit 将源流注册为 `live/device_{id}`。同一个 `device_{id}` 可以被多个窗口使用，只有没有窗口、详情弹窗和录像任务引用时前端才会请求停止代理。
5. ZLMediaKit 通过 `on_stream_changed` 回调更新设备在线状态。

## 2. 仓库目录与职责

```text
backend/                         Python FastAPI 后端
  app/
    api/                         HTTP 接口路由
    adapters/                    摄像机接入适配器
    core/                        JWT 鉴权与依赖
    models/                      SQLAlchemy 数据模型
    schemas/                     Pydantic 请求/响应模型
    services/                    ZLMediaKit 客户端和流同步
    config.py                    环境变量配置
    database.py                  异步数据库引擎和会话
    main.py                      FastAPI 入口、生命周期和静态文件
  .env.example                   后端配置模板
  requirements.txt               Python 依赖
  run.py                         开发启动入口（reload）
  packaged_main.py               Windows 打包后的启动入口
frontend/                        React + TypeScript 前端
  src/api/                       Axios 客户端、接口函数和类型
  src/pages/                     页面级业务
  src/components/                可复用业务组件
  src/layouts/                   页面布局
  src/store/                     登录状态
  src/theme/                     主题配置
  src/hooks/                     动画和交互 Hook
config/zlmediakit.config.ini    ZLMediaKit 关键配置模板
packaging/                       Windows 打包脚本（PyInstaller + Inno Setup）
```

## 3. 后端业务与代码清单

### 3.1 应用基础设施

| 文件 | 职责 |
| --- | --- |
| `backend/app/main.py` | 创建 FastAPI 应用；启动时创建数据库表并种子默认管理员；挂载所有路由；在打包版本中托管 `frontend/dist`；提供 `/api/health`。 |
| `backend/app/config.py` | `Settings` 配置类，读取 `.env`；包含 JWT、SQLite、ZLMediaKit API/端口和 WebHook 地址。 |
| `backend/app/database.py` | 创建 SQLAlchemy 异步引擎、`SessionLocal` 和 `get_db` 依赖。默认数据库为 `backend/data/app.db`（以启动工作目录为相对基准）。 |
| `backend/app/core/security.py` | bcrypt 密码哈希、密码校验、JWT 创建和解析。 |
| `backend/app/core/deps.py` | `get_current_user`（仅请求头）和 `get_current_user_flex`（请求头或 `?token=`）鉴权依赖，以及角色依赖工厂。 |
| `backend/app/schemas/auth.py` | 登录请求、JWT 返回和用户输出模型。 |
| `backend/app/schemas/device.py` | 设备创建、更新和输出模型。 |
| `backend/app/schemas/recording.py` | 录像索引输出模型。 |

### 3.2 数据模型

| 文件 | 主要字段和用途 |
| --- | --- |
| `backend/app/models/user.py` | `users` 表；用户名、bcrypt 密码、角色、启用状态。 |
| `backend/app/models/device.py` | `devices` 表；设备名称、厂商、接入方式、IP/端口、账号密码、RTSP 地址、ONVIF 端口、PTZ/录像/启用开关和在线状态。 |
| `backend/app/models/recording.py` | `recordings` 表；设备、开始/结束时间、ZLMediaKit 文件路径/名称/大小。 |
| `backend/app/models/__init__.py` | 统一导出模型，确保建表时被 SQLAlchemy 导入。 |

### 3.3 摄像机适配器

| 文件 | 职责 |
| --- | --- |
| `backend/app/adapters/base.py` | `CameraAdapter` 抽象接口：`resolve_stream`，以及可选的 PTZ、变焦、抓拍能力。 |
| `backend/app/adapters/onvif.py` | 当前已实现的 RTSP/ONVIF 适配器。优先使用设备的 `rtsp_url`；否则调用 ONVIF `GetStreamUri`；再失败时回退到通用 RTSP 路径。PTZ 使用 `ContinuousMove`/`Stop`，抓拍使用 `GetSnapshotUri`。同步 ONVIF 调用放入线程池。 |
| `backend/app/adapters/cloud.py` | 厂商云 API 模板，当前抛出 `NotImplementedError`。 |
| `backend/app/adapters/sdk.py` | 厂商私有 SDK 模板，当前抛出 `NotImplementedError`。 |
| `backend/app/adapters/registry.py` | 按 `access_type` 选择适配器；可通过 `register_adapter` 扩展新厂商。 |

### 3.4 服务层

| 文件 | 职责 |
| --- | --- |
| `backend/app/services/zlmediakit.py` | ZLMediaKit REST 客户端、统一 stream key、播放地址构造、录像/抓图/在线流查询。设备流名固定为 `device_{device_id}`。 |
| `backend/app/services/stream_sync.py` | `apply_stream`：设备新建或更新后，根据适配器解析的地址调用 ZLMediaKit `addStreamProxy`；设备禁用时删除代理。失败不会阻止设备入库。 |

### 3.5 HTTP 路由文件

| 文件 | 路由前缀 | 业务 |
| --- | --- | --- |
| `backend/app/api/auth.py` | `/api/auth` | 登录和当前用户信息。 |
| `backend/app/api/devices.py` | `/api/devices` | 设备增删改查、在线状态计算和设备流代理同步。 |
| `backend/app/api/streams.py` | `/api/streams` | 流信息、协议地址、启停流、录像控制、状态和抓拍。 |
| `backend/app/api/recordings.py` | `/api/recordings` | 录像索引查询、MP4 文件下载/播放和删除。 |
| `backend/app/api/ptz.py` | `/api/devices` | PTZ 移动、变焦和停止。 |
| `backend/app/api/zlm_hook.py` | `/api/zlm/hook` | 接收 ZLMediaKit 流状态和录像完成 WebHook；不要求用户登录。 |

## 4. 后端 HTTP 接口清单

除特别注明外，接口都需要 `Authorization: Bearer <JWT>`。

### 4.1 系统与鉴权

| 方法 | 路径 | 前端调用 | 说明 |
| --- | --- | --- | --- |
| `GET` | `/api/health` | 启动检查（可选） | 返回 `{"status":"ok"}`，无需登录。 |
| `POST` | `/api/auth/login` | `api.login`，`Login.tsx` | 请求 `{username,password}`，返回 `access_token`。无需登录。 |
| `GET` | `/api/auth/me` | `api.me`，`AuthProvider` | 返回当前用户；用于恢复登录状态。 |

### 4.2 设备管理

| 方法 | 路径 | 前端调用 | 说明 |
| --- | --- | --- | --- |
| `POST` | `/api/devices` | `api.createDevice`，`DeviceForm` | 创建设备并尝试向 ZLMediaKit 下发代理。 |
| `GET` | `/api/devices` | `api.listDevices`，`Devices`/`Dashboard`/`Live`/`Playback` | 返回设备列表；后端实时查询 ZLMediaKit 在线流并计算 `online/offline/unknown`。 |
| `GET` | `/api/devices/{id}` | 可供扩展使用 | 获取单个设备。 |
| `PUT` | `/api/devices/{id}` | `api.updateDevice`，`DeviceForm` | 更新设备并重新同步流代理。 |
| `DELETE` | `/api/devices/{id}` | `api.deleteDevice`，`Devices` | 删除 ZLMediaKit 代理、关联录像索引和设备。 |

### 4.3 实时流、抓拍和录像

| 方法 | 路径 | 前端调用 | 说明 |
| --- | --- | --- | --- |
| `GET` | `/api/streams/{id}` | `api.getStreamInfo`，`Live` | 返回在线状态、录像状态和 TS/FLV/HLS 地址；流离线且设备启用时会自动重新下发代理。 |
| `GET` | `/api/streams/{id}/protocols` | `api.getStreamProtocols`，`Devices` | 返回 RTSP、RTMP、HTTP-FLV、HTTP-TS、HTTP-FMP4、HLS、WebSocket 和 WebRTC 地址。 |
| `POST` | `/api/streams/{id}/start` | `api.startStream`（保留接口） | 手动解析地址并调用 `addStreamProxy`。当前实时页主要通过 `getStreamInfo` 自动启动。 |
| `POST` | `/api/streams/{id}/stop` | `api.stopStream`，`Live` | 删除该设备的共享流代理。只有前端确认没有使用者时才调用。 |
| `POST` | `/api/streams/{id}/record/start` | `api.startRecording`，`Live` | 必要时先启动代理，等待媒体源注册，再调用 ZLMediaKit `startRecord(type=1)`。 |
| `POST` | `/api/streams/{id}/record/stop` | `api.stopRecording`，`Live` | 调用 ZLMediaKit `stopRecord(type=1)`。 |
| `GET` | `/api/streams/{id}/record/status` | `api.getRecordingStatus`（保留接口） | 查询 ZLMediaKit MP4 录像状态。 |
| `GET` | `/api/streams/{id}/snapshot` | `api.captureSnapshot`，`Live` | 先尝试 ONVIF `GetSnapshotUri`，失败后调用 ZLMediaKit `getSnap` 生成 JPEG。返回 `image/jpeg`。 |

### 4.4 录像回放与文件

| 方法 | 路径 | 前端调用 | 说明 |
| --- | --- | --- | --- |
| `GET` | `/api/recordings` | `api.listRecordings`，`Playback` | 按 `device_id`、`start`、`end` 查询录像索引，默认最多 200 条，最多允许 1000 条。 |
| `GET` | `/api/recordings/{recording_id}/file` | `api.recordingFileUrl`，`Playback` | 返回 MP4 文件。`<video>` 不能方便地附加请求头，因此同时支持 `?token=<JWT>`。 |
| `DELETE` | `/api/recordings/{recording_id}` | 可供扩展使用 | 删除磁盘文件并删除录像索引。 |

### 4.5 PTZ

| 方法 | 路径 | 前端调用 | 说明 |
| --- | --- | --- | --- |
| `POST` | `/api/devices/{id}/ptz/move` | `api.ptzMove`，`PTZPanel` | 请求 `{direction,speed}`，方向为 `left/right/up/down`。按住按钮时移动。 |
| `POST` | `/api/devices/{id}/ptz/zoom` | `api.ptzZoom`，`PTZPanel` | 请求 `{direction,speed}`，方向为 `in/out`。 |
| `POST` | `/api/devices/{id}/ptz/stop` | `api.ptzStop`，`PTZPanel` | 停止移动或变焦。 |

### 4.6 ZLMediaKit WebHook

这两个接口由 ZLMediaKit 调用，不使用用户 JWT；必须在 ZLMediaKit 配置中能访问 `WEBHOOK_BASE`。

| 方法 | 路径 | 触发时机 | 后端动作 |
| --- | --- | --- | --- |
| `POST` | `/api/zlm/hook/on_stream_changed` | 流上线或下线 | 从 `stream=device_{id}` 解析设备 ID，更新 `Device.status`。 |
| `POST` | `/api/zlm/hook/on_record_mp4` | MP4 分片完成 | 从回调字段读取开始时间、时长、文件路径、文件名和大小，写入 `Recording` 索引。 |

## 5. 前端业务与代码清单

### 5.1 入口、路由和状态

| 文件 | 职责 |
| --- | --- |
| `frontend/src/main.tsx` | 组合 `ThemeProvider`、`BrowserRouter`、`AuthProvider`，挂载 React 应用。 |
| `frontend/src/App.tsx` | 路由表和登录保护：设备总览 `/`、实时预览 `/live`、录像回放 `/playback`、设备管理 `/devices`。 |
| `frontend/src/store/auth.tsx` | 保存 JWT 到 `localStorage`，登录后加载 `/auth/me`，失效时清除令牌。 |
| `frontend/src/layouts/MainLayout.tsx` | 侧边菜单、顶部用户区、主题切换和页面内容容器。 |

### 5.2 API 层与类型

| 文件 | 职责 |
| --- | --- |
| `frontend/src/api/client.ts` | Axios 实例，基础路径为 `/api`；请求拦截器添加 Bearer JWT；401 自动回登录页。 |
| `frontend/src/api/index.ts` | 所有后端调用函数：登录、用户、设备、流、抓拍、录像、录像查询和 PTZ。 |
| `frontend/src/api/types.ts` | `User`、`Device`、`StreamInfo`、`StreamProtocolsInfo`、`RecordStatus`、`Recording` 等 TypeScript 类型。 |

### 5.3 页面与组件

| 文件 | 职责和调用的 API |
| --- | --- |
| `frontend/src/pages/Login.tsx` | 登录表单，调用 `api.login`。 |
| `frontend/src/pages/Dashboard.tsx` | 设备总数、在线/离线数量和在线率，调用 `api.listDevices`。 |
| `frontend/src/pages/Devices.tsx` | 设备增删改、状态展示和“查看流地址”弹窗；调用设备 CRUD 与 `api.getStreamProtocols`。 |
| `frontend/src/pages/Live.tsx` | 设备树、单/4/9/16 窗口、窗口选中、同设备多窗口播放、暂停、关闭、抓拍、录像和详情弹窗；调用流信息、停止流、抓拍、录像和 PTZ API。 |
| `frontend/src/pages/Playback.tsx` | 设备/时间范围筛选录像，选择录像后播放；调用 `api.listDevices`、`api.listRecordings` 和 `api.recordingFileUrl`。 |
| `frontend/src/components/DeviceForm.tsx` | 添加/编辑设备表单，调用 `api.createDevice` 或 `api.updateDevice`。 |
| `frontend/src/components/VideoPlayer.tsx` | 封装 `<video>` 与 `mpegts.js`；实时流使用 MSE，优先 TS、失败回退 FLV；回放使用原生 MP4。支持暂停、静音和错误回调。 |
| `frontend/src/components/PTZPanel.tsx` | 按住方向/变焦按钮调用 `api.ptzMove`/`api.ptzZoom`，松开调用 `api.ptzStop`。 |
| `frontend/src/components/GridView.tsx` | 通用网格组件，目前为可复用基础组件，实时页使用了自定义网格渲染。 |

### 5.4 视觉和交互支持

| 文件 | 职责 |
| --- | --- |
| `frontend/src/theme/ThemeProvider.tsx` | 亮色/暗色主题状态、Ant Design 主题配置和本地持久化。 |
| `frontend/src/theme/colors.ts` | 两套主题颜色定义。 |
| `frontend/src/hooks/useAnimations.ts` | 数字递增、视差、鼠标位置和元素可见性 Hook。 |
| `frontend/src/index.css` | 全局布局、视频容器、状态指示器、动画和 Ant Design 样式覆盖。 |
| `frontend/package.json` | React、Ant Design、Axios、mpegts.js、Vite 等依赖和构建脚本。 |

## 6. ZLMediaKit 业务与接口

### 6.1 配置文件

`config/zlmediakit.config.ini` 是关键配置模板：

| 配置 | 默认值 | 用途 |
| --- | --- | --- |
| `[api] secret` | 空 | ZLMediaKit REST API 密钥。填写后必须与后端 `ZLM_API_SECRET` 完全一致。 |
| `[http] port` | `8080` | REST API、HTTP-FLV、HTTP-TS、HTTP-FMP4、HLS 共用端口。 |
| `[rtsp] port` | `554` | RTSP 输出端口。 |
| `[rtmp] port` | `1935` | RTMP 输出端口。 |
| `[http] allow_cross_domains` | `1` | 允许前端开发端口跨域读取媒体。 |
| `[general] streamNoneReaderDelayMS` | `0` | 无观看者时不自动删除代理，保证录像和多窗口切换稳定。 |
| `[protocol] enable_*` | 见模板 | 启用 RTSP、RTMP、HLS、TS、FMP4 和 MP4 能力。 |
| `[protocol] mp4_max_second` | `300` | MP4 分片时长，分片完成后触发 WebHook。 |
| `[protocol] mp4_save_path` | `./www/record` | 录像文件保存目录，路径相对于 ZLMediaKit 运行目录。 |
| `[protocol] hls_save_path` | `./www/hls` | HLS 分片保存目录。 |

### 6.2 后端实际调用的 ZLMediaKit REST API

调用基地址为 `ZLM_API_BASE`，当 `ZLM_API_SECRET` 非空时，后端会自动追加 `?secret=<密钥>`（已有查询参数时使用 `&secret=`）。

| ZLMediaKit API | 后端位置 | 作用 |
| --- | --- | --- |
| `POST /index/api/addStreamProxy` | `ZLMClient.add_stream_proxy` | 创建或更新 RTSP 代理；设置 `app=live`、`stream=device_{id}`，启用 RTSP/RTMP/HLS/TS/FMP4，并按设备开关控制 MP4。 |
| `GET /index/api/delStreamProxy` | `ZLMClient.del_stream_proxy` | 删除 `__defaultVhost__/live/device_{id}` 代理。 |
| `GET /index/api/startRecord` | `ZLMClient.start_record` | 以 `type=1`（MP4）开始录像。 |
| `GET /index/api/stopRecord` | `ZLMClient.stop_record` | 停止 MP4 录像。 |
| `GET /index/api/isRecording` | `ZLMClient.is_recording` | 查询 MP4 录像状态。 |
| `GET /index/api/getSnap` | `ZLMClient.get_snapshot` | 从源 RTSP 生成 JPEG 抓图；需要 ZLMediaKit 能找到 `ffmpeg.bin`。 |
| `GET /index/api/getMediaList` | `ZLMClient.online_streams` | 查询当前媒体源，后端据此计算设备在线状态。 |

### 6.3 代理流地址

由 `protocol_urls(device_id)` 按 `ZLM_API_BASE` 主机、配置端口、`ZLM_APP` 和 `device_{id}` 生成：

| 协议 | 地址模板 |
| --- | --- |
| RTSP | `rtsp://<host>:554/live/device_{id}` |
| RTMP | `rtmp://<host>:1935/live/device_{id}` |
| HTTP-FLV | `http://<host>:8080/live/device_{id}.live.flv` |
| HTTP-TS | `http://<host>:8080/live/device_{id}.live.ts` |
| HTTP-FMP4 | `http://<host>:8080/live/device_{id}.live.mp4` |
| HLS | `http://<host>:8080/live/device_{id}/hls.m3u8` |
| WebSocket-FLV | `ws://<host>:8080/live/device_{id}.live.flv` |
| WebSocket-TS | `ws://<host>:8080/live/device_{id}.live.ts` |
| WebSocket-FMP4 | `ws://<host>:8080/live/device_{id}.live.mp4` |
| WebRTC | `http://<host>:8080/index/api/webrtc?app=live&stream=device_{id}&type=play` |

这些地址只有在对应协议已启用且媒体源在线时才可访问。WebRTC 地址是信令接口地址，不能直接当作普通 `<video src>` 使用；需要 WebRTC 客户端完成 SDP/ICE 协商。

## 7. 录像、抓拍和状态的实现原理

### 7.1 录像

1. 前端点击开始录像，调用 `/api/streams/{id}/record/start`。
2. 后端确保 `device_{id}` 已在 ZLMediaKit 注册，然后调用 `startRecord(type=1)`。
3. ZLMediaKit 按 `mp4_max_second` 切分 MP4，并写入 `mp4_save_path`。
4. 每个分片完成后，ZLMediaKit 调用 `on_record_mp4`；后端把回调元数据写入 SQLite 的 `recordings` 表。
5. 回放页查询索引，视频地址为 `/api/recordings/{recording_id}/file?token=<JWT>`，后端以 `video/mp4` 返回原文件。
6. 删除录像时，后端同时删除磁盘文件和数据库索引。

### 7.2 抓拍

实时预览窗口优先使用浏览器当前 `<video>` 画面绘制 Canvas 并下载 JPEG，不经过后端。若视频尚未有可用帧、Canvas 因跨域被污染或绘制失败，则回退调用 `/api/streams/{id}/snapshot`。
后端先尝试 ONVIF `GetSnapshotUri`，失败后调用 ZLMediaKit `getSnap`。因此纯 RTSP 设备也可以抓拍，但 ZLMediaKit 回退路径必须能使用 FFmpeg。

### 7.3 在线状态

ZLMediaKit 的 `on_stream_changed` 回调负责更新数据库状态；设备列表接口还会通过 `getMediaList` 实时校验。设备未启用时状态为 `unknown`，启用但没有对应媒体源时为 `offline`。

## 8. 配置、密钥和部署注意事项

- `SECRET_KEY` 是平台 JWT 签名密钥；前端不保存其原文，只保存登录后得到的 JWT。后端重启后必须保持 `SECRET_KEY` 不变，否则旧令牌全部失效。
- `ZLM_API_SECRET` 是后端调用 ZLMediaKit REST API 的密钥，对应 ZLMediaKit 配置 `[api] secret`。两边都为空表示关闭 ZLMediaKit API 鉴权；只配置一边会导致所有 ZLMediaKit API 调用失败。
- `WEBHOOK_BASE` 必须是 ZLMediaKit 能访问到的后端地址。后端端口默认为 `8000`，前端开发服务器默认为 `5173`。
- Windows 打包入口为 `backend/packaged_main.py`；构建后目标机不需要安装 Python/Node，但仍需要单独运行可访问的 ZLMediaKit（或将其一并放入安装包并配置启动脚本）。
- 浏览器实时播放的主链路是 HTTP-TS + MSE，H.265 最终解码依赖 Windows 和 Chrome/Edge 的 HEVC 能力；当前版本不通过 FFmpeg 转码。

