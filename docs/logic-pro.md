# Logic Pro 分轨与后期替换

把原始音频或视频音轨导入 Logic Pro，用 Stem Splitter 拆分，再导出人声与伴奏。以实际试听决定伴奏是否保留和声；不要求为了本 pipeline 改用服务器分离。

参考 Apple 的 [Stem Splitter](https://support.apple.com/guide/logicpro/extract-vocal-instrumental-stems-stem-lgcp61bae908/mac) 和 [导出轨道](https://support.apple.com/guide/logicpro/export-tracks-as-audio-files-lgcpb27f70f9/mac) 文档。

## 保持时间轴一致

- 推荐 WAV，两个分轨使用同一起止范围、采样率和声道设置。
- 保留开头静音；不自动裁掉静音，不做速度变换。
- 使用原素材实际节奏；关闭会改变音频长度的跟随工程速度或拉伸处理。
- 不添加导致起点偏移的预卷；效果器尾音如延长导出范围，记录实际时长。

`origin_seconds` 表示 **该分轨第一个采样点在原素材时间轴上的位置**。

| 导出方式 | `origin_seconds` | 原素材选取 60–90 秒时如何读取 |
| --- | ---: | --- |
| 从原素材 0 秒导出整首 | 0 | 从分轨 60 秒读取 30 秒 |
| 只导出原素材 60–90 秒 | 60 | 从分轨 0 秒读取 30 秒 |

这两个数字不能混用；“片段有 30 秒”不代表它的时间原点是 0。

## 换掉临时伴奏

假定项目文件在 `.local/demo/project.json`，`clip_start_seconds=60`，Logic 导出整曲伴奏为 `.local/demo/logic-instrumental.wav`：

```bash
auto-karaoke --project .local/demo/project.json replace-audio \
  --video work/karaoke-original.mp4 \
  --audio logic-instrumental.wav \
  --output work/karaoke-logic.mp4 \
  --audio-origin 0
```

如果导出的是 60–90 秒片段，将 `--audio-origin` 改为 `60`。所有文件参数相对于项目文件所在目录。

换轨使用 `-c:v copy`，因此保留画面与已烧录字幕；音频编码为 AAC。它检查时长覆盖，却不能判断 Logic 内部有没有拉伸或手动移动轨道，仍需试听首句和末句。只替换伴奏不必重做字幕；若也换人声并希望重新估计对齐，则重跑 `emit → align → subtitles → render`。
