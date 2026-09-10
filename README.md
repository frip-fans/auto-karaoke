# auto-karaoke

日语卡拉 OK 制作实验：**日语原文 + 假名注音 + 逐词／音拍变色**，保留原 MV / live 画面，导出 MP4，并可替换为 Logic Pro 分离的伴奏。

后续主要运行环境是用户的本地 GPU PC。本仓库保存已完成的服务器实验、可运行的短片段原型，以及接下来给本地 Codex 的工作说明。当前 GPU 分支尚未在真实 GPU 上验证。

## 先复用现成项目

先读 [现成项目评估](docs/existing-projects.md)。Nightingale 已覆盖分离、对齐、歌词编辑和同步播放；它当前展示日语罗马字，播放高亮也不同于假名逐音拍扫色。Karaoke Video Maker 更接近日式字幕视频编辑，但尚未实现自动强制对齐。

后续优先验证和接入这些项目。这里的 Python 代码是已有样片的可复现实验基线，不是另做一套完整播放器或字幕编辑器。

## 当前实现

| 阶段 | 实现与边界 |
| --- | --- |
| 导入 | 本地音频、MV 或 live 视频；选择固定片段；导入已有 vocals / instrumental |
| 分离（可选） | 调用 `audio-separator`；默认小 MDX 模型；也可完全使用 Logic Pro |
| 转写（可选） | faster-whisper small；结果只作为未校对草稿 |
| 对齐 | NextFire 日语歌声 CTC 模型输出声学概率；Viterbi 对齐读音字符，聚合到 mora（音拍） |
| 校对 | 手工确认歌词与假名；独立 `overrides.json` 修改起止时间 |
| 字幕 | 双行 ASS；汉字原文逐词扫色，汉字上方假名逐音拍扫色，平假名词直接逐音拍扫色 |
| 导出 | FFmpeg / libass，720p H.264 + AAC；纯音频使用纯色背景 |
| 换轨 | 保留编码后的视频流，按时间原点截取新伴奏并重新编码音频 |

已用真实 30 秒片段验证过原始样片流程；整理后的代码用合成音视频测试。实际歌词正确性、歌唱读法和时间轴仍需听音校对。`emit` 限制单段最多 60 秒；整曲自动分段与合并、多声部同时演唱、图形校对界面尚未实现。

## 安装与运行

建议 Python 3.12。GPU PC 的安装和验收步骤见 [本地 GPU PC / Codex 交接](docs/local-pc.md)。仅使用已对齐数据生成字幕和视频时，基础依赖不包含 PyTorch。

```bash
python -m venv .venv
# Linux / macOS / WSL
source .venv/bin/activate
# Windows PowerShell 改用：.venv\Scripts\Activate.ps1
python -m pip install -e .
# 需要声学对齐时，再安装对应平台的 PyTorch，然后：
python -m pip install -e '.[align]'
```

还需要带 `ass` 滤镜和 `libx264` 编码器的 FFmpeg，以及单字体 TTF/OTF 日文字体。字体不随仓库分发；TTC 字体集合暂不支持。`font_family` 必须对应 `font_path` 中实际字体的家族名。

把所有素材、歌词和项目配置放在 Git 忽略的 `.local/` 下：

```bash
mkdir -p .local/demo
cp examples/project.example.json .local/demo/project.json
cp examples/lyrics.example.json .local/demo/lyrics.json
```

修改项目 JSON 的素材、字体、起点和时长；示例中的 Linux 字体路径需要按本机修改。**所有相对路径均相对于项目 JSON**，包括 `replace-audio` 的路径参数。示例短语为自造测试文字，必须在本地换成所选片段的已校对歌词。

导入 Logic Pro 分轨的流程：

```bash
auto-karaoke --project .local/demo/project.json doctor --ml
auto-karaoke --project .local/demo/project.json prepare
auto-karaoke --project .local/demo/project.json emit
auto-karaoke --project .local/demo/project.json align
auto-karaoke --project .local/demo/project.json subtitles
auto-karaoke --project .local/demo/project.json render
```

没有分轨时，先删除配置中的 `vocals`、`instrumental` 两项，安装分离扩展，在 `prepare` 后执行：

```bash
python -m pip install -e '.[separate]'
auto-karaoke --project .local/demo/project.json separate
```

需要识别草稿时安装 `.[transcribe]`，在分离或导入 vocals 后运行 `transcribe`；它不会覆盖你确认的 `lyrics.json`。`emit` 和 `transcribe` 默认允许下载模型，`--offline` 仅使用本地缓存。模型及处理产物默认在项目 `work/cache/` 和 `work/`，不上传远端服务。

输出：`work/karaoke.ass`、`work/timing.json`、`work/karaoke-original.mp4`；有伴奏时还生成 `work/karaoke-instrumental.mp4`。这些文件均不提交 Git。

## 歌词与时间轴

`lyrics.json` 每个 token 为 `[显示原文, 平假名读音]`。单音拍助词可加第三项标明实际发音，例如 `["は", "は", "wa"]`。长音请展开成实际平假名读音；英文混唱、多音拍发音覆盖、跨 token 促音需进一步实现和校对。

`timing.json` 保存 `raw_end`、置信分值、音拍 ID 和自动时间。置信分值仅用于定位可疑点，不代表歌词准确率。将修正写入项目 `work/overrides.json`：

```json
{
  "syllables": {
    "line-01-word-01-mora-01": {"start": 0.32, "end": 0.48, "review_note": "人工校对"}
  }
}
```

时间以当前片段起点为 0；上面仅为结构示例，实际起止必须满足整体不重叠。重跑 `align` 保留独立 overrides；变更歌词分词后必须重新核对 ID。换人声音轨后重跑 `emit → align → subtitles → render`；只替换同一时间轴的伴奏可直接换轨，见 [Logic Pro 交接](docs/logic-pro.md)。更换源文件或裁切范围时使用新的 `work_dir`，避免混用旧产物。

## 验证与仓库素材边界

```bash
python -m unittest discover -s tests -v
python scripts/check_repo_content.py
```

测试动态生成正弦音、纯色视频和自造日语短语，不下载歌曲或模型。集成测试需要 FFmpeg 和日文字体；可通过 `AUTO_KARAOKE_FFMPEG`、`AUTO_KARAOKE_TEST_FONT` 设置路径。

仓库只保存代码、文档、配置模板和自造测试数据。**不保存歌曲音视频、分轨、MV 截图、真实歌词、识别文本、成品字幕、模型权重或运行缓存，也不把它们写入 Git 历史。** `.gitignore` 和文本文件白名单检查用于降低误提交风险；新文档仍需人工检查，脚本不能判断一段文字的版权来源。

更多：[服务器实测](docs/benchmarks.md) · [后续 pipeline](docs/pipeline.md) · [现成项目评估](docs/existing-projects.md)。
