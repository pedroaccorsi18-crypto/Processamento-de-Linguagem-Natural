import { createClient } from "@supabase/supabase-js";
import { mkdir, writeFile } from "node:fs/promises";
import { randomUUID } from "node:crypto";
import { dirname } from "node:path";

import { qaStatePath, type QaAccount, type QaRunState } from "./support/qa-state";

const requiredEnvironmentVariables = [
  "E2E_BASE_URL",
  "E2E_API_URL",
  "E2E_SUPABASE_URL",
  "E2E_SUPABASE_SERVICE_ROLE_KEY",
] as const;

type QaAdminClient = {
  auth: {
    admin: {
      createUser: (attributes: {
        email: string;
        password: string;
        email_confirm: boolean;
        user_metadata: Record<string, string | boolean>;
      }) => Promise<{
        data: { user: { id: string } | null };
        error: { message: string } | null;
      }>;
      deleteUser: (userId: string) => Promise<unknown>;
    };
  };
};

export default async function globalSetup(): Promise<void> {
  for (const variableName of requiredEnvironmentVariables) {
    if (!process.env[variableName]?.trim()) {
      throw new Error(`A variável ${variableName} precisa ser definida em .env.e2e.`);
    }
  }

  const baseUrl = new URL(process.env.E2E_BASE_URL!);
  const isLocalTarget = ["localhost", "127.0.0.1"].includes(baseUrl.hostname);
  if (!isLocalTarget && process.env.ALLOW_EXTERNAL_E2E !== "true") {
    throw new Error(
      "Execução externa bloqueada. Use ALLOW_EXTERNAL_E2E=true somente em homologação.",
    );
  }

  const runId = randomUUID();
  const password = `SynapseQA!${randomUUID().replaceAll("-", "")}`;
  const domain = process.env.E2E_QA_EMAIL_DOMAIN || "synapse-e2e.invalid";
  const admin = createClient(
    process.env.E2E_SUPABASE_URL!,
    process.env.E2E_SUPABASE_SERVICE_ROLE_KEY!,
    {
      auth: { autoRefreshToken: false, persistSession: false },
    },
  );

  const accountA = await createQaAccount(admin, `qa-a-${runId}@${domain}`, password, runId);
  try {
    const accountB = await createQaAccount(admin, `qa-b-${runId}@${domain}`, password, runId);
    const state: QaRunState = { runId, accounts: { accountA, accountB } };

    await mkdir(dirname(qaStatePath), { recursive: true });
    await writeFile(qaStatePath, JSON.stringify(state), { encoding: "utf8", mode: 0o600 });
    console.log(`Contas temporárias de QA criadas para a execução ${runId}.`);
  } catch (error) {
    await admin.auth.admin.deleteUser(accountA.id);
    throw error;
  }
}

async function createQaAccount(
  admin: QaAdminClient,
  email: string,
  password: string,
  runId: string,
): Promise<QaAccount> {
  const { data, error } = await admin.auth.admin.createUser({
    email,
    password,
    email_confirm: true,
    user_metadata: { automated_qa: true, qa_run_id: runId },
  });
  if (error || data.user === null) {
    throw new Error(`Não foi possível criar a conta temporária de QA: ${error?.message ?? "erro desconhecido"}.`);
  }
  return { id: data.user.id, email, password };
}
