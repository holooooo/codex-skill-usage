# codex-usage-insights

`codex-usage-insights` 内含同名 Codex skill。它读取本机的 Codex 会话 JSONL 日志，在指定日期范围内统计 skill、项目和消息，并生成 HTML 页面和 JSON 数据文件。

英文主文档：[README.md](README.md)

## 能做什么

- 统计对话中明确出现过的 skill 名称和次数
- 按项目、日期查看消息量和 skill 分布
- 列出所安装但在时间窗口内没有观察到的 skill
- 输出 JSON 数据，页面从同目录加载它并绘制筛选器和趋势图

仓库里的截图和报告使用 `examples/` 中的虚构数据，不包含个人会话路径或项目名。预览页面见 [examples/demo_report.html](examples/demo_report.html)，数据见 [examples/demo_report-data.json](examples/demo_report-data.json)。

直接双击 HTML 也能预览，因为页面保留了内嵌回退数据。要测试外部 JSON 加载，可在输出目录运行 `python3 -m http.server 8000`，然后打开 `http://localhost:8000/报告文件名.html`。

## Install

### 通过 skills.sh 安装

使用开放的 Agent Skills CLI 安装仓库中的 skill：

```bash
npx skills add holooooo/codex-skill-usage
```

如果只需要当前 skill，可在提示中选择 `codex-usage-insights`：

```bash
npx skills add https://github.com/holooooo/codex-skill-usage
```

同一份 skill 源码也可用于 Codex、Claude Code、Cursor 等兼容 agent。
安装后如果 agent 没有立即识别，请重启 agent。

把下面这段 prompt 直接发给 Codex 会话：

```text
请从 https://github.com/holooooo/codex-skill-usage 安装 Codex skill。
读取 codex-usage-insights/SKILL.md，把 skill 安装到 ~/.codex/skills/codex-usage-insights，
并确认 SKILL.md 和 bundled scripts 都存在。不要复制或发布本地会话日志。安装完成后，
只有在我明确要求时才使用 $codex-usage-insights 生成报告。
```

安装完成后，在 Codex 中使用 `$codex-usage-insights` 即可。

## 使用

```bash
python3 codex-usage-insights/scripts/codex_usage_report.py \
  --output /tmp/codex-usage-insights.html \
  --data-output /tmp/codex-usage-insights.json
open /tmp/codex-usage-insights.html
```

默认读取最近 7 个日历日。可以用 `--days 30`，或同时传入 `--start`、`--end`。如果日志或 skill 不在默认目录，可重复传入 `--sessions-root` 和 `--skills-root`。

## 注意

这是本地日志的观察结果，不是账单或服务端用量。只有在选定时间范围内，skill 名称出现在用户或 assistant 文本中时才会计数。系统消息、工具 schema 和工具输出会被忽略。

许可证：MIT，见 [LICENSE](LICENSE)。
