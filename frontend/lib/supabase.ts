import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabasePublishableKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

let browserClient: SupabaseClient | null = null;

export function isSupabaseConfigured(): boolean {
  return Boolean(supabaseUrl && supabasePublishableKey);
}

export function getSupabaseBrowserClient(): SupabaseClient {
  if (!supabaseUrl || !supabasePublishableKey) {
    throw new Error("A autenticação segura da plataforma ainda não foi configurada.");
  }

  browserClient ??= createClient(supabaseUrl, supabasePublishableKey);
  return browserClient;
}
