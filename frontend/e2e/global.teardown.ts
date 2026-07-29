import { createClient } from "@supabase/supabase-js";
import { existsSync } from "node:fs";
import { rm } from "node:fs/promises";

import { qaStatePath, readQaRunState } from "./support/qa-state";

export default async function globalTeardown(): Promise<void> {
  try {
    if (!existsSync(qaStatePath)) {
      return;
    }

    const state = readQaRunState();
    const serviceRoleKey = process.env.E2E_SUPABASE_SERVICE_ROLE_KEY;
    const supabaseUrl = process.env.E2E_SUPABASE_URL;
    if (serviceRoleKey && supabaseUrl) {
      const admin = createClient(supabaseUrl, serviceRoleKey, {
        auth: { autoRefreshToken: false, persistSession: false },
      });
      for (const account of Object.values(state.accounts)) {
        const { error } = await admin.auth.admin.deleteUser(account.id);
        if (error) {
          console.warn(`Não foi possível remover a conta temporária ${account.email}: ${error.message}`);
        }
      }
    }
  } finally {
    await rm(qaStatePath, { force: true });
  }
}
