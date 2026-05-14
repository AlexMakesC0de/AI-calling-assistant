import { env } from "./env";
import { prisma } from "./prisma";

export type ServiceStatus = "healthy" | "unhealthy" | "unknown";

export type ServiceCheck = {
  key: string;
  name: string;
  status: ServiceStatus;
  latencyMs: number | null;
  detail: string | null;
};

const TIMEOUT_MS = 3000;

async function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`Timed out after ${ms}ms`)), ms);
    promise.then(
      (v) => {
        clearTimeout(timer);
        resolve(v);
      },
      (err) => {
        clearTimeout(timer);
        reject(err);
      }
    );
  });
}

async function pingHttp(url: string): Promise<{ ok: boolean; detail: string | null }> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(url, { cache: "no-store", signal: controller.signal });
    if (!response.ok) return { ok: false, detail: `HTTP ${response.status}` };
    return { ok: true, detail: null };
  } catch (err) {
    return { ok: false, detail: err instanceof Error ? err.message : String(err) };
  } finally {
    clearTimeout(timer);
  }
}

async function pingDatabase(): Promise<{ ok: boolean; detail: string | null }> {
  try {
    await withTimeout(prisma.$queryRaw`SELECT 1`, TIMEOUT_MS);
    return { ok: true, detail: null };
  } catch (err) {
    return { ok: false, detail: err instanceof Error ? err.message : String(err) };
  }
}

async function check(key: string, name: string, runner: () => Promise<{ ok: boolean; detail: string | null }>): Promise<ServiceCheck> {
  const start = Date.now();
  const result = await runner();
  const latencyMs = Date.now() - start;
  return {
    key,
    name,
    status: result.ok ? "healthy" : "unhealthy",
    latencyMs,
    detail: result.detail,
  };
}

export async function runHealthChecks(): Promise<ServiceCheck[]> {
  const checks: Array<Promise<ServiceCheck>> = [
    check("database", "PostgreSQL", () => pingDatabase()),
    check("voice-app", "Voice app", () => pingHttp(env.serviceHealth.voiceApp)),
    check("transcriber", "Transcriber (Whisper)", () => pingHttp(env.serviceHealth.transcriber)),
    check("formatter", "Transcript formatter", () => pingHttp(env.serviceHealth.formatter)),
    check("email", "Email sender (SMTP)", () => pingHttp(env.serviceHealth.email)),
    check("mailpit", "Mailpit", () => pingHttp(env.serviceHealth.mailpit)),
    check("telephony", "Telephony ingest", () => pingHttp(env.serviceHealth.telephony)),
    check("ollama", "Ollama", () => pingHttp(env.serviceHealth.ollama)),
  ];
  return Promise.all(checks);
}
