-- Similarity search function for RAG document retrieval
create or replace function match_document_chunks(
  query_embedding vector(768),
  match_user_id uuid,
  match_document_id uuid default null,
  match_count int default 5
)
returns table (
  id uuid,
  document_id uuid,
  chunk_text text,
  chunk_index int,
  similarity float
)
language sql stable
as $$
  select
    document_chunks.id,
    document_chunks.document_id,
    document_chunks.chunk_text,
    document_chunks.chunk_index,
    1 - (document_chunks.embedding <=> query_embedding) as similarity
  from document_chunks
  where document_chunks.user_id = match_user_id
    and (match_document_id is null or document_chunks.document_id = match_document_id)
  order by document_chunks.embedding <=> query_embedding
  limit match_count;
$$;
