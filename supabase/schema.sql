-- Synapse AI - Fases 1 e 2
-- Execute manualmente no Supabase SQL Editor após revisão.
-- Este script é não destrutivo: cria tabelas, políticas e trigger apenas se necessário.

create extension if not exists pgcrypto;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.documents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  filename text not null,
  content_type text,
  size_bytes bigint,
  status text not null default 'planned',
  extracted_text text,
  text_char_count integer not null default 0,
  metadata jsonb not null default '{}'::jsonb,
  processed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.analyses (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  document_id uuid references public.documents(id) on delete cascade,
  title text not null,
  status text not null default 'planned',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.profiles enable row level security;
alter table public.documents enable row level security;
alter table public.analyses enable row level security;

alter table public.documents
  add column if not exists extracted_text text,
  add column if not exists text_char_count integer not null default 0,
  add column if not exists metadata jsonb not null default '{}'::jsonb,
  add column if not exists processed_at timestamptz;

do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'profiles'
    and policyname = 'Users can read their own profile'
  ) then
    create policy "Users can read their own profile"
    on public.profiles for select
    using (auth.uid() = id);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'profiles'
    and policyname = 'Users can update their own profile'
  ) then
    create policy "Users can update their own profile"
    on public.profiles for update
    using (auth.uid() = id)
    with check (auth.uid() = id);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'documents'
    and policyname = 'Users can read their own documents'
  ) then
    create policy "Users can read their own documents"
    on public.documents for select
    using (auth.uid() = user_id);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'documents'
    and policyname = 'Users can insert their own documents'
  ) then
    create policy "Users can insert their own documents"
    on public.documents for insert
    with check (auth.uid() = user_id);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'documents'
    and policyname = 'Users can update their own documents'
  ) then
    create policy "Users can update their own documents"
    on public.documents for update
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'documents'
    and policyname = 'Users can delete their own documents'
  ) then
    create policy "Users can delete their own documents"
    on public.documents for delete
    using (auth.uid() = user_id);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'analyses'
    and policyname = 'Users can read their own analyses'
  ) then
    create policy "Users can read their own analyses"
    on public.analyses for select
    using (auth.uid() = user_id);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'analyses'
    and policyname = 'Users can insert their own analyses'
  ) then
    create policy "Users can insert their own analyses"
    on public.analyses for insert
    with check (auth.uid() = user_id);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'analyses'
    and policyname = 'Users can update their own analyses'
  ) then
    create policy "Users can update their own analyses"
    on public.analyses for update
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'analyses'
    and policyname = 'Users can delete their own analyses'
  ) then
    create policy "Users can delete their own analyses"
    on public.analyses for delete
    using (auth.uid() = user_id);
  end if;
end;
$$;

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email)
  values (new.id, coalesce(new.email, ''))
  on conflict (id) do nothing;
  return new;
end;
$$;

do $$
begin
  if not exists (
    select 1 from pg_trigger
    where tgname = 'on_auth_user_created'
  ) then
    create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function public.handle_new_user();
  end if;
end;
$$;
