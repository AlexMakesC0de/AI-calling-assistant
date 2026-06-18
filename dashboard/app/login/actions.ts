"use server";

import { redirect } from "next/navigation";
import bcrypt from "bcryptjs";
import { prisma } from "@/lib/prisma";
import { setSessionCookie, clearSessionCookie } from "@/lib/auth";

export async function login(
  _prev: { error: string } | null,
  formData: FormData
): Promise<{ error: string }> {
  const email = formData.get("email") as string;
  const password = formData.get("password") as string;

  if (!email || !password) {
    return { error: "Email and password are required." };
  }

  const account = await prisma.account.findUnique({
    where: { accountEmail: email },
  });

  if (!account || !(await bcrypt.compare(password, account.password))) {
    return { error: "Invalid email or password." };
  }

  await setSessionCookie({
    accountId: account.accountId,
    email: account.accountEmail,
    role: account.role,
    name: account.name,
  });

  redirect("/");
}

export async function logout() {
  await clearSessionCookie();
  redirect("/login");
}
