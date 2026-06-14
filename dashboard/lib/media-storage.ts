import { mkdir, writeFile, stat } from "fs/promises";
import { createReadStream } from "fs";
import { join } from "path";
import { Readable } from "stream";
import { NextResponse } from "next/server";

export function sanitizeFilename(name: string): string {
  return name.replace(/[^a-zA-Z0-9._-]/g, "_").slice(0, 200);
}

const EXT_MAP: Record<string, string> = {
  "image/jpeg": ".jpg",
  "image/png": ".png",
  "image/gif": ".gif",
  "image/webp": ".webp",
  "image/svg+xml": ".svg",
  "audio/ogg": ".ogg",
  "audio/mpeg": ".mp3",
  "audio/mp4": ".m4a",
  "audio/wav": ".wav",
  "audio/webm": ".webm",
  "video/mp4": ".mp4",
  "video/webm": ".webm",
  "video/quicktime": ".mov",
  "video/3gpp": ".3gp",
  "application/pdf": ".pdf",
  "application/msword": ".doc",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
  "application/vnd.ms-excel": ".xls",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
  "text/plain": ".txt",
  "text/csv": ".csv",
};

export function guessExtension(contentType: string): string {
  const ct = contentType.split(";")[0].trim().toLowerCase();
  return EXT_MAP[ct] ?? "";
}

export async function downloadAndStore(opts: {
  dir: string;
  filename: string;
  fetchFn: () => Promise<Response>;
}): Promise<{ localPath: string; fileSizeBytes: number }> {
  await mkdir(opts.dir, { recursive: true });
  const localPath = join(opts.dir, opts.filename);

  const res = await opts.fetchFn();
  if (!res.ok) throw new Error(`Download failed: ${res.status}`);

  const buffer = Buffer.from(await res.arrayBuffer());
  await writeFile(localPath, buffer);

  return { localPath, fileSizeBytes: buffer.length };
}

export async function serveFromDisk(
  localPath: string,
  contentType: string,
): Promise<NextResponse | null> {
  try {
    const info = await stat(localPath);
    if (!info.isFile()) return null;
  } catch {
    return null;
  }

  const stream = createReadStream(localPath);
  const webStream = Readable.toWeb(stream) as ReadableStream;
  return new NextResponse(webStream, {
    headers: {
      "Content-Type": contentType,
      "Cache-Control": "private, max-age=3600",
    },
  });
}

export async function fileExists(path: string): Promise<boolean> {
  try {
    const info = await stat(path);
    return info.isFile();
  } catch {
    return false;
  }
}
