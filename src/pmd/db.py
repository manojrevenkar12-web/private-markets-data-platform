"""The database: one PostgreSQL holds landing (raw, pii, ops), the audited builds and the serving views."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from importlib import resources
from typing import Any

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import Connection

from .config import database_url

ROLES = """
do $$ begin
  if not exists (select from pg_roles where rolname = 'pmd_analyst') then create role pmd_analyst nologin; end if;
  if not exists (select from pg_roles where rolname = 'pmd_operations') then create role pmd_operations nologin; end if;
end $$;
revoke all on schema pii from public;
revoke all on all tables in schema pii from public;
grant usage on schema serving to pmd_analyst, pmd_operations;
alter default privileges in schema serving grant select on tables to pmd_analyst, pmd_operations;

-- The only way from a client key to a person: a function that checks the role and writes the log first.
create or replace function pmd_util.reveal_client(p_key text, p_actor text, p_role text, p_reason text)
returns table (client_id text, first_name text, last_name text, email text, phone text, city text)
language plpgsql security definer set search_path = pii, pg_temp as $$
declare allowed boolean := p_role = any (string_to_array(current_setting('pmd.reveal_roles', true), ','));
begin
  if coalesce(length(trim(p_reason)), 0) < 5 then
    raise exception 'a reason is required to see who a client is';
  end if;
  insert into pii.reveal_log (actor, role, client_key, reason, granted) values (p_actor, p_role, p_key, p_reason, coalesce(allowed, false));
  if not coalesce(allowed, false) then
    return;
  end if;
  return query select v.client_id, v.first_name, v.last_name, v.email, v.phone, v.city
    from pii.client_vault v where v.client_key = p_key;
end $$;
revoke all on function pmd_util.reveal_client(text, text, text, text) from public;
grant usage on schema pmd_util to pmd_operations;
grant execute on function pmd_util.reveal_client(text, text, text, text) to pmd_operations;
"""


@lru_cache
def engine() -> Engine:
    return create_engine(database_url(), pool_pre_ping=True, future=True)


@contextmanager
def begin() -> Iterator[Connection]:
    with engine().begin() as c:
        yield c


def bootstrap() -> None:
    """Creates the landing schemas, tables, roles and the reveal function. Idempotent."""
    ddl = resources.files("pmd").joinpath("sql/schema.sql").read_text(encoding="utf-8")
    from .privacy import KeyChanged, key_fingerprint

    fingerprint = key_fingerprint()
    with begin() as c:
        c.exec_driver_sql(ddl)
        c.exec_driver_sql(ROLES)
        c.execute(
            text("insert into ops.pseudonym_key (fingerprint) values (:f) on conflict (id) do nothing"),
            {"f": fingerprint},
        )
        stored = c.execute(text("select fingerprint from ops.pseudonym_key")).scalar()
    if stored != fingerprint:
        raise KeyChanged(
            "PMD_PSEUDONYM_KEY is not the key this database was loaded with: every client would get a second key. "
            "Use the original key, or re-key the vault deliberately."
        )


def rows(sql: str, **params: Any) -> list[dict[str, Any]]:
    with engine().connect() as c:
        return [dict(r._mapping) for r in c.execute(text(sql), params)]


def scalar(sql: str, **params: Any) -> Any:
    with engine().connect() as c:
        return c.execute(text(sql), params).scalar()
