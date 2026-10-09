import browserExtension from "../pi-runtime/node_modules/pi-chrome-use/extensions/browser-execute.ts";
import { spawn } from "node:child_process";
import { createServer } from "node:net";
import { mkdtemp, rm, access } from "node:fs/promises";
import path from "node:path";
import os from "node:os";

/** Private Chrome profile per Pi session. No existing browser is restarted. */
export default function(pi: any) {
  pi.on("before_agent_start", async (event: any) => ({
    systemPrompt: event.systemPrompt + "\nPi Desktop: Never inspect, operate, launch, quit, or modify /Applications/ChatGPT.app. For desktop control, first find the requested app using find_roots with an exact app or bundleId filter; observe only the returned root. Compact outlines hide children: use expand_ui({ref, stateId, depth:4}) or search_ui({role: 'button', stateId}) before act_ui. Never guess @e refs. Never use an unscoped observe_ui fallback that could capture another app. Browser control uses browser_execute in its private Chrome window.",
  }));
  pi.registerCommand("pi-desktop-tools", {
    description: "查看 Pi Desktop 电脑和浏览器工具",
    handler: async (_args: string, ctx: any) => ctx.ui.notify(JSON.stringify(pi.getAllTools().map((t: any) => t.name)), "info"),
  });
  let child: ReturnType<typeof spawn> | undefined;
  let profile: string | undefined;
  let starting: Promise<void> | undefined;
  async function start() {
    if (child && child.exitCode === null && process.env.BU_CDP_WS) return;
    if (starting) return starting;
    starting = (async () => {
      const executable = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
      await access(executable).catch(() => { throw new Error("请安装 Google Chrome 后使用浏览器控制。"); });
      const server = createServer();
      await new Promise<void>((resolve, reject) => { server.once("error", reject); server.listen(0, "127.0.0.1", resolve); });
      const address = server.address();
      if (!address || typeof address === "string") throw new Error("Browser port unavailable");
      const port = address.port;
      await new Promise<void>((resolve, reject) => server.close(e => e ? reject(e) : resolve()));
      profile = await mkdtemp(path.join(os.tmpdir(), "pi-desktop-browser-"));
      child = spawn(executable, [`--remote-debugging-address=127.0.0.1`, `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, "--no-first-run", "--no-default-browser-check", "about:blank"], { stdio: "ignore" });
      let spawnError: Error | undefined;
      child.once("error", error => { spawnError = error; });
      const deadline = Date.now() + 20_000;
      while (Date.now() < deadline) {
        if (spawnError) throw spawnError;
        if (child.exitCode !== null) throw new Error("Pi browser exited during startup");
        try {
          const response = await fetch(`http://127.0.0.1:${port}/json/version`, { signal: AbortSignal.timeout(1000) });
          const version = await response.json() as { webSocketDebuggerUrl?: string };
          if (version.webSocketDebuggerUrl) { process.env.BU_CDP_WS = version.webSocketDebuggerUrl; return; }
        } catch {}
        await new Promise(r => setTimeout(r, 100));
      }
      throw new Error("Pi browser startup timed out");
    })();
    try { await starting; } finally { starting = undefined; }
  }
  browserExtension(new Proxy(pi, { get(target, key) {
    if (key !== "registerTool") return Reflect.get(target, key);
    return (tool: any) => target.registerTool({ ...tool,
      description: tool.description + "\nPi Desktop starts a private Chrome window automatically. Call await session.connect() first. API example: await session.connect(); const {targetId} = await session.Target.createTarget({url: 'about:blank'}); await session.use(targetId); await session.Page.navigate({url: 'https://example.com'}); const result = await session.Runtime.evaluate({expression: 'document.title', returnByValue: true}); console.log(result.result.value). Use session.Target, session.Page, session.Runtime domain methods; session.send does not exist. Never control the Pi app shell or /Applications/ChatGPT.app.",
      execute: async (...args: any[]) => { await start(); return tool.execute(...args); },
    });
  } }));
  pi.on("session_shutdown", async () => {
    child?.kill("SIGTERM");
    delete process.env.BU_CDP_WS;
    if (profile) await rm(profile, { recursive: true, force: true });
  });
}
