# 我做了一个 Codex Skill 使用分析工具：把本地会话日志变成可读的可视化报告

**摘要**

如果你经常在 Codex 里安装和尝试各种 skill，过一段时间通常很难回答三个问题：哪些 skill 真正被用过？哪些项目消耗了最多对话？哪些已经安装的 skill 其实从未触发？我做了一个开源的本地优先工具 `codex-usage-insights`，把这些信息整理成一个浏览器可打开的 HTML 仪表盘。

## 为什么要做它

Codex 的 skill 很容易越装越多，但“安装”不等于“采用”。很多时候我们以为自己在使用某个工作流，实际只是偶尔提到它；也有一些 skill 安装后再也没有被调用。

我想要的是一个轻量、可审计、不会把私人对话上传到云端的报告工具，所以它直接读取本机 Codex 会话 JSONL，并把结果写成 HTML 和 JSON 文件。

## 它能回答什么问题

- 最近一段时间明确使用过哪些 skill，以及各自出现了多少次
- 哪些项目和日期产生了最多消息
- 哪些已经安装的 skill 在选定时间窗口内没有被观察到
- 一个 skill 第一次和最后一次出现在哪个会话、哪个项目

报告页面包含筛选器、趋势图和来源信息。页面既可以通过本地 HTTP 服务加载旁边的 JSON，也保留了内嵌回退数据，直接打开 HTML 文件也能查看。

## 如何安装

现在可以通过 Agent Skills CLI 安装：

```bash
npx skills add holooooo/codex-skill-usage
```

它也支持手动复制到 Codex 的 skill 目录：

```text
~/.codex/skills/codex-usage-insights
```

安装完成后，在 Codex 中明确要求使用 `$codex-usage-insights`，再生成报告。

## 如何生成第一份报告

```bash
python3 codex-usage-insights/scripts/codex_usage_report.py \\
  --output /tmp/codex-usage-insights.html \\
  --data-output /tmp/codex-usage-insights.json
```

默认统计最近 7 个日历日，也可以使用 `--days 30`，或用 `--start` 和 `--end` 指定时间范围。

## 隐私和边界

这个工具只读取本机文件并写入你指定的输出路径：

- 不上传会话日志
- 不读取系统消息、工具 schema 和工具输出作为使用证据
- 只有在用户或 assistant 文本中明确出现 skill 名称时才计数
- 报告是本地观察结果，不是账单、Token 计费或服务端用量数据

仓库里的演示数据是虚构记录，预览图也不包含个人会话路径。

## 项目地址

- GitHub: https://github.com/holooooo/codex-skill-usage
- Skills 安装入口: `npx skills add holooooo/codex-skill-usage`

如果你也在维护一套 Codex skill，欢迎试用后提 issue：我特别想知道大家更关心“skill 采用率”、项目活动趋势，还是长期未使用 skill 的清理建议。

**建议话题**：#OpenAI Codex# #AI编程# #开发者工具# #开源项目# #效率工具#

**配图建议**：使用仓库中的 `docs/preview.png`，或发布一张不含个人路径的报告截图。
