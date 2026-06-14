import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { deleteTokens } from "@/lib/outlook-oauth";

export async function POST() {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  await deleteTokens(session.accountId);
  return NextResponse.json({ ok: true });
}
