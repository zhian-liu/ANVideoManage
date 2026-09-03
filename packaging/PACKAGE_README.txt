VideoManage Windows package
==========================

1. Install Python 3.11 or newer and make sure `py -3.11` is available.
2. Double-click start_windows.bat.
3. On the first run, the script creates backend\.venv and installs Python dependencies.
4. Open http://127.0.0.1:8000 in a browser.
5. Default login: admin / admin123.

The local backend configuration is backend\.env. It is created from .env.example
on first start. The bundled ZLMediaKit configuration is zlm\config.ini.
Keep the [api].secret value and backend\.env ZLM_API_SECRET identical if you
later enable API authentication.

Use stop_windows.bat to close the two package processes.
