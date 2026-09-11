# 本地 GPU PC / Codex 交接

## 工作目标

在用户本地 PC 运行音轨分离、声学对齐与视频制作；假名读法及其时间对齐仍需试听验收。项目现按三个制作模块与独立播放器组织，职责及待实现接口以 [架构与流程](pipeline.md) 为准。Mac 播放端单独使用 [auto-karaoke-player](https://github.com/frip-fans/auto-karaoke-player)，不需要安装下面的模型依赖。

早期样片在 ARM Linux CPU 上运行；本次已在本地 NVIDIA RTX 4070 SUPER 12 GB 环境实跑 MDX23C 整曲分离，并验证 NVENC 编码。运行记录见 [UVR 模型评估](uvr-evaluation.md)。下面的环境检查仍适用于迁移到新设备；已有设备的耗时与显存不能直接推广到其他硬件。

## 本地 Codex 先检查

1. 读取 README、[现成项目评估](existing-projects.md)、[pipeline](pipeline.md) 和 [服务器实测](benchmarks.md)。
2. 检查操作系统、Python、显卡、驱动、显存、可用磁盘空间。NVIDIA 可用 `nvidia-smi`；如是 AMD/Intel，不照搬 CUDA 安装步骤。
3. 独立建立 Python 3.12 环境，不修改系统 Python。
4. 查找本机已有 FFmpeg，检查 `ffmpeg -filters` 中是否有 `ass`，编码器是否有 `libx264`。按能力判断，不只看版本号。
5. 找到可用日文 TTF/OTF 字体及其家族名；使用本机路径更新配置，不把字体拷进 Git。

## GPU 安装与诊断

如果是 NVIDIA，在 [PyTorch 官方选择器](https://pytorch.org/get-started/locally/) 根据本机 OS、驱动与 CUDA 选安装命令，再在同一虚拟环境安装：

```bash
python -m pip install -e '.[align]'
# 有已校对歌词时不必安装转写扩展；有 Logic 分轨时不必安装分离扩展。
python -m pip install -e '.[transcribe]'
python -m pip install -e '.[separate]'
```

后三个推理栈分别是 PyTorch、CTranslate2 和 ONNX Runtime / PyTorch，不共享同一个“GPU 开关”。PyTorch 识别 GPU 不代表另外两个一定可用。faster-whisper 的 CUDA 库要求以 [官方 GPU 安装说明](https://github.com/SYSTRAN/faster-whisper#requirements) 为准。

`.[separate]` 基础安装使用 `onnxruntime` CPU 包。若要加速默认 MDX ONNX 模型，按 [audio-separator 文档](https://github.com/nomadkaraoke/python-audio-separator) 配置兼容的 GPU provider；NVIDIA 通常需要替换为匹配环境的 `onnxruntime-gpu`，避免与 CPU 包同时安装。RoFormer 使用 PyTorch 路径，不能仅凭 ONNX provider 判断它的运行设备。

项目参数：

```json
{
  "align_device": "cuda",
  "transcribe_device": "cuda"
}
```

把这两项合并进完整项目 JSON。`auto` 在对应后端可见 CUDA 时选择 CUDA，否则选 CPU；显式 `cuda` 不可用会报错，不会静默退回 CPU。对齐保持 FP32；转写 CUDA 使用 float16、CPU 使用 int8。分离设备由 audio-separator 选择并写入报告。

```bash
auto-karaoke --project .local/demo/project.json doctor --ml
```

`doctor` 不下载模型，只检查依赖、滤镜、字体和后端。报告中可见 GPU 也不代表推理必然成功；随后必须跑短片段。AMD、Intel、MPS 和 Windows 原生路径没有本仓库实测；需要按平台单独验收，必要时先用 CPU 完成对齐基线。Windows 的峰值 RSS 暂记为 null，不伪造测量。

## 第一轮验收

使用用户本地已有的一段 10–30 秒素材，放入 `.local/`；从已有歌词或人工校对文本准备该片段的 `lyrics.json`。优先导入 Logic vocals / instrumental，减少分离质量对对齐评估的干扰。

运行 `prepare → emit → align → subtitles → render`。如果没有歌词，`transcribe` 只产生草稿，先听音校对再做正式对齐。首次模型下载和本地推理分别记录时长。

验收必须覆盖：

- 汉字读法符合实际唱法，包含助词、连读、促音、长音；不能把自动词典读音当作已核实读法。
- 每个假名音拍都有来自声学对齐的起止时间；不能把整行或整词时长均分后声称逐音拍对齐。
- 原文与上方假名位置一致；不同字体需抽帧检查扫色是否出现重影。
- 手工 `overrides.json` 不被重跑自动步骤覆盖。
- 原视频、伴奏、字幕首句和末句同步；live 使用当前现场人声重新对齐。
- 分离、对齐、渲染顺序执行，记录实际显存与耗时；显存不足先缩短片段，不同时加载多个模型。

拿这段素材同时检验 [候选项目](existing-projects.md) 的假名结构和编辑／导出能力。若能承接时间轴，优先写小型转换器；只有明确缺失的部分才补实现。此次提交没有安装 Nightingale，也没有声称已完成任何上游集成。

## 后续交付

短片段通过后再处理整曲：实现带上下文重叠的分段、全局时间还原、边界重复去除和人工修正保留。当前 `emit` 上限 60 秒，不要直接把整场 live 送入单段模型。

保存本机依赖版本、显卡信息、参数和测量报告到 `.local/`；只把不含素材、歌词或隐私路径的统计摘要整理进 docs。用户的音视频、截图、真实歌词、成品 ASS 和模型缓存不得进入 Git，包括历史提交。
