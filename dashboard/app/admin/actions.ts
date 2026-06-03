"use server";

import { revalidatePath } from "next/cache";
import bcrypt from "bcryptjs";
import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/auth";

async function requireSuperAdmin() {
  const session = await getSession();
  if (!session || session.role !== "super_admin") {
    throw new Error("Forbidden");
  }
  return session;
}

export async function createAccount(
  _prev: { error?: string; success?: string } | null,
  formData: FormData
): Promise<{ error?: string; success?: string }> {
  await requireSuperAdmin();

  const email = (formData.get("email") as string)?.trim();
  const name = (formData.get("name") as string)?.trim() || null;
  const password = formData.get("password") as string;
  const role = formData.get("role") as string;

  if (!email || !password) {
    return { error: "Email and password are required." };
  }

  if (!["user", "admin", "super_admin"].includes(role)) {
    return { error: "Invalid role." };
  }

  const existing = await prisma.account.findUnique({
    where: { accountEmail: email },
  });
  if (existing) {
    return { error: "An account with this email already exists." };
  }

  const hashed = await bcrypt.hash(password, 10);
  await prisma.account.create({
    data: {
      accountEmail: email,
      password: hashed,
      role,
      name,
    },
  });

  revalidatePath("/admin");
  return { success: `Account created for ${email}.` };
}

export async function deleteAccount(accountId: number) {
  const session = await requireSuperAdmin();

  if (session.accountId === accountId) {
    throw new Error("Cannot delete your own account.");
  }

  await prisma.account.delete({ where: { accountId } });
  revalidatePath("/admin");
}
