/**
 * Uploads straight to object storage through a presigned POST, reporting progress (0–100). `fetch` cannot report
 * upload progress, so this uses XMLHttpRequest. Abort with the returned `abort()`.
 */
export function uploadWithProgress(
  target: { url: string; fields: Record<string, string> },
  file: Blob,
  filename: string,
  onProgress: (percent: number) => void,
): { done: Promise<void>; abort: () => void } {
  const request = new XMLHttpRequest();
  const done = new Promise<void>((resolve, reject) => {
    const form = new FormData();
    Object.entries(target.fields).forEach(([field, value]) => form.append(field, value));
    form.append("file", file, filename);
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.min(99, Math.round((event.loaded / event.total) * 100)));
    };
    request.onload = () => (request.status >= 200 && request.status < 300 ? resolve() : reject(new Error("Upload failed")));
    request.onerror = () => reject(new Error("Upload failed. Check your connection."));
    request.onabort = () => reject(new DOMException("Upload cancelled", "AbortError"));
    request.open("POST", target.url);
    request.send(form);
  });
  return { done, abort: () => request.abort() };
}
