const { PrismaClient } = require("@prisma/client");
const p = new PrismaClient();

async function main() {
  const mediaCount = await p.whatsAppMedia.count();
  console.log("Total media records:", mediaCount);

  const msgs = await p.whatsAppMessage.findMany({
    where: { conversationId: 2 },
    select: { id: true, messageType: true, direction: true, body: true },
    take: 5,
    orderBy: { createdAt: "desc" },
  });
  console.log("Messages in conv 2:", JSON.stringify(msgs, null, 2));

  const media = await p.whatsAppMedia.findMany({
    where: { message: { conversationId: 2 } },
    select: { id: true, messageId: true, contentType: true, twilioUrl: true, localPath: true },
  });
  console.log("Media in conv 2:", JSON.stringify(media, null, 2));

  await p.$disconnect();
}

main().catch(console.error);
