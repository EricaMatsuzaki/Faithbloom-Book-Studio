-- REVIEWABLE, OPTIONAL MIGRATION. Not applied by the application.
-- Requires Supabase/PostgreSQL and the server-only service_role role.
-- Keep the Storage bucket private. These RPCs are not a browser capability.
begin;

create table if not exists public.faithbloom_json_documents (
    bucket text not null check (bucket <> '' and position('/' in bucket) = 0),
    path text not null check (
        path <> '' and lower(right(path, 5)) = '.json'
        and path !~ '(^/|/$|//|(^|/)\.{1,2}(/|$)|[[:cntrl:]]|\\)'
    ),
    value jsonb not null,
    revision bigint not null check (revision > 0),
    deleted boolean not null default false,
    updated_at timestamptz not null default now(),
    primary key (bucket, path)
);
alter table public.faithbloom_json_documents enable row level security;
revoke all on public.faithbloom_json_documents from public, anon, authenticated;
grant select, insert, update on public.faithbloom_json_documents to service_role;

create or replace function public.faithbloom_json_get(p_bucket text, p_path text)
returns jsonb language sql stable security invoker set search_path = public as $$
    select coalesce((
        select jsonb_build_object('found', not d.deleted, 'revision', d.revision, 'value', d.value)
        from public.faithbloom_json_documents d where d.bucket = p_bucket and d.path = p_path
    ), jsonb_build_object('found', false, 'revision', 0));
$$;

create or replace function public.faithbloom_json_cas(
    p_bucket text, p_path text, p_expected_revision bigint, p_value jsonb
) returns jsonb language plpgsql security invoker set search_path = public as $$
declare saved_revision bigint;
begin
    if p_expected_revision is null or p_expected_revision < 0 then
        raise exception 'Invalid JSON revision' using errcode = '22023';
    end if;
    if p_expected_revision = 0 then
        insert into public.faithbloom_json_documents (bucket, path, value, revision)
        values (p_bucket, p_path, coalesce(p_value, 'null'::jsonb), 1)
        on conflict (bucket, path) do nothing
        returning revision into saved_revision;
    else
        update public.faithbloom_json_documents d
        set value = coalesce(p_value, 'null'::jsonb), revision = d.revision + 1, deleted = false, updated_at = now()
        where d.bucket = p_bucket and d.path = p_path and d.revision = p_expected_revision
        returning d.revision into saved_revision;
    end if;
    if saved_revision is not null then
        return jsonb_build_object('written', true, 'revision', saved_revision);
    end if;
    select d.revision into saved_revision from public.faithbloom_json_documents d
    where d.bucket = p_bucket and d.path = p_path;
    return jsonb_build_object('written', false, 'revision', coalesce(saved_revision, 0));
end;
$$;

create or replace function public.faithbloom_json_delete(
    p_bucket text, p_path text, p_expected_revision bigint
) returns jsonb language plpgsql security invoker set search_path = public as $$
declare saved_revision bigint;
begin
    if p_expected_revision is null or p_expected_revision <= 0 then
        raise exception 'Invalid JSON revision' using errcode = '22023';
    end if;
    -- Retain a monotonically increasing tombstone: stale pre-delete writers
    -- cannot recreate the document, nor can an old Storage object reappear.
    update public.faithbloom_json_documents d
    set value = 'null'::jsonb, revision = d.revision + 1, deleted = true, updated_at = now()
    where d.bucket = p_bucket and d.path = p_path and d.revision = p_expected_revision
    returning d.revision into saved_revision;
    if saved_revision is not null then
        return jsonb_build_object('written', true, 'revision', saved_revision);
    end if;
    select d.revision into saved_revision from public.faithbloom_json_documents d
    where d.bucket = p_bucket and d.path = p_path;
    return jsonb_build_object('written', false, 'revision', coalesce(saved_revision, 0));
end;
$$;

create or replace function public.faithbloom_json_list(
    p_bucket text, p_prefix text default '', p_offset integer default 0
) returns jsonb language sql stable security invoker set search_path = public as $$
    with page as (
        select d.path, d.deleted from public.faithbloom_json_documents d
        where d.bucket = p_bucket and (
            p_prefix = '' or d.path = p_prefix or left(d.path, length(p_prefix) + 1) = p_prefix || '/'
        ) order by d.path limit 501 offset greatest(p_offset, 0)
    ), visible as (select * from page order by path limit 500)
    select jsonb_build_object(
        'items', coalesce((select jsonb_agg(jsonb_build_object('path', path, 'deleted', deleted) order by path) from visible), '[]'::jsonb),
        'has_more', (select count(*) > 500 from page)
    );
$$;

revoke all on function public.faithbloom_json_get(text, text) from public, anon, authenticated;
revoke all on function public.faithbloom_json_cas(text, text, bigint, jsonb) from public, anon, authenticated;
revoke all on function public.faithbloom_json_delete(text, text, bigint) from public, anon, authenticated;
revoke all on function public.faithbloom_json_list(text, text, integer) from public, anon, authenticated;
grant execute on function public.faithbloom_json_get(text, text) to service_role;
grant execute on function public.faithbloom_json_cas(text, text, bigint, jsonb) to service_role;
grant execute on function public.faithbloom_json_delete(text, text, bigint) to service_role;
grant execute on function public.faithbloom_json_list(text, text, integer) to service_role;

commit;
