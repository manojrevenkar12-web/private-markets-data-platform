# 1. Every run builds into its own schema and is published only after its gates

Status: accepted

Clients see NAVs and capital call status. A model change or a bad source must not reach them half-built. Each
run builds the dbt project into `build_<run id>`, the gates in `config/platform.yaml` run against that schema,
and only a build no blocking gate stops replaces the views in `serving`, all in one transaction. The API and
console read `serving` only.

Consequences: a blocked build costs nothing but disk until cleanup (the newest three are kept); every run has a
diff against the build clients saw; a fund NAV that moves more than the threshold without a new statement
stops the publish, and a second person can approve it (`pmd approve`) once tests have passed.
