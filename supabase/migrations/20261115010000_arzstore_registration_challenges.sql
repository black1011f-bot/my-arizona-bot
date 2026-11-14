create table if not exists public.arzstore_registration_challenges (
  telegram_id bigint primary key,
  username text not null,
  password_hash text not null,
  code_hash text not null,
  expires_at timestamptz not null,
  sent_count integer not null default 0,
  window_started_at timestamptz not null,
  last_sent_at timestamptz not null,
  blocked_until timestamptz,
  attempts integer not null default 0,
  created_at timestamptz not null default now()
);

alter table public.arzstore_registration_challenges enable row level security;
revoke all on table public.arzstore_registration_challenges from anon, authenticated;
grant all on table public.arzstore_registration_challenges to service_role;
