import { redirect } from "next/navigation";
import { getSession } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CreateAccountForm } from "./create-account-form";
import { DeleteAccountButton } from "./delete-account-button";

export const dynamic = "force-dynamic";

export default async function AdminPage() {
  const session = await getSession();
  if (!session || session.role !== "super_admin") redirect("/");

  const accounts = await prisma.account.findMany({
    select: { accountId: true, accountEmail: true, name: true, role: true },
    orderBy: { accountId: "asc" },
  });

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-medium tracking-tight">Accounts</h1>
        <p className="text-sm text-muted-foreground">
          Manage dashboard accounts. Only super admins can access this page.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All accounts</CardTitle>
        </CardHeader>
        <CardContent className="divide-y divide-border p-0">
          {accounts.map((a) => (
            <div
              key={a.accountId}
              className="flex items-center justify-between gap-4 px-6 py-3"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">
                    {a.name ?? a.accountEmail}
                  </span>
                  <Badge variant="default">{a.role}</Badge>
                </div>
                {a.name && (
                  <p className="text-xs text-muted-foreground">
                    {a.accountEmail}
                  </p>
                )}
              </div>
              {a.accountId !== session.accountId && (
                <DeleteAccountButton accountId={a.accountId} />
              )}
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Create account</CardTitle>
        </CardHeader>
        <CardContent>
          <CreateAccountForm />
        </CardContent>
      </Card>
    </div>
  );
}
