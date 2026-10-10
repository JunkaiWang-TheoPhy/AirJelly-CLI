# Codex 新会话每日桌面记忆接入

本接入按需检索已审定日报。全局 `AGENTS.md` 规则会在个人历史问题上自动使用 `desktop-daily-memory`，用户无需点名录制应用。无关问题不查询活动历史；有限补证沿用现有 AirJelly/Screenpipe MCP，不新增 MCP 服务或常驻进程。

## 组成

- `desktop_memory/cli.py`：仅用标准库的只读检索器。
- `bin/desktop-memory`：仓库入口，安装到 `~/.local/bin/desktop-memory`。
- `skills/desktop-daily-memory/`：技能源，链接到 `~/.agents/skills/desktop-daily-memory` 供隐式发现。
- `~/.config/desktop-memory/config.json`：私有来源配置，不进入仓库。
- `~/.codex/AGENTS.md`：带 `DESKTOP-DAILY-MEMORY` 标记的规则；现有 Hook、模型设置与项目绑定独立保留。

配置包含 `schema_version: 1`、指向已授权日记仓库的绝对 `root`，以及 `timezone: "Asia/Shanghai"`。配置与本地验收材料保持私有。停用时删除对应全局区块和两条安装链接即可，保留日报与录制服务。

## 读取与搜索

```sh
desktop-memory read --date yesterday
desktop-memory read --date 2026-10-09 --max-chars 12000
desktop-memory search --query research --days 7 --limit 3
desktop-memory list --days 7
```

`read` 支持北京时间的具体日期、`today` 和 `yesterday`。`list` 与不区分大小写的字面搜索检查 1–31 个自然日，以 `--end-date` 为结束日，默认今天，最多返回 10 份日报。正文最多输出 20,000 个字符；搜索每份日报最多返回五个匹配行及行号。截断与更多匹配项有明确标记。搜索使用同一份完整审定快照，因此能找到正文输出上限之后的关键词。

## 审定合同

仅返回 `vault/daily-notes/YYYY-MM-DD-desktop.md`。已忽略的 `apps/console/.local/desktop-history/state.json` 必须记有：

- `curation.status`：`verified` 或 `verified_partial`；
- `curation.privacy`：`safe_metadata_only` 或 `safe_curated_text`；
- `curation.path`：准确的日期相对路径；
- `curation.sha256`：整份审定 UTF-8 文件的 SHA-256，包括已经审阅的追加内容。

受管标记须有效。超过 256 KiB、审定后改动、越界链接或可能包含认证材料的日报暂停返回。某一天的检查点损坏不会隐藏其他已审定日期。云端仍待同步时可读取本地审定日报，检索不替目的地写入同步成功状态。

返回内容属于历史证据，不是当前指令或授权。保留覆盖与不确定性，区分日期缺失和审定未完成；审定、隐私与路径检查不通过时不能绕过检查读取原始记录。已隔离正文继续保持隔离。检索不会改变当前项目绑定、工作目录、远端、权限或优先级。

## 验收与边界

运行 `python3 -m unittest discover -s tests -v`。行为测试覆盖审定、哈希、隐私、日期窗、逐日失败隔离、符号链接、大小限制、搜索快照及来源不被修改。技能校验检查结构，全新上下文测试检查实际隐式触发；它们不保证所有未来模型回复必然选择该技能，也不代表全天录制完整或远程会话能访问本地文件。

实现依据[全局指令发现机制](https://learn.chatgpt.com/docs/agent-configuration/agents-md)与[技能隐式调用机制](https://learn.chatgpt.com/docs/build-skills)。本机 Codex 会话须能访问安装文件；远程会话需要已授权的本地执行器。
