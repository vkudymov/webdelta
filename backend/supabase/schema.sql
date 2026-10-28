-- WebDelta schema for Supabase (Postgres)
-- Create tables, indexes, and a storage bucket for attachments.

create table if not exists public.pages (
  id bigserial primary key,
  url text not null unique,
  content text not null,
  title text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_pages_url on public.pages (url);

create table if not exists public.snapshots (
  id bigserial primary key,
  page_id bigint not null references public.pages(id) on delete cascade,
  captured_at timestamptz not null default now(),
  content text not null,
  title text,
  local_path text,
  created_at timestamptz not null default now(),
  unique(page_id, captured_at)
);

create index if not exists idx_snapshots_page_id on public.snapshots (page_id);
create index if not exists idx_snapshots_page_id_captured_at on public.snapshots (page_id, captured_at desc);

create table if not exists public.attachments (
  id bigserial primary key,
  snapshot_id bigint not null references public.snapshots(id) on delete cascade,
  url text not null,
  filename text not null,
  content_type text,
  size integer,
  hash text,
  text_content text,
  storage_path text,
  created_at timestamptz not null default now(),
  unique(snapshot_id, url)
);

create index if not exists idx_attachments_snapshot_id on public.attachments (snapshot_id);

-- Optional: keep updated_at fresh on updates
create or replace function public.set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_pages_updated_at on public.pages;
create trigger trg_pages_updated_at
before update on public.pages
for each row execute procedure public.set_updated_at();

-- Storage: create bucket "attachments" (run in Supabase SQL editor with service role).
-- Note: bucket management is often done via Supabase UI. If you manage it in SQL:
-- insert into storage.buckets (id, name, public) values ('attachments','attachments', false)
--   on conflict (id) do nothing;

