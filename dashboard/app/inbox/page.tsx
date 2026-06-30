import { redirect } from "next/navigation";

export const dynamic = "force-dynamic";
export const metadata = { title: "Inbox" };

export default function InboxPage() {
  redirect("/inbox/outlook");
}
