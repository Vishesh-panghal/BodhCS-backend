-- User profile table for authenticated app users.
-- Run this in Supabase SQL editor before using /api/v1/me endpoints.

create table if not exists public.user_profiles (
  uid text primary key,
  name text,
  degree text,
  institution_name text,
  age_group text,
  learning_goal text,
  phone_number text,
  photo_url text,
  daily_planned_minutes int not null default 24,
  target_exam text not null default 'Semester Mastery',
  current_level text not null default 'Intermediate',
  focus_topic text not null default 'Operating Systems',
  onboarding_completed boolean not null default false,
  personal_details_completed boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.user_profiles add column if not exists degree text;
alter table public.user_profiles add column if not exists institution_name text;
alter table public.user_profiles add column if not exists age_group text;
alter table public.user_profiles add column if not exists learning_goal text;
alter table public.user_profiles add column if not exists personal_details_completed boolean not null default false;

create or replace function public.set_updated_at_user_profiles()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_set_updated_at_user_profiles on public.user_profiles;
create trigger trg_set_updated_at_user_profiles
before update on public.user_profiles
for each row execute function public.set_updated_at_user_profiles();

alter table public.user_profiles enable row level security;

-- Optional: lock direct client access and keep writes only through backend service role.
drop policy if exists "deny_all_select_user_profiles" on public.user_profiles;
create policy "deny_all_select_user_profiles"
on public.user_profiles
for select
to authenticated
using (false);

drop policy if exists "deny_all_update_user_profiles" on public.user_profiles;
create policy "deny_all_update_user_profiles"
on public.user_profiles
for update
to authenticated
using (false)
with check (false);

drop policy if exists "deny_all_insert_user_profiles" on public.user_profiles;
create policy "deny_all_insert_user_profiles"
on public.user_profiles
for insert
to authenticated
with check (false);
