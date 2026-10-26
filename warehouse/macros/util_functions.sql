{# Functions the models use, created before every run in pmd_util. #}
{% macro create_util_functions() %}
create schema if not exists pmd_util;

-- XIRR: the annual rate r at which sum(amount_i / (1+r)^((d_i - d_0)/365)) = 0. Newton steps from 10 %,
-- falling back to bisection; null when the cash flows have no sign change or do not converge.
create or replace function pmd_util.xirr(p_dates date[], p_amounts numeric[])
returns numeric language plpgsql immutable as $$
declare
  r double precision := 0.10;
  f double precision; df double precision; t double precision; v double precision;
  lo double precision := -0.99; hi double precision := 10.0; flo double precision; fmid double precision;
  d0 date; i int; k int; n int := coalesce(array_length(p_dates, 1), 0);
  has_pos boolean := false; has_neg boolean := false;
begin
  if n < 2 then return null; end if;
  d0 := (select min(x) from unnest(p_dates) x);
  for i in 1..n loop
    if p_amounts[i] > 0 then has_pos := true; elsif p_amounts[i] < 0 then has_neg := true; end if;
  end loop;
  if not (has_pos and has_neg) then return null; end if;
  for k in 1..60 loop
    f := 0; df := 0;
    for i in 1..n loop
      t := (p_dates[i] - d0) / 365.0;
      v := p_amounts[i] / power(1 + r, t);
      f := f + v;
      df := df - t * v / (1 + r);
    end loop;
    if abs(f) < 1e-7 then return round(r::numeric, 6); end if;
    exit when df = 0;
    r := r - f / df;
    exit when r <= -0.99 or r > 10 or r <> r;
  end loop;
  -- bisection
  flo := 0; for i in 1..n loop flo := flo + p_amounts[i] / power(1 + lo, (p_dates[i] - d0) / 365.0); end loop;
  for k in 1..200 loop
    r := (lo + hi) / 2;
    fmid := 0; for i in 1..n loop fmid := fmid + p_amounts[i] / power(1 + r, (p_dates[i] - d0) / 365.0); end loop;
    if abs(fmid) < 1e-6 then return round(r::numeric, 6); end if;
    if sign(fmid) = sign(flo) then lo := r; flo := fmid; else hi := r; end if;
  end loop;
  return null;
end $$;
{% endmacro %}

{% macro quarter_end(d) -%}
  (date_trunc('quarter', {{ d }}) + interval '3 months' - interval '1 day')::date
{%- endmacro %}

{% macro as_of() -%}
  date '{{ var("as_of") }}'
{%- endmacro %}

{% macro usd_per_eur(d) -%}
  (select fx.usd_per_eur from {{ ref('stg_fx_rates') }} fx where fx.rate_date <= {{ d }} order by fx.rate_date desc limit 1)
{%- endmacro %}
