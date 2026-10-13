# OctoSense App Flow

[English](README.md) | 简体中文

未注明中文版的链接指向英文文档。

**设计、构建、测试并提交 OctoSense 应用的 Agent 流程。**

App Flow（原名 OctoScript App Design Flow）负责制作 [OctoSense](https://github.com/OctoSense-org) 应用，[OctoSense App Hub](https://github.com/OctoSense-org/OctoSense-App-Hub) 负责发布应用。App Flow 不是图形界面 IDE，而是基于命令行的开发工具集，包含 Agent 流程、模板和指南。App Hub 的 [`card-studio`](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/DEVELOPMENT.zh-CN.md#发布前检查卡片card-studio) 是另一个独立工具，用来渲染卡片并辅助评审。

App Flow 带着你（或编码 Agent）从一个想法（一段文字需求、一张生成的 UX 图）走到一个隔离运行的应用包：通过 [OctoSense App Hub](https://github.com/OctoSense-org/OctoSense-App-Hub) 的准入检查，可以生成带 GitHub 证明的 Release 并接受 App Hub 审核，无需单独的开发者签名密钥。

仓库包含：给 Agent 的规则（[AGENTS.md](AGENTS.md)）、分步骤的设计流程（[flows/](flows/README.zh-CN.md)）、开发者文档（[docs/](docs/)）、可直接运行的应用模板（[templates/script-app](templates/script-app/README.zh-CN.md)）、完整示例（[examples/](examples/README.zh-CN.md)），以及 `tools/octo`：一个小型命令行工具，封装 App Hub 的 `card-host` 和 `hub` 程序。`tools/octo` 从不决定准入：`check` 先为未签名的应用包写入摘要（stamp），再原样转交 `hub check` 的输出和退出码。

本仓库面向黑客松选手、其他 OctoSense 应用开发者，以及与他们协作的编码 Agent。本仓库最初名为 *OctoScript-AppCard*。

## 目录

- [黑客松：从这里开始](#黑客松从这里开始)
- [连接账户的应用：GitHub、Gmail 和 Google Calendar](#连接账户的应用githubgmail-和-google-calendar)
- [Agent 从这里开始](#agent-从这里开始)
- [现状](#现状)
- [快速上手](#快速上手)
- [`tools/octo`](#toolsocto)
- [设计流程](#设计流程)
- [应用是什么](#应用是什么)
- [隔离规则](#隔离规则)
- [应用中的 AI](#应用中的-ai)
- [运行应用](#运行应用)
- [无头测试：同时测多个应用，不占屏幕](#无头测试同时测多个应用不占屏幕)
- [发布](#发布)
- [仓库结构](#仓库结构)
- [示例](#示例)
- [参与贡献](#参与贡献)
- [相关仓库](#相关仓库)
- [许可证](#许可证)

## 黑客松：从这里开始

本仓库只负责技术路径。比赛本身（规则、日程、评审、作品如何提交）请见 [Agentic App Hackathon](https://create.gosim.org/agenticapp26/) 页面并咨询主办方。选手需要从这里获得的内容：

| 主题 | 要点 |
| --- | --- |
| **起步** | 下面的[快速上手](#快速上手)：每一步都是 shell 命令。 |
| **机器** | 完整指南已在 Apple 芯片上的 macOS 上运行。App Hub 的 Windows、Linux CI 也已通过原生工具构建及 contract、policy、CLI、模态输入测试；这些平台上的原生应用交互需要单独验证。Linux 软件渲染下的截帧仍未验证。见[平台证据](docs/QUICKSTART.zh-CN.md#1-前置条件)与[快速上手](#快速上手)。 |
| **应用能做什么** | 使用自己的存储；发送公开 HTTPS 请求并披露预计目的地；显示图片和网页；使用相机和设备定位；通过宿主的 `mail` 服务读取邮件；发布速览卡片；调用 `model.complete`；在兼容的 RC 发行版中通过宿主使用用户的 GitHub、Gmail 或 Google Calendar 账户；从 RC2 起，还能导入导出文档（macOS、Windows 和 Android），并在 macOS 和 Android 上读写设备日历、经用户审阅后发送邮件、播放或录制短音频，均按平台限制提供。能力见 [docs/CAPABILITIES.zh-CN.md](docs/CAPABILITIES.zh-CN.md)，语言与全部 API 见 [docs/SCRIPT-API.md](docs/SCRIPT-API.md)。 |
| **应用不能做什么** | 持有密码、API key 或令牌，即使存放在自己的存储里也不行。通过应用自己收集秘密的任意表单登录：兼容 RC 在支持的平台上提供宿主运行的后端登录，后端在应用的清单中声明，或由宿主的运维人员注册（[CAPABILITIES](docs/CAPABILITIES.zh-CN.md#登录应用自己的后端)、[App Hub#16](https://github.com/OctoSense-org/OctoSense-App-Hub/issues/16)）。在 beta.2 或 `card-host` 上生成媒体或计算嵌入向量：这些服务需要 [OctoSense #368](https://github.com/OctoSense-org/OctoSense/pull/368) 的实现，自 RC1 发行版起包含，[下载状态](#下载兼容-shell)（[媒体指南](docs/AI-SERVICES.zh-CN.md#媒体与嵌入向量model)）。自创能力或宿主服务（这需要修改 App Hub 和 Shell），使用只供系统应用的 `llm`、`news`、`calendar` 能力或 `os.*` id，或附带原生代码。 |
| **应用中的 AI** | 开发应用不需要任何 AI 服务，`card-host` 也不提供 AI 服务，所以应用不依赖 AI 也要完整可用。见[应用中的 AI](#应用中的-ai)。 |
| **参考应用** | 三个已发布的[连接账户的应用](#连接账户的应用githubgmail-和-google-calendar)。 |
| **演示** | 在 `card-host` 中运行应用（`tools/octo run`，通过远程控制桥操作），并用 `tools/octo shot` 截取真实截图。要在 OctoSense 内连同宿主服务一起展示，让 OctoSense 桌面端 Shell 读取本地签名目录（[PUBLISHING §4](docs/PUBLISHING.zh-CN.md#4-在本地演练商店流程)）。 |
| **提交到 App Hub** | 先按 [docs/PUBLISHING.zh-CN.md](docs/PUBLISHING.zh-CN.md) 准备好应用包，再由人工按 App Hub 的 [SUBMITTING.zh-CN.md](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/SUBMITTING.zh-CN.md) 开 issue 表达发布意图，并附上带 GitHub 证明的 Release。参赛作品不等于自动提交到 App Hub；比赛需要什么，以黑客松页面为准。 |
| **无头测试** | `tools/octo run … --hidden`：窗口不会出现，Agent 测试应用时不会占用你的屏幕（也可同时测多个应用，每个用自己的 `--port`）。见[无头测试](#无头测试同时测多个应用不占屏幕)。 |
| **检查 Agent 做出的应用** | [docs/MODEL-VALIDATION.zh-CN.md](docs/MODEL-VALIDATION.zh-CN.md)：以原生方式操作应用并截图，修复失败之处，并把证据与最终源码对应起来。 |
| **Agent 应用参考** | [Email Action 与 Meeting Planner](examples/agentic-hackathon/README.zh-CN.md)：虚构邮件/日历、真实应用 Agent 入口、明确标注的离线路径、操作前确认及原生交互测试。 |
| **卡住了** | [QUICKSTART § 故障排查](docs/QUICKSTART.zh-CN.md#故障排查)、[SCRIPT-API § Gotchas](docs/SCRIPT-API.md#gotchas)，然后看 App Hub 的[常见拒绝原因及修复](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/SUBMITTING.zh-CN.md#常见拒绝原因及修复)。 |

## 连接账户的应用：GitHub、Gmail 和 Google Calendar

公开 App Hub 签名目录 **15** 提供以下带 GitHub 证明的版本（GitHub Notes 为 **0.2.2**，其余为 **0.2.1**）。请搜索新的确切 ID；历史 `org.octosense.samples.*` ID 及本地数据不会迁移。App Hub 已在签名目录第 14 版撤回那批较早的、用密钥签名的条目。

| 应用 | 应用 ID | 源码 |
| --- | --- | --- |
| GitHub Notes | `io.github.ymote.githubnotes` | [ymote/octosense-github-notes](https://github.com/ymote/octosense-github-notes/releases/tag/v0.2.2) |
| Inbox Assistant | `io.github.ymote.inboxassistant` | [ymote/octosense-inbox-assistant](https://github.com/ymote/octosense-inbox-assistant/releases/tag/v0.2.1) |
| Google Calendar | `io.github.ymote.googlecalendar` | [ymote/octosense-google-calendar](https://github.com/ymote/octosense-google-calendar/releases/tag/v0.2.1) |

三者都**只声明 macOS**。签名目录还提供静态 [Camera Card Demo 1.1.1](https://github.com/ymote/camera-card/releases/tag/v1.1.1)，ID 为 `io.github.ymote.cameracard`，同样仅限 macOS，不执行拍照。[连接账户示例](examples/connected-apps/README.zh-CN.md)解释架构；当前的 Release 字节以上方公开仓库为准。

### 下载兼容 Shell

**[桌面版 0.1.0-rc.6 已发布](https://github.com/OctoSense-org/OctoSense/releases/tag/desktop-v0.1.0-rc.6)**（2026-10-11），来自源码 [`f9f6fea9`](https://github.com/OctoSense-org/OctoSense/commit/f9f6fea90b52182790cb2641fd0145c425af4d84)和[正式发布构建](https://github.com/OctoSense-org/OctoSense/actions/runs/38125407028)。

RC6 为 Rust/WASI 组件增加普通 TCP 流与监听器、UDP 数据报和 DNS，通过 `wasm.sockets@1` 提供（[Rust 套接字](docs/RUST.zh-CN.md#tcpudp-和-dns)）。它还增加原生 OctoSense Updates 应用，支持 Stable、Release candidate 和 Preview 通道、验证下载及明确的安装程序交接。RC5 没有更新器：须先手动安装一次 RC6，之后才能用它更新后续版本。更新器验证每份桌面校验和清单上的 GitHub 证明；这不等于 macOS Developer ID 签名或 Windows Authenticode 签名。

| 平台 | RC6 下载 |
| --- | --- |
| macOS Apple 芯片 | [DMG](https://github.com/OctoSense-org/OctoSense/releases/download/desktop-v0.1.0-rc.6/OctoSense_0.1.0-rc.6_aarch64.dmg) 或 [应用 ZIP](https://github.com/OctoSense-org/OctoSense/releases/download/desktop-v0.1.0-rc.6/OctoSense_0.1.0-rc.6_macos_aarch64.app.zip) |
| Windows x64 | [安装程序](https://github.com/OctoSense-org/OctoSense/releases/download/desktop-v0.1.0-rc.6/octosense_0.1.0-rc.6_x64-setup.exe) |
| Linux x86_64 | [Debian 包](https://github.com/OctoSense-org/OctoSense/releases/download/desktop-v0.1.0-rc.6/octosense_0.1.0-rc.6_amd64.deb) 或 [AppImage](https://github.com/OctoSense-org/OctoSense/releases/download/desktop-v0.1.0-rc.6/octosense_0.1.0-rc.6_x86_64.AppImage) |

发行版附带 [SHA256SUMS](https://github.com/OctoSense-org/OctoSense/releases/download/desktop-v0.1.0-rc.6/SHA256SUMS)、它的 [GitHub 证明](https://github.com/OctoSense-org/OctoSense/releases/download/desktop-v0.1.0-rc.6/SHA256SUMS.sigstore.json)，以及 [macOS](https://github.com/OctoSense-org/OctoSense/releases/download/desktop-v0.1.0-rc.6/OctoSense_0.1.0-rc.6_macos-arm64.receipt.json)、[Windows](https://github.com/OctoSense-org/OctoSense/releases/download/desktop-v0.1.0-rc.6/OctoSense_0.1.0-rc.6_windows-x64.receipt.json) 和 [Linux](https://github.com/OctoSense-org/OctoSense/releases/download/desktop-v0.1.0-rc.6/OctoSense_0.1.0-rc.6_linux-x64.receipt.json) 安装包收据。8 个安装包及收据文件均通过校验和验证。RC6 原版更新器验证代码接受 [GitHub 签名](https://github.com/OctoSense-org/OctoSense/actions/runs/38137543497)，并拒绝篡改的校验和与错误发布标签。公开 Mac 下载通过更新器检查（RC/Preview：已是最新；Stable：尚无发行版），以及公开 App Hub 的 Repo Radar 安装、打开与重启保留状态检查。Linux 通过 6 项隔离启动检查；Windows 通过静态安装包检查。未测试 Windows 图形界面、原生安装程序交接或替换，以及完整应用功能。App Hub 的 Install 按钮仍位于权限审核内容下方。Mac 包没有 Developer ID 签名或公证；Windows 安装程序没有 Authenticode 签名。

Android Home 单独发行，此桌面发行版不会升级它。查看或自行构建 RC6 请按[固定源码的环境准备指南](https://github.com/OctoSense-org/OctoSense/blob/f9f6fea90b52182790cb2641fd0145c425af4d84/README.zh-CN.md#环境准备)操作。

宿主继续包含带 GitHub 证明的应用、公开 v2 签名目录、Host API v1 和共享 Wasm 组件。能力名称与 `network.hosts` 描述预计用途；遗漏声明不会拒绝公开 API。所需 ABI/API 版本、应用身份、私有存储、资源上限、账户和设备同意及经审核的工具访问仍受检查（[策略](docs/CAPABILITIES.zh-CN.md#当前源码策略与发布边界)）。RC2 引入的 OS API 保留原有[平台限制](docs/HOST-API-FAMILIES.zh-CN.md)。

**历史证据。** [RC4 发布说明](https://github.com/OctoSense-org/OctoSense/releases/tag/desktop-v0.1.0-rc.4) 记录了九个校验通过的附件，以及在经管理员证明的私有演练目录上通过的 11/11 项 Mac 组件检查。这些结果仅适用于 RC4；上文 RC6 检查另行执行。

这些示例使用 Mac：**App Hub → Search → 确切应用 ID → Get → Install → Open**。Install 前审阅权限；**Library** 提供重新打开和兼容更新。保留签名目录、来源及信任锚的默认设置，不需要开发者密钥或 OctoSense 云端账户。Beta.2 无法使用这些发布者证明或公开 v2 签名目录。

RC **没有公开 GitHub/Google OAuth 注册信息**。本地草稿及未连接账户状态可用；登录需要宿主发行方或运维人员提供注册信息（[配置](https://github.com/OctoSense-org/OctoSense/blob/9266b0083544d86bd7636543b5ff60c61b26460f/crates/oauth-service/README.zh-CN.md)）。普通用户不应需要 Google 开发者账户。安装成功不代表真实登录、Gmail 发送、GitHub commit 或日历写入已验证；这些受保护的写操作在支持的平台上需要亲手确认。Linux/Windows 已实现外部浏览器后端登录和清单声明的后端读取；RC2 补上了登录所需的原生链接打开方式，用其源码构建的 Windows 测试程序对模拟后端完成了登录，Linux 上尚未测试。嵌入式后端登录和受保护的写操作仍不支持，会拒绝执行。Android Google 授权仍不可用。普通嵌入网页与登录是不同的流程；Linux 需要 GTK 3/WebKitGTK 和 X11/XWayland，Windows 需要 WebView2。这些引擎不随包附带（[浏览器要求](https://github.com/OctoSense-org/OctoSense/blob/9266b0083544d86bd7636543b5ff60c61b26460f/docs/desktop-embedded-browser.zh-CN.md)）。`card-host` 没有连接账户服务或原生 Markdown 编辑器。

macOS 上的原生公开签名目录安装及 0.2.0 → 0.2.1 更新保留了本地草稿，之后三者都在 `933abbcf` RC1 发行版中重新打开。这验证本地 UI 和发布流程，不代表提供商效果或其他操作系统通过验证。[签名目录审核](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/3842c5ec503a8e9124cbbe99655556ffe24c41e1/catalog-candidates/ymote-github-samples-updates/independent-review.json)记录 Release 身份及范围；历史证据保持原样。

## Agent 从这里开始

每一步都是一条 shell 命令或一次文件修改，任何编码 Agent 或在终端操作的人都能照做。规则以 `AGENTS.md` 为准；`CLAUDE.md` 和 `GEMINI.md` 只是为按这些文件名查找的 Agent 导入它。

`tools/octo` 与 OctoSense 内部的 Agent 内核 octos 无关，也不需要任何 AI 服务或 API key。

按顺序阅读：

1. [AGENTS.md](AGENTS.md)：规则、完成标准，以及每个必须停下来交给人决定的节点。
2. [flows/README.zh-CN.md](flows/README.zh-CN.md)：按起点选择设计流程，然后逐步执行该流程的 `FLOW.md`。
3. [docs/QUICKSTART.zh-CN.md](docs/QUICKSTART.zh-CN.md) 与 [docs/SCRIPT-API.md](docs/SCRIPT-API.md)：用 `tools/octo` 构建并运行应用；只使用有文档的 API（或能在运行时源码、某个系统应用中找到出处的 API）。
4. [docs/PUBLISHING.zh-CN.md](docs/PUBLISHING.zh-CN.md)：定稿应用包、截图、通过准入检查。之后由人工按 App Hub 的 [SUBMITTING.zh-CN.md](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/SUBMITTING.zh-CN.md) 开提交 issue，并补充已通过验证、带 GitHub 证明的 Release。

需要人来把关的节点（Release 工作流、发布者身份与隐私文本、平台声明、付费图像生成、视觉确认、Release 的 tag、提交）都列在 [AGENTS.md](AGENTS.md#how-to-work) 中；[flows/README.zh-CN.md](flows/README.zh-CN.md#每个流程都遵循同一份约定) 说明所有流程共有的那些节点。Agent 绝不伪造人的确认、评审结果或提交记录。

### 脚本应用验证技能

编写或修改脚本应用（`main.splash`）时，使用 [splash-app-verify](skills/splash-app-verify/SKILL.md)。它把工作前移：先写契约和测试场景再写代码，让应用保持可测试的收窄结构，每次修改后在 `card-host` 中运行全部场景，宿主服务的回复由场景提供。场景失败时，按 [MODEL-VALIDATION](docs/MODEL-VALIDATION.zh-CN.md) 要求的格式写出修复请求。它检查行为和位置，不评判外观，也不替代准入检查和视觉评审。

### AppCard UX 技能

设计或验收速览卡片时，使用 [octoscript-app-card-ux](skills/octoscript-app-card-ux/SKILL.md)。它补充摘要 → 展开卡片 → 完整工作区的任务流程、Chat/编辑/审阅共用状态、键盘和滚动检查，以及保留指定模型创作归属的修复循环。验收矩阵区分本地行为、真实 Agent 执行、外部业务效果和视觉批准，历史分数不能代替新卡片的验收。

任何编程 Agent 都可以配合所选流程直接阅读该技能。需要 Codex 自动发现时，把整个 `skills/octoscript-app-card-ux` 目录复制到自己的 Codex skills 目录，再在加载了该目录的会话中使用：`用 $octoscript-app-card-ux 设计并验收这个应用卡片。` 采用后续修订时同步更新已安装的副本。该技能不会给手机系统/应用 Agent 自动配置指令，也不替代 App Hub 发布检查。它适配所选运行时、作者和设备；DeepSeek、MiniMax 和 OnePlus 6 是历史案例，不是每个应用的固定要求。

## 现状

请使用各仓库的 `main`。

| 部分 | 状态 |
| --- | --- |
| 准入检查（`hub`） | [固定的 App Hub `38635915`](https://github.com/OctoSense-org/OctoSense-App-Hub/tree/386359153ed6377b5f047bd9ed2767a6a2ac2bc7)，应用契约 **1.12.0**，校验以下用途声明：连接账户的 `auth`、`github`、`gmail` 和 `gcalendar` 能力、[Host API v1](docs/HOST-API-V1.zh-CN.md) 的各项声明、`wasm` 能力，以及 RC2 的 `files`、`audio` 和 `device_calendar`。 |
| `card-host` | App Hub `main`。它运行单个应用包，除了用于发现宿主 API 的 `runtime`，不提供任何宿主服务。构建方法见[快速上手](#快速上手)。 |
| Shell | [已发布的桌面 RC6](#下载兼容-shell)；各平台下载与验收见该节。桌面端 Shell 和手机 Home 运行系统应用与商店应用；桌面端还支持已连接账户，并为应用 Agent 提供宿主服务工具。 |
| GitHub 发布 | 应用契约 1.8.0 / `publisher-github-v1`，无需开发者密钥。真实发布及公开目录 macOS 安装/更新检查已通过；见 [RC 下载状态](#下载兼容-shell)。隔离手机测试示例不代表仅声明 macOS 的应用可在手机运行。 |
| 提交途径 | 在 OctoSense-App-Hub 开 issue，见 App Hub 的 [SUBMITTING.zh-CN.md](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/SUBMITTING.zh-CN.md)。 |
| 在手机上安装自己的应用包 | 不支持。见[运行应用](#运行应用)。 |

[QUICKSTART §1](docs/QUICKSTART.zh-CN.md#1-前置条件) 列出了确切版本以及搭建工作区的命令。

## 快速上手

前置条件（[QUICKSTART §1](docs/QUICKSTART.zh-CN.md#1-前置条件)）：

- Rust（stable，通过 rustup 安装），并把 `~/.cargo/bin` 加入 `PATH`。
- Python 3.9 或更新版本（`tools/octo` 不需要第三方包；macOS 自带的 `/usr/bin/python3` 即可）。
- 图形会话：`card-host` 会渲染一个真实的 412x892 点窗口，即使 `--hidden` 让它不显示在屏幕上。
- 一个工作区目录，同时放置本仓库和几个同级仓库，因为 App Hub 的 `Cargo.toml` 把 Makepad 和 OctoScript 指向这些路径：

  ```text
  <workspace>/
    OctoSense-App-Flow/           本仓库
    OctoSense-App-Hub/            hub、card-host、appstore
    makepad/                      OctoSense-org/makepad
    octoscript-makepad/           OctoSense-org/Octoscript-Makepad
    octoscript/                   OctoSense-org/Octoscript
  ```

然后创建工作区，并在本仓库中构建和使用这些工具：

```sh
# 0. 工作区：并排克隆本仓库和 App Hub，
#    再由 setup-native.py 加入 makepad、octoscript 和 octoscript-makepad
mkdir octosense-ws && cd octosense-ws
git clone https://github.com/OctoSense-org/OctoSense-App-Flow.git
git clone https://github.com/OctoSense-org/OctoSense-App-Hub.git
cd OctoSense-App-Flow && python3 tools/setup-native.py

# 1. 构建两个工具（只需一次，在 App Hub 仓库中）
(cd ../OctoSense-App-Hub && cargo build --release -p octosense-card-host -p octosense-app-hub)
tools/octo doctor                                        # 查找 hub 和 card-host；找不到时给出修复方法

# 2. 用模板创建应用
tools/octo new ~/apps/my-app --platform macos --id my-notes --name "My Notes"

# 3. 在真实窗口中运行，并开启远程控制桥
tools/octo run ~/apps/my-app/bundle --port 8141 --detach
#    Agent 和脚本请加 --hidden（无头模式：不占用你的屏幕，
#    可同时运行多个应用，每个用自己的 --port；见 QUICKSTART §4a）
curl -s "127.0.0.1:8141/snap?q=Notes"                    # 屏幕上有什么

# 4. 迭代：修改 bundle/main.splash，然后退出并重新运行
curl -s 127.0.0.1:8141/quit
tools/octo run ~/apps/my-app/bundle --port 8141 --detach

# 5. 截取真实截图，然后运行 App Hub 准入检查
tools/octo shot 8141 ~/apps/my-app/bundle/screenshots/01-main.png
curl -s 127.0.0.1:8141/quit
tools/octo check ~/apps/my-app/bundle                    # hub stamp + hub check

# 6. 发布：输出检查表，然后按 docs/PUBLISHING.md 操作
tools/octo package-help
```

如果构建失败并提示 `no variant … TextInputStateQuery`，请看 QUICKSTART 的排错条目 [构建 `card-host` 时报 `TextInputStateQuery` 错误](docs/QUICKSTART.zh-CN.md#构建-card-host-时报-textinputstatequery-错误)。

在 Windows 上，每条 `tools/octo` 命令都写成 `python tools/octo …`。它在与 macOS 相同的位置查找 `hub.exe` 和 `card-host.exe`（[QUICKSTART §2](docs/QUICKSTART.zh-CN.md#2-构建-hub-和-card-host)）。原生工具构建与 CLI 测试已通过 Windows CI；当前固定版本上的完整创建、运行、截图流程仍未验证。

预期结果：

- `new` 输出 `created …`、`bundle stamped` 和 `target platforms: macos; verify each before publishing`。只列出你会实际测试的平台：商店信息会在商店中声明这些平台。
- `run --detach` 等三件事都完成才返回：`card-host` 输出 `card-host: my-notes 0.1.0 admitted — capabilities {"storage"}, …`；远程控制桥在你的 `--port` 上开始监听；第一帧完整画出（`ready: first frame drawn`）。返回后即可点击或 `shot`。如果端口已有程序占用，它以退出码 1 退出，指出占用端口的应用，并给出停止它的 `curl -s 127.0.0.1:<port>/quit`。脚本错误会出现在 `<app>/.local-state/card-host.log` 中 `[SPLASH] eval:` 之后。
- 对刚复制出来的模板执行 `check`，准入检查会**有意拒绝**它：`[refused] listing: screenshots/01-main.png is named by the listing but is not in the bundle`。有了真实截图后才会通过（`my-notes 0.1.0 — PASSED`，外加未签名警告）。不要放占位图片。`check` 还会提示 `listing.json` 中模板留下的发布者占位文本，需要人工替换。

完整流程及每一步的真实输出见 [docs/QUICKSTART.zh-CN.md](docs/QUICKSTART.zh-CN.md)。

## `tools/octo`

用 `tools/octo <command> -h` 查看参数。

| 命令 | 作用 |
| --- | --- |
| `publish-github <app-directory> [--replace]` | 安装经过评审的 `.github/workflows/publish-app.yml`，不推送、不创建 Release、不提交。`new` 也会复制它。新的匹配版本 tag 触发 GitHub 证明和 Release 产物，无需开发者签名 secret。 |
| `doctor` | 检查 Python，查找 App Hub 仓库和 cargo，查找 `hub` 与 `card-host`（排除 GitHub 那个同名的 `hub` CLI），检查模板，并输出缺失项的修复方法。 |
| `new <dir> --platform PLATFORM [--id ID] [--name NAME] [--system]` | 复制 `templates/script-app`（`bundle/`、`AGENTS.md`、`CLAUDE.md`、`GEMINI.md`、`.gitignore`），设置 id、名称和版本 `0.1.0`，把 `--platform` 的值写入商店信息，并为应用包写入摘要。`--platform` 必填，每个要测试的平台写一次。id 格式为 `[a-z0-9.-]{1,64}`；`os.*` 需要 `--system`。id 本身是保留名，或最后一段是保留名时，它在创建任何文件之前就会拒绝（见[应用是什么](#应用是什么)）。 |
| `run <bundle> [--port N] [--hidden] [--detach] [--system] [--no-stamp] [--app-data DIR] [--static PREFIX=DIR]` | 以 `MAKEPAD_REMOTE=<port>`（默认 8141）运行 `card-host --bundle … --app-data … --allow-unsigned --stamp`。端口已有程序占用时拒绝运行。`--detach` 在应用已准入、远程控制桥开始监听并画出第一帧后返回。应用的 jail（它的私有数据目录）在 `<app>/.local-state/<id>/`。 |
| `shot <port> <out.png> [--settle S]` | 等应用的控件出现、且连续两帧相同（最多 `--settle`，默认 2 秒）后，保存运行中窗口的 PNG（`GET /g?raw=1`）。 |
| `check <bundle> [hub check flags]` | 先 `hub stamp`，再 `hub check --allow-unsigned`；检查不通过时以非零退出码退出。其他参数（如 `--catalog`）原样传给 `hub check`。不会为已封存（带有 `integrity.github` 或旧格式签名）的清单重新写入摘要。写入摘要失败时，立即返回其退出码，不运行准入检查。 |
| `package-help` | 输出发布检查表。 |
| `wasm new <name> [--app DIR] [--sdk auto\|git\|path]`、`wasm build [--app DIR] [--crate DIR]`、`wasm call <function> [JSON] [--app DIR] [--file F] [--storage DIR]`、`wasm doctor [--crate DIR]`、`wasm info <file.wasm> [--json]` | 把应用自己的 Rust 代码做成 WebAssembly 组件（OctoSense ADR 0014）：`new` 根据 `templates/rust-component` 在 `<app>/components/<name>` 写出 crate；`build` 为 `wasm32-wasip2` 构建它，拒绝宿主不提供给组件的导入，记录构建它所用的 crate，把它复制到 `bundle/fns/<name>.wasm`，并补上清单所需的内容；`call` 借助 OctoSense 检出目录中的 `wasm_call` 示例，在命令行运行已构建组件的一个函数；`doctor` 检查 Rust、目标和 crate 的依赖，并指出 OctoSense 已经提供的功能；`info` 输出函数文件的导入、带类型的导出和 crate 清单。源码集成已在 OctoSense #453 合并；兼容发布版本与确切应用仍需分别验收（见 [docs/RUST.zh-CN.md](docs/RUST.zh-CN.md)）。 |

`doctor` 会列出它查找 `hub` 和 `card-host` 的每个位置；查找顺序（包括 Windows 上的 `.exe` 文件名）见 [QUICKSTART §2](docs/QUICKSTART.zh-CN.md#2-构建-hub-和-card-host)。App Hub 的 [`hub` 命令参考](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/SUBMITTING.zh-CN.md#hub-命令)列出了所有 `hub` 命令（包括 `tools/octo` 封装的那些），以及每个命令由谁运行、用在提交的哪一步。

## 设计流程

一个设计流程把一种输入变成 OctoSense 能运行的产物。每个 `FLOW.md` 先给出前置检查，然后是编号步骤，每一步都有命令和通过条件，并标明需要人把关的节点。

| 流程 | 起点 | 产出 | 步骤列表 |
| --- | --- | --- | --- |
| script-app | 一段文字需求：应用做什么、有哪些界面、数据、状态和要访问的主机 | 一个隔离运行的脚本应用包（`manifest.json`、`listing.json`、`main.splash`、`assets/`、真实截图），能通过准入检查 | [flows/script-app/FLOW.md](flows/script-app/FLOW.md) |
| image-to-card | 一张生成的 UX 图：一个服务流程 8–12 个界面的画面图集，或单个界面 | 原生 L0 卡片（`page.card`、`page.data.json`、`kit/`）、拆分出的服务卡片、一个卡片应用包，可选 WASM | [flows/image-to-card/FLOW.md](flows/image-to-card/FLOW.md) |
| kits/sketch | 一套有授权的 Sketch 设计套件 | 一个**主题套件**（原生 L0 组件与主题），不是应用；供其他流程使用 | [flows/kits/sketch/FLOW.md](flows/kits/sketch/FLOW.md) |

文字需求请用 script-app：这是 `tools/octo` 从头到尾自动化的唯一路径。图像和 Sketch 流程需要 macOS、Python 3.12、各自的虚拟环境，原生截图还需要 Makepad Studio；各自的 `FLOW.md` 列出了前置条件。所有应用类流程的交接环节相同（写入摘要、检查、在 `card-host` 中运行、截图、生成 Release、提交），详见 [flows/README.zh-CN.md](flows/README.zh-CN.md#每个流程都遵循同一份约定)。

## 应用是什么

OctoSense 应用是一个隔离运行、不超过 8 MiB 的应用包。提交的只有 `bundle/`；应用仓库里的其他内容都不放进去。

```text
my-app/                     应用自己的 Git 仓库
  AGENTS.md  CLAUDE.md      由 tools/octo new 复制；不提交
  GEMINI.md  .gitignore     由 tools/octo new 复制；不提交
  .gitattributes            由 tools/octo new 复制：bundle/** -text，让 Git 不改动应用包
  BRIEF.md  build/          你的需求、hub scan 的审核包；不提交
  .local-state/             card-host 的 jail 和日志；不提交
  bundle/                   提交的内容
    manifest.json           id、名称、版本、能力、主机、完整性
    listing.json            商店展示的内容
    main.splash             程序（卡片应用则是 page.card + kit/）
    assets/icon.svg         商店信息引用的图标
    screenshots/01-main.png 真实截图，1 到 8 张，由商店信息引用
```

**`manifest.json`**（清单）包含：

| 字段 | 内容 |
| --- | --- |
| `schema`、`id`、`name`、`version` | 身份信息，每次发布都要新的 `version`。id 的最后一段（最后一个 `.` 之后的部分）不能是宿主保留的名字（`notes`、`weather`、`terminal`、`rinx`、`system` 等）：准入检查会拒绝 `com.example.notes`，`my-notes` 则可以通过。`tools/octo new` 在创建任何文件之前就会拒绝这样的 id；之后修改 id 的话，准入检查也会拒绝。 |
| `capabilities` | 向用户和审核人员披露的预计 API 用途，不是执行授权。 |
| `network.hosts` | 以纯主机名披露预计目的地，不是运行时白名单。 |
| `storage`、`compute`、`agent` | 可选的申请项，宿主会把它们限制在上限以内；当前 `hub check` 用 `declarations:` 行显示声明及解析后的上限。`storage.accounts: true` 为每个账户分别提供数据文件夹和 Agent，而不是共用一个 `device` 文件夹；`storage.agent_workspace` 决定 Agent 能读什么：它所属账户的文件夹（默认）或者什么都不读。 |
| `integrity.github` | Release 工作流加入的仓库/所有者/工作流/tag/commit 身份和 GitHub 证明（`publisher-github-v1`，需要 RC1 或更高版本）。 |
| `integrity.bundle_blake3` | 开发时由 `hub stamp` 写入；GitHub 工作流准备最终摘要和证明。 |

全部字段见 App Hub 的 [清单](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/PUBLISHING.zh-CN.md#清单)。

**能力**是 App Hub 定义的封闭列表：[契约 1.11.0 包含 42 个能力族](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/8347a489141c0e24cab564883db7c4592935a8b2/crates/app-contract/src/manifest.rs#L63)，例如 `storage`、`net`、`images`、`web`、`camera`、`location`、`mail`、`glance`、`model`、RC2 的 `files`、`audio` 和 `device_calendar`，以及连接账户用的 `auth`、`github`、`gmail` 和 `gcalendar`；另有 78 个精确的宿主服务名：设备助手的 4 个 `octos.*`、Rinx 的 45 个 `matrix.*`，以及目前没有任何 OctoSense Shell 提供的 29 个 `palpo.*`。安装前商店会为每项能力显示一行通俗的使用说明。在使用契约 1.11 的 RC4 中，遗漏声明不会拒绝公开 API；声明应准确反映用途。实际同意、账户 scope、资源上限和所需 API 版本仍须检查；[旧发行版保留原有行为](docs/CAPABILITIES.zh-CN.md#当前源码策略与发布边界)。[docs/CAPABILITIES.zh-CN.md](docs/CAPABILITIES.zh-CN.md) 说明每项能力对应的 API 用途、哪些目前还没有可用路径（`prompt`、`ledger.read`、`clipboard`）、哪些只有系统应用能用；[docs/AI-SERVICES.zh-CN.md](docs/AI-SERVICES.zh-CN.md) 说明助手相关能力和应用自己的 Agent 在 OctoSense 中能做什么。

**`listing.json`**（商店信息）包含商店展示的内容：副标题、描述、类别、关键词、图标、截图、实际测试过的平台、年龄分级，以及发布者信息（名称、支持方式、HTTPS 隐私政策 URL）。合法取值见 App Hub 的 [商店信息](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/PUBLISHING.zh-CN.md#商店信息)。

**`main.splash`** 是程序本身。Makepad Script 在 Splash 隔离环境中对它求值，无需 Rust 编译；它与 OctoScript L0（`page.card`）是不同的语言。程序在顶层声明 `let` 状态和 `fn`，然后是一个根控件。由于 `ui` 在主体执行后才注入，请用 `start_timeout(0.05, || boot())` 启动逻辑。源码中的 `{{assets}}` 会替换为提供应用包内容的本地回环地址（`http_resource("{{assets}}/thumbs/a.jpg")`）。[docs/SCRIPT-API.md](docs/SCRIPT-API.md) 列出应用可以调用的全部内容，以及最费时间的坑。

## 隔离规则

每个已准入应用运行在自己的隔离环境中，具有私有存储目录和资源上限。使用声明描述预计行为；设备和账户的实际同意、经审核的工具权限仍单独检查。准入检查（`hub check`，与 App Hub 处理提交时运行的是同一份代码）检查包结构与元数据；运行时执行访问和隔离规则。全部检查项见 App Hub 的 [准入检查的规则](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/PUBLISHING.zh-CN.md#准入检查的规则)。

- **应用中不得有密钥或密码。** 不得有密码、PIN 或一次性验证码输入框，不得有登录表单，应用包和应用的存储中都不得有 API key 或令牌。准入检查会拒绝 `is_password: true` 以及密码、验证码类型的输入，运行时也会让这类输入框失效。登录在宿主自有的**面板**上完成：面板是宿主服务覆盖在应用之上的界面，专门用来输入只有用户本人才能填写的内容。
- **披露网络用途。** 在 `network.hosts` 中列出预计的 HTTPS 目的地。配套 SDK 即使没有 `net` 声明也提供网络模块；不会因 HTTPS 主机未列出而拒绝访问。`http://`、`file://` 和 `../` 一律拒绝。
- **只放应用包文件。** 允许的扩展名为 `.card .json .l0 .octoscript .splash .svg .png .jpg .jpeg .webp .ttf .otf .txt .md`；应用还可以带上最多 8 个 WebAssembly 模块，路径为 `fns/<name>.wasm`。其他文件一律拒绝，包括 macOS 的 `.DS_Store`。准入检查还会拒绝其他脚本、压缩包、二进制文件和符号链接。普通 `.txt`、`.md` 文档可以包含署名或许可 URL；Agent 指引与结构化资源仍须通过原有的主机、资源检查。
- **特权操作交给宿主服务。** 应用调用 `host.request("<family>.<method>", args, fn(r){…})`，服务检查已准入的应用身份、可用性、账户 scope 和实际同意；遗漏能力族使用声明不会导致拒绝执行。Mail 是完整示例（`mail.accounts`、`mail.add_account`、`mail.list`、`mail.send` 等）：服务弹出自己的面板收集密码，并把密码存进平台的密钥存储，位于任何应用的 jail 之外。`<family>.sheet.*` 方法只接受来自面板的调用。新增宿主服务要修改 Shell，而不是应用包，详见 [docs/HOST-SERVICES.zh-CN.md](docs/HOST-SERVICES.zh-CN.md)。
- **商店应用与系统应用。** `os.` 开头的 id 保留给系统应用：准入检查会拒绝，任何商店也不会安装。系统应用（[OctoSense `apps/`](https://github.com/OctoSense-org/OctoSense/tree/main/apps) 中的 News、Photos、Maps、Camera、Mail、AI providers）的应用包结构与商店应用相同，但随 Shell 一起发布，上限也更高（例如存储为 64 MiB 而不是 16 MiB）。`tools/octo new --system` 和 `tools/octo run --system` 用于开发系统应用；App Hub 没有接收它们的提交途径。其余都是商店应用，只通过 App Hub 签名目录分发。

## 应用中的 AI

OctoSense 每个 Shell 运行一个 octos Agent 内核，由用户在系统应用 AI providers 中配置；应用永远拿不到密钥。内核运行**系统 Agent**（Shell 的助手）以及每个明确启用 Agent 的应用各自的**应用 Agent**。下表描述[桌面 RC4 源码 `9266b008`](https://github.com/OctoSense-org/OctoSense/blob/9266b0083544d86bd7636543b5ff60c61b26460f/crates/ai-host/src/contained.rs#L132) 中的 API 契约，仍受平台、账户及实际同意限制，不代表真实提供商调用已通过验证；见[发行与验收状态](#下载兼容-shell)。

| 应用可以 | 方式 | 在 `card-host` 中 |
| --- | --- | --- |
| 一次性调用模型，结果按 schema 校验 | 已准入应用调用 `host.request("model.complete", …)`，使用宿主已配置的提供商，受 `model.budget` 报告的应用每日预算限制。`model` 声明只披露用途，不授予执行权限。 | `no service answers "model"` |
| 在自己的界面上与助手对话 | 明确启用 Agent，并取得用户首次使用时的同意。之后可使用全部四个公开 `octos.*` 方法；逐项能力名称不授予这些方法。 | `no service answers "octos"` |
| 拥有自己的 Agent，供用户直接聊天并接收系统 Agent 委派的任务 | 声明 `agent` 块；应用有工具时添加 `tools.json`。已准入的 `AGENT.md` 和 skills 为每轮提供指引。工具访问、共享和账户检查独立于 Agent 同意。 | 只能用 `hub check` 检查 |
| 向 Agent 提供自己的工具 | `implemented_by: "host-service"` 工具选择经审核的精确 `host_method`，仍须满足账户 scope、最低风险级别和人工审阅要求。`implemented_by: "app"` 需要 `script-tools-v1`，派发到已打开应用的 Splash 处理函数；应用关闭时返回 `app_not_running`。见 [HOST-API-V1 §5](docs/HOST-API-V1.zh-CN.md#5-实现声明的应用工具)。 | 只能用 `hub check` 检查 |
| 发布支持应用 Agent 聊天并标注 AI 文本的速览卡片 | `glance.publish` 检查已准入发布者，卡片归该应用所有并受速率限制。Agent 工具可提交已准入的 `template` 与 `initial`，或 L0 `source` 与 `data`；不能发布任意 `script`。聊天仍需用户同意该应用的 Agent。 | `no service answers "glance"` |
| 收到新 Gmail 时运行应用 Agent | 已准入应用须有属于自己的、当前有效且获准 `mail.read` 的 Google 连接、Agent 同意、`agent.background: true` 及 `agent.triggers.events: ["<namespace>.new_message"]`。`<namespace>` 是应用 ID 的最后一段；宿主还须允许运行后台任务。`auth`/`gmail` 声明不是唤醒授权。 | 不支持 |

`agent.tools` 中的精确共享工具请求还须匹配宿主准入时提供的工具列表。默认商店列表不含系统工具箱；写入 `workflow.*` 或 `toolbox.*` 不能将其启用。见[工具箱边界](docs/AI-SERVICES.zh-CN.md#系统工具箱)。上述规则可沿固定版本的[助手代理](https://github.com/OctoSense-org/OctoSense/blob/9266b0083544d86bd7636543b5ff60c61b26460f/crates/ai-host/src/contained.rs#L486)、[模型准入检查](https://github.com/OctoSense-org/OctoSense/blob/9266b0083544d86bd7636543b5ff60c61b26460f/crates/shell/src/apps.rs#L221)、[工具执行器](https://github.com/OctoSense-org/OctoSense/blob/9266b0083544d86bd7636543b5ff60c61b26460f/crates/shell/src/host_tools/script_apps.rs#L403)与 [Gmail 事件发现](https://github.com/OctoSense-org/OctoSense/blob/9266b0083544d86bd7636543b5ff60c61b26460f/crates/shell/src/connected_events.rs#L138)核查。

图片、语音、视频和嵌入向量已在 [OctoSense #368](https://github.com/OctoSense-org/OctoSense/pull/368) 中实现，自 RC1 发行版起包含，[下载状态](#下载兼容-shell)。beta.2 与 `card-host` 不提供这些方法；需要兼容的 Shell，以及宿主中已配置且具有相应权益的提供商。真实付费提供商和设备验证仍为**未验证**。发现方法、应用 Agent 别名及固定源码版本的 API 参考见[媒体与嵌入向量](docs/AI-SERVICES.zh-CN.md#媒体与嵌入向量model)。

运行应用自身代码的 Agent 工具在 RC1 及之后的发行版上可用：清单必须声明 `requires: ["script-tools-v1"]`，而且只有应用打开时工具才会运行。`desktop-v0.1.0-beta.2` 拒绝 `implemented_by: "app"`，在这个版本上，宿主服务工具只能调用已有的宿主服务方法。`llm` 只为系统应用管理 AI 提供商。附带 `tools.json` 的应用包即使没有 `agent` 块也会有应用 Agent，请在商店信息中写明。添加 AI 功能之前，请先读 [docs/AI-SERVICES.zh-CN.md](docs/AI-SERVICES.zh-CN.md)：其中有一个经过验证、能处理“不可用”状态的调用。

## 运行应用

**独立运行：在 `card-host` 中**（开发循环）。`card-host` 是 App Hub 为单个应用包提供的参考隔离宿主。`tools/octo run` 启动它时会在本地端口开启 Makepad 的远程控制桥，人或 Agent 可以通过 HTTP 操作真实窗口（所有路由都是 GET；坐标为窗口点，y 轴向下）：

| 路由 | 作用 |
| --- | --- |
| `/snap`（`?q=` 过滤） | 列出控件及其矩形和文本 |
| `/d` | 以文本形式输出整棵控件树 |
| `/click?x=&y=&wait=1` | 发送一次真实点击 |
| `/t?t=TEXT&wait=1` | 向获得焦点的输入框输入文字 |
| `/k?k=down&c=ReturnKey` | 发送一个按键事件 |
| `/log?n=50` | 返回最近的日志行 |
| `/g?raw=1` | 返回窗口的 PNG（即 `tools/octo shot` 保存的内容） |
| `/quit`（或 `/gq`：截下所有窗口后退出） | 退出；最后一定要调用 |

`on_render` 生成的控件与其他控件一样出现在 `/snap` 和 `/d` 中；应用稍后才添加的内容（来自定时器或响应）在绘制后才出现，请轮询 `/snap?q=` 等待它。`card-host` **不**注册任何宿主服务，所以类似 Mail 的应用在其中会得到 `no service answers "mail" on this device`。`card-host` 还会拒绝已封存的 Release：请在创建 Release 之前测试可编辑源码并截图。

**在 Shell 中。** OctoSense 桌面端 Shell 和手机 Home 通过 App Hub 的 Card runner（App Hub `crates/appstore` 中的 `card` 模块）运行应用，而不是 `card-host`；Card runner 执行同一套清单策略。系统应用从 OctoSense 的 `apps/` 打包进 Shell 构建；商店应用从 App Hub 商店根据签名目录安装。想在 App Hub 发布之前在桌面端 Shell 中试用应用的某个 Release：用一次性信任锚把它的 Release pack 发布到本地签名目录，设置 `OCTOSENSE_HUB_CATALOG=legacy`，再使用新的应用数据目录，把 `OCTOSENSE_HUB` / `OCTOSENSE_HUB_ANCHOR` 指向该镜像；之后 Shell 的商店就能安装并打开该应用（[PUBLISHING §4](docs/PUBLISHING.zh-CN.md#4-在本地演练商店流程)）。**这些旧格式命令尚未验证**带 GitHub 证明的 Release；其既有记录来自一个用密钥签名的测试应用。RC4 使用经管理员证明的签名目录单独演练，见[下载证据](#下载兼容-shell)。

**目前在手机上**（[QUICKSTART §9](docs/QUICKSTART.zh-CN.md#9-在-octosense-手机上运行)）：

- 无法把任意应用包侧载到普通 OctoSense 手机上。手机商店读取 App Hub 内置地址上的签名目录，只信任编译进构建的信任锚；`OCTOSENSE_HUB` / `OCTOSENSE_HUB_ANCHOR` 是环境变量，Android 启动器不会设置。在设备上从本地签名目录安装不受支持，也未验证。
- 最接近的路径是上面的桌面端演练。
- Android 版 `card-host` 不编译远程控制桥，所以手机测试不使用 `tools/octo`。
- Hub 准入后，宿主仍须支持应用所需的 API/ABI 及声明平台。上述连接账户示例只声明 macOS；隔离手机测试示例不代表这些应用兼容 Android。桌面 RC4 不升级 Home。

## 无头测试：同时测多个应用，不占屏幕

Makepad 有隐藏窗口模式，这里称为无头（headless）模式：应用仍然需要[快速上手](#快速上手)中的图形会话，但窗口**从不显示、也不抢焦点**，而远程控制桥（`/snap`、`/click`、`/t`、`/g` 截图）照常工作。凡是由 Agent 或脚本操作应用，都应使用它：不会占用你的屏幕和键盘，还能同时测试多个应用，或同一应用的多个副本，彼此不争抢显示器。

```sh
tools/octo run ~/apps/my-app/bundle     --port 8161 --hidden --detach
tools/octo run ~/apps/second-app/bundle --port 8162 --hidden --detach
curl -s "127.0.0.1:8161/snap?q=Button"        # 每个应用在自己的端口上响应
tools/octo shot 8161 first.png && tools/octo shot 8162 second.png
curl -s 127.0.0.1:8161/quit; curl -s 127.0.0.1:8162/quit
```

- `--hidden` 会设置 `MAKEPAD_HIDE_WINDOWS=1`；所有 Makepad 应用都支持它，包括 OctoSense 的 Shell。
- 每个应用用自己的 `--port`（端口已有程序占用时 `run` 会拒绝运行）；同一个应用包运行两份时，每份用自己的 `--app-data`。
- 截图由应用自身渲染，即使屏幕上什么都没有，截图也是完整的。
- **脚本化 UI 测试：** Makepad 的 [`makepad_test`](https://github.com/OctoSense-org/makepad/tree/main/libs/makepad_test) 测试框架会以隐藏窗口启动应用、通过同一个远程控制桥操作它，并在测试失败时保存截图、控件树和日志；设置 `MAKEPAD_TEST_PARALLEL=1` 可并发运行多个测试（每个测试一个隐藏应用）。配置方法和 `card-host` 示例见 [QUICKSTART §4b](docs/QUICKSTART.zh-CN.md#4b-用-makepad_test-编写脚本化-ui-测试)。

已在 macOS（Apple 芯片）上验证：两个隐藏窗口的应用同时接受点击。`makepad_test` 示例在当前锁定的版本上**未验证**；它在较早的 App Hub 和 Makepad 上通过过。

## 发布

**开提交 issue，请 App Hub 发布你的应用。** 提供仓库、版本/commit、截图和请求的权限。可以先开 issue，再准备 Release。审核人员对确切的 Release 运行准入检查，并在 issue 中反馈缺项或拒绝原因；随后由 App Hub 管理员批准确切的候选版本，再由 Hub 发布它的签名目录条目。

[docs/PUBLISHING.zh-CN.md](docs/PUBLISHING.zh-CN.md) 讲解本地准入检查、截图和审核答案。`tools/octo publish-github <app-directory>` 安装 Release 工作流（`new` 也会复制它）。评审后 commit 已测试源码，再推送新的 `v<manifest.version>` tag。GitHub Actions 使用原生身份依次准备、证明、验证和打包。App Hub 只接受带 GitHub 证明的 Release（[ADR 0002](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/adr/0002-github-attested-publisher-identity.zh-CN.md)），所以你无需创建 `publisher.key`，也无需保管签名 secret。

把成功的工作流和确切的 Release pack 附到同一个提交 issue。GitHub Release 提供可验证的字节，不是新的 App Hub 提交渠道，也不会自动获批。见 App Hub 的 [SUBMITTING.zh-CN.md](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/SUBMITTING.zh-CN.md)。在 App Hub 首次发布应用之前，每个新 Release 都以评论的形式发在同一个 issue 中，写明它的 tag、完整的 commit SHA 和工作流运行链接，并更新 issue 标题和 Version 字段；发布之后，每个新版本都开新 issue。日常更新使用同一仓库、所有者和工作流下的新版本/新 tag。不要移动已用于 Release 的 tag，也不要手改 Hub 已准入的签名目录和产物。

此路径需要契约 1.8.0 / `publisher-github-v1`。真实的 GitHub Release 及原生 Store 的安装、更新检查已在隔离的测试签名目录中通过（[历史证据](docs/PUBLISHING.zh-CN.md#36-github-发布者身份human)）。当前公开签名目录中的示例已在 macOS 完成安装与更新；RC 状态及限制见[兼容 Shell 指南](#下载兼容-shell)。

## 仓库结构

| 路径 | 内容 |
| --- | --- |
| [AGENTS.md](AGENTS.md) | 给编码 Agent 的规则、完成标准和汇报方式 |
| [flows/](flows/README.zh-CN.md) | 设计流程：[script-app](flows/script-app/FLOW.md)、[image-to-card](flows/image-to-card/FLOW.md)、[kits/sketch](flows/kits/sketch/FLOW.md)；共享代码在 [core/](flows/core/README.md)（策略、评审、修复、检查；[NATIVE-INSTRUMENT.md](flows/core/NATIVE-INSTRUMENT.md) 是原生测试手册）和 [image-lib/](flows/image-lib/README.md) |
| [docs/QUICKSTART.zh-CN.md](docs/QUICKSTART.zh-CN.md)（[English](docs/QUICKSTART.md)） | 唯一路径：构建工具、创建、运行、修改、检查、手机、发布 |
| [docs/SCRIPT-API.md](docs/SCRIPT-API.md) | Splash 语言及隔离应用可调用的全部 API |
| [docs/CAPABILITIES.zh-CN.md](docs/CAPABILITIES.zh-CN.md)（[English](docs/CAPABILITIES.md)） | 每项能力：解锁什么、用户看到什么、规则 |
| [docs/HOST-SERVICES.zh-CN.md](docs/HOST-SERVICES.zh-CN.md)（[English](docs/HOST-SERVICES.md)） | `host.request`、面板、“密钥归宿主所有”、新增宿主服务 |
| [docs/RUST.zh-CN.md](docs/RUST.zh-CN.md)（[English](docs/RUST.md)） | 应用自己的 Rust 代码：组件（普通的 Rust，`tools/octo wasm`）和核心模块，以及设备 API、网络、文件和原生代码各走哪条路 |
| [docs/AI-SERVICES.zh-CN.md](docs/AI-SERVICES.zh-CN.md)（[English](docs/AI-SERVICES.md)） | OctoSense 的助手（octos）：应用目前能用什么、应用 Agent 及其工具、速览卡片和卡片内对话（`sys.chat`） |
| [docs/MODEL-VALIDATION.zh-CN.md](docs/MODEL-VALIDATION.zh-CN.md)（[English](docs/MODEL-VALIDATION.md)） | 检查编码 Agent 做出的应用：原生输入与截图、评审循环、修复 |
| [docs/PUBLISHING.zh-CN.md](docs/PUBLISHING.zh-CN.md)（[English](docs/PUBLISHING.md)） | 从能运行的应用到提交 issue 和带 GitHub 证明的 Release：定稿商店信息、截图、准入/审核、工作流与 Hub 批准 |
| [docs/CODE-WALKTHROUGH.md](docs/CODE-WALKTHROUGH.md) | `tools/octo`、App Hub 与 OctoSense Shell 如何衔接，沿一个请求逐层追踪 |
| [docs/HOST-API-FAMILIES.zh-CN.md](docs/HOST-API-FAMILIES.zh-CN.md)（[English](docs/HOST-API-FAMILIES.md)） | 每个 `host.request` 能力族：Shell 响应哪些应用、支持哪些平台、从哪个版本开始；自动生成 |
| [docs/RUNTIME-TYPES.zh-CN.md](docs/RUNTIME-TYPES.zh-CN.md)（[English](docs/RUNTIME-TYPES.md)） | 锁定的运行时可以解析的全部类型名，按命名空间列出；自动生成 |
| [docs/GLOSSARY.md](docs/GLOSSARY.md) | 每个术语只有一个含义 |
| [docs/NATIVE-WORKSPACE.md](docs/NATIVE-WORKSPACE.md)、[docs/l0/](docs/l0/) | 原生运行时所需同级仓库的配置；L0 卡片示例 |
| [templates/script-app/](templates/script-app/README.zh-CN.md) | `tools/octo new` 复制的可运行模板（“My Notes”） |
| [templates/card-app/](templates/card-app/README.zh-CN.md) | 指向卡片应用路径的说明 |
| [examples/](examples/README.zh-CN.md) | image-to-card 完整示例项目，以及 [examples/connected-apps](examples/connected-apps/README.zh-CN.md) 中三个连接账户的参考应用 |
| [tools/octo](tools/octo) | 上文介绍的命令行工具 |
| `tools/setup-native.py` | 在本仓库旁准备锁定版本的 OctoScript-Makepad 运行时（[native-runtime.lock.json](native-runtime.lock.json)） |
| `tools/image-to-appcard-flow.sh`、`tools/beauty-pipeline.sh`、`tools/beauty-studio.sh` | image-to-card 与套件流水线的入口 |
| `tools/check-links.py` | 检查 Markdown 相对链接能否解析（CI 中运行） |

## 示例

这些示例包括用 image-to-card 流程构建的参考用户旅程、用 script-app 流程构建的受控应用，以及 Android 模型编写的原型档案。各示例的源码、验证证据和当前限制都与示例放在一起。

| 示例 | 形态 | 内容 |
| --- | --- | --- |
| [黑客松 Agent 应用](examples/agentic-hackathon/README.zh-CN.md) | 原生 Splash / 应用 Agent | 使用虚构数据的 Email Action 与 Meeting Planner，含本地操作确认及原生测试 |
| [Aircon](examples/aircon/README.zh-CN.md) | 原生卡片 / WASM | 从购买到安装的完整旅程：12 个界面状态，14 个服务卡片变体 |
| [School](examples/school/README.zh-CN.md) | 原生卡片 / WASM | 学校通知、日历与缴费 |
| [Health](examples/health/README.zh-CN.md) | 原生卡片 / WASM | 虚构的体检预约 |
| [Reunion](examples/reunion/README.zh-CN.md) | 原生卡片 / WASM | 聚会筹划、出席回复与付款 |
| [Calendar](examples/calendar/README.zh-CN.md) | 原生卡片 / 浏览器预览 + 同步服务器 | 两台设备共用一份日历，附基于 SQLite 的同步服务器 |
| [Android 模型编写的卡片原型](examples/android-a2app-card-templates/README.zh-CN.md) | Android 上的 AppStudio；概览/展开/完整应用 | 两份模型编写的六类集合：各自离线原型整体 4.5/5、视觉 4.4/5；源码精确重放及原生证据。 |

脚本应用的完整示例是[连接账户的应用](#连接账户的应用githubgmail-和-google-calendar)、[OctoSense `apps/`](https://github.com/OctoSense-org/OctoSense/tree/main/apps) 中的第一方应用包（`apps/<name>/bundle/`），以及 [templates/script-app](templates/script-app/README.zh-CN.md)。

## 参与贡献

- 从 `main` 建分支并提 pull request；CI 必须通过。
- CI 运行 `python tools/check-links.py`（受版本管理的 Markdown 中的相对链接必须能解析），并在 Windows、Linux 和 macOS 上运行 `tools/test_*.py` 中的测试（`tools/octo` 的起步模板、二进制查找和示例约定）。在 macOS 上，CI 还会用 `tools/setup-native.py` 准备原生运行时，运行 flow、core、Sketch 和维护相关的单元测试（见 [.github/workflows/ci.yml](.github/workflows/ci.yml)）。
- 保持文档真实：文档中的每条命令都实际运行过，没运行过的标注**未验证**。运行时或 `hub` 与文档不一致时，修正文档，或附上复现步骤报告问题。
- 对运行时、准入检查、Shell 或系统应用的修改属于各自的仓库（见下），不在这里。
- 不要把购买的设计素材、密钥、`.local-state/` 或本地日志纳入版本库。

## 相关仓库

| 仓库 | 作用 |
| --- | --- |
| [OctoSense-App-Hub](https://github.com/OctoSense-org/OctoSense-App-Hub) | 签名目录、准入检查、`hub`、`card-host`、商店、Card runner 与提交途径 |
| [OctoSense](https://github.com/OctoSense-org/OctoSense) | Shell 及其内置的一切：桌面端 Shell（`desktop/`）、手机 Shell，即 Home（`phone/`，可作为 Home 应用安装，也可放进由 `rom/` 构建的 ROM 镜像），以及第一方应用和它们的宿主服务（`apps/`）。原为 OctoSense-Desktop、OctoSense-ROM 和 OctoSense-System-Apps 三个仓库。 |
| [OctoSense `apps/`](https://github.com/OctoSense-org/OctoSense/tree/main/apps) | 第一方应用（News、Photos、Maps、Camera、Mail、AI providers）及其宿主服务（`mail`、`llm`） |
| [OctoSense `apps/appcard`](https://github.com/OctoSense-org/OctoSense/tree/main/apps/appcard) | AppCard 助手（`octos-app`，在 Shell 中需 `--features app-appcard` 才启用） |
| [OctoSense-org/makepad](https://github.com/OctoSense-org/makepad)、[OctoScript](https://github.com/OctoSense-org/Octoscript)、[OctoScript-Makepad](https://github.com/OctoSense-org/Octoscript-Makepad) | Makepad：Splash 隔离环境和控件。OctoScript：L0 解析器和检查器。OctoScript-Makepad：L0 渲染层。 |

## 许可证

Apache-2.0；见 [LICENSE](LICENSE) 和 [NOTICE](NOTICE)。
