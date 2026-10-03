alter table public.paper_orders
  add column if not exists strategy_id uuid references public.strategy_versions(strategy_id),
  add column if not exists strategy_name text,
  add column if not exists strategy_version text,
  add column if not exists source_experiment_id uuid;

alter table public.paper_trades
  add column if not exists strategy_id uuid references public.strategy_versions(strategy_id),
  add column if not exists strategy_name text,
  add column if not exists strategy_version text,
  add column if not exists source_experiment_id uuid;

create index if not exists paper_orders_strategy_status_idx
  on public.paper_orders (strategy_id, status, created_at desc);

create index if not exists paper_trades_strategy_closed_idx
  on public.paper_trades (strategy_id, closed_at desc);
