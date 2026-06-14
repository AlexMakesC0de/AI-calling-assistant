import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

function daysAgo(n) {
  return new Date(Date.now() - n * 24 * 60 * 60 * 1000);
}

function hoursAgo(n) {
  return new Date(Date.now() - n * 60 * 60 * 1000);
}

const incidents = [
  {
    category: "Billing",
    priority: "High",
    callerName: "Sarah O'Brien",
    agentName: "Tom Reilly",
    audioFilename: "call_2026-06-01_sarah_obrien.wav",
    completedAt: daysAgo(1),
    sentiment: "Frustrated",
    summary: "Customer called about being double-charged on their June invoice for packaging compliance fees. Wants a refund and explanation of how it happened.",
    transcript: "Agent: Good morning, you're through to Repak support, my name is Tom. How can I help?\nCaller: Hi Tom, my name is Sarah O'Brien. I'm calling because I just got my June invoice and I've been charged twice for the same compliance fee.\nAgent: I'm sorry to hear that, Sarah. Can I get your account number?\nCaller: Sure, it's RPK-44291.\nAgent: Let me pull that up... I can see the duplicate charge. That looks like a system error on our end.\nCaller: This is really frustrating. I need this sorted quickly.\nAgent: Absolutely, I'll process the refund right now. You should see it within 3-5 business days.",
    formData: {
      form_id: "INC-2026-0601-001",
      caller_information: { name: "Sarah O'Brien", account_or_reference: "RPK-44291", contact_info: "sarah.obrien@greenpack.ie" },
      call_details: { date: "2026-06-01", agent_name: "Tom Reilly", duration_estimate: "4 minutes" },
      issue: { category: "Billing", priority: "High", description: "Double charge on June invoice for packaging compliance fees", error_messages: "Duplicate transaction ID TXN-88412" },
      resolution: { status: "Resolved", steps_taken: ["Verified duplicate charge on account RPK-44291", "Initiated refund for €245.00", "Flagged billing system for review"], outcome: "Refund processed, 3-5 business days" },
      follow_up: { required: true, actions: ["Confirm refund received by June 8", "Billing team to investigate root cause of duplicate"], department: "Billing" },
      customer_sentiment: "Frustrated",
      call_summary: "Customer double-charged on June invoice. Refund of €245 processed. Billing team flagged to investigate duplicate transaction.",
    },
  },
  {
    category: "Collection",
    priority: "Medium",
    callerName: "Declan Murphy",
    agentName: "Anna Walsh",
    audioFilename: "call_2026-05-30_declan_murphy.wav",
    completedAt: daysAgo(3),
    sentiment: "Neutral",
    summary: "Business owner requesting a change in collection schedule from bi-weekly to weekly due to increased packaging waste volume.",
    transcript: "Agent: Repak support, Anna speaking.\nCaller: Hi Anna, Declan Murphy here from Murphy's Hardware. I need to change our collection schedule.\nAgent: Of course, Declan. What change are you looking for?\nCaller: We've expanded the shop and we're producing a lot more cardboard and plastic now. The bi-weekly pickup isn't enough.\nAgent: I understand. I can put in a request to move you to weekly collections. Your current account is RPK-31087.\nCaller: That's right. How soon can it start?\nAgent: Typically within two weeks once approved. I'll escalate this today.",
    formData: {
      form_id: "INC-2026-0530-002",
      caller_information: { name: "Declan Murphy", account_or_reference: "RPK-31087", contact_info: "declan@murphyshardware.ie" },
      call_details: { date: "2026-05-30", agent_name: "Anna Walsh", duration_estimate: "3 minutes" },
      issue: { category: "Collection", priority: "Medium", description: "Request to increase collection frequency from bi-weekly to weekly" },
      resolution: { status: "In Progress", steps_taken: ["Logged schedule change request", "Escalated to logistics team"], outcome: "Pending logistics approval, estimated 2 weeks" },
      follow_up: { required: true, actions: ["Logistics to confirm new schedule", "Call customer back with start date"], department: "Logistics" },
      customer_sentiment: "Neutral",
      call_summary: "Business owner requesting weekly collections instead of bi-weekly. Escalated to logistics. Expected 2-week turnaround.",
    },
  },
  {
    category: "Registration",
    priority: "Low",
    callerName: "Fiona Byrne",
    agentName: "Tom Reilly",
    audioFilename: "call_2026-05-28_fiona_byrne.wav",
    completedAt: daysAgo(5),
    sentiment: "Satisfied",
    summary: "New business registering for Repak compliance scheme. All documentation submitted and account created.",
    transcript: "Agent: Good afternoon, Repak support. Tom here.\nCaller: Hi Tom, I'm Fiona Byrne from Byrne Bakery. We're a new business and need to register for packaging compliance.\nAgent: Welcome, Fiona. I'd be happy to help with that. Do you have your company registration number?\nCaller: Yes, it's IE-2026-48821.\nAgent: Perfect. And your estimated annual packaging tonnage?\nCaller: Around 2.5 tonnes, mostly cardboard boxes and plastic wrapping.\nAgent: Great. I've created your account — your reference number is RPK-52103. You'll receive a welcome pack by email within 24 hours.",
    formData: {
      form_id: "INC-2026-0528-003",
      caller_information: { name: "Fiona Byrne", account_or_reference: "RPK-52103", contact_info: "fiona@byrnebakery.ie" },
      call_details: { date: "2026-05-28", agent_name: "Tom Reilly", duration_estimate: "5 minutes" },
      issue: { category: "Registration", priority: "Low", description: "New business registration for packaging compliance scheme" },
      resolution: { status: "Resolved", steps_taken: ["Verified company registration IE-2026-48821", "Created new account RPK-52103", "Scheduled welcome pack dispatch"], outcome: "Account created, welcome pack sent" },
      follow_up: { required: false, actions: [], department: "Onboarding" },
      customer_sentiment: "Satisfied",
      call_summary: "New bakery business registered for Repak scheme. Account RPK-52103 created. Annual packaging estimate: 2.5 tonnes.",
    },
  },
  {
    category: "Compliance",
    priority: "High",
    callerName: "Kevin Doyle",
    agentName: "Anna Walsh",
    audioFilename: "call_2026-06-02_kevin_doyle.wav",
    completedAt: daysAgo(0),
    sentiment: "Angry",
    summary: "Customer received a compliance warning letter for late submission of annual packaging data. Disputes the deadline and claims submission was on time.",
    transcript: "Agent: Repak support, Anna speaking. How can I help?\nCaller: I'm Kevin Doyle, account RPK-22045. I just received a compliance warning and I'm furious. I submitted my data on time.\nAgent: I'm sorry to hear that, Kevin. Let me check your submission history.\nCaller: I submitted everything on March 28th. The deadline was March 31st.\nAgent: I can see a submission dated March 28th, but it shows as incomplete — the plastics breakdown was missing.\nCaller: Nobody told me it was incomplete! I would have fixed it immediately.\nAgent: You're right, we should have notified you. I'll escalate this to the compliance team to have the warning reviewed.",
    formData: {
      form_id: "INC-2026-0602-004",
      caller_information: { name: "Kevin Doyle", account_or_reference: "RPK-22045", contact_info: "kevin.doyle@doylepacking.ie" },
      call_details: { date: "2026-06-02", agent_name: "Anna Walsh", duration_estimate: "6 minutes" },
      issue: { category: "Compliance", priority: "High", description: "Disputes compliance warning for late data submission. Submission was on time but flagged as incomplete without notification.", error_messages: "COMP-WARN-2026-1847" },
      resolution: { status: "Escalated", steps_taken: ["Verified submission dated March 28 was flagged incomplete", "Confirmed no incompleteness notification was sent to customer", "Escalated to compliance team for warning review"], outcome: "Pending compliance team review" },
      follow_up: { required: true, actions: ["Compliance team to review warning COMP-WARN-2026-1847", "Call customer with outcome within 48 hours", "Review notification process for incomplete submissions"], department: "Compliance" },
      customer_sentiment: "Angry",
      call_summary: "Customer disputes compliance warning. Submission was on time but incomplete (missing plastics). No notification was sent. Warning escalated for review.",
    },
  },
  {
    category: "Collection",
    priority: "High",
    callerName: "Marie Flanagan",
    agentName: "Tom Reilly",
    audioFilename: "call_2026-05-29_marie_flanagan.wav",
    completedAt: daysAgo(4),
    sentiment: "Frustrated",
    summary: "Customer reports three consecutive missed collections. Waste is piling up and creating a health concern at the business premises.",
    transcript: "Agent: Good morning, Repak support.\nCaller: Hi, this is Marie Flanagan, RPK-18903. Your collectors have missed us three times in a row now. We have packaging waste everywhere.\nAgent: I'm really sorry about that, Marie. Three missed collections is unacceptable.\nCaller: It's becoming a health issue. We're a food business — we can't have waste piling up.\nAgent: Absolutely understood. I'm going to arrange an emergency collection for tomorrow and flag your location for priority service.\nCaller: Thank you. But this can't keep happening.\nAgent: Agreed. I'll also escalate to the route manager to investigate why your stop is being missed.",
    formData: {
      form_id: "INC-2026-0529-005",
      caller_information: { name: "Marie Flanagan", account_or_reference: "RPK-18903", contact_info: "marie@flanaganfoods.ie" },
      call_details: { date: "2026-05-29", agent_name: "Tom Reilly", duration_estimate: "4 minutes" },
      issue: { category: "Collection", priority: "High", description: "Three consecutive missed collections. Waste accumulation creating health concern at food business." },
      resolution: { status: "In Progress", steps_taken: ["Scheduled emergency collection for May 30", "Flagged location for priority service", "Escalated to route manager"], outcome: "Emergency collection arranged, investigation ongoing" },
      follow_up: { required: true, actions: ["Confirm emergency collection completed", "Route manager to provide explanation", "Monitor next 4 scheduled collections"], department: "Logistics" },
      customer_sentiment: "Frustrated",
      call_summary: "Three missed collections at food business. Emergency pickup arranged for next day. Route manager investigating.",
    },
  },
  {
    category: "Billing",
    priority: "Medium",
    callerName: "Conor Ryan",
    agentName: "Anna Walsh",
    audioFilename: "call_2026-05-27_conor_ryan.wav",
    completedAt: daysAgo(6),
    sentiment: "Neutral",
    summary: "Customer enquiring about fee structure changes for 2026 and requesting a detailed breakdown of charges.",
    formData: {
      form_id: "INC-2026-0527-006",
      caller_information: { name: "Conor Ryan", account_or_reference: "RPK-37612", contact_info: "conor@ryanretail.ie" },
      call_details: { date: "2026-05-27", agent_name: "Anna Walsh", duration_estimate: "7 minutes" },
      issue: { category: "Billing", priority: "Medium", description: "Enquiry about 2026 fee structure changes and request for detailed charge breakdown" },
      resolution: { status: "Resolved", steps_taken: ["Explained new fee tiers for 2026", "Emailed detailed breakdown to customer", "Updated account preferences for itemised invoicing"], outcome: "Information provided, itemised invoicing enabled" },
      follow_up: { required: false, actions: [], department: "Billing" },
      customer_sentiment: "Neutral",
      call_summary: "Customer enquired about 2026 fee changes. Detailed breakdown emailed. Account updated for itemised invoicing.",
    },
  },
  {
    category: "Technical",
    priority: "Medium",
    callerName: "Niamh Kelly",
    agentName: "Tom Reilly",
    audioFilename: "call_2026-06-03_niamh_kelly.wav",
    completedAt: hoursAgo(8),
    sentiment: "Neutral",
    summary: "Customer unable to log into the Repak online portal. Password reset emails not arriving.",
    formData: {
      form_id: "INC-2026-0603-007",
      caller_information: { name: "Niamh Kelly", account_or_reference: "RPK-41558", contact_info: "niamh@kellylogistics.ie" },
      call_details: { date: "2026-06-03", agent_name: "Tom Reilly", duration_estimate: "5 minutes" },
      issue: { category: "Technical", priority: "Medium", description: "Cannot log into online portal. Password reset emails not being received.", error_messages: "Email delivery failure — customer's mail server rejecting from noreply@repak.ie" },
      resolution: { status: "Resolved", steps_taken: ["Verified email address on file is correct", "Identified mail server rejection for noreply@repak.ie", "Manually reset password and sent via alternative email"], outcome: "Password reset, customer can now access portal" },
      follow_up: { required: true, actions: ["IT to investigate email deliverability to kellylogistics.ie domain"], department: "IT" },
      customer_sentiment: "Neutral",
      call_summary: "Portal login issue caused by email deliverability problem. Password manually reset. IT to investigate.",
    },
  },
  {
    category: "Compliance",
    priority: "Low",
    callerName: "Brendan Walsh",
    agentName: "Anna Walsh",
    audioFilename: "call_2026-05-26_brendan_walsh.wav",
    completedAt: daysAgo(7),
    sentiment: "Satisfied",
    summary: "Customer requesting information about upcoming packaging regulations and how they affect small producers under 10 tonnes.",
    formData: {
      form_id: "INC-2026-0526-008",
      caller_information: { name: "Brendan Walsh", account_or_reference: "RPK-28734", contact_info: "brendan@walshproduce.ie" },
      call_details: { date: "2026-05-26", agent_name: "Anna Walsh", duration_estimate: "8 minutes" },
      issue: { category: "Compliance", priority: "Low", description: "Enquiry about upcoming packaging regulations for small producers under 10 tonnes" },
      resolution: { status: "Resolved", steps_taken: ["Explained upcoming EU packaging regulation changes", "Confirmed small producer exemptions still apply", "Sent compliance guide PDF by email"], outcome: "Information provided, compliance guide sent" },
      follow_up: { required: false, actions: [], department: "Compliance" },
      customer_sentiment: "Satisfied",
      call_summary: "Small producer enquiry about new packaging regulations. Confirmed exemptions still apply. Compliance guide emailed.",
    },
  },
  {
    category: "Registration",
    priority: "Medium",
    callerName: "Aisling Nolan",
    agentName: "Tom Reilly",
    audioFilename: "call_2026-06-02_aisling_nolan.wav",
    completedAt: hoursAgo(20),
    sentiment: "Positive",
    summary: "Existing customer updating business details after a merger. Needs to consolidate two Repak accounts into one.",
    formData: {
      form_id: "INC-2026-0602-009",
      caller_information: { name: "Aisling Nolan", account_or_reference: "RPK-15320 / RPK-39871", contact_info: "aisling@nolanbros.ie" },
      call_details: { date: "2026-06-02", agent_name: "Tom Reilly", duration_estimate: "10 minutes" },
      issue: { category: "Registration", priority: "Medium", description: "Account consolidation required after business merger. Two accounts need to be merged." },
      resolution: { status: "In Progress", steps_taken: ["Documented merger details", "Initiated account consolidation request", "Sent required forms to customer"], outcome: "Consolidation forms sent, awaiting signed return" },
      follow_up: { required: true, actions: ["Customer to return signed consolidation forms", "Process merge once documents received", "Update billing to single entity"], department: "Account Management" },
      customer_sentiment: "Positive",
      call_summary: "Business merger — two accounts to be consolidated. Forms sent for signing. Merge will proceed once returned.",
    },
  },
  {
    category: "Collection",
    priority: "Low",
    callerName: "Padraig Brennan",
    agentName: "Anna Walsh",
    audioFilename: "call_2026-05-31_padraig_brennan.wav",
    completedAt: daysAgo(2),
    sentiment: "Satisfied",
    summary: "Customer requesting information about adding glass recycling to their existing collection service.",
    formData: {
      form_id: "INC-2026-0531-010",
      caller_information: { name: "Padraig Brennan", account_or_reference: "RPK-42156", contact_info: "padraig@brennanpub.ie" },
      call_details: { date: "2026-05-31", agent_name: "Anna Walsh", duration_estimate: "3 minutes" },
      issue: { category: "Collection", priority: "Low", description: "Enquiry about adding glass recycling to existing collection service" },
      resolution: { status: "Resolved", steps_taken: ["Checked service availability in customer's area", "Added glass collection to account", "Confirmed next collection date includes glass"], outcome: "Glass recycling added, starts next scheduled collection" },
      follow_up: { required: false, actions: [], department: "Logistics" },
      customer_sentiment: "Satisfied",
      call_summary: "Pub owner adding glass recycling to service. Available in area, added to account. Starts next collection cycle.",
    },
  },
];

const whatsappConversations = [
  {
    contactPhone: "+353871234567",
    contactName: "Sarah O'Brien",
    messages: [
      { direction: "inbound", body: "Hi, I was told my refund would arrive in 3-5 days. It's been a week now.", type: "text", hoursAgo: 26 },
      { direction: "outbound", body: "Hi Sarah, apologies for the delay. Let me check the status of your refund right away.", type: "text", hoursAgo: 25 },
      { direction: "outbound", body: "I can confirm the refund of €245 was processed on June 2nd. It should appear in your account today or tomorrow.", type: "text", hoursAgo: 25 },
      { direction: "inbound", body: "Okay thank you for checking. I'll keep an eye on it.", type: "text", hoursAgo: 24 },
    ],
  },
  {
    contactPhone: "+353862345678",
    contactName: "Marie Flanagan",
    messages: [
      { direction: "inbound", body: "The emergency collection came through today, thanks. But the regular one was missed again yesterday.", type: "text", hoursAgo: 72 },
      { direction: "outbound", body: "Thank you for letting us know, Marie. I've flagged this with the route manager again. We're taking this very seriously.", type: "text", hoursAgo: 71 },
      { direction: "inbound", body: null, type: "voice_note", hoursAgo: 48 },
      { direction: "outbound", body: "I've listened to your voice note. I completely understand your frustration. The route manager will call you directly today.", type: "text", hoursAgo: 47 },
      { direction: "inbound", body: "He called. Says it's sorted now. We'll see.", type: "text", hoursAgo: 30 },
    ],
  },
  {
    contactPhone: "+353853456789",
    contactName: "Declan Murphy",
    messages: [
      { direction: "inbound", body: "Any update on switching to weekly collections?", type: "text", hoursAgo: 50 },
      { direction: "outbound", body: "Hi Declan, the logistics team has approved your request. Weekly collections will start from Monday June 9th.", type: "text", hoursAgo: 48 },
      { direction: "inbound", body: "Brilliant, thanks Anna!", type: "text", hoursAgo: 47 },
    ],
  },
  {
    contactPhone: "+353894567890",
    contactName: null,
    messages: [
      { direction: "inbound", body: "Hello is this Repak? I need to register my company", type: "text", hoursAgo: 100 },
      { direction: "outbound", body: "Hello! Yes this is Repak. You can register online at repak.ie/register or I can help you over the phone. Would you like to call us at 01 467 0190?", type: "text", hoursAgo: 99 },
      { direction: "inbound", body: "I'll try the website first thanks", type: "text", hoursAgo: 98 },
    ],
  },
];

const emailConversations = [
  {
    senderEmail: "kevin.doyle@doylepacking.ie",
    senderName: "Kevin Doyle",
    messages: [
      {
        direction: "inbound",
        subject: "RE: Compliance Warning COMP-WARN-2026-1847",
        fromEmail: "kevin.doyle@doylepacking.ie",
        fromName: "Kevin Doyle",
        toEmail: "support@repak.ie",
        bodyText: "Hi,\n\nFollowing up on our phone conversation. I've attached the screenshot of my March 28th submission confirmation. As you can see, it shows 'Submitted Successfully' with no indication that anything was incomplete.\n\nI expect this warning to be withdrawn.\n\nRegards,\nKevin Doyle\nDoyle Packing Ltd",
        hoursAgo: 20,
      },
      {
        direction: "outbound",
        subject: "RE: Compliance Warning COMP-WARN-2026-1847",
        fromEmail: "support@repak.ie",
        fromName: "Repak Support",
        toEmail: "kevin.doyle@doylepacking.ie",
        bodyText: "Dear Kevin,\n\nThank you for providing the screenshot. We have forwarded this evidence to the compliance team along with your case. We expect a resolution within 48 hours.\n\nApologies for the inconvenience.\n\nBest regards,\nAnna Walsh\nRepak Support",
        hoursAgo: 18,
      },
    ],
  },
  {
    senderEmail: "aisling@nolanbros.ie",
    senderName: "Aisling Nolan",
    messages: [
      {
        direction: "inbound",
        subject: "Account Consolidation Forms - Signed",
        fromEmail: "aisling@nolanbros.ie",
        fromName: "Aisling Nolan",
        toEmail: "support@repak.ie",
        bodyText: "Hi Tom,\n\nPlease find attached the signed consolidation forms for merging RPK-15320 and RPK-39871 into a single account under Nolan Brothers Ltd.\n\nLet me know if anything else is needed.\n\nThanks,\nAisling",
        hoursAgo: 10,
      },
    ],
  },
  {
    senderEmail: "facilities@greenmounthotel.ie",
    senderName: "John Murray",
    messages: [
      {
        direction: "inbound",
        subject: "Enquiry - Large Event Waste Collection",
        fromEmail: "facilities@greenmounthotel.ie",
        fromName: "John Murray",
        toEmail: "support@repak.ie",
        bodyText: "Hello,\n\nWe're hosting a large conference on June 20-22 and expect significantly more packaging waste than usual. Is it possible to arrange additional collection during that period?\n\nOur account reference is RPK-50234.\n\nMany thanks,\nJohn Murray\nFacilities Manager\nGreenmount Hotel",
        hoursAgo: 5,
      },
      {
        direction: "outbound",
        subject: "RE: Enquiry - Large Event Waste Collection",
        fromEmail: "support@repak.ie",
        fromName: "Repak Support",
        toEmail: "facilities@greenmounthotel.ie",
        bodyText: "Hi John,\n\nAbsolutely, we can arrange additional collections for your event. I've raised this with our logistics team and they'll contact you within 24 hours to confirm dates and any extra bins needed.\n\nBest regards,\nTom Reilly\nRepak Support",
        hoursAgo: 3,
      },
    ],
  },
];

async function run() {
  console.log("Seeding data...\n");

  // Get the admin account to link sessions to
  const account = await prisma.account.findFirst({ where: { role: "super_admin" } });
  if (!account) throw new Error("No admin account found. Run seed-admin.mjs first.");

  // Ensure filetypes exist
  const wavType = await prisma.fileType.upsert({
    where: { fileTypeName: "audio/wav" },
    update: {},
    create: { fileTypeName: "audio/wav" },
  });

  // Seed incidents
  for (const inc of incidents) {
    const session = await prisma.recordSession.create({
      data: { startTime: inc.completedAt, accountId: account.accountId },
    });

    const file = await prisma.file.create({
      data: {
        fileTypeId: wavType.id,
        fileUrl: `/recordings/${inc.audioFilename}`,
        recordingSessionId: session.id,
      },
    });

    const form = await prisma.incidentForm.create({
      data: {
        fileId: file.id,
        status: "completed",
        category: inc.category,
        priority: inc.priority,
        completedAt: inc.completedAt,
      },
    });

    await prisma.incidentGeneralInformation.create({
      data: {
        incidentFormId: form.id,
        callerName: inc.callerName,
        agentName: inc.agentName,
        audioFilename: inc.audioFilename,
        formData: inc.formData,
      },
    });

    await prisma.incidentTranscription.create({
      data: {
        incidentFormId: form.id,
        langCode: "en",
        transcriptText: inc.transcript ?? null,
        summary: inc.summary,
        sentiment: inc.sentiment,
      },
    });

    console.log(`  Incident: ${inc.callerName} — ${inc.category} (${inc.priority})`);
  }

  // Seed WhatsApp conversations
  for (const conv of whatsappConversations) {
    const lastMsg = conv.messages[conv.messages.length - 1];
    const conversation = await prisma.whatsAppConversation.create({
      data: {
        contactPhone: conv.contactPhone,
        contactName: conv.contactName,
        lastMessageAt: hoursAgo(lastMsg.hoursAgo),
      },
    });

    for (const msg of conv.messages) {
      await prisma.whatsAppMessage.create({
        data: {
          conversationId: conversation.id,
          direction: msg.direction,
          status: msg.direction === "inbound" ? "received" : "delivered",
          messageType: msg.type,
          body: msg.body,
          rawPayload: {},
          createdAt: hoursAgo(msg.hoursAgo),
        },
      });
    }

    console.log(`  WhatsApp: ${conv.contactName ?? conv.contactPhone} (${conv.messages.length} messages)`);
  }

  // Seed email conversations
  for (const conv of emailConversations) {
    const lastMsg = conv.messages[conv.messages.length - 1];
    const conversation = await prisma.emailConversation.create({
      data: {
        senderEmail: conv.senderEmail,
        senderName: conv.senderName,
        lastMessageAt: hoursAgo(lastMsg.hoursAgo),
      },
    });

    for (const msg of conv.messages) {
      await prisma.emailMessage.create({
        data: {
          conversationId: conversation.id,
          direction: msg.direction,
          subject: msg.subject,
          fromEmail: msg.fromEmail,
          fromName: msg.fromName,
          toEmail: msg.toEmail,
          bodyText: msg.bodyText,
          headers: {},
          envelope: {},
          rawPayload: {},
          createdAt: hoursAgo(msg.hoursAgo),
        },
      });
    }

    console.log(`  Email: ${conv.senderName} (${conv.messages.length} messages)`);
  }

  console.log("\nDone! Seeded:");
  console.log(`  ${incidents.length} incidents`);
  console.log(`  ${whatsappConversations.length} WhatsApp conversations`);
  console.log(`  ${emailConversations.length} email conversations`);

  await prisma.$disconnect();
}

run().catch((e) => {
  console.error(e);
  process.exit(1);
});
