-- Keyword (lexical) search layer for hybrid RAG retrieval.
-- Adds a generated full-text-search column + GIN index, and a BM25-style
-- ts_rank search function. Complements the semantic vector search in
-- match_document_chunks so retrieval catches exact terms (names, codes,
-- acronyms) that embeddings often miss.

-- Generated tsvector column: auto-maintained, populates existing rows too.
alter table document_chunks
  add column if not exists fts tsvector
  generated always as (to_tsvector('english', chunk_text)) stored;

create index if not exists document_chunks_fts_idx
  on document_chunks using gin (fts);

-- Lexical search. websearch_to_tsquery tolerates arbitrary natural-language
-- input (no query-syntax errors), so we can pass the raw question through.
create or replace function keyword_search_chunks(
  query_text text,
  match_user_id uuid,
  match_document_id uuid default null,
  match_count int default 20
)
returns table (
  id uuid,
  document_id uuid,
  chunk_text text,
  chunk_index int,
  rank float
)
language sql stable
as $$
  select
    document_chunks.id,
    document_chunks.document_id,
    document_chunks.chunk_text,
    document_chunks.chunk_index,
    ts_rank(document_chunks.fts, websearch_to_tsquery('english', query_text)) as rank
  from document_chunks
  where document_chunks.user_id = match_user_id
    and (match_document_id is null or document_chunks.document_id = match_document_id)
    and document_chunks.fts @@ websearch_to_tsquery('english', query_text)
  order by rank desc
  limit match_count;
$$;
