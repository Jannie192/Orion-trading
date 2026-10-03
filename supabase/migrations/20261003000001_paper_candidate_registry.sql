alter table public.strategy_versions
  add column if not exists candidate_parameters jsonb,
  add column if not exists validation jsonb,
  add column if not exists source_experiment_id uuid;

create index if not exists strategy_versions_paper_candidate_idx
  on public.strategy_versions (status, instrument, timeframe)
  where status = 'PAPER_CANDIDATE';
