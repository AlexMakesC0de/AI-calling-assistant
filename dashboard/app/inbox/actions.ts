"use server";

import { revalidatePath } from "next/cache";
import {
  deleteMailpitMessages,
  setMailpitRead,
  setMailpitTags,
} from "@/lib/mailpit";

export type ActionResult = { ok: true } | { ok: false; error: string };

function toError(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

export async function markRead(ids: string[], read: boolean): Promise<ActionResult> {
  if (ids.length === 0) return { ok: true };
  try {
    await setMailpitRead(ids, read);
    revalidatePath("/inbox");
    revalidatePath("/");
    return { ok: true };
  } catch (err) {
    return { ok: false, error: toError(err) };
  }
}

export async function deleteMessages(ids: string[]): Promise<ActionResult> {
  if (ids.length === 0) return { ok: true };
  try {
    await deleteMailpitMessages(ids);
    revalidatePath("/inbox");
    revalidatePath("/");
    return { ok: true };
  } catch (err) {
    return { ok: false, error: toError(err) };
  }
}

export async function updateTags(ids: string[], tags: string[]): Promise<ActionResult> {
  if (ids.length === 0) return { ok: true };
  try {
    await setMailpitTags(ids, tags);
    revalidatePath("/inbox");
    return { ok: true };
  } catch (err) {
    return { ok: false, error: toError(err) };
  }
}
