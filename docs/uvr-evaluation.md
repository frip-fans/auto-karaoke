# UVR5 模型与接入评估

评估日期：2026-09-10。结论：继续通过现有 audio-separator 接入 UVR 模型生态，优先增加模型预设与对比试听；不把桌面 GUI 当作新的分离模型或音质升级。

## 核实范围

- [UVR 官方仓库](https://github.com/Anjok07/ultimatevocalremovergui)，master tree `5517e0cf0d1acd16a1618eeedec596957523f9e1`，README 标注 GUI v5.6。
- [官方模型下载目录](https://raw.githubusercontent.com/TRvlvr/application_data/main/filelists/download_checks.json)。下载目录与桌面版本支持范围必须分开判断：目录同时有 `other_network_list`；所查 master 源码树没有 RoFormer 实现文件，不能据目录断言每个 v5.6 安装包都能原生运行全部 RoFormer。
- [audio-separator](https://github.com/nomadkaraoke/python-audio-separator)，本地安装 0.47.0；读取本地模型加载与 ensemble 实现。

## 模型家族

| 家族 | 下载目录中的代表模型 | 对当前任务的意义 |
| --- | --- | --- |
| VR Architecture | 1_HP-UVR、5_HP-Karaoke-UVR、6_HP-Karaoke-UVR | 可作为另一种分离或主唱/和声处理候选，具体输出语义需逐模型确认 |
| MDX-Net | Inst HQ 3/4/5、Kim Vocal 1/2、Kim Inst、Karaoke 1/2 | 原项目默认 Inst HQ 3 就属于 UVR 模型目录；可作较轻量基线 |
| MDX23C | MDX23C-InstVoc HQ (`MDX23C-8KFFT-InstVoc_HQ.ckpt`) | 值得与当前 RoFormer 做同片段对比 |
| BS-RoFormer | Viperx 1297、1296、1053 | 本次已运行的 Viperx 1297 与目录文件名完全一致 |
| MelBand RoFormer | Viperx 1143、Unwa Inst V1/V2、InstVoc Duality V1/V2 | 可试一个偏伴奏的候选，不能仅按参数量断定音质 |
| Demucs v4 | htdemucs、htdemucs_ft、htdemucs_6s | 适用于更多乐器分轨；本项目包装目前仅接受 vocals/instrumental 两轨，不能直接宣称兼容多轨输出 |

以上是目录与实现核查，不是同歌听感排行榜。主唱去除、和声保留、齿音残留与乐器损伤之间存在取舍；模型名称中的 Karaoke 不应直接等同于“去掉所有人声”。

## 与现有项目的关系

`src/auto_karaoke/ml.py::separate` 已调用 audio-separator，可通过 CLI `separate --model <目录文件名>` 选择模型。当前已有真实 CUDA RoFormer 分离结果；更换 GUI 本身没有证据会改善结果。相同权重、预处理、精度、分段和后处理才是公平对比条件，不能保证不同实现输出逐样本相同。

尚未接入的能力：

1. 可读模型预设和配置优先级。当前 CLI 默认小 MDX；仅在项目 JSON 填 `separator_model` 不会被 CLI 自动使用，本次通过本地调用脚本显式传入。
2. 每个候选独立输出目录，防止试听比较时覆盖现有分轨及对齐缓存。
3. 可配置 overlap、精度、后处理和实际设备/参数记录。
4. 多模型 ensemble。上游 audio-separator 已有波形/频域及 UVR min/max spec 组合实现，但本项目没有暴露；不同算法不能笼统当作平均，也不能预先宣称必然更好。
5. 主唱/和声与多乐器输出的显式映射；现有包装遇到两轨以外输出会报错。

## 建议的下一轮验证

保留当前 BS-RoFormer Viperx 1297 作为基线。在同一段约 30 秒的主唱、副歌、密集编曲素材上，另跑 MDX23C-InstVoc HQ 和一个 Unwa MelBand Inst 模型。做响度匹配的试听，比较残留主唱、和声保留、鼓镲/合成器损伤与耗时，再选是否跑整曲或尝试 ensemble。

已按用户后续要求实跑 MDX23C-InstVoc HQ 整曲；没有安装 UVR 桌面版，也没有实跑新增 MelBand 候选或做听感优劣声明。模型权重与相关代码的使用条件应分别核对，不能从 GUI 的说明推断所有第三方权重的授权范围。

## 后续实跑：MDX23C-InstVoc HQ

同一约 304 秒输入、RTX 4070 SUPER 12 GB、audio-separator 0.47.0、batch size 1、遵循模型配置的 overlap：

| 模型 | 加载（含首次下载） | 分离与写出 | RTF |
| --- | --- | --- | --- |
| BS-RoFormer Viperx 1297 | 17.97 秒 | 142.17 秒 | 0.468 |
| MDX23C-InstVoc HQ | 17.27 秒 | 71.11 秒 | 0.234 |

这次 MDX23C 运行时 CPU 同时在编码视频；不是受控性能基准，不能把约两倍速度差推广到所有设备或设置。两模型均通过样本长度、有限数值与轨道结构检查；听感没有量化评分。另生成两组各 30 秒、固定增益匹配 RMS 的伴奏试听，未做动态压缩；这不是感知 LUFS 匹配。音视频、试听与报告保留在 Git 忽略的本地目录。
