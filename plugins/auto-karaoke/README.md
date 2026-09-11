# Auto Karaoke 插件

包含环境配置 `karaoke-setup`，以及 `audio-separate`、`karaoke-author`、`karaoke-render` 三个制作 skills。

## 安装

### Codex

从仓库根目录执行：

```bash
codex plugin marketplace add .
codex plugin add auto-karaoke@frip-fans
```

新开会话后使用 `$karaoke-setup`，让 Codex 检查电脑并提出安装方案。安装依赖、创建环境或下载模型前，需要你明确同意。检查脚本随插件提供，不依赖制作工具或模型；真正的计算仍使用单独安装的 `auto-karaoke` CLI。

### Claude Code

在本仓库根目录启动 Claude Code，在会话内执行：

```text
/plugin marketplace add .
/plugin install auto-karaoke@frip-fans
```

新开会话后使用：

```text
/auto-karaoke:karaoke-setup 检查我的电脑，告诉我分离音轨还需要安装什么。
/auto-karaoke:audio-separate 将这份 MV 分离成伴奏和纯人声。
/auto-karaoke:karaoke-author 用歌词和分轨制作时间轴。
/auto-karaoke:karaoke-render 用已确认的时间轴生成 1080p 视频。
```

Claude Code 和 Codex 共用 `skills/`，分别读取 `.claude-plugin/` 和 `.codex-plugin/` 清单。插件不包含制作引擎，仍需单独安装 `auto-karaoke` CLI；安装环境和下载模型前，skills 会先征得明确同意。

本地开发可从仓库根目录运行 `claude --plugin-dir ./plugins/auto-karaoke`，仅在该会话加载插件。

### 单独安装 skills

只需要单个 skill 时，也可以用复制安装脚本：

```bash
python plugins/auto-karaoke/install_skills.py --skill audio-separate
```

默认安装到 `~/.agents/skills/`，不覆盖已有同名目录。Claude Code 可加 `--destination ~/.claude/skills`；单独安装后的调用方式为 `/audio-separate` 等，不带插件前缀。每个客户端选择插件或单独 skills 安装即可，避免重复加载。

## 更新与卸载

Codex：更新仓库中的插件版本后，重新执行安装命令并新开会话。卸载：

```bash
codex plugin remove auto-karaoke@frip-fans
```

Claude Code：更新本地仓库后，在会话内执行以下命令并新开会话：

```text
/plugin marketplace update frip-fans
/plugin update auto-karaoke@frip-fans
```

卸载使用 `/plugin uninstall auto-karaoke@frip-fans`。发布插件更新时递增 `.claude-plugin/plugin.json` 中的 `version`。

配置检查（仓库根目录）：

```bash
claude plugin validate .
claude plugin validate ./plugins/auto-karaoke
```

格式与命令参考：[Claude Code 插件文档](https://code.claude.com/docs/en/plugins)、[marketplace 文档](https://code.claude.com/docs/en/plugin-marketplaces)。

[GPLv3](LICENSE) (`GPL-3.0-only`)。
