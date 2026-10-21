# 脚本应用模板

[English](README.md) | 简体中文

未注明中文版的链接指向英文文档。

这个模板是一个可运行的 OctoSense 脚本应用：**My Notes**。输入一条笔记，应用把它存进自己的存储，点一下即可删除。`tools/octo new <dir> --platform macos` 会复制这个模板，设置 id 和名称，并把平台写入商店信息；`tools/octo run <dir>/bundle` 会运行它。

```text
script-app/
  README.md        英文说明（不复制）
  README.zh-CN.md  本文件（不复制）
  AGENTS.md        给新应用仓库中编码 Agent 的说明（复制）
  CLAUDE.md        为 Claude Code 导入 AGENTS.md（复制）
  GEMINI.md        为 Gemini CLI 导入 AGENTS.md（复制）
  .gitignore       不让密钥、构建产物和 .local-state 进入 Git（复制）
  .gitattributes   不让 Git 改写应用包的字节（复制）
  bundle/          应用本身，唯一提交的内容（复制）
    manifest.json  id my-notes，版本 0.1.0，能力 storage
    listing.json   商店信息：发布者字段和部分描述是占位内容
    main.splash    程序
    assets/icon.svg
```

## 演示内容

以下内容都能在 `card-host` 中运行：

- 用顶层 `let` 保存状态，由 `start_timeout(0.05, …)` 调度的函数加载；
- 在应用的 jail（私有数据目录）中使用 `fs.exists`、`fs.read` 和 `fs.write`，配合 `parse_json` 与 `to_json`；
- `ui.<id>.text()`、`set_text()` 和 `render()`；
- 带空状态的 `on_render` 列表、一个 `ButtonFlat{on_click}` 按钮，以及 `GestureView{on_tap}` 行。

空状态是 `for` 之前单独的一个 `if`。不要在 `on_render` 中写 `if … else for …`：测试中空分支什么都没画，屏幕上还残留着旧的行。

## 发布之前要补完的内容

模板有意留着不完整，以免有人误把复制出来的应用发布出去：

- `listing.json` 引用了 `screenshots/01-main.png`，但这个文件并不存在。在你用 `tools/octo shot` 截取真实截图之前，准入检查会拒绝这个应用包。不要放占位图片。
- 发布者名称、支持 URL 和隐私政策 URL 都是占位内容，描述的最后一句（“Replace this with …”）也是。`tools/octo check` 会提示它们；发布者字段由人来替换。
- `assets/icon.svg` 演示已批准的 OctoSense 家族格式。必须用应用自己的插画物件替换其身份：64 点正方形原稿、中央 66% 前景、克制的象牙白/墨色材质与点缀色，不预置平台圆角或外部阴影。检查 64/40/24 像素及平台外框；打包和评审规则由 App Hub 的 [ICONS.zh-CN.md](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/ICONS.zh-CN.md)规定。
- `platforms` 是空列表，准入检查会拒绝空列表（`listing names no platforms`）。`tools/octo new` 必须指定 `--platform`，并写入你传入的平台；每个平台写一次。传入平台只是声明，不是测试：发布之前，只保留你实际运行过的平台，并由人确认这一声明。在 Mac 上运行 `card-host` 测试的是 `macos`，不是 Android。
- 如果修改 id，它的最后一段不能是 App Hub 的保留名（`notes`、`weather`、`terminal` 等）。`tools/octo new` 创建应用时会拒绝保留名；之后改过的 id 若用了保留名，准入检查会拒绝。

## 发布完成的应用

`new` 还会从开发工具集中经过评审的 Release 工作流模板安装 `.github/workflows/publish-app.yml`；它位于 `bundle/` 之外，不是上面列出的模板源文件。已有应用可运行 `tools/octo publish-github <app-directory>`，命令不会推送或提交。

开 App Hub issue 来请求发布，附仓库/版本/commit、截图和权限。审阅并 commit 已测试源码和工作流，再推送新的 `v<manifest.version>` tag。GitHub 会准备、证明、验证和打包这个 Release；App Hub 只接受带 GitHub 证明的 Release，所以你不需要签名密钥。把成功的 Release 补充到 issue；发布到签名目录仍需管理员批准。在 App Hub 首次发布应用之前，每个新的 Release 都发在同一个 issue 中，并更新 issue 标题和 Version 字段；发布之后，每个新版本都开新 issue。日常更新使用同一仓库、所有者和工作流身份下的新版本/新 tag。

此路径需要 `publisher-github-v1` / 契约 1.8.0，以及兼容宿主：OctoSense 桌面版 0.1.0-rc.1 可以在 macOS 上安装带 GitHub 证明的应用。证据与限制见 [PUBLISHING](../../docs/PUBLISHING.zh-CN.md)。

下一步：[docs/QUICKSTART.zh-CN.md](../../docs/QUICKSTART.zh-CN.md)。
