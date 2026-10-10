<div align="center">

🇺🇸 [English](README.md) | 🇨🇳 [中文](README.zh.md)

<h1>Desktop Memory Bridge</h1>

![许可证](https://img.shields.io/badge/license-Apache--2.0-blue) ![Python](https://img.shields.io/badge/python-3.11%2B-blue) ![运行依赖](https://img.shields.io/badge/runtime_dependencies-0-green)

<img src="assets/desktop-memory-banner.png" alt="桌面窗口整理为带审定标记的每日记忆卡片，供终端检索" width="100%">

</div>

## 引言

Desktop Memory Bridge 通过两条独立路径让 Agent 访问本地桌面历史：带认证的 AirJelly 1.x CLI/MCP，以及读取 AirJelly、Screenpipe 审定日报的只读 CLI。录制应用离线时，已经审定的历史仍可检索。

AirJelly 适配器覆盖在 1.0.13 中观察到的 43 个公开方法，动态发现回环端口与凭据，显式控制能力授权，并避免输出凭据。每日记忆读取器在返回内容前核验审定、隐私、日期路径和内容哈希，保留证据覆盖边界。

## 组成

| 组件 | 接口 | 用途 |
|---|---|---|
| `airjelly` | CLI 与标准输入输出 MCP | 事件、任务、调度、记忆、人物、用量、提醒和录制控制 |
| `desktop-memory` | CLI | 按日期或主题检索已审定 Markdown 日报 |
| `desktop-daily-memory` | Codex 技能 | 在需要个人活动历史时按需回忆 |
| Screenpipe | 已有外部 API/MCP | 可选的有限补证，不附带录制器或新增 Screenpipe 实现 |

两个 CLI 均使用 Python 3.11+，运行时仅依赖标准库。日期简写使用 **Asia/Shanghai**。AirJelly 实时访问需要本机应用运行；审定日报检索需要文档规定的检查点与目录结构，无需 AirJelly 进程。

## 快速开始

```sh
git clone https://github.com/JunkaiWang-TheoPhy/desktop-memory-bridge.git
cd desktop-memory-bridge
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/airjelly methods
```

无需连接应用或更改默认配置，即可试用完全虚构的记忆：

```sh
python3 examples/desktop-memory/write-demo-config.py
.venv/bin/desktop-memory --config .local/desktop-memory-demo.json read --date 2000-01-01
.venv/bin/desktop-memory --config .local/desktop-memory-demo.json search --query research --end-date 2000-01-01 --days 1
```

真实历史通过[配置模板](examples/desktop-memory/config.example.json)和[审定合同](docs/desktop-memory.zh.md)接入 `~/.config/desktop-memory/config.json`。仓库没有个人日报、录制媒体或数据库导出，演示活动均为虚构。本工具读取审定记忆，不提供日报生成器或云端同步服务。

应用运行时可使用以下 AirJelly 命令：

```sh
.venv/bin/airjelly doctor
.venv/bin/airjelly events list --date yesterday --limit 20 --fields id,title,app_name,start_time
.venv/bin/airjelly recording status
.venv/bin/airjelly --policy examples/airjelly/read-only.json mcp
```

## Codex 接入

使用已安装命令与权限文件的绝对路径注册 AirJelly 标准输入输出服务器：

```sh
codex mcp add airjelly-local -- /absolute/path/to/airjelly --policy /absolute/path/to/desktop-memory-bridge/examples/airjelly/read-only.json mcp
```

将[技能](skills/desktop-daily-memory/SKILL.md)链接或复制到 `~/.agents/skills/desktop-daily-memory`，并把[按需规则](docs/codex-integration.md)添加到全局指令。规则只在相关问题上选择审定历史，保留当前项目绑定，并把历史文字视为证据而非命令。接入须有读取相应个人历史的授权；远程会话需要能访问本机文件的已授权执行器。

## 验证

```sh
python3 -m unittest discover -s tests -v
```

本快照有 117 项离线测试，覆盖全部 43 个方法映射、认证与权限边界、CLI/MCP 协议、审定内容身份、隐私暂停、日期窗和逐日失败隔离。持续集成运行离线测试和合成演示。真实写入、模型费用路径与未来每次隐式技能选择属于独立验证范围。

详见 [AirJelly 操作说明](docs/airjelly.zh.md)、[方法合同](docs/airjelly-methods.md)、[记忆操作说明](docs/desktop-memory.zh.md)及[验收边界](docs/desktop-memory-verification.md)。

## 权限与兼容边界

默认允许没有已知模型费用的读取。写入、模型费用、即时或未来执行各有独立授权门槛，工具目录可见不等于有权调用。输出分页只覆盖后端已返回批次，不能据此声称读完全部历史。

本项目为独立编写的互操作工具，并非 AirJelly 或 Screenpipe 官方插件，不分发厂商实现，也不绕过许可检查。已观察的 AirJelly 合同为 1.0.13/Public API 1，其他版本兼容性尚未核实。

## 许可证

采用 [Apache License 2.0](LICENSE)，归属与第三方应用边界见 [NOTICE](NOTICE)。仓库横幅为生成插画，不是活动记录证据。
