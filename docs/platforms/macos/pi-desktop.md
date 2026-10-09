# Pi Desktop 个人封装

本分支是只运行 Pi 的 macOS 个人封装；不是上游完整 CodexHost 发行。

用户打开应用 → 无需 OpenAI 登录 → Pi 默认代理 → 本机 Pi RPC → 官方外壳显示结果。

- Launcher 优先使用本机 Pi，可回退到包内 Pi；复用 `~/.pi/agent`。
- Host、原生外壳后端及 Electron 配置在 `~/Library/Application Support/Pi Desktop` 下隔离。
- 原生后端以无需 OpenAI 身份的本地 provider 配置启动，仅用于外壳服务。
- Renderer 的启用代理只有 Pi；代理菜单和 `#` 菜单不列 Codex。
- DraftAgentController 不重新注入原生 Codex；Pi 模式不能切回 Codex。
- Host 将新会话分类限定到 Pi，拒绝原生创建、生成与 fork 请求。
- 官方 `app.asar` 原样保留；副本重新签名时去掉厂商受限权限及共享组。
- 不修改、启动或退出 `/Applications/ChatGPT.app`；仅使用独立下载的只读安装输入。

构建与验证见 [`pi-desktop-packaging/README.txt`](../../../pi-desktop-packaging/README.txt)。
测试覆盖 Pi-only 默认、禁止 Codex 切换、Host 新会话路由、独立数据目录、应用发现、签名权限与打包检查。
侧边聊天通过原生 Pi fork 继承历史。`thread/inject_items` 验证文本消息，经 Adapter 的可选 `injectContext` 能力调用 Pi 扩展命令。扩展写入隐藏的原生 custom 消息，不启动模型 Turn。Pi 历史保存边界说明，后续模型调用能读取。不能用成功空响应替代注入。

Pi 控制工具显式随启动加载，不安装进全局 `~/.pi/agent`：
- `pi-chrome-use@1.1.1` 提供 `browser_execute`。封装按会话启动私有 Chrome profile，关闭 Pi 会话时结束该 Chrome；不接管用户现有浏览器。需要已安装 Google Chrome。
- 优先复用本机已配置的 `@injaneity/pi-computer-use` 及其辅助应用和系统授权；缺少时显式加载包内版本。不会重复注册同名工具。包内 `@injaneity/pi-computer-use@0.5.1` 提供 `find_roots`、`observe_ui`、`act_ui` 等。包内独立签名辅助应用运行在 Pi 专用 socket；辅助功能和屏幕录制由 macOS 用户授权。RPC 启动时延迟权限检查，普通聊天不受影响。
- 两项 MIT 依赖保留原许可证；封装的两处适配仅延迟启动授权、允许包内 helper 自主管理 Pi 专用 socket。
- 官方 macOS native helper 修复已包含在固定上游，见 [PR164](https://github.com/BytePioneer-AI/codex-host/pull/164)。官方代理的工具启动兼容不等于 Pi 工具注册；本封装显式加载 Pi 扩展。

真实验收必须覆盖免登录、两个代理菜单仅 Pi、本机 Pi 回答与工具、取消、退出重开及最终 DMG。
不将构建、签名或菜单出现当成真实会话验收。
