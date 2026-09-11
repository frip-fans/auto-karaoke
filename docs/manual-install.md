# 手动安装 CLI（无需 Codex）

`auto-karaoke` 可以直接在终端运行，不需要 Codex、插件、订阅或云端 API 密钥。歌词、读音和时间轴可以手工校对。

## 1. 系统要求

- Python 3.11 或更新版本，推荐 3.12。
- [FFmpeg](https://ffmpeg.org/download.html)；渲染需要 `ass` 滤镜与 `libx264` 编码器。
- 渲染日语字幕需要单字体 TTF/OTF 文件，并配置正确的字体家族名；不支持 TTC 字体集合。
- 初次安装依赖和下载模型需要网络。GPU 非必需，但 NVIDIA GPU 可加速分离、声学对齐和 NVENC 编码。

先安装 Python 和 FFmpeg，并确认终端能找到它们：

```bash
python3 --version
ffmpeg -version
ffprobe -version
```

Windows 可用 `py -3.12 --version` 检查已安装的 Python 3.12。FFmpeg 的下载页提供各平台安装入口；具体发行版是否包含字幕滤镜和编码器，以后面的检查结果为准。

## 2. 安装基础工具

获取源码并进入目录：

```bash
git clone https://github.com/frip-fans/auto-karaoke.git
cd auto-karaoke
```

macOS / Linux / WSL：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Windows PowerShell：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

如果 PowerShell 不允许执行激活脚本，可以直接使用虚拟环境里的解释器，无需修改执行策略：

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m auto_karaoke --help
```

Linux 创建环境时若提示缺少 `ensurepip`，安装与所用 Python 版本对应的发行版 venv 包后重试。虚拟环境用法参见 [Python 文档](https://docs.python.org/3/library/venv.html)。

## 3. 按任务安装依赖

在已激活的虚拟环境中，只执行需要的项目：

| 任务 | 安装命令 |
| --- | --- |
| 分离伴奏与纯人声 | `python -m pip install -e '.[separate]'` |
| 生成声学对齐数据 | `python -m pip install -e '.[align]'` |
| 可选的语音转写草稿 | `python -m pip install -e '.[transcribe]'` |
| 计算音乐拍点 | `python -m pip install -e '.[rhythm]'` |
| 用已有时间轴、分轨和拍点渲染视频 | 基础安装即可 |

同时需要多项时可以合并，例如 `python -m pip install -e '.[separate,align,rhythm]'`。已有外部分轨时不用安装分离模型，已有歌词时也不必安装转写工具。

使用 NVIDIA 加速时，先按 [PyTorch 官方安装页](https://pytorch.org/get-started/locally/) 选择与系统和驱动相符的安装命令，再安装对应扩展。MDX23C 使用 PyTorch；ONNX 模型和 faster-whisper 分别使用其他后端，详见 [GPU 配置](local-pc.md)。`h264_nvenc` 仅加速视频编码，字幕绘制仍在 CPU 上。

## 4. 检查安装

```bash
python -m pip check
auto-karaoke --help
ffmpeg -hide_banner -filters
ffmpeg -hide_banner -encoders
```

渲染需要滤镜列表中的 `ass`、编码器列表中的 `libx264`，或已验证可用的 `h264_nvenc`。

也可以直接运行仓库自带的检查脚本；虽然文件位于插件目录，它不依赖 Codex，也不会安装软件：

```bash
python plugins/auto-karaoke/skills/karaoke-setup/scripts/check_environment.py --stage render --encoder libx264
```

检查分离环境时改用 `--stage separate --backends`。脚本只报告能力；检测到 CUDA 不代表所有模型都能装进显存。

## 5. 跑通一个短片段

新建 `.local/demo/`，放入你的 `source.mp4`，然后创建 `.local/demo/project.json`：

```json
{
  "schema_version": 1,
  "source": "source.mp4",
  "clip_start_seconds": 0,
  "clip_duration_seconds": 30,
  "work_dir": "work"
}
```

素材需至少 30 秒；否则相应缩短 `clip_duration_seconds`。相对路径都以项目 JSON 所在目录为基准。

安装分离扩展后运行：

```bash
auto-karaoke --project .local/demo/project.json prepare
auto-karaoke --project .local/demo/project.json separate --model MDX23C-8KFFT-InstVoc_HQ.ckpt
```

首次分离可能下载模型。输出在 `.local/demo/work/`：`original.wav`、`instrumental.wav`、`vocals.wav`。只需要分轨的用户到这里即可。

制作字幕和视频请继续阅读 [CLI 制作与字幕参数](production.md)：添加歌词与字体配置，运行 `emit → align`，手工校对，再执行 `subtitles → render`。`emit` 单次最多处理 60 秒；当前 CLI 尚无通用的整曲自动切分／合并入口。

以后打开新终端时重新激活同一个虚拟环境即可，不需要重复安装。换设备或移动源码目录后应重新创建环境；音视频和项目文件可单独保留。
