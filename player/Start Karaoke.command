#!/bin/bash
set -e
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
trap 'echo; echo "启动失败，请查看上面的错误。按回车关闭。"; read -r' ERR
command -v python3 >/dev/null || { echo '请先安装 Python：brew install python'; exit 1; }
command -v ffmpeg >/dev/null || { echo '请先安装 FFmpeg：brew install ffmpeg'; exit 1; }
python3 -c 'import sys; assert sys.version_info >= (3, 10), "需要 Python 3.10 或更新版本"'
if [ ! -x .venv/bin/python ]; then python3 -m venv .venv; fi
if ! .venv/bin/python -c 'import flask, waitress' 2>/dev/null; then
  .venv/bin/python -m pip install -r requirements.txt
fi
# A folder dragged onto this script (or passed from Terminal) becomes the library.
exec .venv/bin/python server.py --library "${1:-$PWD/songs}"
