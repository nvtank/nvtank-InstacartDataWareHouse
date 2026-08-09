# Data-mining and recommendation lab

This module provides three command-line workflows over the loaded Instacart warehouse:

1. reproducible K-Means customer clustering;
2. deterministic, bounded-by-default market-basket mining with FP-Growth or Apriori;
3. exact-set association-rule and cluster-popularity recommendation fused by weighted reciprocal rank.

The commands write local experiment artifacts. They do not train during dashboard startup, serve an online API, or modify warehouse tables.

## Prerequisites

Install the project and load the seven-table warehouse before running any mining command:

```bash
make install
cp .env.example .env
# Edit .env and place the six source CSV files under ./data.
make etl
source .venv/bin/activate
```

The commands read `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, and `DB_NAME` through the shared ETL configuration. Their default output directory is `mining/results/`, which is intentionally ignored by Git.

## Quick commands

Run deterministic clustering without rendering plots:

```bash
instacart-cluster --max-k 10 --silhouette-sample-size 10000 --no-plots
```

Mine a deterministic sample of at most 100,000 complete orders, restricted to the 2,000 most frequent products:

```bash
instacart-basket \
  --order-limit 100000 \
  --top-products 2000 \
  --min-support 0.01 \
  --min-confidence 0.3 \
  --no-plot
```

After both commands have produced artifacts, request a hybrid ranking. Replace the example user and cart with a `user_id` from `cluster_labels.csv` and exact product names present in the rule artifact:

```bash
instacart-recommend \
  --user-id 1 \
  --cart "Banana" "Bag of Organic Bananas" \
  --top-n 10
```

Use `--help` on any command for the complete option list.

## Customer clustering

`instacart-cluster` aggregates one row per user with at least `--min-orders` orders. The model standardizes these four features before fitting K-Means:

- `total_orders`
- `avg_basket_size`
- `avg_reorder_ratio`
- `avg_days_between_orders`

By default, candidate K values run from 2 through `min(--max-k, number_of_users - 1)`. The command chooses the candidate with the highest silhouette score unless `--clusters` supplies an explicit K. Both candidate selection and final fitting use the configured seed and K-Means uses `n_init=10` and `max_iter=300`.

Silhouette scoring is bounded by `--silhouette-sample-size` (default 10,000) and deterministically includes every cluster in the scoring sample. Model fitting still uses every eligible user. When plots are enabled, the PCA scatter renders at most 20,000 deterministic points; clustering labels are not sampled.

Useful controls:

```bash
instacart-cluster \
  --min-orders 5 \
  --max-k 8 \
  --clusters 4 \
  --silhouette-sample-size 5000 \
  --seed 42 \
  --output-dir artifacts/clustering-run
```

Omit `--clusters` to restore silhouette-based K selection. Add `--no-plots` to skip both PNG files.

### Clustering artifacts

All JSON metadata currently uses `artifact_schema_version: 1`.

| File | Schema or contents |
| --- | --- |
| `cluster_profiles.csv` | `cluster`, `cluster_name`, `num_users`, `total_orders_mean`, `total_orders_median`, `avg_basket_size_mean`, `avg_reorder_ratio_mean`, `avg_days_between_orders_mean` |
| `cluster_labels.csv` | `user_id`, `cluster`, sorted by `user_id` |
| `kmeans_model.joblib` | Fitted scikit-learn `KMeans` object, including recorded training metrics |
| `standard_scaler.joblib` | Fitted `StandardScaler` for the four ordered feature columns |
| `clustering_metadata.json` | Feature order, minimum-order filter, row count, seed, silhouette bound, selected K and source, per-candidate inertia/silhouette values, final training metrics, optional PCA metrics, embedded cluster profiles, and artifact filenames |
| `cluster_selection.png` | Optional candidate-K inertia and silhouette chart |
| `clusters_pca.png` | Optional two-dimensional PCA projection coloured by cluster |

Final training metrics in the metadata are `silhouette`, `davies_bouldin`, and `inertia`. They describe the fitted sample; this repository does not publish fixed expected values.

### Two different segment concepts

The warehouse and mining module deliberately expose different contracts:

| Contract | Source | Meaning | Current consumer |
| --- | --- | --- | --- |
| Rule-based segment | `Dim_User.user_segment` | `VIP` for 50+ orders, `Frequent` for 20–49, `Regular` for 10–19, and `New` for fewer than 10 | Dashboard customer page |
| K-Means cluster | `cluster_labels.csv` | Data-driven assignment using the four standardized features above | Hybrid recommender and offline analysis |

`cluster_name` is a post-hoc description derived from each cluster's mean order count (`VIP Customers`, `Frequent Shoppers`, `Regular Customers`, or `Occasional Buyers`). It does not turn the K-Means assignment into the ETL rule and multiple clusters may receive the same description.

## Market-basket mining

`instacart-basket` selects complete orders deterministically by sorting a seeded CRC32 value of `order_id`. `--order-limit` therefore limits orders before joining their line items; it never truncates a basket. If no mode flag is supplied, `MINING_ORDER_LIMIT` supplies the bound (100,000 in `.env.example`).

The command then:

1. removes baskets below `--min-items` (default 2);
2. keeps the `--top-products` most frequent product identifiers (default 2,000);
3. builds a pandas sparse transaction matrix while retaining one row per selected basket, including rows emptied by product pruning;
4. runs FP-Growth by default, or Apriori with `--algorithm apriori`;
5. filters rules by `--min-confidence` and writes exact ID/name itemsets as JSON arrays inside CSV cells.

Keeping emptied rows preserves the selected-transaction denominator used by support. JSON arrays avoid ambiguous comma-delimited parsing when a product name itself contains a comma.

Sample and full modes are mutually exclusive:

```bash
# Reproducible bounded experiment
instacart-basket --order-limit 25000 --seed 42 --no-plot

# Explicitly process every warehouse order
instacart-basket --full
```

`--full` is intentionally opt-in. Its runtime and memory demand depend on the loaded data, thresholds, and product bound.

### Market-basket artifacts

| File | Schema or contents |
| --- | --- |
| `frequent_itemsets.csv` | `itemsets_json`, `support`, `length`, `item_names_json` |
| `association_rules.csv` | `antecedents_json`, `consequents_json`, `support`, `confidence`, `lift`, `leverage`, `conviction`, `antecedent_names_json`, `consequent_names_json` |
| `market_basket_metadata.json` | Schema version, creation time, sample/full mode, requested order limit, seed, minimum basket size, retained transaction count, product bound, matrix shape, algorithm, thresholds, result counts, elapsed seconds, and artifact filenames |
| `association_rules.png` | Optional support-versus-confidence scatter plot coloured by lift |

The CLI supplies the product catalog, so its CSV artifacts contain both identifier and name JSON columns. The lower-level save helpers can omit name columns when no catalog is passed.

## Hybrid recommendation

`instacart-recommend` reads `association_rules.csv` and `cluster_labels.csv` from `mining/results/` unless `--rules` or `--clusters` points elsewhere. It also needs the live warehouse to rank products purchased by users in the target user's cluster.

The rule ranking applies a rule only when its complete antecedent is an exact subset of the cart. The CLI matches exact product names; it does not use substring matching. The cluster ranking uses a connection-local temporary table, joins cluster members through orders and order details, ranks product popularity, and drops the temporary table before returning.

The two independent rankings are combined with weighted reciprocal-rank fusion:

- rule weight: `0.6` by default;
- cluster weight: `0.4` by default;
- RRF constant: `60` by default.

These weights affect rank fusion; they are not probabilities. Cart items are excluded from the output. The command prints the final ranking and score but does not write a recommendation artifact.

Use artifacts from a custom run like this:

```bash
instacart-recommend \
  --user-id 1 \
  --cart "Banana" \
  --rules artifacts/basket-run/association_rules.csv \
  --clusters artifacts/clustering-run/cluster_labels.csv \
  --rule-weight 0.6 \
  --cluster-weight 0.4 \
  --rrf-k 60
```

## Verification

The mining tests are deterministic and do not require a live warehouse:

```bash
MPLBACKEND=Agg .venv/bin/python -m pytest \
  tests/test_mining_artifacts.py \
  tests/test_mining_clustering.py \
  tests/test_mining_market_basket.py \
  tests/test_mining_recommendation.py \
  -W error::FutureWarning

.venv/bin/python -m ruff check mining tests/test_mining_*.py
```

## Known limitations

- Reproducibility assumes the same warehouse contents, package versions, seed, and CLI parameters. Cluster numeric IDs have no stable business meaning across changed runs.
- K-Means model fitting uses all eligible users. Only silhouette evaluation and rendered PCA points are bounded.
- Market-basket sampling and top-product pruning trade coverage for bounded local execution. Results describe the selected transaction population, not every possible product relationship.
- FP-Growth and Apriori currently have no maximum itemset length. Lower support thresholds or full mode can still create combinatorial memory and runtime pressure.
- Association rules describe co-occurrence, not causality. Their support and confidence are not recommendation accuracy metrics.
- `evaluate_recommendations` reports descriptive rule statistics only; there is no temporal holdout, precision/recall evaluation, online experiment, or serving API.
- Users missing from `cluster_labels.csv` have no cluster-popularity ranking. Carts with no exact matching antecedent have no rule ranking, so the final result can be partial or empty.
- Only load `.joblib` artifacts produced by a trusted run; joblib files are not a safe interchange format for untrusted input.
