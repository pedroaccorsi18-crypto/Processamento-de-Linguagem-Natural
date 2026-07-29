import { readFileSync } from "node:fs";
import { resolve } from "node:path";

export type QaAccount = {
  id: string;
  email: string;
  password: string;
};

export type QaRunState = {
  runId: string;
  accounts: {
    accountA: QaAccount;
    accountB: QaAccount;
  };
};

export const qaStatePath = resolve(process.cwd(), "test-results", ".synapse-e2e-state.json");

export function readQaRunState(): QaRunState {
  return JSON.parse(readFileSync(qaStatePath, "utf8")) as QaRunState;
}
