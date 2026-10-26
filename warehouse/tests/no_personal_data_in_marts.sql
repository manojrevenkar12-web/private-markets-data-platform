-- No column of any model in the build looks like personal data: no e-mail addresses, no IBANs, no names of
-- the personal columns in config/platform.yaml.
select table_name, column_name
from information_schema.columns
where table_schema = '{{ target.schema }}'
  and column_name in ('name', 'first_name', 'last_name', 'email', 'birth_date', 'iban', 'tax_id', 'street', 'phone')
