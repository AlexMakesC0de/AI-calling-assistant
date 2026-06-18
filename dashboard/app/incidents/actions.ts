"use server";

import { revalidatePath } from "next/cache";
import { getSession } from "@/lib/auth";
import { prisma } from "@/lib/prisma";

export async function updateIncidentStatusAction(
  ids: number[],
  status: string,
): Promise<{ ok: boolean; error?: string }> {
  const session = await getSession();
  if (!session) return { ok: false, error: "Not authenticated." };
  if (ids.length === 0) return { ok: false, error: "No incidents selected." };

  await prisma.incidentForm.updateMany({
    where: { id: { in: ids } },
    data: { status },
  });

  revalidatePath("/incidents");
  return { ok: true };
}
