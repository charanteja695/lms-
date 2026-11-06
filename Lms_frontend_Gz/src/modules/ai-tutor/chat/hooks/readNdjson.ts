/** Reads an `application/x-ndjson` body, calling `onEvent` once per JSON line as it arrives. */
export async function readNdjson(body: ReadableStream<Uint8Array>, onEvent: (event: Record<string, unknown>) => void): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const lines = buffer.split("\n");
    buffer = done ? "" : (lines.pop() ?? "");
    for (const line of lines) {
      if (line.trim()) onEvent(JSON.parse(line) as Record<string, unknown>);
    }
    if (done) return;
  }
}
