# CLI 制作与字幕参数

这里保存现有命令、歌词文件和渲染选项的详细用法；模块交接与尚未实现的接口见 [架构与流程](pipeline.md)。以下命令从仓库根目录执行。

## 安装与运行

建议 Python 3.12。GPU PC 的安装和验收步骤见 [本地 GPU PC / Codex 交接](local-pc.md)。仅使用已对齐数据生成字幕和视频时，基础依赖不包含 PyTorch。

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

设置 `"dual_audio": true` 后，额外生成 `work/karaoke-dual-audio.mp4`：一条视频流、两条同步音轨。第一条音轨为默认伴奏（`Instrumental`），第二条默认是分离人声（`Vocals`）；视频和已编码伴奏直接复制，人声 WAV 编码一次 AAC。设置 `dual_audio_source: "original_mix"` 可改为原唱混音。普通播放器可切换音轨；自制播放器需同时解码两路音频，再按 `伴奏增益 × Instrumental + 人声增益 × Vocals` 混音，默认人声增益可设为 0，并为叠加保留音量余量。

`background_image` 可指定静态背景，`render_width` / `render_height` 可指定输出尺寸（例如 1920×1080）；源音轨仍来自 `source`。不指定背景时保留原视频画面。

NVIDIA GPU 可在项目配置中设置 `"video_encoder": "h264_nvenc"`，使用 NVENC 的 p5 / HQ / VBR 编码；`"video_quality": 20` 控制 CQ，值越低通常质量越高。默认仍为 `libx264` fast，此时同一字段控制 CRF；CQ 与 CRF 数值不能视为等效画质。当前解码、缩放和 libass 字幕绘制仍在 CPU 上。需要 FFmpeg 支持 NVENC 且运行环境可访问 GPU；显式选择 GPU 后不可用会报错，不会静默改用 CPU。

## 歌词与时间轴

`lyrics.json` 每个 token 为 `[显示原文, 平假名读音]`。单音拍助词可加第三项标明实际发音，例如 `["は", "は", "wa"]`。长音请展开成实际平假名读音；英文词可用 `language: "en"` 或逐词 `token_languages` 标记，读音使用模型支持的小写字母；多音拍发音覆盖和跨 token 促音仍需进一步实现和校对。

注音仅放在连续汉字上方，词中的假名作为读音边界，不重复显示注音。例如 `食べる / たべる` 只给 `食` 标 `た`，`引き出す / ひきだす` 分别给 `引`、`出` 标 `ひ`、`だ`。读音无法匹配这些边界时会报错，需要校正读音或分词。相邻英文词保留可见空格。

`subtitle_font_scale` 默认为 `1.2`，同时放大正文与注音；过长的行会缩小到安全边界。每段内奇数句固定在左上排，偶数句固定在右下排，从预读到唱完都不换排：第一句结束后，上排换成第三句，第二句继续在下排演唱。达到长间隔阈值（默认 6 秒）后，新段落重新从上排开始。长间奏中的预读最多提前 8 秒，避免一直挂着遥远的下一句。

正式导出可设置 `"show_preview_label": false`，去掉右上角的草稿提示。标题和歌手图例独立保留。引号和标点不参与读音匹配，汉字注音仍对应实际汉字位置。

正文与注音默认使用更粗的黑色描边，可用 `subtitle_outline`（默认 4）和 `ruby_outline`（默认 2.2）调整。`intro_card` 可设置 `title`、`artist`、`album`、`vocals` 和 `seconds`，在开头居中显示；`outro_card` 沿用相同信息，可单独设置 `seconds`。本批专辑开头和结尾各显示 10 秒，不延长音视频，底部歌词照常显示。

英文词可通过行级 `language: "en"` 或逐 token 的 `token_languages` 指定，以声学字符路径聚合为词级时间；不会把英文词伪装成日语音拍。`token_singers` 可保留 Word 行内轮唱对应的颜色。自动词典读音和复杂重叠演唱仍需试听复核。

长间隔后的三点倒数是默认功能，没有开关：`● ● ● → ● ● → ● → 无圆点 → 开唱`，每个阶段至少 1 秒，按音乐拍点向前取整；最后一个点消失后再保留一个同节奏的准备间隔。圆点放在即将开唱的歌词前方，与正文、注音一起显示；该句保留圆点前缀的空间，避免圆点消失时歌词左右跳动。默认间隔阈值为 6 秒，可用 `countdown.min_gap_seconds` 调整。安装 `.[rhythm]` 后，`subtitles` 会在需要时自动分析本地 `original.wav` 的节拍；也可先运行 `beats`。缓存为 `work/beats.json`，需人工调整时可通过 `countdown.beats_file` 指定同一时间轴的节拍文件。节拍不足、过旧或明显不规则时不编造倒数。此提示依据自动检测的音乐节拍，仍需试听校验。

### 可选的手工歌手配色

已有带格式的 Word 歌词可先批量导入：

```bash
python scripts/import_docx_lyrics.py .local/album --output .local/album/lyrics-import
```

DOCX 导入器保留段落和手动换行，根据每段标题中人名的普通字／斜体／加粗格式建立局部映射；映射可随段落反转，整曲 solo 标记也会保留。行内多个角色保存到 `singer_segments`，整行暂标为 `unknown` 待审核，不擅自把轮唱或括号和声合并为整句合唱。输出尚无读音和声学时间戳，可用下方单页工具继续处理。默认不覆盖已有输出，重跑需显式传入 `--overwrite`。

推荐直接打开独立单页 [歌词标注器](../tools/lyric-annotator.html)，无需启动服务器或安装前端依赖：

1. 载入项目 `lyrics.json` 或 `timing.json`；也支持 TXT / LRC 草稿。
2. 添加歌手，修改姓名、歌手颜色和独立合唱颜色。
3. 选择左侧歌手画笔，点击歌词逐句标记；Shift + 单击可标记连续多句，支持撤销、重做与筛选。
4. 点击“另存为新歌词文件”。输出 `*-annotated.json`，保留原 JSON 的读音、音拍时间轴和其他字段，增加歌手表及每行标记。可再次载入继续编辑。
5. 用下方 `import-singers --file ... --enable` 导入这个完整歌词文件。导入只更新分唱标记和配色，不覆盖已有歌词或时间轴；不同曲目的行 ID 或歌词文字不匹配会报错。

可另选本地音频逐句试听。TXT/LRC 导入会生成结构化 JSON 草稿，尚需读音与声学对齐；给已有视频配色时，优先载入对应项目的 JSON，保留稳定行 ID。页面不会上传文件，也不会自动覆盖源文件。

只有歌手配色有开关：`"singer_colors_enabled": false` 为默认关闭；打开后读取独立的 `singer_map`。默认颜色为 `mao`（上杉真央，粉色）、`hisayo`（阿部寿世，黄色）、`duet`（二人合唱，橙色），`unknown` 为未标注。也支持 A/B 及自定义 `singers` 颜色表。关闭时不加载标记文件，统一使用白字和黄色扫色。

启用歌手配色后，第一位歌手及每次歌手切换的那句会在注音上方显示 `【姓名】`／`【合唱】` 标签（44 号字），与该句颜色一致；同一歌手连续演唱不重复显示。标签从该句预读出现到结束，跟随所属歌词排，未知歌手不显示姓名。

```bash
auto-karaoke --project .local/demo/project.json singer-template
auto-karaoke --project .local/demo/project.json singer-review
auto-karaoke --project .local/demo/project.json import-singers --file annotations.json --enable
auto-karaoke --project .local/demo/project.json subtitles
auto-karaoke --project .local/demo/project.json render
```

`singer-review` 导出本地逐句试听页面，可选择演唱者并下载 JSON；网页不会自动写回项目，下载后用 `import-singers` 导入。导入相对路径以项目 JSON 为基准。没有配置 `singer_map` 时默认使用 `work/singer-map.json`。模板不会覆盖现有文件，导入会保留未修改的行，并保存前一版标记备份。改配色或分唱标记不需要重跑音拍对齐。

可按行 ID 或完整时间段标记，示例为结构说明：

```json
{
  "schema_version": 1,
  "lines": {"line-01": "mao", "line-02": "hisayo"},
  "ranges": [{"start": 30, "end": 45, "singer": "duet"}]
}
```

时间以当前项目片段为零点。时间段必须完整覆盖歌词行；截断一行、重叠指定同一行或无效 ID 会报错。行 ID 指定优先于时间段。此入口不会自动识别歌手，模型方向见 [歌手识别评估](singer-identification.md)。

`timing.json` 保存 `raw_end`、置信分值、音拍 ID 和自动时间。置信分值仅用于定位可疑点，不代表歌词准确率。将修正写入项目 `work/overrides.json`：

```json
{
  "syllables": {
    "line-01-word-01-mora-01": {"start": 0.32, "end": 0.48, "review_note": "人工校对"}
  }
}
```

时间以当前片段起点为 0；上面仅为结构示例，实际起止必须满足整体不重叠。重跑 `align` 保留独立 overrides；变更歌词分词后必须重新核对 ID。换人声音轨后重跑 `emit → align → subtitles → render`；只替换同一时间轴的伴奏可直接换轨，见 [Logic Pro 交接](logic-pro.md)。更换源文件或裁切范围时使用新的 `work_dir`，避免混用旧产物。

## 验证与仓库素材边界

```bash
python -m unittest discover -s tests -v
python scripts/check_repo_content.py
```

测试动态生成正弦音、纯色视频和自造日语短语，不下载歌曲或模型。集成测试需要 FFmpeg 和日文字体；可通过 `AUTO_KARAOKE_FFMPEG`、`AUTO_KARAOKE_TEST_FONT` 设置路径。

仓库只保存代码、文档、配置模板和自造测试数据。**不保存歌曲音视频、分轨、MV 截图、真实歌词、识别文本、成品字幕、模型权重或运行缓存，也不把它们写入 Git 历史。** `.gitignore` 和文本文件白名单检查用于降低误提交风险；新文档仍需人工检查，脚本不能判断一段文字的版权来源。

更多：[服务器实测](benchmarks.md) · [后续 pipeline](pipeline.md) · [现成项目评估](existing-projects.md)。
