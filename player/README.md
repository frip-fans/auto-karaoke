# 本地唱片室

离线卡拉 OK 播放器：Flask 本地服务 + 浏览器控制台。沿用 `karaoke-stage` worktree 的深色舞台、青色控件和点歌思路，重写曲库与音频引擎；原 worktree 保持原样。

## Mac 启动

1. 解压 `Karaoke-Mac.zip`，把整个 `Karaoke` 文件夹放到 Mac。
2. 首次需要 Python 3.10+ 和 FFmpeg。已有 Homebrew 时运行 `brew install python ffmpeg`。
3. 双击 `Start Karaoke.command`，首次自动创建 Python 环境并安装 Flask / Waitress；以后离线运行。打开 `http://127.0.0.1:8787`。若 Finder 不允许直接打开，可在终端运行 `bash "/完整路径/Karaoke/Start Karaoke.command"`。
4. 保持启动终端和控制页面打开。终端按 Ctrl+C 结束服务。

也可以指定外置硬盘上的曲库：

```bash
bash "Start Karaoke.command" "/Volumes/My SSD/我的曲库"
```

Linux / 已有 Python 环境：

```bash
python -m pip install -r player/requirements.txt
python player/server.py --library /path/to/library
```

仅监听本机 `127.0.0.1`；无登录、云端或外部素材请求。系统依赖和首次 pip 安装需要网络。端口被占用时可用 `server.py --port 8789`。

## 曲库、专辑、多个版本

“导入 MP4”会把文件复制进曲库。一次可以选多个，填写共有专辑、歌手、版本；每首曲名随后用“编辑”修正。**专辑、曲名、歌手相同**的条目合并展示，不同版本仍有各自的播放和点歌按钮。例如同一首歌的“专辑版”和“Live 2026”。

曲库结构：

```text
songs/
  library.json          # 专辑、曲名、版本、音轨映射和稳定 ID
  media/*.mp4           # 相对路径，原文件内容不修改
  .karaoke-cache/       # 可删除的本地解码缓存
```

关掉服务后，拷贝整个 `songs` 文件夹即可搬到另一台设备，也可重命名曲库根目录。无需同步数据库服务。缓存可以不拷贝，下次自动生成。不要单独改 MP4 的相对路径，否则原记录会显示文件缺失。也可直接把 MP4 放进曲库后点击“↻”扫描，再编辑专辑信息。

队列、最近唱过的记录和音量存在浏览器 `localStorage`，不写入曲库、不随文件夹同步。换浏览器、设备、端口或清除网站数据会得到独立记录。最近唱过目前记录完整播放结束的歌曲。曲库本身不受影响。

## 调音与 HDMI

视频必须有浏览器支持的编码，推荐现有 H.264 / AAC MP4。画面始终静音。本地服务从 MP4 取出伴奏和**分离的纯人声**，解码为同一时间零点的 PCM；两条 AudioBufferSource 同时开始、同时定位，共用 AudioContext 时钟。

- 伴奏、人声各自 0–100%，人声增大不会降低伴奏；总音量控制混合结果。`V` 切换纯人声导唱。
- `Instrumental` / `Vocals` 标记自动识别。`Original Mix` 不会自动作为纯人声。未标记的双轨需在“编辑 → 音轨对应关系”手动确认。单轨可播放，但没有独立人声调节。
- 首播需等待本地音轨准备；5 分钟歌曲约产生 106 MB PCM 缓存、约 212 MB 解码缓冲。浏览器仅持有当前歌曲的音频；长 Live 视频会需要更多内存。
- 用两个分离 stem 相加，不保证与发行母带逐样本相同。提供轻度限幅防止叠加峰值过载；默认总音量 80%。
- HDMI 选择**扩展屏幕**。点击“观众窗口”，拖到电视/投影仪后点全屏；Mac“系统设置 → 声音”选择 HDMI 输出。观众窗口只显示静音画面，声音由控制窗口统一输出。
- 保持控制窗口运行、Mac 不休眠。观众窗口通过本机 BroadcastChannel 同步画面；后台页面节流可能影响画面跟随，声音两轨仍共用音频时钟。可调“画面延迟”补偿电视处理延迟，正值让画面落后声音。
- 单屏使用画面右下角全屏按钮。Space 播放/暂停，左右键前后 5 秒，F 全屏。浏览器首次可能要求用户点击以启用声音或允许弹窗。

浏览器控制台与观众屏已在 Linux Chromium 实测；尚未实机验证 macOS / Safari / HDMI。建议在出门前用目标 Mac 和音响试播。应用不提供麦克风回放；麦克风接现有卡拉 OK 设备或混音器。

## 验证与打包

```bash
python -m unittest discover -s player/tests -v
# 浏览器测试自动创建、清理合成曲库与临时本地服务；需已安装 Playwright / Chromium。
NODE_PATH=/path/to/node_modules python player/tests/run_browser.py
python player/package.py --library /path/to/library --output /path/to/Karaoke-Mac.zip
```

打包不包含 Python 环境、解码缓存或浏览器记录。代码仓库只保存程序和测试，不保存曲库、歌曲或真实歌词。
