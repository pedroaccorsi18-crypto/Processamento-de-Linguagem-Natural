-- Synapse AI - Fases 1 e 2
-- Execute manualmente no Supabase SQL Editor após revisão.
-- Este script é não destrutivo: cria tabelas, políticas e trigger apenas se necessário.

create extension if not exists pgcrypto;
create extension if not exists vector;

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
  storage_bucket text,
  storage_path text,
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
  question text,
  answer text,
  sources jsonb not null default '[]'::jsonb,
  model text,
  metadata jsonb not null default '{}'::jsonb,
  status text not null default 'planned',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.document_chunks (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  document_id uuid not null references public.documents(id) on delete cascade,
  chunk_index integer not null,
  content text not null,
  content_char_count integer not null default 0,
  embedding vector(1536) not null,
  embedding_model text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (document_id, chunk_index)
);

alter table public.profiles enable row level security;
alter table public.documents enable row level security;
alter table public.analyses enable row level security;
alter table public.document_chunks enable row level security;

alter table public.documents
  add column if not exists extracted_text text,
  add column if not exists text_char_count integer not null default 0,
  add column if not exists storage_bucket text,
  add column if not exists storage_path text,
  add column if not exists metadata jsonb not null default '{}'::jsonb,
  add column if not exists processed_at timestamptz;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'documents',
  'documents',
  false,
  10485760,
  array[
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/json',
    'application/mbox',
    'text/plain',
    'text/markdown',
    'text/csv',
    'text/vtt',
    'text/calendar',
    'message/rfc822',
    'audio/mpeg',
    'audio/mp3',
    'audio/mp4',
    'audio/m4a',
    'audio/x-m4a',
    'audio/wav',
    'audio/x-wav',
    'audio/webm',
    'audio/ogg',
    'video/mp4',
    'video/mpeg',
    'video/webm',
    'application/octet-stream'
  ]
)
on conflict (id) do update
set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

alter table public.analyses
  add column if not exists question text,
  add column if not exists answer text,
  add column if not exists sources jsonb not null default '[]'::jsonb,
  add column if not exists model text,
  add column if not exists metadata jsonb not null default '{}'::jsonb;

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
    where schemaname = 'public' and tablename = 'document_chunks'
    and policyname = 'Users can read their own document chunks'
  ) then
    create policy "Users can read their own document chunks"
    on public.document_chunks for select
    using (auth.uid() = user_id);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'storage' and tablename = 'objects'
    and policyname = 'Users can read their own stored documents'
  ) then
    create policy "Users can read their own stored documents"
    on storage.objects for select
    using (
      bucket_id = 'documents'
      and auth.uid()::text = split_part(name, '/', 1)
    );
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'storage' and tablename = 'objects'
    and policyname = 'Users can insert their own stored documents'
  ) then
    create policy "Users can insert their own stored documents"
    on storage.objects for insert
    with check (
      bucket_id = 'documents'
      and auth.uid()::text = split_part(name, '/', 1)
    );
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'storage' and tablename = 'objects'
    and policyname = 'Users can update their own stored documents'
  ) then
    create policy "Users can update their own stored documents"
    on storage.objects for update
    using (
      bucket_id = 'documents'
      and auth.uid()::text = split_part(name, '/', 1)
    )
    with check (
      bucket_id = 'documents'
      and auth.uid()::text = split_part(name, '/', 1)
    );
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'storage' and tablename = 'objects'
    and policyname = 'Users can delete their own stored documents'
  ) then
    create policy "Users can delete their own stored documents"
    on storage.objects for delete
    using (
      bucket_id = 'documents'
      and auth.uid()::text = split_part(name, '/', 1)
    );
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'document_chunks'
    and policyname = 'Users can insert their own document chunks'
  ) then
    create policy "Users can insert their own document chunks"
    on public.document_chunks for insert
    with check (auth.uid() = user_id);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'document_chunks'
    and policyname = 'Users can update their own document chunks'
  ) then
    create policy "Users can update their own document chunks"
    on public.document_chunks for update
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'document_chunks'
    and policyname = 'Users can delete their own document chunks'
  ) then
    create policy "Users can delete their own document chunks"
    on public.document_chunks for delete
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

create index if not exists document_chunks_document_id_idx
on public.document_chunks (document_id);

create index if not exists document_chunks_user_id_idx
on public.document_chunks (user_id);

create index if not exists analyses_user_id_created_at_idx
on public.analyses (user_id, created_at desc);

create index if not exists document_chunks_embedding_idx
on public.document_chunks
using ivfflat (embedding vector_cosine_ops)
with (lists = 100);

create or replace function public.match_document_chunks(
  match_user_id uuid,
  query_embedding vector(1536),
  match_count integer default 5,
  similarity_threshold float default 0.1
)
returns table (
  document_id uuid,
  filename text,
  chunk_index integer,
  content text,
  similarity float
)
language sql
stable
as $$
  select
    dc.document_id,
    d.filename,
    dc.chunk_index,
    dc.content,
    1 - (dc.embedding <=> query_embedding) as similarity
  from public.document_chunks dc
  join public.documents d on d.id = dc.document_id
  where dc.user_id = match_user_id
    and auth.uid() = dc.user_id
    and 1 - (dc.embedding <=> query_embedding) >= similarity_threshold
  order by dc.embedding <=> query_embedding
  limit match_count;
$$;

create or replace function public.match_document_chunks_in_documents(
  match_user_id uuid,
  query_embedding vector(1536),
  filter_document_ids uuid[],
  match_count integer default 5,
  similarity_threshold float default 0.1
)
returns table (
  document_id uuid,
  filename text,
  chunk_index integer,
  content text,
  similarity float
)
language sql
stable
as $$
  select
    dc.document_id,
    d.filename,
    dc.chunk_index,
    dc.content,
    1 - (dc.embedding <=> query_embedding) as similarity
  from public.document_chunks dc
  join public.documents d on d.id = dc.document_id
  where dc.user_id = match_user_id
    and auth.uid() = dc.user_id
    and dc.document_id = any(filter_document_ids)
    and 1 - (dc.embedding <=> query_embedding) >= similarity_threshold
  order by dc.embedding <=> query_embedding
  limit match_count;
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
