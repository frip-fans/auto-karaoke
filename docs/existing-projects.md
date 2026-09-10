# 现成项目评估与复用方向

评估日期：2026-09-10。这里只读了上游文档和相关源码，**没有安装或实跑这些应用，也没有复制其实现代码**。

目标是本地 GPU PC 制作日语卡拉 OK 视频，核心验收项是原文、假名读法及逐音拍时间轴。Logic Pro 提供可选分轨。

## Nightingale

检查版本：[`7e4ff5f`](https://github.com/rzru/nightingale/tree/7e4ff5f00d9abb54ae6ef39d70510678aaa45a2e)。

它已经提供本地曲库、分离、转写与对齐、歌词编辑、原视频背景和同步播放；还包含打分、调音调速等播放功能。支持 Windows、macOS、Linux 和自托管模式，上游列有 Linux aarch64 构建。见 [README](https://github.com/rzru/nightingale/blob/7e4ff5f00d9abb54ae6ef39d70510678aaa45a2e/README.md)。

对我们的关键差异：

| 需求 | 源码核实结果 | 对后续工作的影响 |
| --- | --- | --- |
| 假名注音 | 日语内部会生成平假名读音用于对齐，但显示用 `reading()` 返回 pykakasi Hepburn 罗马字 | 不能把“支持 CJK reading”直接当作支持假名注音；需要调整显示数据 |
| 假名逐音拍扫色 | 播放器对整个 token 插值调整颜色和透明度；未见独立假名音拍扫色 | 需要保留假名级时间戳并扩展渲染，不能只把 romaji 换成 kana |
| 导出字幕视频 | 所查 README 和播放实现以同步播放为主，未找到现成 ASS / 烧录字幕 MP4 导出入口 | 需要进一步确认或接外部导出器 |
| 导入 Logic Pro 分轨 | 实验性 USDX 包可同时指定 `#VOCALS` 和 `#INSTRUMENTAL`，跳过分离 | 有现成入口，但需 USDX 时间与音符数据，不是任意丢入两个 WAV 就完成对齐 |

读音与对齐依据：[cjk.py](https://github.com/rzru/nightingale/blob/7e4ff5f00d9abb54ae6ef39d70510678aaa45a2e/app-core/analyzer/cjk.py)。播放依据：[lyrics-display.tsx](https://github.com/rzru/nightingale/blob/7e4ff5f00d9abb54ae6ef39d70510678aaa45a2e/client/src/features/playback/components/lyrics-display.tsx)。分轨导入依据：[USDX 文档](https://github.com/rzru/nightingale/blob/7e4ff5f00d9abb54ae6ef39d70510678aaa45a2e/site/docs/src/usdx.md)。

因此，Nightingale 值得作为播放器或分析前端候选。它不是当前需求已全部完成的直接替代品；“没有找到导出入口”也不等于证明所有分支都不存在这一功能。

上游标注 GPL-3.0-or-later。本仓库当前未引入其代码或设置许可证继承关系；真正复用前按具体代码和分发方式处理许可。

## Karaoke Video Maker

检查版本：[`ff48e02`](https://github.com/Mihaly-Ma/karaoke-video-maker/tree/ff48e022b1dd9a8d4804bebc8889dd013bd66fe9)。

它的产品形态更贴近本任务：本地导入、日式假名字幕、逐字变色、时间轴／注音编辑、ASS 预览及 MP4 导出；CLI 有片段导出和音轨替换入口。见 [README](https://github.com/Mihaly-Ma/karaoke-video-maker/blob/ff48e022b1dd9a8d4804bebc8889dd013bd66fe9/README.md)。

但其 [功能状态文档](https://github.com/Mihaly-Ma/karaoke-video-maker/blob/ff48e022b1dd9a8d4804bebc8889dd013bd66fe9/docs/status.md) 明确说明：

- 自动 forced alignment / CTC 尚未实现；时间来自 QRC 或手工制作。
- 自动读音生成尚未实现；假名来自歌词源或人工输入。
- 商业音源时间轴到 MV 的自动重新对齐尚未实现。
- 实际验证环境为 Apple Silicon Mac；Windows 尚未实跑。

它适合优先评估“编辑器与视频导出”这一部分，但本地 GPU PC 可运行性和对齐接口仍需实测。不能仅凭项目简介认定它已解决假名自动对齐。

## 其他可复用组件

- [nomadkaraoke/karaoke-gen](https://github.com/nomadkaraoke/karaoke-gen)：面向成品视频的完整生产流程，提供歌词校对和 ASS / MP4 等产物；此次仅核实文档，没有验证日语假名与音拍时间轴支持。
- [yuna0x0/karaoke-ass](https://github.com/yuna0x0/karaoke-ass)：带假名的双行 ASS 模板及可选命令行工具，适合评估字幕渲染替换；输入仍需要已有音节时间轴。
- 当前已复用的底层组件：audio-separator、NextFire CTC 模型、faster-whisper、pykakasi、FFmpeg / libass。没有自行训练分离或语音模型。

## 后续选择

优先做小规模接入验证，再决定集成对象：

1. 在本地 PC 用同一段已校对素材验证候选项目安装、音频导入、时间轴格式和视频导出。
2. 检查能否无损表达 `原文 token → 显示假名 → 实际发音 → 每个音拍的起止时间`，以及人工修正是否会被重算覆盖。
3. 如候选缺少自动对齐，尝试将本仓库的对齐结果转换到其项目结构；如缺少视频导出，评估外接 ASS 导出。
4. 假名对齐、编辑和换轨通过后，再迁移整曲流程。暂不扩建自己的播放器、曲库或图形编辑器。

这里的顺序是工程建议，不是已完成集成的声明。
