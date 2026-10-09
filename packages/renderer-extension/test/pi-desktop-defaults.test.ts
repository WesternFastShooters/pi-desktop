import { expect, test, vi } from "vitest";
import { DraftAgentController } from "../src/agent-selection-state.js";
import { PI_DESKTOP_RENDERER_DEFAULTS } from "../src/install-renderer-binding.js";

test("Pi Desktop installs the real controller and starts new drafts on Pi", () => {
  const controller = new DraftAgentController(PI_DESKTOP_RENDERER_DEFAULTS);
  expect(controller.get({}).agent).toBe("pi");
  expect(PI_DESKTOP_RENDERER_DEFAULTS.enabledAgents).toEqual(["pi"]);
});

test("Pi-only controller cannot regain or switch to native Codex", async () => {
  const controller = new DraftAgentController({enabledAgents: ["pi"], defaultAgent: "pi"});
  const composer = {};
  controller.mount(composer, ["default"]);
  controller.setEnabledAgents(["pi"]);
  const operations = {applyAgent: vi.fn(() => true), clearPrewarm: vi.fn(async () => {})};
  expect(await controller.switchAgent(composer, "codex", operations)).toBe(false);
  expect(operations.applyAgent).not.toHaveBeenCalled();
  expect(controller.get(composer).agent).toBe("pi");
});
