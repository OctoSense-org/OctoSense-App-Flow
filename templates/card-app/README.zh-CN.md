# 卡片应用模板（指引）

[English](README.md) | 简体中文

未注明中文版的链接指向英文文档。

**卡片应用**是用 L0（声明式卡片语言）编写的 `page.card`，加上它的 `page.data.json` 和 `kit/`，由宿主转换为控件。它是生成出来的，不是手写的：使用 [image-to-card 流程](../../flows/image-to-card/FLOW.md)（或者用 [Sketch 套件流程](../../flows/kits/sketch/FLOW.md)生成套件），然后按 [flows/README.zh-CN.md](../../flows/README.zh-CN.md#每个流程都遵循同一份约定) 中的统一交接步骤完成；应用包中放的是 `page.card` 和 `kit/`，而不是 `main.splash`。

App Hub 的 [`templates/app/`](https://github.com/OctoSense-org/OctoSense-App-Hub/tree/main/templates/app) 是卡片应用包的元数据脚手架：清单、商店信息、图标和 Agent 说明。它没有入口文件（`page.card`），也没有截图，即使先运行 `hub stamp`，准入检查仍会报 `entry` 和 `listing` 两项拒绝。请加入流程生成的 `page.card`、`kit/` 和一张真实截图，并把占位的 `platforms` 换成你测试过的平台。按照 App Hub 的 [OctoSense 图标格式](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/ICONS.zh-CN.md#设计与导出建议)，用自己的身份替换模板图标：64 点正方形、中央 66% 前景、克制的插画物件，不预置平台圆角或外部阴影。从卡片提取的界面素材不能替代这一步图标创作。

要使用自己的字体，把 `.ttf` 或 `.otf` 文件放进应用包，并在 `font_src` 中用相对于应用包的路径引用它，例如 `"font_src": "assets/Body.ttf"`。打包的字体计入 8 MiB 上限，所以较大的中日韩字体请只打包所需的子集。字体中没有的字形（例如中文）会改用 Makepad 内置的中文字体霞鹜文楷（LXGW WenKai）。套件可以引用的内置字体只有 `makepad_widgets:resources/Inter.ttf`、`makepad_widgets:resources/LXGWWenKaiRegular.ttf` 和 `makepad_widgets:resources/LXGWWenKaiBold.ttf`（[App Hub PUBLISHING § 字体](https://github.com/OctoSense-org/OctoSense-App-Hub/blob/main/docs/PUBLISHING.zh-CN.md#字体)）。请用 `MAKEPAD_SYSTEM_FONTS=0` 检查文字，这样系统字体就掩盖不了缺失的字形。

`desktop-v0.1.0-beta.2` 早于这项字体加载功能：它会安装带打包字体的应用，但卡片不会加载这些字体。要在这个版本上显示中文，请用纯 L0 角色套件（`Surface`、`TextTitle`、`TextBody` 等）组合卡片，并且不设 `font_src`；中文由霞鹜文楷显示。在 OctoSense 桌面版 0.1.0-rc.1 中，字体能否加载尚未验证。

如果应用有自己的逻辑、状态和请求，请改用[脚本应用模板](../script-app/README.zh-CN.md)。
