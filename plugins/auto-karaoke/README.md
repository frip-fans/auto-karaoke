# Auto Karaoke 插件

包含环境配置 `karaoke-setup`，以及 `audio-separate`、`karaoke-author`、`karaoke-render` 三个制作 skills。

## 安装

从仓库根目录执行：

```bash
codex plugin marketplace add .
codex plugin add auto-karaoke@frip-fans
```

新开会话后使用 `$karaoke-setup`，让 Codex 检查电脑并提出安装方案。安装依赖、创建环境或下载模型前，需要你明确同意。检查脚本随插件提供，不依赖制作工具或模型；真正的计算仍使用单独安装的 `auto-karaoke` CLI。

只需要单个 skill 时，也可以用复制安装脚本：

```bash
python plugins/auto-karaoke/install_skills.py --skill audio-separate
```

默认安装到 `~/.agents/skills/`，不覆盖已有同名目录。两种安装方式选一种即可。

## 更新与卸载

更新仓库中的插件版本后，重新执行安装命令并新开会话。卸载：

```bash
codex plugin remove auto-karaoke@frip-fans
```

[GPLv3](LICENSE) (`GPL-3.0-only`)。
