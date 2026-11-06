/**
 * The entire-screen share a strict proctored test needs. Held here (module scope) so the stream the pre-check got
 * survives the navigation to the exam player; a page reload loses it, and the player asks to share again.
 */
let current: MediaStream | null = null;

export const screenShare = {
  get(): MediaStream | null {
    return current && current.getVideoTracks().some((track) => track.readyState === "live") ? current : null;
  },
  stop(): void {
    current?.getTracks().forEach((track) => track.stop());
    current = null;
  },
  /** Asks the browser to share; resolves only for an entire screen (a window or a tab is refused, and stopped). */
  async request(): Promise<MediaStream> {
    if (!navigator.mediaDevices?.getDisplayMedia) throw new Error("This browser cannot share its screen. Use a desktop browser such as Chrome or Edge.");
    const stream = await navigator.mediaDevices.getDisplayMedia({ video: { displaySurface: "monitor" }, audio: false });
    const surface = stream.getVideoTracks()[0]?.getSettings().displaySurface;
    if (surface && surface !== "monitor") {
      stream.getTracks().forEach((track) => track.stop());
      throw new Error("Share your entire screen, not a window or a tab.");
    }
    screenShare.stop();
    current = stream;
    return stream;
  },
};

/** One JPEG frame of a live video stream (a screen share). */
export async function grabFrame(stream: MediaStream, maxWidth = 1280): Promise<Blob | null> {
  const video = document.createElement("video");
  video.muted = true;
  video.srcObject = stream;
  await video.play().catch(() => undefined);
  const scale = Math.min(1, maxWidth / (video.videoWidth || maxWidth));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round((video.videoWidth || maxWidth) * scale);
  canvas.height = Math.round((video.videoHeight || maxWidth * 0.5625) * scale);
  canvas.getContext("2d")?.drawImage(video, 0, 0, canvas.width, canvas.height);
  video.srcObject = null;
  return new Promise((resolve) => canvas.toBlob((blob) => resolve(blob), "image/jpeg", 0.7));
}
