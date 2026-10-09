import { describe, it, expect } from "vitest";
import { FakeHarnessAdapter } from "@codexhost/harness-adapter/testing";
import { encodeExternalTransportSelection } from "@codexhost/protocol-core";
import { harnessIdSchema } from "@codexhost/shared-contracts";
import {
  createFixture,
  startExternalThread,
  writeRequest,
  requestId,
  closeFixture,
} from "./app-server-host-fixture.js";

describe("Pi side conversation context", () => {
  it("injects the boundary into the external native session before acknowledging", async () => {
    const adapter = new FakeHarnessAdapter(harnessIdSchema.parse("pi"));
    const fixture = createFixture({ externalAdapters: new Map([["pi", adapter]]) });
    try {
      const threadId = await startExternalThread(
        fixture,
        encodeExternalTransportSelection("pi", { model: adapter.catalog.defaultModel! }),
      );
      const received: unknown[] = [];
      Object.assign(adapter.sessions[0]!, {
        injectContext: async (items: unknown) => {
          received.push(items);
          return { ok: true, value: undefined };
        },
      });
      const items = [
        {
          type: "message",
          role: "user",
          content: [{ type: "input_text", text: "Inherited history is reference only." }],
        },
      ];
      writeRequest(fixture.desktopInput, {
        id: 22,
        method: "thread/inject_items",
        params: { threadId, items },
      });
      const response = await fixture.collector.waitFor((m) => requestId(m, 22));
      expect(response.error).toBeUndefined();
      expect(received).toEqual([[{ role: "user", text: "Inherited history is reference only." }]]);
      writeRequest(fixture.desktopInput, {
        id: 23,
        method: "thread/inject_items",
        params: {
          threadId,
          items: [
            {
              type: "message",
              role: "user",
              content: [{ type: "input_image", image_url: "not-text" }],
            },
          ],
        },
      });
      const invalid = await fixture.collector.waitFor((m) => requestId(m, 23));
      expect(invalid.error).toMatchObject({ code: -32602 });
      expect(received).toHaveLength(1);
      Object.assign(adapter.sessions[0]!, {
        injectContext: async () => ({
          ok: false,
          error: { code: "sessionBusy", message: "busy", retryable: true },
        }),
      });
      writeRequest(fixture.desktopInput, {
        id: 24,
        method: "thread/inject_items",
        params: { threadId, items },
      });
      const busy = await fixture.collector.waitFor((m) => requestId(m, 24));
      expect(busy.error).toMatchObject({ code: -32072, message: "busy" });
    } finally {
      await closeFixture(fixture);
    }
  });
});
