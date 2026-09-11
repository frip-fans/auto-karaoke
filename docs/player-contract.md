# 制作端与独立播放器的交接

播放器项目：[frip-fans/auto-karaoke-player](https://github.com/frip-fans/auto-karaoke-player)。它负责曲库、点歌、混音和 HDMI 投屏，已从本仓库移出。维护中的输入说明见 [MP4 interface v1](https://github.com/frip-fans/auto-karaoke-player/blob/main/docs/media-format.md)。

制作端的职责到最终 MP4 为止：

- H.264 视频，字幕、注音与标题卡已烧录到画面。
- 第一条音轨为 `Instrumental`，默认播放。
- 第二条音轨为分离的 `Vocals`，非默认；不能用 `Original Mix` 代替。
- 推荐双轨 AAC / 44.1 kHz / 立体声；两轨与视频必须对应同一演唱版本、时长和时间原点。
- 同时写入音轨 title 与 handler_name 时，保持语义一致。

当前制作配置使用 `dual_audio: true`、`dual_audio_source: "vocals"`；交付 `work/karaoke-dual-audio.mp4`。播放器导入此文件即可，不需要工作目录、歌词 JSON、模型缓存或制作环境。

专辑、曲名、演唱者和版本可以在播放器导入时填写，不要求从制作项目配置读取。曲库文件夹可独立移动，浏览器队列和历史不属于制作产物。

职责分别维护：改变歌词或视觉效果在制作端重新输出视频；点歌、调节导唱音量与投屏在播放器端完成。原 `player/` 的提交历史仍保留在本仓库历史中，后续播放器代码在独立仓库更新。
