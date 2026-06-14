import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { deleteGmailTokens } from "@/lib/gmail-oauth";

export async function POST() {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  await deleteGmailTokens(session.accountId);
  return NextResponse.json({ ok: true });
}
