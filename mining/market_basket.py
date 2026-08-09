"""Deterministic, bounded market-basket analysis with exact JSON itemsets."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Iterator, Sequence
from pathlib import Path
from time import perf_counter

import matplotlib.pyplot as plt
import pandas as pd
from mlxtend.frequent_patterns import apriori, association_rules, fpgrowth
from mlxtend.preprocessing import TransactionEncoder
from sqlalchemy import text
from sqlalchemy.engine import Engine

from etl.config import Settings, get_engine, get_settings
from mining.artifacts import ensure_results_dir, itemset_to_json, utc_timestamp, write_json

DEFAULT_TOP_PRODUCTS = 2_000


class BasketDataError(ValueError):
    """Raised when transaction extraction or rule mining has no valid input."""


def _transaction_chunks(
    engine: Engine,
    *,
    limit: int | None,
    random_state: int,
    chunk_size: int,
) -> Iterator[pd.DataFrame]:
    if limit is not None:
        query = text(
            """
            SELECT
                details.order_id,
                details.product_id
            FROM (
                SELECT order_id
                FROM Fact_Orders
                ORDER BY CRC32(CONCAT(CAST(order_id AS CHAR), ':', :seed)), order_id
                LIMIT :order_limit
            ) sampled_orders
            JOIN Fact_Order_Details details
                ON sampled_orders.order_id = details.order_id
            ORDER BY details.order_id, details.add_to_cart_order
            """
        )
        parameters = {"seed": random_state, "order_limit": limit}
    else:
        query = text(
            """
            SELECT order_id, product_id
            FROM Fact_Order_Details
            ORDER BY order_id, add_to_cart_order
            """
        )
        parameters = None

    with engine.connect() as connection:
        yield from pd.read_sql(
            query,
            connection,
            params=parameters,
            chunksize=chunk_size,
        )


def extract_transactions(
    limit: int | None = None,
    min_items: int = 2,
    *,
    engine: Engine | None = None,
    random_state: int | None = None,
    chunk_size: int | None = None,
    settings: Settings | None = None,
) -> list[list[str]]:
    """Extract complete ordered baskets; a non-NULL limit is a deterministic sample."""
    if limit is not None and limit <= 0:
        raise ValueError("limit must be positive or None for explicit full mode")
    if min_items < 1:
        raise ValueError("min_items must be at least 1")
    resolved = settings or get_settings()
    seed = resolved.mining_random_state if random_state is None else random_state
    read_chunk_size = resolved.chunk_size if chunk_size is None else chunk_size
    if read_chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    warehouse_engine = engine or get_engine(resolved)

    transactions: list[list[str]] = []
    current_order_id: int | None = None
    current_basket: list[str] = []
    extracted_rows = 0
    for chunk in _transaction_chunks(
        warehouse_engine,
        limit=limit,
        random_state=seed,
        chunk_size=read_chunk_size,
    ):
        required = {"order_id", "product_id"}
        missing = sorted(required.difference(chunk.columns))
        if missing:
            raise BasketDataError(f"Transaction query missing columns: {', '.join(missing)}")
        if chunk.loc[:, ["order_id", "product_id"]].isna().any().any():
            raise BasketDataError("Transaction query returned NULL order_id or product_id")

        for row in chunk.itertuples(index=False):
            order_id = int(row.order_id)
            product_id = str(int(row.product_id))
            extracted_rows += 1
            if current_order_id is None:
                current_order_id = order_id
            if order_id != current_order_id:
                if len(current_basket) >= min_items:
                    transactions.append(current_basket)
                current_order_id = order_id
                current_basket = []
            current_basket.append(product_id)

    if current_order_id is not None and len(current_basket) >= min_items:
        transactions.append(current_basket)
    if extracted_rows == 0:
        raise BasketDataError("No order details were extracted")
    if not transactions:
        raise BasketDataError(f"No baskets satisfy min_items={min_items}")
    return transactions


def load_product_catalog(engine: Engine) -> dict[str, str]:
    query = text("SELECT product_id, product_name FROM Dim_Product ORDER BY product_id")
    with engine.connect() as connection:
        products = pd.read_sql(query, connection)
    if products.empty:
        raise BasketDataError("Dim_Product contains no products")
    if products[["product_id", "product_name"]].isna().any().any():
        raise BasketDataError("Dim_Product contains NULL identifiers or names")
    return {
        str(int(row.product_id)): str(row.product_name)
        for row in products.itertuples(index=False)
    }


def create_basket_matrix(
    transactions: list[list[str]],
    top_n_products: int = DEFAULT_TOP_PRODUCTS,
) -> pd.DataFrame:
    """Build a pandas sparse matrix while preserving every basket in the denominator."""
    if not transactions:
        raise BasketDataError("At least one transaction is required")
    if top_n_products <= 0:
        raise ValueError("top_n_products must be positive")

    frequencies = Counter(item for basket in transactions for item in set(basket))
    selected = [
        item
        for item, _ in sorted(frequencies.items(), key=lambda pair: (-pair[1], pair[0]))[
            :top_n_products
        ]
    ]
    if not selected:
        raise BasketDataError("No products are available for basket encoding")
    selected_set = set(selected)
    filtered = [[item for item in basket if item in selected_set] for basket in transactions]

    encoder = TransactionEncoder()
    encoded = encoder.fit(filtered).transform(filtered, sparse=True).tocsc()
    matrix = pd.DataFrame(
        {
            product: pd.arrays.SparseArray.from_spmatrix(encoded.getcol(index))
            for index, product in enumerate(encoder.columns_)
        }
    )
    if len(matrix) != len(transactions):
        raise BasketDataError("Basket encoding changed the transaction denominator")
    return matrix


def run_fpgrowth(df_basket: pd.DataFrame, min_support: float = 0.01) -> pd.DataFrame:
    if not 0 < min_support <= 1:
        raise ValueError("min_support must be in (0, 1]")
    if df_basket.empty or df_basket.shape[1] == 0:
        raise BasketDataError("Basket matrix is empty")
    itemsets = fpgrowth(
        df_basket,
        min_support=min_support,
        use_colnames=True,
        max_len=None,
    )
    if itemsets.empty:
        raise BasketDataError("FP-Growth found no itemsets; lower min_support")
    itemsets["length"] = itemsets["itemsets"].map(len)
    return itemsets.sort_values(["support", "length"], ascending=[False, True])


def run_apriori(df_basket: pd.DataFrame, min_support: float = 0.01) -> pd.DataFrame:
    if not 0 < min_support <= 1:
        raise ValueError("min_support must be in (0, 1]")
    if df_basket.empty or df_basket.shape[1] == 0:
        raise BasketDataError("Basket matrix is empty")
    itemsets = apriori(
        df_basket,
        min_support=min_support,
        use_colnames=True,
        max_len=None,
    )
    if itemsets.empty:
        raise BasketDataError("Apriori found no itemsets; lower min_support")
    itemsets["length"] = itemsets["itemsets"].map(len)
    return itemsets.sort_values(["support", "length"], ascending=[False, True])


def generate_rules(
    frequent_itemsets: pd.DataFrame,
    metric: str = "confidence",
    min_threshold: float = 0.3,
) -> pd.DataFrame:
    if frequent_itemsets.empty:
        raise BasketDataError("Frequent itemsets are empty")
    rules = association_rules(
        frequent_itemsets,
        metric=metric,
        min_threshold=min_threshold,
        support_only=False,
    )
    if rules.empty:
        raise BasketDataError(
            f"No association rules satisfy {metric}>={min_threshold}; lower the threshold"
        )
    return rules.sort_values(
        ["lift", "confidence", "support"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


def _display_items(items: object, catalog: dict[str, str] | None) -> str:
    identifiers = sorted(str(item) for item in items)
    if catalog is None:
        return ", ".join(identifiers)
    return ", ".join(catalog.get(item, f"product:{item}") for item in identifiers)


def display_top_rules(
    rules: pd.DataFrame,
    n: int = 20,
    *,
    catalog: dict[str, str] | None = None,
) -> None:
    if n <= 0:
        raise ValueError("n must be positive")
    for rank, row in enumerate(rules.head(n).itertuples(index=False), start=1):
        antecedents = _display_items(row.antecedents, catalog)
        consequents = _display_items(row.consequents, catalog)
        print(
            f"{rank:>2}. {antecedents} -> {consequents} "
            f"(support={row.support:.4f}, confidence={row.confidence:.3f}, lift={row.lift:.3f})"
        )


def visualize_rules(
    rules: pd.DataFrame,
    top_n: int = 50,
    *,
    output_dir: Path | str | None = None,
) -> Path:
    if rules.empty:
        raise BasketDataError("Cannot visualize empty rules")
    selected = rules.head(top_n)
    figure, axis = plt.subplots(figsize=(9, 7))
    scatter = axis.scatter(
        selected["support"],
        selected["confidence"],
        c=selected["lift"],
        cmap="viridis",
        alpha=0.7,
    )
    axis.set(title="Association-rule quality", xlabel="Support", ylabel="Confidence")
    figure.colorbar(scatter, ax=axis, label="Lift")
    figure.tight_layout()
    path = ensure_results_dir(output_dir) / "association_rules.png"
    figure.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(figure)
    return path


def save_rules(
    rules: pd.DataFrame,
    filename: Path | str | None = None,
    *,
    catalog: dict[str, str] | None = None,
) -> Path:
    """Save exact ID and display-name itemsets as JSON arrays inside CSV cells."""
    if rules.empty:
        raise BasketDataError("Cannot save empty rules")
    path = (
        Path(filename)
        if filename is not None
        else ensure_results_dir() / "association_rules.csv"
    )
    path.parent.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, object]] = []
    for row in rules.itertuples(index=False):
        antecedent_ids = frozenset(str(item) for item in row.antecedents)
        consequent_ids = frozenset(str(item) for item in row.consequents)
        record: dict[str, object] = {
            "antecedents_json": itemset_to_json(antecedent_ids),
            "consequents_json": itemset_to_json(consequent_ids),
            "support": float(row.support),
            "confidence": float(row.confidence),
            "lift": float(row.lift),
            "leverage": float(row.leverage),
            "conviction": float(row.conviction),
        }
        if catalog is not None:
            record["antecedent_names_json"] = itemset_to_json(
                catalog.get(item, f"product:{item}") for item in antecedent_ids
            )
            record["consequent_names_json"] = itemset_to_json(
                catalog.get(item, f"product:{item}") for item in consequent_ids
            )
        records.append(record)
    pd.DataFrame.from_records(records).to_csv(path, index=False)
    return path


def save_frequent_itemsets(
    itemsets: pd.DataFrame,
    path: Path,
    *,
    catalog: dict[str, str] | None = None,
) -> Path:
    records = []
    for row in itemsets.itertuples(index=False):
        identifiers = frozenset(str(item) for item in row.itemsets)
        record: dict[str, object] = {
            "itemsets_json": itemset_to_json(identifiers),
            "support": float(row.support),
            "length": len(identifiers),
        }
        if catalog is not None:
            record["item_names_json"] = itemset_to_json(
                catalog.get(item, f"product:{item}") for item in identifiers
            )
        records.append(record)
    pd.DataFrame.from_records(records).to_csv(path, index=False)
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--order-limit", type=int, help="Deterministic sample size")
    mode.add_argument("--full", action="store_true", help="Explicitly process every order")
    parser.add_argument("--seed", type=int, help="Override MINING_RANDOM_STATE")
    parser.add_argument("--min-items", type=int, default=2)
    parser.add_argument("--top-products", type=int, default=DEFAULT_TOP_PRODUCTS)
    parser.add_argument("--min-support", type=float, default=0.01)
    parser.add_argument("--min-confidence", type=float, default=0.3)
    parser.add_argument("--algorithm", choices=("fpgrowth", "apriori"), default="fpgrowth")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--no-plot", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = get_settings()
    random_state = settings.mining_random_state if args.seed is None else args.seed
    order_limit = None if args.full else (args.order_limit or settings.mining_order_limit)
    if order_limit is not None and order_limit <= 0:
        raise ValueError("order limit must be positive")
    output_dir = ensure_results_dir(args.output_dir)
    engine = get_engine(settings)
    mode_label = "FULL DATASET (explicit)" if order_limit is None else (
        f"deterministic sample of at most {order_limit:,} orders (seed={random_state})"
    )
    print(f"Market-basket input: {mode_label}")

    started = perf_counter()
    transactions = extract_transactions(
        order_limit,
        args.min_items,
        engine=engine,
        random_state=random_state,
        chunk_size=settings.chunk_size,
        settings=settings,
    )
    matrix = create_basket_matrix(transactions, args.top_products)
    mining_function = run_fpgrowth if args.algorithm == "fpgrowth" else run_apriori
    itemsets = mining_function(matrix, args.min_support)
    rules = generate_rules(itemsets, min_threshold=args.min_confidence)
    catalog = load_product_catalog(engine)
    display_top_rules(rules, catalog=catalog)
    rules_path = save_rules(
        rules,
        output_dir / "association_rules.csv",
        catalog=catalog,
    )
    itemsets_path = save_frequent_itemsets(
        itemsets,
        output_dir / "frequent_itemsets.csv",
        catalog=catalog,
    )
    plot_path = None if args.no_plot else visualize_rules(rules, output_dir=output_dir)
    metadata = {
        "artifact_schema_version": 1,
        "created_at": utc_timestamp(),
        "mode": "full" if order_limit is None else "deterministic_sample",
        "requested_order_limit": order_limit,
        "random_state": random_state,
        "min_items": args.min_items,
        "transactions": len(transactions),
        "top_products": args.top_products,
        "basket_matrix_rows": int(matrix.shape[0]),
        "basket_matrix_columns": int(matrix.shape[1]),
        "algorithm": args.algorithm,
        "min_support": args.min_support,
        "min_confidence": args.min_confidence,
        "frequent_itemsets": len(itemsets),
        "association_rules": len(rules),
        "elapsed_seconds": perf_counter() - started,
        "artifacts": {
            "rules": rules_path.name,
            "itemsets": itemsets_path.name,
            "plot": None if plot_path is None else plot_path.name,
        },
    }
    write_json(output_dir / "market_basket_metadata.json", metadata)
    print(
        f"Mined {len(rules):,} rules from {len(transactions):,} baskets in "
        f"{metadata['elapsed_seconds']:.1f}s. Artifacts: {output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
