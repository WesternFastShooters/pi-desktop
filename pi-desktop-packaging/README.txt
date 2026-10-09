Pi Desktop — macOS arm64 个人自用原型

当前目标
打开后无需 OpenAI 登录；新会话只使用 Pi。
优先连接本机已安装的 Pi，复用 ~/.pi/agent 中的设置、凭证、扩展和会话。
没有本机 Pi 时使用包内 Pi；包内也包含 Node。
本次提供的临时 API key 已停止使用，不在源码或安装包中。

隔离边界
本机 Pi 数据共享，属于用户最新明确要求。
Host、Codex 外壳后端、Electron 数据仍分别隔离到：
~/Library/Application Support/Pi Desktop/host
~/Library/Application Support/Pi Desktop/codex
~/Library/Application Support/Pi Desktop/electron
诊断：~/Library/Application Support/Pi Desktop/launcher.log
不修改、启动或退出 /Applications/ChatGPT.app。
封装输入仅来自单独官方下载后只读挂载的安装包。

免登录入口
首次启动创建不需要 OpenAI 身份验证的外壳后端配置。
原生 Codex 推理未启用；Pi 的模型凭证由本机 Pi 自己管理。
没有 Pi 凭证也可以进入应用；发送消息时才由 Pi 显示实际配置错误。
首次使用可能出现官方外壳的欢迎引导；这不是登录。
外壳内部窗口可能仍显示 ChatGPT 名称。

已验证
6 项 Python 行为测试；4 项 Rust 隔离/命令入口测试；38 项界面代理控制器与 Host 路由测试；124项Pi接口与侧边上下文测试。
TypeScript、Renderer、Rust release 构建及依赖边界检查。
App 深度严格签名；内置 Node 环境下 Pi 1.1.0；独立 Bundle 路径发现。
实际签名过滤了厂商身份、受限服务、官方应用组和共享 Keychain 组。
UI app.asar 与官方下载包完全一致，没有修改。
最终启动、会话和 DMG 验收结论见交付目录中的验收报告。

重新构建
固定上游：https://github.com/BytePioneer-AI/codex-host.git
commit：08c7d65dddb03a79d5b311d47a0381c299316a3b
需要 macOS、Xcode Command Line Tools、Git、Node 24/npm、Python 3、Rust。
输入为独立官方应用副本和完整 pi-runtime（含锁定的 pi-computer-use@0.5.1、pi-chrome-use@1.1.1）；pi-runtime package.json/package-lock.json 随源码交付。完整 pi-runtime（可执行 bin/pi；链接不能指向目录外）。
运行：bash build.sh /path/to/official.app /path/to/pi-runtime /path/to/new-output
输出目录必须不存在。构建保留所有源码与补丁，并执行隔离测试。

修复原源码包
重新生成可应用于固定上游的补丁。
修复 macOS --custom-install 命令入口。
在首次加载打包程序前生成共享 TypeScript 合约。
inspect JSON 有 desktopError 或没有 desktop 时明确停止。
Ad-hoc 签名只保留普通安全权限，避免受限权限造成系统拒绝启动。
按最新要求复用本机 Pi，并移除 OpenAI 登录门槛。
界面代理控制器支持 Pi-only；两个代理菜单均不列 Codex，不能切回 Codex。
Host 强制新会话使用 Pi，并拒绝原生 Codex 创建、生成和 fork 转发。

限制
Ad-hoc 签名，未 Apple 公证；首次 Gatekeeper 行为尚未全项验收。
不能通过退出、移除或修改原 ChatGPT 来验证共存；用户明确禁止操作原应用。
官方外壳的 OAuth、通知、Keychain、内置更新和干净系统安装需要另行验证。
只有完整 SPEC 验收通过后才能宣称独立产品全部可用。
仅供个人实验，不扩展官方软件再分发授权。
CodexHost 为 LGPL-3.0-only；修改源码与许可证随交付保留。

新增侧边聊天与控制工具
侧边历史由原生Pi fork继承；边界说明由thread/inject_items真正写入原生Pi历史。
browser_execute按会话开启私有Chrome；需要本机Google Chrome。
电脑工具优先复用本机扩展与helper，缺少时使用包内Pi Computer Use.app；首次使用需要macOS辅助功能、屏幕录制授权。
普通聊天不会因缺少这两项系统授权而阻塞。实际控制验收状态见验收报告。
依赖许可证：pi-chrome-use和pi-computer-use均为MIT，原许可证保留于runtime包内。

本机已有电脑扩展时复用原扩展与helper；本机缺少时使用包内后备。两个路径均有启动去重测试。
