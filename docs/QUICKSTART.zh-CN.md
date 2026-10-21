# 快速入门：构建、运行并发布 OctoSense 脚本应用

[English](QUICKSTART.md) | 简体中文

未注明中文版的链接指向英文文档。

从一个空目录出发，沿一条路径走到一个能通过 App Hub 准入检查的应用包。每条命令都在 macOS（Apple 芯片）上运行过，标注为**未验证**的除外。引用的输出均为真实输出，其中的本地路径和进程号省略为 `…`。

```text
1 前置条件 → 2 构建 hub + card-host → 3 octo new → 4 octo run → 5 迭代修改
→ 6 能力 → 7 常见的坑 → 8 octo check → 9 在手机上运行 → 10 发布
```

## 当前源码策略与发布边界

能力名称与 `network.hosts` 是使用披露，不是权限开关。已发布的
[桌面 RC4](../README.zh-CN.md#下载兼容-shell) 使用 App Hub 契约 1.11.0，
让应用即使遗漏对应声明，也能使用已实现
的公开 API、网络模块和带配额的独立存储。仍应向用户与审核人员准确披露用途。
修改文档不会改变 RC2 或更早工具的行为；请使用相互匹配的宿主、Hub 和运行时。

实际授权继续生效：逐应用设备同意与系统权限、连接账户归属和提供商 scope、
外部写入的原生审阅、Agent 启用和跨应用共享。所需 API 版本、组件 ABI 与导入
检查、发布证明、确切摘要、平台可用性及配额也继续生效。用 `runtime.list` 和
`runtime.describe` 查询实现；修正后的宿主不要求先声明 `runtime`。
宿主私有用户资料与不带调用方身份的 `agent.notify` 不是公开应用 API。
普通 `card-host` 没有设备同意代理，不开放私有设备读取；请在兼容 Shell 中以
`host-api-v1` 验证这些功能。


## 1. 前置条件

| 平台 | 状态 |
| --- | --- |
| Apple 芯片上的 macOS | 已验证：本页所有命令都在这个平台上运行过。 |
| Windows | App Hub CI 已通过原生 `hub`、`card-host` 构建及 contract、policy、CLI、模态输入测试。App Flow 的 `tools/test_*.py` 也在该平台运行。当前固定版本上的完整创建、运行、截图流程仍未验证。通过 Python 运行 `tools/octo`（§2），并保留应用包的原始换行符（§3）。 |
| Linux | 同一套 App Hub 构建与测试已在 Ubuntu 24.04 通过；App Flow 的 `tools/test_*.py` 也在该平台运行。这里尚未验证原生应用交互与截帧。有报告称，在软件渲染（llvmpipe、WSL）下截帧（`/g`、`tools/octo shot`）会超时。 |

Windows、Linux 构建与测试结果来自 [App Hub CI 37724164489](https://github.com/OctoSense-org/OctoSense-App-Hub/actions/runs/37724164489)，对应 `582a6ed`，由 [App Hub #146](https://github.com/OctoSense-org/OctoSense-App-Hub/pull/146) 合并为 `8885c375`，使用固定版本的普通 Makepad。该次 CI 的 macOS 任务仍在排队；本地 macOS release 构建与原生打包字体截图已通过。这些结果不能证明提供商登录、应用 UX，或本页每条命令都已在 Windows、Linux 上运行。

你需要：

- **Rust**（stable，通过 rustup 安装）。`cargo` 位于 `~/.cargo/bin`，请把这个目录加入 `PATH`（`export PATH=$HOME/.cargo/bin:$PATH`）。
- **Python 3.9+**，供 `tools/octo` 和 `setup-native.py` 使用，不需要任何第三方包。macOS 自带的 `/usr/bin/python3` 即可。
- **Git。**
- **约 3 GB 磁盘空间：** 克隆占 2 GB（其中 1.5 GB 是本仓库，大部分是设计证据；只构建应用的话，`git clone --depth 1` 就够了），构建占 1 GB。试用桌面端 Shell（[PUBLISHING §4](PUBLISHING.zh-CN.md#4-在本地演练商店流程)）还要再多约 1 GB，另加它自身构建所占的空间。
- **图形会话**，供 `card-host` 使用。即使 `--hidden` 让窗口不出现在屏幕上，`card-host` 也会渲染一个真实的 412x892 点窗口（§4a）。
- **App Hub 及其同级源码**，放在同一个工作区目录中：

  ```text
  <workspace>/
    OctoSense-App-Flow/           本仓库
    OctoSense-App-Hub/            hub、card-host、appstore
    makepad/                      OctoSense-org/makepad
    octoscript-makepad/           OctoSense-org/Octoscript-Makepad
    octoscript/                   OctoSense-org/Octoscript
  ```

  App Hub 的 `Cargo.toml` 把它的 Makepad 和 OctoScript 依赖固定指向这几个同级路径（`../makepad`、`../octoscript-makepad`、`../octoscript`）。`setup-native.py` 按 [native-runtime.lock.json](../native-runtime.lock.json) 选定的版本，克隆这三个运行时同级仓库（目录名为小写，如上所示）。它的选项见 [NATIVE-WORKSPACE](NATIVE-WORKSPACE.md)。

创建工作区：

```sh
mkdir octosense-ws && cd octosense-ws
git clone https://github.com/OctoSense-org/OctoSense-App-Flow.git
git clone https://github.com/OctoSense-org/OctoSense-App-Hub.git
cd OctoSense-App-Flow
python3 tools/setup-native.py           # 在本仓库旁克隆 makepad、octoscript 和 octoscript-makepad
python3 tools/setup-native.py --check   # 通过时以退出码 0 退出，并输出锁定的版本
```

`setup-native.py` 需要运行 20 到 30 秒。如果之后 `--check` 失败，运行 `python3 tools/setup-native.py --update`，把没有本地改动的同级仓库切换到锁定的版本。

App Hub 和本仓库都请使用 `main`。运行时为 OctoScript-Makepad `6cf2d90a`，它锁定了 Makepad `d653bc44` 和 OctoScript `2e37d9e6`。它包含 makepad #110–#116，没有按应用设置的 URL、媒体、套接字或累计指令数限制（[makepad#117](https://github.com/OctoSense-org/makepad/pull/117)），在 `host.request` 之前也不检查能力（[makepad#118](https://github.com/OctoSense-org/makepad/pull/118)、[OctoSense#450](https://github.com/OctoSense-org/OctoSense/issues/450)）。

## 2. 构建 `hub` 和 `card-host`

```sh
cd <workspace>/OctoSense-App-Hub
cargo build --release -p octosense-card-host -p octosense-app-hub
```

构建成功时，输出以 `Finished release profile …` 结尾。生成的程序位于 `target/release/`（或 `$CARGO_TARGET_DIR/release/`）：`hub`（准入检查）和 `card-host`（运行单个应用包的宿主）。在 Windows 上，文件名是 `hub.exe` 和 `card-host.exe`。

更新已有工作区时，请在 App Hub 的干净 `main` 分支上运行 `git pull --ff-only`，再用上面的命令重建两个程序。只更新 App Flow 或运行 `setup-native.py` 不会更新旧的 `hub` / `card-host` 可执行文件。例如，App Hub #199 修复了原生宿主服务调用所使用的已准入应用身份。`doctor` 只检查能否找到程序，不检查版本；请查看它选择的路径，同时更新 `OCTO_HUB` / `OCTO_CARD_HOST` 指向的程序。这个预览构建与复制到应用[发布工作流](PUBLISHING.zh-CN.md#36-github-发布者身份human)中的固定工具版本相互独立。

如果构建失败并提示 `no variant … TextInputStateQuery`，请看[构建 `card-host` 时报 `TextInputStateQuery` 错误](#构建-card-host-时报-textinputstatequery-错误)。

然后在本仓库中运行：

```sh
export OCTOSENSE_APP_HUB=<workspace>/OctoSense-App-Hub   # App Hub 位于同级目录时可省略
tools/octo doctor
```

`doctor` 依次在以下位置查找 `hub` 和 `card-host`：`$OCTO_HUB` 和 `$OCTO_CARD_HOST`；然后是 `$OCTOSENSE_APP_HUB/target/release`、`$CARGO_TARGET_DIR/release`、`$OCTOSENSE_APP_HUB/../target/release`、同级的 `../OctoSense-App-Hub/target/release`、`../target/release`；最后是 `PATH`。它会排除 GitHub 那个同名但无关的 `hub` CLI。两个程序都找到时，最后输出：

```text
ready: tools/octo new <dir> --platform <target> && tools/octo run <dir>/bundle
```

有缺失项时，它输出一行 `[fail]`、查找过的每个位置，以及修复用的命令。

**Windows。** Windows 不会按 shebang 运行这个脚本，所以每条 `tools/octo` 命令都要通过 Python 运行。在上面列出的每个目录中，`tools/octo` 都先查找 `hub.exe` 和 `card-host.exe`，再查找不带 `.exe` 的文件名：

```powershell
python tools/octo doctor
```

如果程序在别的位置，把 `$env:OCTO_HUB` 和 `$env:OCTO_CARD_HOST` 设为它们的完整路径。CI 会在 Windows 上测试这套查找逻辑；完整指南在该平台仍未验证。社区用户在 [App Hub#41](https://github.com/OctoSense-org/OctoSense-App-Hub/issues/41) 中报告，曾在较早的版本上验证过 Windows 11 原生构建（Rust 和 MSVC，不用 WSL）：`hub` 和 `card-host` 能构建，`hub stamp` 和 `hub check` 能运行，`card-host --remote` 能响应 `/g` 截帧。当前 CI 已验证原生工具构建及其测试（§1），但没有重跑该图形截帧。

## 3. 创建应用

```sh
tools/octo new ~/apps/my-app --platform macos --id my-notes --name "My Notes"
```

`new` 复制 [templates/script-app](../templates/script-app/README.zh-CN.md)（`bundle/`、`AGENTS.md` 及导入它的 `CLAUDE.md` 和 `GEMINI.md`、`.gitignore` 和 `.gitattributes`），设置清单中的 `id` 和 `name` 以及 `main.splash` 中的标题标签，把 `--platform` 的值写入商店信息，并为应用包写入摘要：

```text
created …/my-app
  id my-notes, name 'My Notes', version 0.1.0, bundle stamped
  target platforms: macos; verify each before publishing
```

`--platform` 是必填项，你要在哪些平台上运行应用，就为每个平台写一次：`macos`、`windows`、`linux`、`android`、`ios`、`openharmony` 或 `web`。在 Mac 上用 `card-host` 运行，测试的是 `macos`。商店信息会在商店中声明这些平台，所以发布之前，只保留你实际测试过的平台，并由人确认这一声明。不加这个选项时，`new` 会停止，并输出 `tools/octo new: error: the following arguments are required: --platform`。

复制的图标只演示格式，不是应用最终身份。按照 App Hub 的 [OctoSense 家族格式](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/ICONS.zh-CN.md#设计与导出建议)替换为独立图标：64 点正方形原稿、中央 66% 前景、克制的插画物件，不预置平台圆角或外部阴影。提交前检查 64/40/24 像素及平台外框；准入检查不评判设计。

请慎重选择 id：

- 长度为 1 到 64 个字符，只能用 `[a-z0-9.-]`，不能以 `.` 开头，也不能包含 `..`。`new` 会检查这一点。
- 不能以 `os.` 开头，这个前缀保留给系统应用。除非传入 `--system`，否则 `new` 会拒绝这样的 id。
- id 本身及其最后一段都不能是宿主保留的名字，例如 `notes`、`weather`、`calculator`、`browser`、`terminal` 或 `system`。`new` 在创建任何文件之前就会拒绝这样的 id：`octo: id 'com.example.notes' uses reserved native/host namespace 'notes'; choose an app-specific name`。如果之后把 id 改成这样的名字，准入检查会拒绝它（§8）。全部保留名见 App Hub 的 [准入检查的规则](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/PUBLISHING.zh-CN.md#准入检查的规则)。

把 `~/apps/my-app` 建成独立的 Git 仓库。应用包的摘要覆盖每一个字节，如果检出时转换了换行符（Windows 上设置了 `core.autocrlf=true` 的 Git 就会这样），摘要就会失效。`new` 写入的 `.gitattributes` 含有 `bundle/** -text`，可以禁止 Git 改写应用包。检查这条规则是否生效：

```sh
cd ~/apps/my-app
git init
git check-attr text -- bundle/manifest.json
```

成功时输出 `bundle/manifest.json: text: unset`。如果输出的是 `text: unspecified`，说明缺少这条规则，不是由 `new` 创建的仓库就会这样。请用 `printf 'bundle/** -text\n' >> .gitattributes` 加上它；`>>` 是追加写入，已有的 `.gitattributes` 会保留原来的规则。

如果把应用移到一个更大的仓库里，根目录 `.gitattributes` 中的 `bundle/**` 覆盖不到它的应用包。请把应用自己的 `.gitattributes` 留在它的 `bundle/` 旁边：其中的模式从它所在的目录算起。也可以在根目录的文件中写出应用包的路径，例如 `apps/my-app/bundle/** -text`，或者写 `**/bundle/** -text`，匹配任意层级的 `bundle/` 文件夹。然后在根目录下，用清单的真实路径检查：`git check-attr text -- apps/my-app/bundle/manifest.json`。在那里检查 `bundle/manifest.json` 说明不了任何问题：只要路径与模式匹配，`git check-attr` 就输出 `unset`，即使这个文件并不存在。

## 4. 在桌面上运行

```sh
tools/octo run ~/apps/my-app/bundle --port 8141            # 前台运行；按 Ctrl-C 退出
tools/octo run ~/apps/my-app/bundle --port 8141 --detach   # 后台运行；应用已准入并完成绘制后返回
```

`run` 在 App Hub 目录中启动 `card-host --bundle <bundle> --app-data <app>/.local-state --allow-unsigned --stamp`，并设置 `MAKEPAD_REMOTE=8141`。`--detach` 会输出：

```text
[makepad-remote] listening on 127.0.0.1:8141 pid=… app=card-host …
… card-host: my-notes 0.1.0 admitted — capabilities {"storage"}, hosts {}, storage 16777216 bytes, agent none
ready: first frame drawn
pid …  log …/my-app/.local-state/card-host.log
drive it:  curl -s 127.0.0.1:8141/snap   |   tools/octo shot 8141 <out.png>   |   curl -s 127.0.0.1:8141/quit
```

- `run` 先检查端口是否空闲。如果该端口上已有程序在响应，它以退出码 1 退出，输出 `port 8141 is already taken by card-host pid …`，并给出退出那个实例的命令（`curl -s 127.0.0.1:8141/quit`）。
- `--detach` 在两件事都完成后才返回：应用的控件已完成布局（`/snap` 能列出它们及其文本），并且此后已完整画出一帧。紧接着发送的 `shot`、点击或 `/t` 都会作用在已完成的界面上。
- `run` 会传入 `--stamp`，所以 `card-host` 每次启动都会重写清单中的摘要，改动不用另外执行 `hub stamp` 就能运行。`tools/octo run --no-stamp` 不传这个参数，此时 `card-host` 会拒绝字节有变化的应用包。`--no-stamp` 是 `tools/octo` 的参数，不是 `card-host` 的参数（`card-host --help` 会列出它自己的参数）。
- `--system` 按系统应用的上限准入 `os.*` 系统应用。
- 应用的文件存放在它的 jail 中，即私有数据目录 `<app>/.local-state/<id>/`。
- 在日志中查找 `admitted`，以及 `[SPLASH] eval:` 之后的错误（脚本错误会输出在这里；见 [SCRIPT-API](SCRIPT-API.md#errors-and-the-log)）。按下面这些错误格式搜索，不要搜索“error”这个词：即使运行正常，Makepad 的 `[ui-hang]` 诊断信息也会提到 Metal 的 `MTLCompilerError`。

  ```sh
  grep -nE '\[E\]|splash:[0-9]+:|refused|on_render closure failed|callback error' <app>/.local-state/card-host.log
  ```

通过 HTTP 操作应用。所有路由都是 GET；坐标为窗口点，y 轴向下：

| 命令 | 作用 |
| --- | --- |
| `curl -s 127.0.0.1:8141/snap` | 列出控件及其矩形和文本：`{"s":[{"i":id,"ty":type,"r":[x,y,w,h],"t":text}]}`；用 `?q=` 过滤 |
| `curl -s 127.0.0.1:8141/d` | 以文本形式输出整棵控件树 |
| `curl -s "127.0.0.1:8141/click?x=150&y=140&wait=1"` | 发送一次真实点击（`wait=1`：画完下一帧后再响应） |
| `curl -s "127.0.0.1:8141/t?t=Buy%20milk&wait=1"` | 向获得焦点的输入框输入文字 |
| `curl -s "127.0.0.1:8141/k?k=down&c=ReturnKey"` | 发送一个按键事件 |
| `curl -s "127.0.0.1:8141/log?n=50"` | 返回最近的日志行 |
| `curl -s 127.0.0.1:8141/s` | 返回远程控制桥的状态，包括应用名称和进程号 |
| `tools/octo shot 8141 out.png` | 把窗口保存为 PNG（`/g?raw=1`） |
| `curl -s 127.0.0.1:8141/quit` | 退出；最后一定要调用它（或调用 `/gq`：截下所有窗口后退出） |

操作技巧：

- `/t` 向当前获得焦点的控件输入文字。点击按钮会让 `TextInput` 失去焦点，所以发送下一个 `/t` 之前，要再点一下输入框。要清空输入框，每个字符发送一次 `/k?k=down&c=Backspace`。
- `?q=` 也会匹配 `Splash` 控件本身，它的文本就是你的整个 `main.splash`；请按类型过滤结果（`"ty":"Label"`），或根据矩形判断。
- `tools/octo shot` 先等应用的控件出现，再反复截帧，直到相邻两帧完全相同（最多等待 `--settle` 指定的时长，默认 2 秒），所以不会保存画了一半的首帧。即便如此，仍要逐张查看 PNG。
- 窗口大小为 412x892 点；在 Retina 屏幕的 Mac 上，`/g?raw=1` 按 2 倍分辨率截图：把截图的像素坐标除以 2，就得到点击坐标。截图顶部包含 `card-host` 的标题栏（macOS 上为 32 点）。标题栏是同一窗口中的控件，所以点击坐标也从同一个顶边算起：不要减去标题栏的高度。

在模板应用中，`/snap` 会显示标题标签 `"t":"My Notes"`。按下面的步骤完整操作一遍：

1. 点击输入框，然后发送 `/t?t=Buy%20milk`。
2. 点击 **Add**。应用把 `["Buy milk"]` 写入 `.local-state/my-notes/notes.json`，并画出这一行。
3. 点击这一行。应用会删除它。
4. 重启应用。已保存的笔记会重新加载。

`on_render` 生成的控件与其他控件一样出现在 `/snap` 和 `/d` 中，所以按 `/snap` 给出的矩形点击即可。应用稍后才生成的内容（来自 `start_timeout` 或网络响应）要等绘制之后才会出现：请轮询 `/snap?q=` 等待它，不要只读一次 `/snap`。

### 4a. 无头模式：不占屏幕，同时测试多个应用

Makepad 有隐藏窗口模式，这里称为无头（headless）模式。应用仍然需要 §1 中的图形会话，但窗口**从不显示、也不抢焦点**，上面介绍的远程控制桥（`/snap`、`/click`、`/t`、`/g` 截图）也完全照常工作。所有自动化检查都应使用这种模式：编码 Agent 不会占用你的屏幕或键盘焦点，你还可以同时测试多个应用，或同一应用的多个副本。

```sh
tools/octo run ~/apps/my-app/bundle     --port 8161 --hidden --detach
tools/octo run ~/apps/second-app/bundle --port 8162 --hidden --detach
curl -s "127.0.0.1:8161/snap?q=Button"             # 每个应用在自己的端口上响应
curl -s "127.0.0.1:8162/click?x=X&y=Y&wait=1"      # X、Y：/snap 给出的某个矩形的中心点
tools/octo shot 8161 first.png && tools/octo shot 8162 second.png
curl -s 127.0.0.1:8161/quit; curl -s 127.0.0.1:8162/quit
```

`--hidden` 会为 `card-host` 设置 `MAKEPAD_HIDE_WINDOWS=1`；所有 Makepad 应用都支持这个变量，包括 OctoSense 的 Shell。同时运行多个应用时，遵守以下规则：

- **每个应用一个端口。** 为每个实例指定自己的 `--port`；端口已有程序占用时，`run` 会拒绝运行，并指出占用端口的应用。
- **每个副本一个 `--app-data`。** 两个不同的应用包本来就有各自的 jail（`<app>/.local-state`）。同一个应用包运行两份时，需要用 `--app-data` 把它们的存储和日志分开。
- **隐藏时也能截图。** 截图由应用自己渲染，即使屏幕上什么都没有，截图也是完整的。每张都要查看。

已在 macOS 上验证：两个隐藏窗口的应用同时接受点击，各自保持了自己的状态，两张截图也都正确。

### 4b. 用 `makepad_test` 编写脚本化 UI 测试

要做可重复的回归测试，锁定版本的 Makepad 自带一个 Rust 测试框架：`libs/makepad_test`（[README](https://github.com/OctoSense-org/makepad/blob/main/libs/makepad_test/README.md)、[GUIDE](https://github.com/OctoSense-org/makepad/blob/main/libs/makepad_test/GUIDE.md)）。它会自己构建并启动应用（默认隐藏窗口），通过同一个远程控制桥操作应用，并在测试失败时保存截图、控件树和日志。要测试应用包，让它指向 App Hub 的 `card-host`，并把应用包作为应用参数传入：

```rust
// tests/ui.rs，所在的小 crate 声明了
// [dev-dependencies] makepad-test = { path = "../makepad/libs/makepad_test" }
use makepad_test::{run_with_config, Selector, TestApp, TestConfig};

fn app(test: &str, bundle: &str) -> TestConfig {
    let card_host = "../OctoSense-App-Hub/crates/card-host";
    let mut c = TestConfig::new(card_host, "octosense-card-host", test).unwrap();
    c.bin_name = Some("card-host".into());
    c.app_args = vec!["--bundle".into(), format!("{bundle}/bundle"),
        "--app-data".into(), format!("{bundle}/.test-state"),
        "--allow-unsigned".into(), "--stamp".into()];
    c
}

#[test]
fn tip_20_percent() {
    run_with_config(app("tip", "/abs/path/apps/tip-split"), |app: TestApp| {
        app.locator(Selector::widget_type("Button").text_exact("20%")).wait_visible().click();
        app.locator(Selector::id("tip_line")).wait_text("Tip 20%: 0.00");
    }).unwrap();
}
```

这个示例测试的是一个分摊小费的应用，它有一个 `20%` 按钮和一个 `tip_line` 标签；请按你的应用修改选择器。用 `cargo test --release --test ui` 运行。设置 `MAKEPAD_TEST_PARALLEL=1` 可以并发运行测试（每个测试一个隐藏应用），设置 `MAKEPAD_TEST_VISIBLE=1` 则可以观看测试过程。用你在页面中声明的控件作为目标（`Selector::id` 对应 `name := …`，也可以用按钮文字）；`on_render` 中生成的控件同样在测试框架的快照里。

**在当前锁定的版本上未验证：** 这个示例曾在 macOS 上与另一个应用并行运行并通过，当时用的是较早的 App Hub 和 Makepad。它的 API 与当前锁定的 Makepad 版本一致。

## 5. 迭代修改

1. 修改 `bundle/main.splash`。语言说明见 [SCRIPT-API](SCRIPT-API.md)。
2. 运行 `curl -s 127.0.0.1:8141/quit`，再重新运行 `tools/octo run … --detach`。重启时会重新读取应用包，并重新写入摘要。
3. 运行 `tools/octo shot 8141 /tmp/now.png`，然后打开这张 PNG。
4. 如果画面不对，用 grep 搜索日志（§4），并修复第一个错误。

`.local-state/` 会在多次运行之间保留应用数据；要测试首次启动，删除这个目录即可。

## 6. 添加能力

在 `bundle/manifest.json` 中只添加界面实际用到的能力：

```json
"capabilities": ["storage", "net"],
"network": { "hosts": ["api.open-meteo.com"] }
```

在围绕某个宿主 API 搭建界面之前，先确认它所属的能力族会在你声明的平台上响应商店应用（[HOST-API-FAMILIES](HOST-API-FAMILIES.zh-CN.md)）：准入检查接受的能力，仍可能只响应系统应用。

在 `network.hosts` 中披露预计的 HTTPS 目的地。配套 SDK 不会因为 HTTPS 主机未列出而拒绝访问；每个已准入应用都有网络模块和带配额的私有存储，即使未声明 `net` 或 `storage`。普通 `http://`、`file://` 和不安全的包内路径仍会被准入检查拒绝。旧工具保留旧行为。[CAPABILITIES](CAPABILITIES.zh-CN.md) 说明使用披露和实际授权边界；[HOST-SERVICES](HOST-SERVICES.zh-CN.md) 介绍 Mail 等服务。

**已连接账户。** 要使用用户的 GitHub 或 Google 账户，像参考应用那样声明 `auth`、对应提供商的能力族（`github`、`gmail` 或 `gcalendar`）和 `storage.accounts: true`；如果只需识别用户身份、不读取其数据，只声明 `auth` 就够了。登录由宿主完成，宿主给应用的是连接句柄，绝不是令牌。这些服务需要兼容的 OctoSense Shell。当前公开应用使用 [RC4 发行版](../README.zh-CN.md#下载兼容-shell)。它没有公开提供商注册信息，需要发行方或运维人员提供，例如通过 `oauth/clients.json`（[CAPABILITIES § 限制](CAPABILITIES.zh-CN.md#限制)）。`card-host` 会返回 `no service answers "…" on this device`。完整示例见 [examples/connected-apps](../examples/connected-apps/README.zh-CN.md)。

**AI。** 在 OctoSense 的 Shell 中，隔离运行的应用可以调用 `model.complete`；用户允许该应用的 Agent 之后，还可以调用 4 个 `octos.*` 方法。在 `card-host` 中，这类调用一律返回 `no service answers "…" on this device`。请让应用在没有这些服务时也完整可用。[AI-SERVICES](AI-SERVICES.zh-CN.md) 列出了已有和计划中的功能，并给出一个经过验证、能处理“不可用”状态的调用。

**Host API v1。** [RC 发行版](../README.zh-CN.md#下载兼容-shell)（RC1 及之后）允许应用发现宿主 API、申请设备权限、调用自己的后端，以及用 Splash 实现 Agent 工具（[HOST-API-V1](HOST-API-V1.zh-CN.md)）。这类应用会在 `requires` 中列出 `host-api-v1`、`backend-api-v1` 或 `script-tools-v1`。`card-host` 会拒绝列出其中任何一项的应用，所以 `tools/octo run` 无法运行它们：`run` 会输出 `admitted`，但窗口显示 `card-host refused this bundle` 和宿主缺少的 API。请在兼容 RC4 发行版中按其平台限制测试这类应用（[HOST-API-V1 § 发布前](HOST-API-V1.zh-CN.md#发布前)）。`desktop-v0.1.0-beta.2` 同样会拒绝它们。

## 7. 最费时间的坑

### `main.splash` 方面

完整列表见 [SCRIPT-API](SCRIPT-API.md#gotchas)。

- 十六进制颜色中只要有 `e` 紧挨着数字，就要写成 `#x` 形式，如 `#x1e1e2e`。所有颜色都写成 `#x` 形式也没有问题。
- 用 `for i in n` 循环（0..n-1）；没有 `range()`。
- 在 `on_render` 中，写成 `if list.len() == 0 { EmptyLabel } for i in list.len() { Row }`，**不要**写成 `if … {…} else for …`。用 `else for` 测试这个模板时，空分支什么都没画，屏幕上还残留着旧的行。
- 在 `card-host` 中，带 `show_bg: true` 的 `View` 不绘制背景，无论它一开始就可见还是之后才显示；需要填充背景的容器时，请用 `SolidView` 或 `RoundedView`。
- `ButtonFlat` 不能包含 `Label` 子控件；可点击的行请用 `GestureView{on_tap: |x, y| …}`。
- 准入检查会拒绝密码和一次性验证码输入框。机密信息只在宿主服务的面板中输入。

### 应用包与 Git 方面

- **保留 id。** `tools/octo new` 只检查它创建时用的 id。如果之后把 id 改成 `com.example.notes`，准入检查会拒绝它，因为最后一段 `notes` 是保留名（§3）。
- **`.DS_Store`。** Finder 会把它写进你打开过的文件夹，而准入检查会拒绝任何扩展名未知的文件。检查之前先删除它：`find ~/apps/my-app/bundle -name .DS_Store -delete`。
- **换行符。** 如果 Git 检出时转换了换行符，字节就会改变，摘要随之失效。请 commit `new` 写入的 `.gitattributes`（§3）。
- **卡片中的字体。** 要使用自己的字体，把 `.ttf` 或 `.otf` 文件放进应用包，并在套件的 `font_src` 中用相对于应用包的路径引用它，例如 `"font_src": "assets/Body.ttf"`。`card-host` 从应用包自己的素材服务加载它，不需要网络权限。打包的字体计入 8 MiB 上限，所以较大的中日韩字体请只打包所需的子集。字体中没有的字形（例如中文）会改用 Makepad 内置的中文字体霞鹜文楷（LXGW WenKai）。套件可以引用 `makepad_widgets:resources/` 下三种确切的内置字体：`Inter.ttf`、`LXGWWenKaiRegular.ttf`、`LXGWWenKaiBold.ttf`。单层 `$token` 引用可以解析为受支持的字符串；任意对象、嵌套 token 引用及其他 crate 资源路径，准入检查会拒绝。[App Hub #146](https://github.com/OctoSense-org/OctoSense-App-Hub/pull/146) 已在禁用系统字体回退的 macOS 原生 `card-host` 中验证两种霞鹜文楷字重的绘制。
- **`desktop-v0.1.0-beta.2` 上的字体。** 这个版本早于打包字体的加载功能：它会安装带打包字体的应用，但卡片不会加载这些字体。要在这个版本上显示中文，请用纯 L0 角色套件（`Surface`、`TextTitle`、`TextBody` 等）组合卡片，并且不设 `font_src`；中文由霞鹜文楷显示。
- **脚本应用中的字体。** 把字体文件放进应用包，例如 `bundle/fonts/X.ttf`，然后在 `main.splash` 中把它作为 `TextStyle` 的 `FontFamily` 成员加载：`FontMember{res: http_resource("{{assets}}/fonts/X.ttf")}`。许可条款要求随字体提供许可证时，请保留在应用包中，使用受支持的扩展名，例如 `fonts/OFL.txt`。普通文档中的署名 URL 可以通过检查，不会增加网络权限。Agent 指引与结构化资源仍须通过原有的主机、资源检查。
- **缺失的字形。** 用 `MAKEPAD_SYSTEM_FONTS=0` 测试应用（`MAKEPAD_SYSTEM_FONTS=0 tools/octo run …`）。不设这个变量时，macOS 的系统字体会补上你的字体缺少的字形，把问题掩盖起来。**未验证**：在没有中日韩系统字体的 Linux 上，同样的文字是否会显示为方框，以及字体在 OctoSense 桌面发行版（0.1.0-rc.1、0.1.0-rc.2）中的表现。
- **大小。** 应用包不能超过 8 MiB（8,388,608 字节）。

## 8. 检查应用包

```sh
tools/octo shot 8141 ~/apps/my-app/bundle/screenshots/01-main.png   # 先把应用操作到真实状态
curl -s 127.0.0.1:8141/quit
tools/octo check ~/apps/my-app/bundle
```

`check` 先运行 `hub stamp`，再运行 `hub check --allow-unsigned`，检查不通过时返回非零退出码。如果在 `shot` 之前运行 `check`（例如对刚复制出来的模板），准入检查会拒绝这个应用包，因为模板的商店信息有意引用了 `screenshots/01-main.png`：

```text
octo: hub stamp -> 32363ac4…
octo: …/hub check …/my-app/bundle --allow-unsigned
my-notes 0.1.0 — REFUSED
  [warning] publisher-signature: unsigned: accountability rests on the hub alone
  [refused] listing: screenshots/01-main.png is named by the listing but is not in the bundle
  grants: capabilities {"storage"}, hosts {}, storage 16777216 bytes, agent none
hub: the bundle was refused
octo: note: listing.json still holds template placeholders (example.com, Replace with, Replace this); the gate accepts them, a reviewer will not.
```

有了第一条命令截取的截图，检查就会通过（绝不要用占位图片代替）：

```text
my-notes 0.1.0 — PASSED
  [warning] publisher-signature: unsigned: accountability rests on the hub alone
  grants: capabilities {"storage"}, hosts {}, storage 16777216 bytes, agent none
```

开发可编辑源码期间，出现未签名警告是正常的。在人工填写发布者字段之前，占位提示会一直存在。

要检查版本是否已经发布过，加上 App Hub 经过认证的签名目录：`tools/octo check <bundle> --catalog <workspace>/OctoSense-App-Hub/catalog-v2.json`。如果版本号已经用过，准入检查会拒绝并输出 `[refused] version: version 0.1.0 of <id> is already published; publish a new version`。请对照 `catalog-v2.json` 检查，而不是旧格式的 `catalog.json`：只通过 GitHub 发布的版本不会出现在后者中。

`check` 会先为未签名的应用包重新写入摘要。如果你在最后一次 `check` 之后又修改了应用包，却没有重新运行就 commit，commit 中的摘要就是过期的：审核人员直接运行 `hub check` 时，会以 `[refused] digest` 拒绝它。每次源码 commit 之前，都把 `tools/octo check` 作为最后一步。GitHub 工作流会另行生成并验证封存的 Release pack（§10）；可编辑的 tag 源码不包含这个证明。

App Hub 的 [`hub` 命令参考](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/SUBMITTING.zh-CN.md#hub-命令)列出了所有 `hub` 命令，以及每个命令由谁运行、用在提交的哪一步。

## 9. 在 OctoSense 手机上运行

目前的情况：

- **无法把任意应用包侧载到普通 OctoSense 手机上。** 手机商店读取内置的 Hub 地址（`DEFAULT_HUB`，即 `raw.githubusercontent.com/OctoSense-org/OctoSense-App-Hub/main/`），并且只信任编译进构建的信任锚（App Hub 的根公钥）。`OCTOSENSE_HUB` 和 `OCTOSENSE_HUB_ANCHOR`（镜像目录或 URL，及其信任锚）是环境变量，Android 启动器不会设置它们；也没有找到在设备上设置它们的选项。**在设备上未验证。**
- **桌面端的可选演练**：用你自己的一次性信任锚把应用的 Release pack 发布到本地签名目录，显式设置 `OCTOSENSE_HUB_CATALOG=legacy` 并使用新的应用数据目录，再用 App Hub 的商店安装；这个商店运行的安装代码与手机上的相同（[PUBLISHING §4](PUBLISHING.zh-CN.md#4-在本地演练商店流程)）。OctoSense 桌面端 Shell 同样读取 `OCTOSENSE_HUB` 和 `OCTOSENSE_HUB_ANCHOR`；它的商店会从这个签名目录安装你的应用，并在 Shell 的 Card runner 中打开。**这些旧格式目录命令尚未验证**带 GitHub 证明的 Release。RC4 使用经管理员证明的签名目录单独演练，见[下载证据](../README.zh-CN.md#下载兼容-shell)。
- **第一方应用**作为系统应用进入手机：应用包位于 [OctoSense `apps/`](https://github.com/OctoSense-org/OctoSense/tree/main/apps)，列在 Shell 的 `system-apps.json` 中（手机上是 OctoSense 的 `phone/system-apps.json`），由 App Hub 的 `crates/app-hub-app/build.rs` 打包，再经过 Home 或 ROM 构建。这条路径用于 OctoSense 维护的 `os.*` 应用，不用于商店应用。
- **连接账户的示例**目前只声明 macOS。隔离手机测试示例不代表这些已发布应用能在 Android 上运行。
- **Hub 准入之后**，宿主仍须支持所需 API/ABI 和声明平台。出现在签名目录中不代表兼容；桌面 RC4 不升级 Home。

Android 版 `card-host` 不编译远程控制桥。在手机上，请用 OctoSense 测试构建中的 App Studio 工具操作应用（[MODEL-VALIDATION](MODEL-VALIDATION.zh-CN.md#选择测试方式)），而不是 `tools/octo`。

## 10. 发布

**开 App Hub 提交 issue 来请求发布。** 填写应用仓库、版本/commit、截图和权限。可以先开 issue，再补充经过验证的 Release 产物。之后由审核人员检查确切的 Release，并在 issue 中反馈问题；App Hub 管理员批准后，再由 Hub 把应用发布到签名目录。

完整流程见 [PUBLISHING](PUBLISHING.zh-CN.md)。测试源码后执行：

```sh
tools/octo publish-github ~/apps/my-app
tools/octo package-help
```

评审 `.github/workflows/publish-app.yml`，与已测试应用一起 commit，再推送新的 `v<manifest.version>` tag。GitHub Actions 会准备、证明、验证和打包。App Hub 只接受带 GitHub 证明的 Release，所以无需 `publisher.key` 或开发者签名 secret。把成功的工作流和确切的 Release pack 附到提交 issue。在 App Hub 首次发布应用之前，每个新 Release 都以评论的形式发在这个 issue 中，并更新 issue 标题和 Version 字段；发布之后，每个新版本都开新 issue。安装工作流、创建 GitHub Release 都不会自动提交或批准应用。日常更新使用同一身份下的新版本/新 tag。

此路径需要契约 1.8.0 / `publisher-github-v1`。真实的 Release 及原生 Store 的安装、更新检查已在隔离的测试签名目录中通过（[历史证据](PUBLISHING.zh-CN.md#36-github-发布者身份human)）。当前公开的 macOS 示例也通过了原生安装、更新及 RC 重新打开检查；见[下载状态与平台限制](../README.zh-CN.md#下载兼容-shell)。旧宿主和 `card-host` 会拒绝已封存的 Release。本地商店演练（[PUBLISHING §4](PUBLISHING.zh-CN.md#4-在本地演练商店流程)）是可选的；这些旧格式目录命令尚未用带 GitHub 证明的 Release 验证。RC4 的证明目录验收单独记录（[下载证据](../README.zh-CN.md#下载兼容-shell)）。

## 故障排查

| 现象 | 原因与修复 |
| --- | --- |
| 构建停在 `octosense-appstore`，并提示 `no variant … TextInputStateQuery` | 见[构建 `card-host` 时报 `TextInputStateQuery` 错误](#构建-card-host-时报-textinputstatequery-错误)。 |
| 找不到 `cargo` | `export PATH=$HOME/.cargo/bin:$PATH`（rustup 把它安装在这里）。 |
| 构建在 `path = "../makepad/..."` 依赖处失败 | 同级仓库缺失或版本不对：在本仓库中运行 `python3 tools/setup-native.py`，然后用 `--check` 检查。 |
| `doctor`：`[fail] hub` 或 `card-host` | 构建它们（§2）。如果 `hub` 指向的是 GitHub 的 `hub` CLI，`doctor` 会指出来；请设置 `OCTO_HUB` / `OCTO_CARD_HOST` 或 `CARGO_TARGET_DIR`。 |
| Windows：`tools/octo` 无法启动 | 以 `python tools/octo …` 的形式运行（§2）。 |
| Windows：`doctor` 找不到 `hub.exe` | 先构建（§2）。如果它不在 `doctor` 列出的目录中，把 `OCTO_HUB` 和 `OCTO_CARD_HOST` 设为对应 `.exe` 的路径。 |
| `new`：`the following arguments are required: --platform` | 传入 `--platform macos`，或你要测试的每个平台（§3）。 |
| `new`：`id '…' uses reserved native/host namespace '…'` | 换一个最后一段不是保留名的 id（§3）。 |
| `run`：`port 8141 is already taken by card-host pid …` | 之前的实例仍占用着该端口。运行消息中给出的 `curl -s 127.0.0.1:8141/quit`，或换一个 `--port`。 |
| 点击、输入或修改似乎都不起作用 | 某个处理函数失败了（搜索日志，见 §4）；或者你没有用 `tools/octo run` 启动应用，操作的是该端口上一个较旧的实例（`curl -s 127.0.0.1:8141/s` 会显示它的进程号）。 |
| `shot` 提示 `still changing after 2s` | 应用在持续播放动画；PNG 是最后一帧。查看这张图，或传入更长的 `--settle`。 |
| 在 Linux 上 `shot` 或 `/g?raw=1` 超时 | 有报告称，在软件渲染（llvmpipe、WSL）下截帧会超时。请在 macOS 上截图，这是经过验证的做法。仅限 Linux，此处**未验证**：启动应用时设置 `MAKEPAD_WRITE_FRAMEBUFFER_PNG=<file>`（`MAKEPAD_WRITE_FRAMEBUFFER_PNG=<file> tools/octo run …`），Makepad 的 Linux OpenGL 后端就会把绘制到窗口的每一帧写入 `<file>`，覆盖上一帧。绝不要根据 `/snap` 重画截图。 |
| 在 WSL 下，通过输入法输入的中文到不了 `card-host` | 有人报告过，**未验证**。请在 macOS 上测试文字输入。 |
| 卡片中的中日韩文字显示为方框或 `NO GLYPH` | 在 `card-host` 中：运行时早于 OctoScript-Makepad `704a3ad7`，卡片文字从这个版本起才有中文后备字体。运行 `python3 tools/setup-native.py --update`，然后重新构建 `card-host`（§2）。`desktop-v0.1.0-beta.2` 早于这个运行时：在这个版本上请用不设 `font_src` 的纯 L0 角色套件组合卡片（§7）。 |
| 按钮上不显示文字 | `ButtonFlat` 的默认文字是为深色主题准备的白色；请设置 `draw_text +: {color: …}`（[SCRIPT-API § Gotchas](SCRIPT-API.md#gotchas)）。 |
| 数字显示为 `NaN` | `"".to_f64()` 和非数字文本得到的是 NaN，而不是 nil；请用 `if v >= 0` 判断（[SCRIPT-API § Data and strings](SCRIPT-API.md#data-and-strings)）。 |
| 输入文字后出现 `widget has no uid` / `widget '<id>' not found in tree` | 运行时早于 Makepad `d0a9def5`：在这些版本中，`TextInput` 的 `on_change` 无法通过 `ui` 读取同一个输入框。运行 `python3 tools/setup-native.py --update`，然后重新构建 `card-host`。 |
| `variable net not found in scope` | 检查宿主、SDK 和运行时版本是否匹配（§6）；新适配器即使没有声明也安装 `net`，旧适配器可能省略它。 |
| `this app may not reach <url>` | 这是旧运行时策略。升级到相互匹配的配套宿主、SDK 和运行时；`network.hosts` 是披露信息，不是运行时白名单。 |
| `no service answers "…" on this device` | 除了用于发现宿主 API 的 `runtime`，`card-host` 不提供任何宿主服务，出现这条消息是正常的；请在 OctoSense Shell 中试用应用（[HOST-SERVICES](HOST-SERVICES.zh-CN.md)）。 |
| `run` 输出 `admitted`，但窗口显示 `card-host refused this bundle`，以及 `app <id> needs a host implementing …@1` 或 `this host does not implement required APIs: …` 这样的原因 | 清单的 `requires` 中列有 `host-api-v1`、`backend-api-v1` 或 `script-tools-v1`，而 `card-host` 缺少它们所要求的 API。请在兼容 RC4 发行版中按其平台限制测试应用（[HOST-API-V1 § 发布前](HOST-API-V1.zh-CN.md#发布前)）。 |
| `check`：`screenshots/01-main.png is named by the listing but is not in the bundle` | 截取真实截图（§8）；绝不要用占位图片。 |
| `check`：`[refused] listing: listing names no platforms` | 商店信息的 `platforms` 为空，原始模板就是这样。在 `listing.json` 中列出你测试过的平台，或用 `tools/octo new … --platform …` 创建应用（§3）。 |
| `check`：`[refused] identity: app id "…" ends in "…", which is reserved: …` | 修改 id 的最后一段（§3）。同样的检查结果还会在 `policy` 下再出现一次。 |
| `check`：`[refused] contents: .DS_Store has extension "", which a bundle may not hold` | 删除这个文件：`find <bundle> -name .DS_Store -delete`。其他扩展名未知的文件也必须移出 `bundle/`。 |
| `check`：`[refused] digest: the bundle hashes to …, the manifest claims …` | 上次写入摘要之后，字节发生了变化。可编辑源码：再运行一次 `tools/octo check`。已封存的 Release：修复可编辑源码，用新版本和新 tag 生成 Release；绝不要给 Release 重新写入摘要。只在全新克隆上出现时：检出时转换了换行符（commit `new` 写入的 `.gitattributes`，见 §3），或者 commit 中的摘要已过期（§8）。 |
| `check`：`[refused] assets: … contains https://…`（普通许可 `.txt` 或 `.md` 文件） | 从 App Hub #146 或更新版本重新构建 `hub`。普通文档 URL 可以通过检查；保留要求提供的许可声明。Agent 指引与结构化资源引用仍须单独检查。 |
| `check`：`[refused] resource-invalid (…/font_src): not a portable bundle path: "makepad_widgets:resources/…"` | 当前 `hub` 接受内置 `Inter.ttf`、`LXGWWenKaiRegular.ttf`、`LXGWWenKaiBold.ttf` 的确切路径（§7）；请重建旧版准入工具。其他字体要随应用打包并使用相对路径，例如 `assets/Body.ttf`。`desktop-v0.1.0-beta.2` 仍早于打包字体加载功能；这个版本请使用不设 `font_src` 的纯 L0 角色套件。 |
| `hub: the bundle exceeds the size limit`，没有报告 | 应用包超过了 8 MiB。压缩或删除图片和字体。 |
| `card-host: refused: card-host --stamp refuses publisher signing metadata; use an unsigned development copy` | `tools/octo run` 会传入 `--stamp`，所以 `card-host` 在检查证明之前就会拒绝已封存的 Release。请改为运行可编辑源码。 |
| `card-host: refused: this host has no GitHub publisher verifier` | `card-host` 不运行已封存的 Release。请测试未签名的可编辑源码；准入之后，在兼容宿主（例如 [RC4 发行版](../README.zh-CN.md#下载兼容-shell)）中测试这个 Release。 |
| `hub scan … --packet build/review.json` 输出 `hub: build/review.json: No such file or directory (os error 2)` | `hub` 不会创建审核包所在的目录。先运行 `mkdir -p build`。 |
| `hub check --help` 输出 `hub: No such file or directory (os error 2)` | 你的 `hub` 比 App Hub 当前的 `main` 旧；在当前 `main` 中，`--help` 会输出用法。重新构建（§2），或不带参数运行 `hub`。 |
| 准入检查的其他拒绝 | 见 App Hub 的[常见拒绝原因及修复](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/SUBMITTING.zh-CN.md#常见拒绝原因及修复)。 |

### 构建 `card-host` 时报 `TextInputStateQuery` 错误

`cargo build --release -p octosense-card-host -p octosense-app-hub` 报错中止：

```text
error[E0599]: no variant, associated function, or constant named `TextInputStateQuery` found for enum `makepad_widgets::Event` in the current scope
   --> crates/appstore/src/services.rs:393:18
error: could not compile `octosense-appstore` (lib) due to 1 previous error
```

同一个错误也会让 [PUBLISHING §4](PUBLISHING.zh-CN.md#4-在本地演练商店流程) 中的 `appstore` 构建中止。`hub` 不使用 Makepad，单独构建仍能成功：`cargo build --release -p octosense-app-hub`。

更新 App Hub，然后严格按照 §2 只构建这两个包：

```sh
cd <workspace>/OctoSense-App-Hub
git pull
cargo build --release -p octosense-card-host -p octosense-app-hub
```

App Hub `main` 构建 `card-host` 时关闭了 `appstore` 的 `text-input-state-query` 特性，因此可以基于未打补丁的 Makepad 构建。如果你本地的 App Hub 早于这项改动，或者你构建的是 App Hub 的其他包或整个工作区，错误仍会出现：这些构建会开启该特性，需要 OctoSense 打过补丁的 Makepad。[PUBLISHING §4](PUBLISHING.zh-CN.md#4-在本地演练商店流程) 中的 `octosense-appstore-app` 构建就属于这一类；请按该节的说明构建。
