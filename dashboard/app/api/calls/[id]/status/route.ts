import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const call = await prisma.twilioCall.findUnique({
    where: { id: Number(id) },
    select: {
      status: true,
      transcriptText: true,
      incidentFormId: true,
      errorMessage: true,
    },
  });

  if (!call) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }

  return NextResponse.json({
    status: call.status,
    hasTranscript: Boolean(call.transcriptText),
    incidentFormId: call.incidentFormId,
    errorMessage: call.errorMessage,
  });
}
