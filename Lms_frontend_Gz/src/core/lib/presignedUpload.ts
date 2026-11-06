/** Uploads straight to object storage via a presigned POST (`{url, fields}`) so file bytes never pass through our API. */
export async function uploadToPresignedPost(target: { url: string; fields: Record<string, string> }, file: Blob, filename: string): Promise<void> {
  const formData = new FormData();
  Object.entries(target.fields).forEach(([field, value]) => formData.append(field, value));
  formData.append("file", file, filename);
  const response = await fetch(target.url, { method: "POST", body: formData });
  if (!response.ok) throw new Error("Upload failed");
}
