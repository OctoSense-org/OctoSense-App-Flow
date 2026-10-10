# 能力

[English](CAPABILITIES.md) | 简体中文

未注明中文版的链接指向英文文档。

能力是应用在 `manifest.json` 中申请的权限。脚本只能获得清单申请并经准入检查放行的能力。

准入检查的规则，以及商店向用户显示的文字，都以 App Hub 的 [PUBLISHING § 清单](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/PUBLISHING.zh-CN.md#清单) 为准。哪个 Shell 提供哪项宿主服务，见 [HOST-SERVICES](HOST-SERVICES.zh-CN.md)。

## 申请能力

```json
"capabilities": ["storage", "net"],
"network": { "hosts": ["api.open-meteo.com"] }
```

- **列表是封闭的。** App Hub `crates/app-contract/src/manifest.rs` 中的 `KNOWN_CAPABILITIES` 共有 105 个名称：27 个大类能力（例如 `storage` 和 `glance`）和 78 个精确服务名（例如 `octos.turn.start`）。准入检查会拒绝其他任何名称（例如 `contacts`），也会拒绝单独的前缀（例如 `octos.`）：

  ```text
  [refused] policy: app dev.example.myapp requests unknown capability "contacts"
  ```

- **没有隐含授权。** 应用得不到它没有申请的能力，任何能力也不会连带授予另一项能力。
- **只申请应用必需的能力。** 界面上用不到的授权，审核人员都会指出来。
- **商店展示的是清单，不是商店信息。** 安装前，用户会看到每项能力对应的一行权限说明和一份隐私概要，两者都根据 `manifest.json` 生成。商店信息中的文字无法淡化这些内容。

## 设备与数据

| 能力 | 脚本得到什么 | 未申请时 |
| --- | --- | --- |
| `storage` | 应用自己的存储 jail，即按应用 ID 划分的私有数据目录：[`fs.*`](SCRIPT-API.md#storage-fs)、相机拍摄的内容，以及控件读取的本地文件（例如地图数据包）。 | 没有 jail。每个 `fs.*` 调用都报错 `storage not available in this context`，拍摄的内容不会保存，控件也读不到任何本地文件。 |
| `camera` | `CameraPreview`：预览、拍照和录像。拍摄的内容以 `DCIM/IMG_<ms>.jpg` 和 `DCIM/VID_<ms>.mp4` 存入 jail，所以还要申请 `storage`。自 RC1 起在 Android 和 macOS 上提供。 | `CameraPreview` 拒绝运行：`this app was not granted the camera`。无论是否申请，都仍要经过操作系统自己的相机授权。 |
| `microphone` | 相机录像中的声音；从 RC2 起还有 `microphone.record_start/record_status/record_stop/record_cancel`：在前台录一段短音频（单声道 WAV，最长 30 秒）存入应用存储，所以还要申请 `storage`；授权通过 `microphone.permission.request` 和操作系统的提示完成。自 RC1 起在 Android 和 macOS 上提供；录音的硬件验收仍待完成。 | 录像没有声音，录音会被拒绝。 |
| `library` | 每次拍摄的内容还会提供给系统相册，其他应用可以在相册中看到。 | 拍摄的内容只留在应用的 jail 中。 |
| `location` | 设备位置：`sys.gps(...)`，以及 `MapView` 的跟随视角。仍要经过操作系统的定位授权。自 RC1 起在 Android 和 macOS 上提供；`location.get` 仅限 Android，RC2 新增的 `location.sample` 在两者上都能为前台应用获取实时位置。 | `sys.gps("ok")` 读出 0，表示没有定位结果。 |
| `files` | 从 RC2 起：`files.import` 和 `files.export` 在原生文件对话框和应用存储之间移动一个文档（所以还要申请 `storage`），`files.pick_photo` 导入一张 PNG、JPEG 或 WebP 图片，`files.share` 把文本交给 Android 的分享面板；单个文件最大 1 MiB，仅限前台。在 macOS、Windows 和 Android 上提供；Linux 需要 zenity、qarma、matedialog 或 kdialog；选择器的验收仍待完成。 | 每个 `files.*` 调用都会被拒绝。 |
| `audio` | 从 RC2 起：`audio.play`、`audio.status` 和 `audio.stop` 在应用处于前台时播放应用存储中的一个 WAV、MP3、FLAC 或 Ogg 文件（最大 1 MiB、最长 60 秒），所以还要申请 `storage`。在 macOS 和 Android 上提供；硬件验收仍待完成。 | `audio.play` 会被拒绝。 |

未申请 `storage` 时，`hub check` 的 `grants:` 行显示 `storage none`，准入检查还会对每个调用 `fs.*` 的脚本以及 `camera` 授权发出警告：

```text
[warning] storage: main.splash calls fs.read, fs.write, fs.exists, which fail without the storage capability
```

## 网络

| 能力 | 脚本得到什么 | 未申请时 |
| --- | --- | --- |
| `net` | `net.http_request` 和 `net.web_socket`，只能访问 `network.hosts` 中列出的主机。主机必须写成精确的小写纯主机名：不带协议、路径、端口或通配符。组件的 `wasi:http` 请求同样需要 `net`，但可以访问任何主机：按 OctoSense 2026 年 10 月 8 日的裁定，应用的网络声明在安装时展示，运行时不强制（已在 OctoSense `main` 上实现，尚无发行版包含；见 [RUST § 网络](RUST.zh-CN.md#网络)）。 | 脚本中根本没有 `net`：`variable net not found in scope`。申请了 `net` 但主机列表为空时也是如此。 |
| `images` | 任何公开 `https://` 主机上的图片（`Image{src: http_resource(url)}`），不限于 `network.hosts`，例如 RSS 阅读器的缩略图。`net.http_request` 的访问范围不会因此扩大。 | 只能加载已列出主机上的图片。 |
| `web` | `WebReader` 可以在系统的网页视图中打开任何公开的 `https://` 网页。网页无法反过来访问应用。可用性取决于[宿主与平台限制](../README.zh-CN.md#下载兼容-shell)。 | `WebReader.open` 只能打开已列出主机上的网页，其他一律拒绝：``refused <url>: not on this app's host list, and no `web` grant``。 |

桌面 RC1 和 RC2 在 Windows 上使用 WebView2、在 Linux X11/XWayland 上使用 GTK 3/WebKitGTK 内嵌普通网页。这些引擎不随包附带；原生 Wayland 内嵌及 Windows/Linux 嵌入式后端登录仍不支持（[运行条件](../README.zh-CN.md#下载兼容-shell)）。历史版本中，`card-host` 和 `desktop-v0.1.0-beta.1` 的 Linux、Windows 版本会让 `open` 返回 `true`，但不显示网页，日志中显示 `Not implemented on this platform: CxOsOp::SpawnSystemBrowser`。`desktop-v0.1.0-beta.2` 只有 macOS 版本。

运行时和准入检查会拒绝以下情况：

| 请求 | 结果 |
| --- | --- |
| 向未列出的主机发起 `net` 请求 | `this app may not reach <url>` |
| 私有或内部地址，无论申请了什么能力 | `host not permitted (private/internal): <host>` |
| 列出了主机，却没有申请 `net` | 准入检查拒绝：`lists hosts but does not request the net capability` |
| 主机带有协议或路径，例如 `https://x` | 准入检查拒绝：`host "https://x" must be a bare host name, with no scheme or path` |
| `main.splash` 中提到未列出的 `https://` 主机 | 准入检查在 `assets` 检查项下拒绝（`main.splash reaches <host>, which the manifest does not declare in network.hosts`），除非应用申请了 `images` 或 `web` |
| 源码中有任何 `http://` URL | 准入检查在 `assets` 检查项下拒绝，无论是否申请了 `web` |

脚本一侧的规则见 [SCRIPT-API § Network](SCRIPT-API.md#network)。

## 宿主服务

宿主服务在 Shell 中完成应用绝不能自己做的事，例如保管密码或令牌。脚本用 `host.request("<family>.<method>", args, fn(r){…})` 调用它（[SCRIPT-API](SCRIPT-API.md#host-services-hostrequest)）。每次调用都需要 `<family>` 这项能力。未申请时，回调会立即运行，`r.is_ok` 为 false，并带有以下错误：

```text
this app was not granted "mail", which "mail.accounts" needs
```

| 能力 | 脚本得到什么 |
| --- | --- |
| `mail` | 用户在宿主面板上登录的邮件账户：文件夹、邮件和同步。从 RC2 起，商店应用也能发送：`mail.compose` 和 `mail.compose_status` 保存草稿，`mail.review_send`（或打开同一审阅界面的 `mail.send`）把邮件显示在宿主的原生审阅界面上，由用户亲手点按确认。这个审阅界面只在 macOS 和 Android 上有；在 Windows 和 Linux 上它会以 `Physical Mail send approval is unavailable on this platform` 失败，SMTP 投递也尚未验证。在 RC1 上，商店应用没有发送路径（[OctoSense #409](https://github.com/OctoSense-org/OctoSense/issues/409)）。方法见 [HOST-SERVICES § Mail](HOST-SERVICES.zh-CN.md#完整示例mail)。 |
| `auth` | 用户在宿主面板上批准的 GitHub 和 Google 连接；从桌面 RC1 起，还能让用户登录应用自己的后端。应用拿到的是连接句柄，绝不是令牌。只申请 `auth` 可以识别用户身份，但读不到用户的任何数据。见[使用已连接账户](#使用已连接账户)。 |
| `github` | 读取仓库；保存要经用户在宿主面板上批准。需要 `auth`。 |
| `gcalendar` | 读取和同步 Google Calendar；写入要经用户在宿主面板上批准。需要 `auth`。 |
| `gmail` | 读取 Gmail，使用带版本号的回复草稿，经用户在宿主的审阅界面上批准后发送邮件，并为应用 Agent 提供新邮件事件。需要 `auth`。 |
| `glance` | `glance.publish`、`glance.withdraw` 和 `glance.list`：在速览栏上发布卡片，这些卡片只会打开本应用。见 [AI-SERVICES § 发布到速览栏](AI-SERVICES.zh-CN.md#发布到速览栏)。 |
| `model` | `model.complete` 和 `model.budget`：通过用户自己的 AI 提供商进行一次性模型调用，结果按应用的 JSON Schema 校验，并受每日预算限制。见[一次性调用](AI-SERVICES.zh-CN.md#一次性模型调用model)。OctoSense #368 中的[媒体与嵌入向量](AI-SERVICES.zh-CN.md#媒体与嵌入向量model) 使用同一能力，自[桌面 RC1](../README.zh-CN.md#下载兼容-shell) 起包含；beta.2 和 `card-host` 不提供这些方法。提供商权益与真实调用验证需单独确认。 |
| `runtime` | `runtime.list` 和 `runtime.describe`：当前构建实现了哪些宿主 API，不含任何账户数据。桌面 RC1、RC2 和 `card-host` 都会响应；desktop-v0.1.0-beta.2 拒绝这项能力。见 [HOST-API-V1 §2](HOST-API-V1.zh-CN.md#2-提供可选功能前先查询)。 |
| `wasm` | 应用自带的函数：应用包 `fns/` 中的 WebAssembly 模块（最多 8 个），由宿主的 `wasm` 服务在沙盒中运行，有截止时间和内存上限。函数只拿到自己的输入，接触不到文件、网络、时钟或其他应用。Agent 工具可以用 `host_method: "wasm.<function>"` 运行其中一个函数。商店显示的说明是“Run its own sandboxed functions on this device”。桌面 RC2 在 macOS 和 Linux 上提供这项服务，Android 上的标准 Home 源码构建也提供，属于有限支持；Windows、iOS 和 OpenHarmony 的构建不包含它，RC1 也没有提供。WebAssembly 组件（OctoSense ADR 0014；自 2026 年 10 月 10 日起已在 OctoSense `main` 上，尚无发行版包含）还能访问时钟、随机数，有 `storage` 时还能访问应用的存储文件夹，并且需要 `requires: ["wasm-components-v1"]`；有 `net` 时它还能访问网络（任何主机：`network.hosts` 在安装时展示，不强制），并能调用应用获授权的宿主服务。函数的编写、构建和调用方法见 [RUST](RUST.zh-CN.md)。 |
| `device_calendar` | 从 RC2 起：操作系统中已配置的日历。`device_calendar.permission.request` 请求用户授权和操作系统权限，`calendars.list` 和 `calendars.select` 选择日历并返回句柄，`events.list` 和 `events.get` 读取日程（重复日程和参与者只读），`events.create`、`events.update` 和 `events.delete` 要等用户在原生审阅界面上亲手点按。需要 `requires: ["host-api-v1"]`。在 macOS（EventKit）和 Android Home 上提供；与系统日历的实际交互仍待验收。与 `calendar`（Calendar 自己的服务）和 `gcalendar`（Google）是不同的服务。 |

除 `runtime` 外，这些服务都不在 `card-host` 中运行，在那里每次调用都返回 `no service answers "<family>" on this device`。请在 OctoSense Shell 中测试它们。

## 商店应用用不上的能力

没有任何 Shell 向商店应用提供这些名称。准入检查接受其中除引擎名称以外的所有名称，引擎名称则直接拒绝。不要申请这些能力。

| 能力 | 实际情况 |
| --- | --- |
| `calendar` | `calendar` 服务只响应系统应用 Calendar：`calendar is Calendar's own service`。要访问用户的 Google Calendar，请用 `gcalendar`。 |
| `photos`、`youtube` | 两者各自只有一个服务，而且只响应对应系统应用的 `notify` 调用：`photos.notify serves os.photos only`。 |
| `llm` | 该服务管理设备上的 AI 提供商，只响应系统应用（返回 `llm is for OctoSense's own apps.`）。要调用模型，请用 `model`。 |
| `news` | 该服务只响应系统应用（返回 `The news service serves system apps only.`）。 |
| `research`、`crawl` | 供应用 Agent 使用的系统工具箱。各 Shell 只把它授予系统应用，而且只在启用了 `toolbox-peers` 构建特性的版本中授予。准入检查仍要求清单带有顶层的 `research` 范围：`requests research but declares no research scope`。商店应用尚不支持：[OctoSense#64](https://github.com/OctoSense-org/OctoSense/issues/64)。 |
| `prompt` | 尚不支持：没有宿主读取它，`host.prompt` 也不存在。应用 Agent 通过 `ask_user_question` 向用户提问，这个工具在 `agent.tools` 中声明。 |
| `ledger.read`、`clipboard` | 任何发行版都没有宿主通过 `host.request` 提供它们：每次调用都会失败。`clipboard` 授权只解锁 WebCard 自己的只写剪贴板桥接。 |
| `sheet`、`photo`、`word`、`deck`、`cad`、`light`、`sound`、`design`、`film`、`effect`、`vector`、`pdf` | 面向系统应用的 craft 引擎宿主服务（[ADR 0013](https://github.com/OctoSense-org/OctoSense/blob/main/docs/adr/0013-craft-engines-as-pinned-services.zh-CN.md)），随桌面 RC2 发行，供系统助手使用。App Hub `main` 的契约现已把这十二个名称列为可申请的能力，但 RC2 的准入检查（契约 1.10.0）仍会拒绝写了它们的清单，这些服务在任何构建上都不响应商店应用。 |

按能力族汇总的平台和起始版本见 [HOST-API-FAMILIES](HOST-API-FAMILIES.zh-CN.md)。

## 使用已连接账户

应用通过宿主服务访问用户的 GitHub 或 Google 数据。Shell 保管提供商凭据，应用只持有连接句柄。

1. 声明 `auth`、提供商对应的能力族（family），以及按账户划分的存储。不要把提供商的 API 主机写进 `network.hosts`：请求由宿主服务发出。

   ```json
   "capabilities": ["storage", "auth", "github"],
   "network": { "hosts": [] },
   "storage": { "accounts": true }
   ```

   此时 `hub check` 显示：

   ```text
   grants: capabilities {"auth", "github", "storage"}, hosts {}, storage 16777216 bytes, agent none
   ```

2. 在应用自己的某个界面上，请用户连接账户：

   ```splash
   host.request("auth.connect", {provider: "github" scopes: ["public_repo"]}, fn(r){
       if !r.is_ok { ui.status.set_text(r.error) }
   })
   ```

   宿主会弹出自己的登录面板。成功时，`r.data` 就是新建的连接：`handle` 指代这个连接，`subject` 和 `label` 标识对应的账户。每个权限（scope）都需要相应的能力。身份类权限只需要 `auth`，因此应用可以只识别用户身份，而不读取用户的数据：

   | 提供商 | 权限 | 所需能力 |
   | --- | --- | --- |
   | `github` | `read:user` | `auth` |
   | `github` | `public_repo`、`repo` | `auth` 和 `github` |
   | `google` | `openid`、`email`、`profile` | `auth` |
   | `google` | `calendar.list`、`calendar.events` | `auth` 和 `gcalendar` |
   | `google` | `mail.read`、`mail.send` | `auth` 和 `gmail` |

   调用失败时，`r.error` 会说明原因：

   | 错误 | 原因 |
   | --- | --- |
   | `Requested scopes exceed this app's granted services` | 某个权限所属的能力族不在 `capabilities` 中。 |
   | `Open the app to connect an account` | 调用来自速览卡片或 Agent 的工具。 |
   | `OAuth is not configured. Add provider registrations in the host's oauth/clients.json` | beta.2 宿主没有 `clients.json`（[限制](#限制)）。 |
   | `This provider is not configured in OctoSense` | beta.2 宿主的 `clients.json` 中没有该提供商的注册信息。 |
   | `GitHub sign-in is unavailable in this build. Check for an OctoSense update or contact its distributor.`（或 `Google sign-in …`） | 桌面 RC1 或之后的构建中没有该提供商的注册信息；公开的 RC 安装包不含任何注册信息（[限制](#限制)）。 |

3. 调用提供商能力族中的方法。把连接的 `handle` 作为 `connection` 传入，例如调用 `github.repositories` 时传入 `{connection: <handle> page: 1}`。

   | 服务 | 方法 |
   | --- | --- |
   | `auth` | `connect`、`accounts`、`active`、`select`、`disconnect`；从桌面 RC1 起还有 `backend.me` 和 `backend.request`（[见下文](#登录应用自己的后端)） |
   | `github` | `repositories`、`files`、`read`、`review_save` |
   | `gcalendar` | `calendars`、`cached`、`refresh`、`get`、`prepare`、`review_save`；`sync` 仅在 desktop-v0.1.0-beta.2 上可用（[限制](#限制)） |
   | `gmail` | `labels`、`messages`、`message`、`draft.open`、`draft.get`、`draft.edit`、`draft.review`、`events.status`、`event.status`、`event.decide` |

   每个方法的参数和返回值见 OctoSense 的 [`crates/oauth-service/README.zh-CN.md`](https://github.com/OctoSense-org/OctoSense/blob/main/crates/oauth-service/README.zh-CN.md#应用接口)。

4. 让用户批准每一次写入。`github.review_save` 和 `gcalendar.review_save` 会冻结改动并显示在宿主面板上，由用户在那里批准。在 desktop-v0.1.0-beta.2 上，这个面板不检查是否为亲手点按；桌面 RC1 及之后版本要求在原生 **Approve & Save** 控件上亲手点按；Windows/Linux 的受保护写操作仍不支持，会拒绝执行。`gmail.draft.review` 打开宿主的审阅界面，在所有版本上，用户都要在上面亲手点按才能发送：脚本、Agent 和远程点击都无法发送邮件。

三个[连接账户的参考应用](../examples/connected-apps/README.zh-CN.md)已在 App Hub 签名目录中发布，用的正是这套做法。App Hub 的[提交指南](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/SUBMITTING.zh-CN.md#三个参考应用)概述了这三个应用。

### 登录应用自己的后端

从[桌面 RC1](../README.zh-CN.md#下载兼容-shell) 起，宿主可以在已记录的平台限制内让用户登录应用自己的后端，并调用后端已声明的操作。历史 `desktop-v0.1.0-beta.2` 的发布早于这项功能。

1. 声明 `auth` 和 `storage.accounts: true`，并用以下两种方式之一注册后端：
   - 在清单的 `backend` 块中声明后端，并在 `requires` 中加入 `backend-api-v1`，写法见 [HOST-API-V1 §4](HOST-API-V1.zh-CN.md#4-连接应用自己的后端)。宿主从已准入的签名应用包中读取这项声明。
   - 请宿主的运维人员在 `<apps root>/.host/oauth/backends.json` 中注册。只有应用包没有声明 `backend` 时，宿主才读取这个文件。
2. 用 `backend` 提供商及其唯一的权限连接：

   ```splash
   host.request("auth.connect", {provider: "backend" scopes: ["app.session"]}, fn(r){
       if !r.is_ok { ui.status.set_text(r.error) }
   })
   ```

   在 macOS 和 Android 9 及更高版本上，宿主在自己的 WebView 中打开后端的登录页，用户在那里注册或登录；应用无法打开或读取这个页面。在 macOS 上，`presentation: "browser"` 会改用系统浏览器；在 Windows 和 Linux 上，只支持浏览器方式；RC2 补上原生链接打开方式后它才可用：用 RC2 源码构建的 Windows 测试程序对模拟后端完成了登录，Linux 上尚未测试。
3. 用 `{connection: <handle>}` 调用 `auth.backend.me`。它返回 `{connection, backend_id, identity: {sub, label}}`，即后端验证过的身份。
4. 用 `auth.backend.request` 调用已声明的操作（[HOST-API-V1 §4](HOST-API-V1.zh-CN.md#4-连接应用自己的后端)）。写操作要等用户在宿主面板上亲手点按批准后才会执行。

没有注册时，`auth.connect` 会返回 `This app's backend sign-in is unavailable. Contact the app's distributor.` 这句话。后端必须在同一个 HTTPS 源上提供使用 S256 PKCE 的 OAuth 授权码流程和 `/me` 端点。详情见 OctoSense 的[开发者后端契约](https://github.com/OctoSense-org/OctoSense/blob/main/crates/oauth-service/README.zh-CN.md#开发者后端接口约定)。iOS 不支持后端登录。Windows/Linux 使用外部浏览器；嵌入式登录和受保护的写操作仍不支持。合成后端检查不代表真实提供商登录通过验证。

### 限制

- **版本。** 当前带 GitHub 证明的应用使用[桌面 RC2](../README.zh-CN.md#下载兼容-shell)，RC1 也能安装它们。历史 OctoSense desktop-v0.1.0-beta.2（macOS，Apple 芯片）提供 `auth`、`github`、`gcalendar` 和 `gmail`。beta.1 的商店（desktop-v0.1.0-beta.1 和 home-v0.1.0-beta.1）会列出这类应用，但拒绝安装，因为它们的契约不认识 `auth`。目前没有任何已发布的手机版本能安装这类应用。
- **提供商注册信息。** 公开的 RC 包（RC1、RC2）不附带 Google/GitHub 注册信息，需要宿主发行方或运维人员提供。beta.2 只从 `<apps root>/.host/oauth/clients.json` 读取 GitHub 和 Google 的注册信息，而它的下载包中没有任何注册信息，所以运行 beta.2 的人要自己提供这个文件。自行构建 RC 时，可以改为把分发者的注册信息编译进去；此时 `clients.json` 是可选的运维人员覆盖配置，会替换编译进去的全部注册信息（[OctoSense：配置发布版本](https://github.com/OctoSense-org/OctoSense/blob/main/crates/oauth-service/README.zh-CN.md#配置发行版本维护者)、[运维人员高级覆盖配置](https://github.com/OctoSense-org/OctoSense/blob/main/crates/oauth-service/README.zh-CN.md#高级运维覆盖配置)）。
- **日历同步。** 在 desktop-v0.1.0-beta.2 上，`gcalendar.refresh` 同步整个日历，并从最早的日程开始返回；`gcalendar.sync` 返回 Google 的原始日程分页。OctoSense 桌面 RC1 及之后版本只同步从今天之前 30 天到之后 366 天的日程，并展开重复日程，还会以 `window: {time_min, time_max}` 返回这个范围。它会拒绝 `gcalendar.sync`，并返回 `Use gcalendar.refresh for the bounded agenda; raw history synchronization is not exposed`。
- **未验证**：真实 GitHub 和 Google 服务上的大部分实际使用，包括写入仓库和发送 Gmail。OctoSense `main` 记录了两次 macOS 上的检查：一是通过原生宿主、仅验证身份的 GitHub 和 Google 登录（Google 用的是测试账户）；二是一次手动的 Google Calendar 会话，列出了日历并保存了一个日程（[当前交付边界](https://github.com/OctoSense-org/OctoSense/blob/main/crates/oauth-service/README.zh-CN.md#当前交付边界)）。
- **尚不支持**：在 Android 上登录 Google。`auth.connect` 返回 `Google authorization needs the Android host adapter; desktop login is not supported on this device`。
- **后端平台限制**：RC1 和 RC2 支持[上文](#登录应用自己的后端)的宿主登录流程；Windows/Linux 的嵌入式登录和受保护的写操作仍不可用，RC2 使之可达的 Windows/Linux 浏览器登录也只由一个 Windows 测试程序验证过。

## 精确服务名

除了 27 个大类能力，`KNOWN_CAPABILITIES` 还有 78 个精确服务名。每个名称都是一项单独的授权；前缀不授予任何能力。

| 名称 | 授予什么 | 由谁提供 |
| --- | --- | --- |
| `octos.session.open`、`octos.session.history`、`octos.turn.start`、`octos.turn.interrupt` | 应用与设备助手的专属对话。见 [AI-SERVICES](AI-SERVICES.zh-CN.md#助手相关能力)。 | 运行 octos 内核的 OctoSense Shell，前提是用户已允许该应用的 Agent。在此之前，调用会返回 `Waiting for the person to allow this app's agent (OctoSense asks the first time)`。Matrix 客户端 Rinx 也向以迷你应用形式导入其中的应用包提供这些服务。 |
| `matrix.*`（45 个名称，例如 `matrix.read_messages`） | 每个名称对应用户 Matrix 账户上的一项操作。 | 任何 OctoSense Shell 都不提供。只有 Rinx 应用通过自己的宿主，向用户导入其中的迷你应用提供 `matrix.*`；这不属于 App Hub 的安装途径。 |
| `palpo.*`（29 个名称，例如 `palpo.inbox.list`） | 每个名称对应一项操作，在 Matrix 服务器 Palpo 上针对用户的账户执行。 | 没有任何 OctoSense Shell 提供。不要申请。 |

## 存储、计算与 Agent 上限

| 字段 | 含义 | 上限：商店应用 / 系统应用 |
| --- | --- | --- |
| `storage.max_bytes` | 整个 jail 的配额 | 16 MiB / 64 MiB |
| `storage.accounts` | `true`：每个账户各有自己的数据和一个 Agent。默认：一个 `device` 文件夹 | – |
| `storage.agent_workspace` | `"account"`（默认）：Agent 读取所属账户的文件夹。`"none"`：没有文件 | – |
| `storage.cache_max_bytes` | jail 中 `cache/` 的上限 | – |
| `compute.instruction_budget` | 每个会话累计执行的脚本指令数 | 20,000,000 / 4,000,000,000 |
| `compute.memory_bytes` | 隔离环境的堆内存 | 64 MiB / 128 MiB |
| `agent.max_iterations`、`agent.token_budget` | 应用 Agent 每次请求可用的模型轮数和 token 数 | 8 轮和 200,000 个 token / 相同 |
| `research`（顶层） | `research` 和 `crawl` 的范围；申请其中任一项时必填 | – |

值超过上限时，准入检查会把它降到上限，而不是拒绝；未填写的值直接取上限。`hub check` 的 `grants:` 行显示最终结果。申请 100 MiB 存储的清单会得到：

```text
grants: capabilities {"storage"}, hosts {}, storage 16777216 bytes, agent none
```

`agent` 块的其余部分（`profile`、工具、模型需求、触发器、`AGENT.md` 和技能）见 [AI-SERVICES § 清单中的 `agent`](AI-SERVICES.zh-CN.md#清单中的-agent)。

## 应用不能使用的名称

- **ID 末段的保留名称。** 应用 ID 的最后一段会成为它的工具命名空间，因此有 23 个保留名称（App Hub `crates/app-contract/src/manifest.rs` 中的 `RESERVED_NAMES`），其中包括 `notes`、`weather` 和 `terminal`：

  ```text
  [refused] identity: app id "dev.example.notes" ends in "notes", which is reserved: its tools would be notes.*, a native app's or the host's
  ```

- **`os.*` ID** 属于设备自带的系统应用。准入检查会拒绝这类 ID（`[refused] identity: os.mything is under os., which is reserved for system apps that ship with the device`），任何商店也不会安装这类应用。开发时可以用 `card-host --system` 运行。
- **`profile` 和 `agent`** 是运行时检查，不是能力。没有 `profile` 时，依赖它的 `sys.*` 辅助函数读出的都是空值；没有 `agent` 时，运行时会拒绝 `agent.notify`。这两个名称都不在列表中，所以任何商店应用都不会拥有它们。

## 新增能力

新增能力是对 App Hub 的修改：`KNOWN_CAPABILITIES` 中的名称、它在权限说明和隐私概要中的文字，以及执行它的服务或运行时代码，要一起评审。应用不能自创能力。新增宿主服务见 [HOST-SERVICES § 新增宿主服务](HOST-SERVICES.zh-CN.md#新增宿主服务)。
