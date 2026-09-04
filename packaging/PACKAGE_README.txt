VideoManage Windows package
==========================

1. Run the VideoManageSetup.exe installer.
2. Use the desktop shortcut or start VideoManage from the Start menu.
3. The installed program contains its own backend executable; Python is not required.
4. Open http://127.0.0.1:8000 in a browser.
5. Default login: admin / admin123.
6. In the live preview, each window supports snapshot and MP4 recording controls. Snapshots
   are generated from the playing video frame first, so FFmpeg is not required for normal
   window captures. The backend snapshot API falls back to ZLMediaKit getSnap and requires
   FFmpeg when ONVIF capture is unavailable.

The local backend configuration is backend\.env. It is created from .env.example
on first start. The bundled ZLMediaKit configuration is zlm\config.ini.
Keep the [api].secret value and backend\.env ZLM_API_SECRET identical if you
later enable API authentication.

Use stop_windows.bat to close the two package processes.
