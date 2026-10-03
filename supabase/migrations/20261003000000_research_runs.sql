create table if not exists public.research_runs (
  run_id uuid primary key default gen_random_uuid(),
  strategy_name text not null,
  strategy_version text not null,
  instrument text not null,
  timeframe text not null,
  start_at timestamptz not null,
  end_at timestamptz not null,
  data_rows integer not null check (data_rows >= 0),
  data_downloaded integer not null check (data_downloaded >= 0),
  gaps_filled integer not null check (gaps_filled >= 0),
  initial_equity numeric not null,
  final_equity numeric not null,
  total_return_pct numeric not null,
  max_drawdown_pct numeric not null,
  trade_count integer not null check (trade_count >= 0),
  wins integer not null check (wins >= 0),
  losses integer not null check (losses >= 0),
  win_rate_pct numeric not null,
  profit_factor numeric,
  profit_factor_infinite boolean not null default false,
  created_at timestamptz not null default now()
);

alter table public.research_runs enable row level security;

revoke all on table public.research_runs from anon, authenticated;
grant select, insert, update, delete on table public.research_runs to service_role;

create index if not exists research_runs_lookup_idx
  on public.research_runs (instrument, timeframe, created_at desc);

create index if not exists research_runs_strategy_idx
  on public.research_runs (strategy_name, strategy_version, created_at desc);
