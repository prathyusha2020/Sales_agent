-- Run this once in Supabase SQL Editor.
-- Uses 1024-dim embeddings (Voyage AI voyage-3.5-lite).
-- If you switch to a different embedding model, update 1024 to match its dims.

create extension if not exists vector;

create table if not exists documents (
  id          bigserial primary key,
  content     text,
  metadata    jsonb,
  embedding   vector(1024)
);

-- HNSW index for fast similarity search
create index if not exists documents_embedding_idx
  on documents using hnsw (embedding vector_cosine_ops);

-- RPC the app calls for similarity search with optional metadata filter
create or replace function match_documents (
  query_embedding vector(1024),
  match_count int default 5,
  filter jsonb default '{}'::jsonb
) returns table (
  id        bigint,
  content   text,
  metadata  jsonb,
  similarity float
)
language plpgsql
as $$
begin
  return query
  select
    documents.id,
    documents.content,
    documents.metadata,
    1 - (documents.embedding <=> query_embedding) as similarity
  from documents
  where documents.metadata @> filter
  order by documents.embedding <=> query_embedding
  limit match_count;
end;
$$;
