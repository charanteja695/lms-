import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

export interface Account {
  username: string;
  password: string;
  mfaCode?: string;
}

export interface LearnerSignup {
  emailLogFile: string;
  razorpayKeySecret: string;
}

export type Role = "superAdmin" | "admin" | "head" | "staff" | "student";

interface AccountsFile extends Partial<Record<Role, Account>> {
  learnerSignup?: LearnerSignup;
}

const FILE = fileURLToPath(new URL("../accounts.json", import.meta.url));

/** e2e/accounts.json, read once. Missing accounts make the tests that need them skip, with the reason. */
export const accounts: AccountsFile = existsSync(FILE) ? (JSON.parse(readFileSync(FILE, "utf8")) as AccountsFile) : {};

export function account(role: Role): Account | undefined {
  const found = accounts[role];
  return found?.username && found.password ? found : undefined;
}
