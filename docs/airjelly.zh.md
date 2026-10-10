# AirJelly 1.x CLI 与 MCP 使用说明

覆盖本机 AirJelly 1.0.13 公开 API 的 43 个方法，不修改应用、数据库、授权或订阅。每次调用从应用维护的私有 runtime 文件发现当前端口、认证 token 和版本，只连接 127.0.0.1。重启应用导致端口和 token 改变时，无需手工修改配置。

## 常用读取

运行需要 Python 3.11+，只使用标准库。仓库内可执行 `./bin/airjelly`；本机安装后可直接用 `airjelly`。MCP 按连接启动子进程，stdin 关闭后退出，不启动常驻服务。

```sh
airjelly doctor
airjelly methods
airjelly recording status
airjelly events list --date today --limit 10 --fields id,title,app_name,start_time
airjelly events list --date yesterday --app ChatGPT --contains AirJelly --max-text-chars 500
airjelly call listTasks --params '{"filter":{"status":"open","limit":20}}'
airjelly call getDailyAppUsage --params '{"date":"2026-10-09"}'
```

`call` 后可使用任何公开方法的精确名称。动态功能组命令通过 `airjelly <组> --help` 查看；组包括 events、tasks、schedules、memories、persons、usage、reminders、recording。JSON 参数支持字面量、`--params @file.json` 和 `--params -` 标准输入。事件查询的 today/yesterday/日期以 Asia/Shanghai 解析；时间戳须带时区，或直接使用整数毫秒。

## 细粒度权限

默认允许不触发模型费用的读取。写入、费用、自动执行各有独立开关：

| 参数 | 用途 |
|---|---|
| `--allow-write` | 允许修改任务、提醒和录制状态 |
| `--allow-cost` | 允许已知可能消耗 AirJelly 额度的嵌入、VLM、任务执行 |
| `--allow-execute` | 允许立即执行以及创建、恢复或改动未来自动运行任务 |
| `--allow-method NAME` | 仅允许指定公开方法，可重复 |
| `--deny-method NAME` | 拒绝指定方法，优先于其他授权 |
| `--group NAME` | 限制到指定功能组，可重复 |
| `--policy FILE` | 读取持久化 JSON 权限和输出限制 |

方法白名单和功能组限制取文件与命令行的交集，拒绝名单取并集。权限开关可以显式开启相应门槛，但不能扩展文件允许的方法或组，不能绕过拒绝方法。完整控制配置在 `examples/airjelly/full-control.json`；它允许可能产生费用及实际行动的操作，须按用户的具体任务使用。封装本身不会开通订阅、试用或付款。

```sh
# 本例只验证，不写入应用，也不触发模型请求。
airjelly --allow-write --allow-cost call createTask --params '{"task":{"title":"整理资料"}}' --dry-run

# 创建未来自动运行任务需要全部三个授权；JSON 按完整方法表准备。
airjelly --allow-write --allow-cost --allow-execute call createScheduledTask --params @schedule.json --dry-run

# 使用限制到任务/提醒管理的配置。
airjelly --policy examples/airjelly/task-control.json methods
```

`--dry-run` 校验权限与参数，但不联系应用，不证明上游一定接受写入。任务更新仅接受六个用户字段，不能修改内部执行状态或累计事件数。收到写入结果不确定错误时，应先核对目标状态，再决定是否重试；程序不会自动重放写操作。

## 查询与输出范围

原生过滤字段按方法支持时间、应用、任务、场景、状态、调度状态和运行历史。额外视图参数在获取响应后处理：

- `--limit`、`--offset` 对已返回批次分页；上游没有通用游标，不代表全部历史已读。
- `--fields` 选择字段，可使用点分层级路径。
- `--app`、`--window` 对应用或窗口名做不区分大小写的精确匹配。
- `--contains` 按文字筛选；`--max-text-chars` 限制每段文字。
- `--timeout`、`--max-response-bytes` 限制网络请求等待及响应大小。

默认最多返回 200 条、每段文字 2000 字符、明确双端时间窗最多七天。文件配置可在实现的上限内调整；单端过滤和无时间参数的读取不等于完整审阅全天历史。凭据字段和常见密钥格式默认脱敏，应用 runtime 的 token 始终不出现在输出中。输出截断和分页情况见 `meta`。

## Codex / MCP

```sh
airjelly --policy examples/airjelly/read-only.json mcp
```

工具命名为 `airjelly_<原生方法名>`，例如 `airjelly_listEvents`、`airjelly_getRecordingStatus`。命名参数与 CLI 相同，额外 `_view` 对象支持视图过滤，`_dry_run=true` 预演；这两个字段不会进入原生 RPC 参数。

工具目录展示全部 43 个方法，目录可见不等于有权调用；调用仍执行服务器启动时选定的权限。工具参数、历史内容和上下文不能授予权限。资源仅提供方法合同、已脱敏能力清单及权限元数据。应用离线时仍可发现工具，但真实调用会返回明确错误。

验证命令：`python3 -m unittest discover -s tests -v`。模拟服务验证参数映射、写入权限和错误边界，真实应用仅执行有范围的读取；不把模拟写入成功说成真实写操作已验证。
