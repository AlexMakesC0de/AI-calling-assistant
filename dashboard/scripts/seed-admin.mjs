import { PrismaClient } from "@prisma/client";
import bcrypt from "bcryptjs";

const prisma = new PrismaClient();

async function run() {
  await prisma.$executeRawUnsafe(
    `ALTER TABLE account ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'user'`
  );
  await prisma.$executeRawUnsafe(
    `ALTER TABLE account ADD COLUMN IF NOT EXISTS name VARCHAR(255)`
  );
  console.log("Schema columns added");

  const hash = bcrypt.hashSync("admin", 10);
  await prisma.$executeRawUnsafe(
    `INSERT INTO account (password, account_email, role, name)
     VALUES ($1, $2, $3, $4)
     ON CONFLICT (account_email) DO UPDATE SET password = $1, role = $3, name = $4`,
    hash,
    "admin@repak.ie",
    "super_admin",
    "Repak Admin"
  );
  console.log("Admin account ready — admin@repak.ie / admin");
  console.log("Hash verify:", bcrypt.compareSync("admin", hash));

  await prisma.$disconnect();
}

run().catch((e) => {
  console.error(e);
  process.exit(1);
});
