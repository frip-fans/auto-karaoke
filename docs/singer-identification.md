# 歌手识别模型评估

评估日期：2026-09-10。当前产品保留手工标记、导入和默认关闭的歌手配色开关。之前的 Gemini 自动分组已退出当前标记文件，不作为可靠标签或训练真值。

## Whisper 与说话人分段

[Whisper 官方说明](https://github.com/openai/whisper)将它定位为语音识别、翻译与语言识别模型。[WhisperX](https://github.com/m-bain/whisperX)额外组合时间对齐和说话人分段组件，分段使用 pyannote。分成 Speaker A/B 与认出真实姓名是两件事；姓名映射仍需参考录音或人工确认。

OpenAI API 同样区分普通转写与带 speaker 标签的 diarized_json，见 [官方 CLI 文档](https://developers.openai.com/api/docs/libraries/openai-cli#transcription)。这不代表本地 Whisper 自带歌手身份识别。

## 候选模型

| 候选 | 官方能力 | 用于本项目的判断 |
| --- | --- | --- |
| [Sony CSL Singer Identity](https://github.com/SonyCSLParis/ssl-singer-identity) | 面向歌声的身份表示；公开 BYOL、contrastive、VICReg 等预训练模型；输入原生 44.1 kHz 音频，输出 embedding | 最值得优先验证；用已确认独唱样本比较相似度，不能直接生成姓名或判断合唱 |
| [SpeechBrain ECAPA-TDNN](https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb) | VoxCeleb 声纹识别/验证与 embedding | 可作语音领域的对照基线；歌唱的音高、拖音与制作处理会造成领域差异 |
| [pyannote Community-1](https://huggingface.co/pyannote/speaker-diarization-community-1) | 说话人分段、变更及重叠说话分析 | 可辅助寻找变化位置，官方语音基准不能直接当作双人歌曲的合唱准确率；使用前需按模型页完成访问条件 |

Sony 的[论文](https://arxiv.org/abs/2401.05064)专门讨论歌声身份表示以及与语音模型基线的比较。这里只完成文档核查，没有对本歌实跑这三个候选，也没有声称它们一定比 Gemini 更准确。

## 建议的验证方法

1. 用户分别确认两位歌手的若干干净独唱片段，尽量覆盖高低音与不同唱法。使用分离后的 44.1 kHz 人声作原始样本，按各模型要求预处理。
2. 按现有歌词时间轴切片，先用歌声身份 embedding 与两个参考集合比较，再用人工标记检验。低相似度或两类分数接近时保留未知。
3. 跨曲评估时单独检查录音与音域差异，不能假定一个高音片段就代表歌手全部音色。
4. 合唱独立处理：两类相似度接近不等于合唱，单人叠唱、和声和混响也会产生混合特征。先保留人工合唱标签，再评估是否需要专门的双人混合检测或条件分离模型。
5. 任何自动结果均为候选，不能覆盖用户已确认的手工标记。

当前可直接使用的功能是手工标记导入与颜色渲染；研究模型尚未集成。
