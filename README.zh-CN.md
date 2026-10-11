# qqmusicmcp

[English](README.md) | **简体中文**

**实验性 / Alpha 开发版 · 适用于 Linux 的非官方 QQ 音乐 MCP 服务（Python 3.11+）**

本项目通过一个 [Model Context Protocol（MCP）](https://modelcontextprotocol.io/) **stdio** 服务，整合腾讯音乐官方 QQ 音乐 Skill HTTP API，以及可选的、基于**非官方网页接口**的个人音乐库功能。

**本项目并非腾讯音乐官方产品，不代表腾讯音乐对本项目的授权、认可或背书。**

> 当前为早期开发版本，**不是稳定生产版本**。非官方网页 API 可能随时调整、失效或受到服务方限制。请自行评估账号风险并遵守相关服务条款、法律法规及版权要求。普通部署不依赖特定云厂商，无须域名或开放公网 MCP 端口。

## 功能与限制

| 功能 | 当前状态 |
| --- | --- |
| 官方搜索、每日推荐、猜你喜欢电台、排行榜、公开歌单、听歌报告 | 已实现；需要官方 API Key |
| 读取个人歌单和「我喜欢」、歌曲 MID 解析为数字 ID / 类型 | 已实现；需要 QQ 音乐网页登录 Cookie，属于非官方接口 |
| 创建普通歌单、添加或移除歌曲、删除**空歌单** | 实验性功能；默认禁用，须逐次在服务器终端人工批准 |
| 对「我喜欢」执行红心收藏或取消收藏 | **尚未实现**，目录 ID `201` 只读 |
| 批量事务、自动回滚 | **尚未实现**；不确定的写入结果必须人工核查 |
| 官方 AI 解读 SSE 接口 | 尚未实现 |

## 一、Linux 安装

运行要求：**Python 3.11 或更高版本**、[uv](https://docs.astral.sh/uv/)、Git，以及访问 QQ 音乐 API 的网络连接。

```bash
git clone https://github.com/flipped0419/qqmusicmcp.git
cd qqmusicmcp

uv sync --extra test
uv run pytest -q
```

运行 stdio MCP 服务：

```bash
uv run qqmusicmcp
```

该命令会等待 MCP 客户端的 JSON-RPC 请求，而不是启动供浏览器访问的 HTTP 网站。终端无普通输出是正常的；可以用 `Ctrl+C` 退出。

在支持 stdio 的 MCP 客户端中，将启动命令指向项目安装的可执行文件（通常为 `<项目目录>/.venv/bin/qqmusicmcp`），并将工作目录设为项目根目录。

某些环境会注入与项目依赖冲突的全局 `PYTHONPATH`；遇到这种情况，可尝试 `env -u PYTHONPATH uv run ...`。这只是特定环境的兼容处理，**不是 Linux 通用要求**。

本仓库不捆绑远程隧道、外部 OAuth 服务或公开 HTTP MCP 端点。如需从 ChatGPT 等远程客户端访问，可以另行配置带身份验证的 MCP 隧道；隧道安装、凭据和守护进程管理均属于**部署环节**，不必写入项目源码。

## 二、配置私有凭据

QQ 音乐**官方 Skill API Key** 与用于个人歌单的**浏览器 Cookie** 是两种独立凭据。

1. 从 [QQ 音乐 Skill 页面](https://y.qq.com/n/ryqq_v2/qqmusic_skills)申请官方 API Key。
2. 若需要读取个人歌单，请先在电脑浏览器登录 [QQ 音乐网页版](https://y.qq.com/)，打开开发者工具的 Network（网络）面板，从已登录的 QQ 音乐请求中获取 **Cookie 请求头的值**。
3. 在自己信任的 Linux 主机交互式终端执行：

```bash
uv run python scripts/configure_api_key.py
uv run python scripts/configure_cookie.py
```

两个脚本均使用隐藏输入，不会在终端回显凭据。**不要把 Key、Cookie、Token 等内容发送到聊天、写进命令行参数或提交到 GitHub。**

从源码仓库运行时，默认私有凭据文件位于项目根目录的**同级目录**：

```text
工作目录/
├── qqmusicmcp/                 # Git 项目源码
└── .qqmusicmcp/
    └── credentials.json       # 私有凭据（0600）
```

以已安装 Python 包方式运行时，默认使用 XDG 状态目录。可通过 `QQMUSIC_SECRETS_FILE` 指定其他凭据文件位置，或用 `QQMUSIC_API_KEY`、`QQMUSIC_COOKIE` 进程环境变量覆盖文件中的对应值。私有目录权限要求为 `0700`，凭据文件为 `0600`；有主机管理员权限的用户仍可能访问这些内容。

### 只读验证

```bash
uv run python scripts/test_personal_read.py
```

该脚本仅输出是否成功、歌单数量及「我喜欢」歌曲数量，不打印实际 Cookie、账号 ID 或歌曲清单。

在 MCP 客户端中，可以调用 `qqmusic_status` 检查配置状态；使用 `qqmusic_search` 搜索歌曲，再调用 `qqmusic_resolve_song_mid` 将搜索结果的 `songMid` 转换为写入操作所需的数字歌曲 ID / 类型。个人歌单工具支持只读列出歌单与歌曲。

## 三、实验性歌单写入

**默认只读：** 未显式启用时，`QQMUSIC_ENABLE_WRITES=false`。AI 仅获得预览票据并**不能**直接批准写入。

进行正常写入必须同时满足以下条件：

1. 当前账号与接口协议版本已经完成**一次性写入能力探针**。探针成功记录不因时间流逝自动过期，正常操作**不需要反复测试或创建临时歌单**。
2. 运营者有意为 MCP **进程**配置 `QQMUSIC_ENABLE_WRITES=true`。不要在面向不可信用户的服务上随意启用。
3. MCP 客户端调用 `qqmusic_preview_write`，生成对应操作的预览和有效期 **5 分钟**、仅可使用一次的 `confirmation_token`。
4. 用户必须在自己可信任的 Linux **交互终端**独立批准：

```bash
uv run python scripts/approve_write.py
```

根据提示输入预览票据，核对操作类型、目标歌单和歌曲 ID，再输入脚本要求的完整确认短语。此脚本**只记录审批，不执行 QQ 音乐写入**。绝不能将服务器终端或此审批脚本开放为可由 AI 随意调用的 MCP 工具。

5. 获得人工批准后，由 MCP 客户端调用 `qqmusic_apply_write` 并使用**同一张票据**。服务会检查权限、账号、目标及歌单当前状态，在网络写入前记录审计信息，随后只执行一次操作并回读验证。

服务器终端人工审批是一道独立安全措施；客户端自身的确认对话框也值得开启，但不能替代它。

### 首次写入探针：谨慎使用

只有首次需要验证非官方写入接口、并明确接受其风险时，才在交互终端运行：

```bash
QQMUSIC_ENABLE_WRITES=true uv run python scripts/test_write_probe.py
```

脚本会提示确认真实创建、加歌、移歌及删除**临时歌单**。**QQ 音乐可能在「恢复歌单」中保留删除记录**，因此请勿为日常写入反复运行探针，也不要未经同意自动执行。

若此前版本已经成功测试过探针，可以只迁移本地记录（**不会修改 QQ 音乐账号**）：

```bash
uv run python scripts/migrate_probe.py
```

### 网络超时、异常与人工恢复

网络超时**不等于操作未执行**。本 Alpha 版本不自动重试、不承诺完整回滚：

- 每次尝试写入都会在本地私有状态目录的 `write_journal/` 中留下持久审计记录，包含操作及必要的状态摘要，**不含 API Key 或 Cookie**。记录仍可能包含歌单名称或歌曲数字 ID，应视为私有账号数据。
- 如果出现超时、无法确认结果或进程中断，操作将保留为 `uncertain` 或 `in_flight`，**后续写入自动锁定**。
- 在终端运行只读核查与人工确认：

```bash
uv run python scripts/reconcile_writes.py
```

该脚本通过再次读取 QQ 音乐歌单，比对操作前后的状态；仅在结果可明确判断且用户人工确认后，才解除对应的本地锁定。它**不会再次提交写入、自动撤销或清理真实歌单**。若结果存在冲突或无法读取，保持锁定并人工排查。

审批记录与审计数据保存在源码目录之外。程序会对本机多个写入进程进行串行化，但其他设备上的 QQ 音乐客户端仍可能同时修改歌单；状态不一致时应停止写入，而不是盲目重试。

## 四、开发、测试与安全

```bash
uv sync --extra test
uv run pytest -q
uv tool run --from ruff==0.14.7 ruff check --select E4,E7,E9,F src scripts tests
uv build
```

自动化测试主要采用模拟 HTTP 响应和假凭据，不会直接修改真实 QQ 音乐账号。GitHub Actions 在 Linux 上检查 Python 3.11 / 3.12、代码规范、构建及仓库敏感文件跟踪规则。

建议阅读：

- [安全政策与漏洞反馈说明](SECURITY.md)
- [贡献指南](CONTRIBUTING.md)
- [MIT 许可证](LICENSE)
- [第三方版权与许可声明](THIRD_PARTY_NOTICES.md)

### 上游来源

- [tencentmusic/qqmusic-skills](https://github.com/tencentmusic/qqmusic-skills)（Apache-2.0）：本项目根据官方文档**独立实现** Skill HTTP 协议，未捆绑上游源码。
- [baoozak/qqmusic-mcp](https://github.com/baoozak/qqmusic-mcp)（MIT）：个人音乐库及歌单写入接口的协议实现参考与改编，原版权声明保存在 [licenses/baoozak-MIT.txt](licenses/baoozak-MIT.txt)。
- [L-1124/QQMusicApi](https://github.com/L-1124/QQMusicApi)（GPL-3.0-or-later）：仅用于研究，**没有复制或引入其源码**。

**提交 Issue、PR 或日志前，务必删除真实 API Key、Cookie、账号 ID、个人歌单内容及其他敏感信息。**
