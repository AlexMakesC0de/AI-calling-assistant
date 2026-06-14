import { NextResponse, type NextRequest } from "next/server";
import { getSession } from "@/lib/auth";
import { env } from "@/lib/env";
import { fetchUserEmail, saveTokens } from "@/lib/outlook-oauth";

export async function POST(request: NextRequest) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = (await request.json()) as { deviceCode: string };
  if (!body.deviceCode) {
    return NextResponse.json({ error: "Missing deviceCode" }, { status: 400 });
  }

  const res = await fetch(
    "https://login.microsoftonline.com/common/oauth2/v2.0/token",
    {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        client_id: env.outlook.clientId,
        grant_type: "urn:ietf:params:oauth:grant-type:device_code",
        device_code: body.deviceCode,
      }),
      cache: "no-store",
    },
  );

  const data = (await res.json()) as {
    access_token?: string;
    refresh_token?: string;
    expires_in?: number;
    error?: string;
    error_description?: string;
  };

  if (data.error === "authorization_pending") {
    return NextResponse.json({ status: "pending" });
  }

  if (data.error === "slow_down") {
    return NextResponse.json({ status: "slow_down" });
  }

  if (data.error) {
    return NextResponse.json(
      { status: "error", error: data.error_description ?? data.error },
      { status: 400 },
    );
  }

  if (!data.access_token || !data.refresh_token || !data.expires_in) {
    return NextResponse.json(
      { status: "error", error: "Incomplete token response" },
      { status: 502 },
    );
  }

  try {
    const email = await fetchUserEmail(data.access_token);
    await saveTokens(session.accountId, {
      access_token: data.access_token,
      refresh_token: data.refresh_token,
      expires_in: data.expires_in,
    }, email);
    return NextResponse.json({ status: "success", email });
  } catch (err) {
    return NextResponse.json(
      { status: "error", error: err instanceof Error ? err.message : "Failed to save tokens" },
      { status: 500 },
    );
  }
}
