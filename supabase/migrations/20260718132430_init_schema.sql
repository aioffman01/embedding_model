-- Enable the pgvector extension to work with embedding vectors
create extension if not exists vector;

-- Create the movies table
create table if not exists movies (
  id bigserial primary key,
  title text not null,
  year integer not null,
  actors text[] not null,
  synopsis text not null,
  category text not null,
  embedding vector(3072) -- gemini-embedding-2 generates 3,072 dimensions
);

-- Grant privileges to Supabase API roles
grant all privileges on table public.movies to postgres, anon, authenticated, service_role;

-- Create a semantic similarity matching function (RPC)
create or replace function match_movies (
  query_embedding vector(3072),
  match_threshold float,
  match_count int,
  filter_category text
)
returns table (
  title text,
  year integer,
  actors text[],
  synopsis text,
  category text,
  similarity float
)
language sql stable
as $$
  select
    title,
    year,
    actors,
    synopsis,
    category,
    1 - (movies.embedding <=> query_embedding) as similarity
  from movies
  where category = filter_category
    and 1 - (movies.embedding <=> query_embedding) > match_threshold
  order by movies.embedding <=> query_embedding
  limit match_count;
$$;

-- Grant execution of function to Supabase API roles
grant execute on function public.match_movies to postgres, anon, authenticated, service_role;
