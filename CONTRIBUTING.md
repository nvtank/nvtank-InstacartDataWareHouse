# Contributing

Thanks for improving Instacart Decision Intelligence. Contributions should preserve its
central promise: every displayed metric, ETL result, and mining artifact must have an
explicit and testable data contract.

## Development setup

The package supports Python 3.11 through 3.13. Docker with the Compose plugin is optional
for offline development and required for the local live warehouse workflow.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install --editable ".[dev]"
```

Do not commit `.env`, source CSV files, generated ETL reports, mining artifacts, coverage
files, or database volumes.

## Fast offline workflow

The default development checks require neither MariaDB nor network access after dependencies
are installed:

```bash
ruff check etl dashboard mining tests
MPLBACKEND=Agg pytest -q
```

The current suite exercises ETL contracts and orchestration, all six dashboard pages in demo
mode, repository safety, and deterministic mining/recommendation behavior. Keep new tests
isolated from external services unless the change explicitly introduces a separately marked
integration suite.

To run the dashboard against deterministic representative aggregates:

```bash
DASHBOARD_MODE=demo bash run_dashboard.sh
```

Or use the containerized workflow:

```bash
make demo
```

The dashboard is available at `http://localhost:8501` by default.

## Live warehouse workflow

The full dataset is distributed separately. Place these six files under `./data`:

```text
aisles.csv
departments.csv
products.csv
orders.csv
order_products__prior.csv
order_products__train.csv
```

Copy the environment template and set local-only credentials:

```bash
cp .env.example .env
```

Then run the ordered workflow:

```bash
make db
make schema
make etl
make live
```

`make etl` also depends on the schema target, so the explicit sequence is primarily useful
when diagnosing a stage. Live mode is fail-closed: it must not silently display demo values
when the warehouse is unavailable.

Useful operational commands:

```bash
make validate
make logs
make down
```

`make down` preserves the named MariaDB volume. Removing that volume is intentionally not a
standard project target.

## Project contracts

### ETL

- Validate source presence and shape before opening write transactions.
- Keep transformations pure: return a new frame and do not mutate caller-owned input.
- Stream large fact inputs in configurable chunks; do not concatenate the full corpus.
- Preserve the first-order `days_since_prior_order = NULL` contract.
- Refuse duplicate appends into populated ETL targets.
- Require both `--reset-data` and `--yes` for destructive reloads.
- Use transaction scopes that are narrow enough to fail and retry predictably.
- Add or update post-load reconciliation whenever a derived metric or relationship changes.
- Keep CLI errors non-zero and keep the JSON execution report useful on both success and
  failure.
- Never interpolate credentials into logs, reports, or exception messages.

For a configuration and file check without a database connection:

```bash
instacart-etl --dry-run
```

For warehouse checks without loading data:

```bash
instacart-etl --validate-only
```

### SQL schema

- Keep normal schema scripts idempotent. Destructive database reset belongs only in the
  explicitly named reset script.
- State table grain in comments and enforce it with keys or quality checks.
- Remember that MariaDB partition keys constrain primary and unique keys.
- Because partitioned facts do not use foreign keys, every relationship change needs ETL
  validation and a warehouse reconciliation query.
- Add an index only with a named access pattern and, for performance claims, measured
  `EXPLAIN` and timing evidence.

### Dashboard

- Pages depend on `AnalyticsRepository`; do not put connection creation or ad hoc SQL in page
  modules.
- Preserve the semantics of `demo`, `live`, and `auto` source modes.
- Label representative data visibly and never describe it as a live query result.
- Bind values as SQL parameters. Dynamic identifiers must first resolve through the fixed
  table whitelist.
- Catch infrastructure failures at repository/UI boundaries and display sanitized messages.
- Reconcile percentages to the complete denominator before applying a top-N display filter.
- Provide a table or CSV fallback for new visualizations when practical.
- Add a Streamlit `AppTest` path for every new page or navigation branch.

### Mining and recommendations

- Every stochastic operation needs an explicit seed and deterministic tie-breaking.
- Keep potentially expensive work bounded by default; full-dataset execution must require an
  explicit option.
- Retain sparse representations for basket data and preserve all sampled baskets in support
  denominators.
- Serialize itemsets as JSON arrays. Never reintroduce comma-splitting for product names.
- Version artifact schemas and record the parameters, input size, metrics, timestamp, and
  output filenames needed to reproduce a run.
- A rule applies only when its complete antecedent is an exact cart subset.
- Keep identifier and product-name rankings in one resolved item space during fusion.
- Exclude cart contents from every recommendation source.
- Do not add model-quality or business-impact claims without a documented evaluation set and
  result.

## Testing expectations

Add the smallest test that would have caught the regression. Prefer temporary paths, small
data frames, fake engines/connections, and deterministic seeds.

Before requesting review, run:

```bash
ruff check etl dashboard mining tests
MPLBACKEND=Agg pytest -q
```

Changes to mining code must also pass the warning policy used by CI:

```bash
MPLBACKEND=Agg pytest \
  tests/test_mining_artifacts.py \
  tests/test_mining_clustering.py \
  tests/test_mining_market_basket.py \
  tests/test_mining_recommendation.py \
  -W error::FutureWarning
```

GitHub Actions is configured for Python 3.11 and 3.13. Its coverage gates are 90% for the
selected ETL modules and 80% for the complete `dashboard` package. Do not weaken a gate to
make an unrelated change pass; add meaningful coverage or explain why the measured scope
should change.

## Documentation and evidence

- Update documentation whenever a command, environment variable, artifact schema, table
  grain, or source-mode behavior changes.
- Separate code-backed capability from runtime evidence.
- Mark demo values as representative aggregates.
- Put hardware, dataset checksums, commands, repeated timings, metrics, and limitations in a
  benchmark report before making scale or performance claims.
- Use the evidence boundary in `docs/portfolio.md` when writing CV or interview material.

## Commit and review workflow

1. Create a focused branch from the current mainline.
2. Keep each commit to one reviewable purpose and use an imperative conventional prefix such
   as `feat:`, `fix:`, `test:`, `docs:`, `refactor:`, or `chore:`.
3. Preserve unrelated working-tree changes; never hide them inside your commit.
4. In the review description, state the problem, design choice, affected data contract,
   verification commands, observed results, and any live validation still pending.
5. Call out destructive SQL, artifact incompatibility, benchmark assumptions, or changes to
   demo/live semantics explicitly.

By contributing, you agree that your contribution may be distributed under this project's
MIT License.
