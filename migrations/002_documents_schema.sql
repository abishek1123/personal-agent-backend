create extension if not exists vector;

create table documents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) not null,
  title text not null,
  storage_path text,
  status text not null default 'processing',
  created_at timestamp with time zone default now()
);

alter table documents enable row level security;

create policy "Users can manage own documents"
on documents for all
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

create table document_chunks (
  id uuid primary key default gen_random_uuid(),
  document_id uuid references documents(id) on delete cascade not null,
  user_id uuid references auth.users(id) not null,
  chunk_text text not null,
  chunk_index int not null,
  embedding vector(768),
  created_at timestamp with time zone default now()
);

alter table document_chunks enable row level security;

create policy "Users can manage own chunks"
on document_chunks for all
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

create index on document_chunks using ivfflat (embedding vector_cosine_ops) with (lists = 100);
