-- Landing tables the loaders write. dbt reads raw and ops; nothing reads pii except the reveal function.
-- Idempotent: safe to run before every load.

create schema if not exists raw;
create schema if not exists pii;
create schema if not exists ops;
create schema if not exists serving;
create schema if not exists pmd_util;

create table if not exists ops.files (
  file_id      bigserial primary key,
  source       text not null,
  path         text not null,
  sha256       text not null unique,
  bytes        bigint not null,
  received_on  date not null,
  registered_at timestamptz not null default now(),
  status       text not null default 'registered',   -- registered | loaded | quarantined | duplicate
  duplicate_of bigint references ops.files(file_id)
);
create table if not exists ops.file_names (            -- every name a file arrived under, duplicates included
  path text primary key,
  sha256 text not null,
  seen_at timestamptz not null default now()
);
create table if not exists ops.quarantine (
  file_id    bigint not null references ops.files(file_id),
  rule       text not null,
  detail     text not null,
  at         timestamptz not null default now(),
  released_by text,
  released_at timestamptz,
  primary key (file_id, rule)
);

create table if not exists raw.gp_statements (
  file_id        bigint primary key references ops.files(file_id),
  fund           text not null,
  period_end     date not null,
  currency       text not null,
  commitment     numeric(18,2) not null,
  paid_in        numeric(18,2) not null,
  distributed    numeric(18,2) not null,
  nav            numeric(18,2) not null,
  unfunded       numeric(18,2),
  statement_date date,
  unit_scale     integer not null default 1,
  received_on    date not null,
  parser         text not null,
  loaded_at      timestamptz not null default now()
);

create table if not exists raw.bank_statements (
  file_id     bigint primary key references ops.files(file_id),
  account_iban text not null,
  statement_date date not null,
  sequence    integer not null,
  opening     numeric(18,2) not null,
  closing     numeric(18,2) not null
);
create table if not exists raw.bank_entries (
  bank_ref        text primary key,
  file_id         bigint not null references ops.files(file_id),
  account_iban    text not null,
  booking_date    date not null,
  amount          numeric(18,2) not null,        -- signed: credit positive
  counterparty_key text not null,                -- keyed hash of the counterparty IBAN
  remittance      text not null,                 -- client numbers replaced by client keys
  ref_call_id     text,
  ref_client_key  text
);

create table if not exists raw.payment_events (
  event_id         text primary key,
  account_iban     text not null,
  amount           numeric(18,2) not null,
  counterparty_key text not null,
  remittance       text not null,
  ref_call_id      text,
  ref_client_key   text,
  received_at      timestamptz not null,
  bank_ref         text,
  topic_partition  integer,
  topic_offset     bigint,
  consumed_at      timestamptz not null default now()
);

create table if not exists raw.clients (
  client_key   text primary key,
  segment      text not null,
  risk_profile text,
  country      text,
  age_band     text,
  onboarded_on date,
  advisor      text,
  status       text not null,
  loaded_at    timestamptz not null default now()
);
create table if not exists raw.client_accounts (   -- which counterparty key belongs to which client
  counterparty_key text primary key,
  client_key text not null
);
create table if not exists raw.commitments (
  subscription_id text primary key,
  client_key text not null,
  feeder text not null,
  amount numeric(18,2) not null,
  signed_on date not null
);
create table if not exists raw.capital_calls (
  call_id text primary key, feeder text not null, notice_date date not null, due_date date not null,
  percent numeric(9,4) not null
);
create table if not exists raw.distributions (
  distribution_id text primary key, feeder text not null, pay_date date not null, percent numeric(9,4) not null
);
create table if not exists raw.target_commitments (
  fund text primary key, feeder text not null, currency text not null, commitment numeric(18,2) not null
);
create table if not exists raw.fx_rates (
  rate_date date primary key, usd_per_eur numeric(12,6) not null
);

create table if not exists pii.client_vault (
  client_key text primary key, client_id text not null unique,
  first_name text, last_name text, email text, phone text, birth_date date,
  street text, postal_code text, city text, iban text, tax_id text
);
create table if not exists pii.counterparty_vault (
  counterparty_key text primary key, name text, iban text
);
create table if not exists pii.reveal_log (
  id bigserial primary key, at timestamptz not null default now(), actor text not null, role text not null,
  client_key text not null, reason text not null, granted boolean not null
);

create table if not exists ops.erasure_requests (
  request_id text primary key, client_key text not null, requested_on date not null,
  status text not null,             -- erased | retention_hold
  reason text not null,
  decided_at timestamptz not null default now()
);
create table if not exists ops.consumer_offsets (
  consumer text not null, topic text not null, part integer not null, next_offset bigint not null,
  primary key (consumer, topic, part)
);
create table if not exists ops.runs (
  run_id text primary key, started_at timestamptz not null default now(), finished_at timestamptz,
  build_schema text not null, status text not null, as_of date not null,
  gates jsonb not null default '[]', counts jsonb not null default '{}', diff jsonb
);
create table if not exists ops.break_actions (
  id bigserial primary key, break_id text not null, action text not null,   -- resolve | reopen | note
  note text not null, actor text not null, at timestamptz not null default now()
);
create table if not exists ops.statement_releases (
  file_id bigint primary key references ops.files(file_id), actor text not null, note text not null,
  at timestamptz not null default now()
);
create table if not exists ops.dead_events (
  event_id text, rule text not null, detail text not null, at timestamptz not null default now(),
  topic_partition integer, topic_offset bigint
);
create table if not exists raw.feeders (
  feeder text primary key, name text not null, collection_account text not null, first_close date not null,
  min_ticket numeric(18,2) not null
);
create table if not exists raw.target_funds (
  fund text primary key, feeder text not null, name text not null, gp text not null, region text not null,
  strategy text not null, currency text not null
);
alter table ops.runs add column if not exists build jsonb;
alter table ops.runs add column if not exists approved_by text;
alter table ops.runs add column if not exists approval_note text;

-- Which pseudonymisation key this database was loaded with, as a fingerprint (never the key). Loading with
-- another key would give the same client a second key and split their history; bootstrap refuses instead.
create table if not exists ops.pseudonym_key (
  id integer primary key default 1 check (id = 1),
  fingerprint text not null,
  first_seen timestamptz not null default now()
);
