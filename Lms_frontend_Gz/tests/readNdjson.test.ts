import { describe, expect, it } from "vitest";

import { readNdjson } from "./readNdjson";

function streamOf(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
      controller.close();
    },
  });
}

describe("readNdjson", () => {
  it("emits one event per line, even when a line is split across chunks", async () => {
    const events: Record<string, unknown>[] = [];
    await readNdjson(streamOf(['{"type":"start"}\n{"type":"del', 'ta","text":"Hel"}\n{"type":"delta","text":"lo"}\n', '{"type":"message"}']), (event) => events.push(event));
    expect(events.map((event) => event.type)).toEqual(["start", "delta", "delta", "message"]);
    expect(events.filter((event) => event.type === "delta").map((event) => event.text).join("")).toBe("Hello");
  });

  it("ignores blank lines", async () => {
    const events: Record<string, unknown>[] = [];
    await readNdjson(streamOf(['{"type":"start"}\n\n\n{"type":"message"}\n']), (event) => events.push(event));
    expect(events).toHaveLength(2);
  });
});
