"""Reproducible K-Means customer segmentation over warehouse aggregates."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import davies_bouldin_score, silhouette_score
from sklearn.preprocessing import StandardScaler
from sqlalchemy import text
from sqlalchemy.engine import Engine

from etl.config import Settings, get_engine, get_settings
from mining.artifacts import dump_joblib, ensure_results_dir, utc_timestamp, write_json

FEATURE_COLUMNS = (
    "total_orders",
    "avg_basket_size",
    "avg_reorder_ratio",
    "avg_days_between_orders",
)
DEFAULT_SILHOUETTE_SAMPLE_SIZE = 10_000

sns.set_style("whitegrid")


class ClusteringDataError(ValueError):
    """Raised when warehouse features cannot produce a meaningful clustering model."""


def extract_features(
    engine: Engine | None = None,
    *,
    min_orders: int = 3,
    settings: Settings | None = None,
) -> pd.DataFrame:
    """Extract user features directly from Dim_User and Fact_Orders."""
    if min_orders < 2:
        raise ValueError("min_orders must be at least 2")
    resolved = settings or get_settings()
    warehouse_engine = engine or get_engine(resolved)
    query = text(
        """
        SELECT
            users.user_id,
            COUNT(*) AS total_orders,
            AVG(orders.total_items) AS avg_basket_size,
            AVG(orders.reorder_ratio) AS avg_reorder_ratio,
            AVG(orders.days_since_prior_order) AS avg_days_between_orders
        FROM Dim_User users
        JOIN Fact_Orders orders ON users.user_id = orders.user_id
        WHERE orders.total_items > 0
        GROUP BY users.user_id
        HAVING COUNT(*) >= :min_orders
        ORDER BY users.user_id
        """
    )
    with warehouse_engine.connect() as connection:
        features = pd.read_sql(query, connection, params={"min_orders": min_orders})
    _feature_matrix(features)
    return features


def _feature_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in ("user_id", *FEATURE_COLUMNS) if column not in frame]
    if missing:
        raise ClusteringDataError(f"Missing clustering columns: {', '.join(missing)}")
    if len(frame) < 3:
        raise ClusteringDataError("At least three active users are required for clustering")

    matrix = frame.loc[:, FEATURE_COLUMNS].apply(pd.to_numeric, errors="coerce")
    values = matrix.to_numpy(dtype=float)
    if not np.isfinite(values).all():
        invalid = matrix.columns[~np.isfinite(values).all(axis=0)].tolist()
        raise ClusteringDataError(
            "Clustering features contain NULL or non-finite values: " + ", ".join(invalid)
        )
    return matrix


def _bounded_silhouette(
    values: np.ndarray,
    labels: np.ndarray,
    *,
    sample_size: int,
    random_state: int,
) -> float:
    if sample_size < 2:
        raise ValueError("silhouette sample size must be at least 2")
    if len(values) != len(labels):
        raise ClusteringDataError("Feature rows and cluster labels must have equal length")

    unique_labels = np.unique(labels)
    if len(unique_labels) < 2 or len(unique_labels) >= len(values):
        raise ClusteringDataError(
            "Silhouette scoring requires between 2 and number_of_rows - 1 clusters"
        )

    # sklearn samples rows without stratification, which can create an invalid
    # sample containing one row per label (or only one label). Seed one row from
    # every cluster, then fill the remaining deterministic budget at random.
    bounded_size = min(
        max(sample_size, len(unique_labels) + 1),
        len(values),
    )
    if bounded_size == len(values):
        return float(silhouette_score(values, labels))

    rng = np.random.default_rng(random_state)
    selected = [
        int(rng.choice(np.flatnonzero(labels == label))) for label in unique_labels
    ]
    available = np.setdiff1d(np.arange(len(values)), selected, assume_unique=True)
    extra = rng.choice(
        available,
        size=bounded_size - len(selected),
        replace=False,
    )
    indices = np.sort(np.concatenate((np.asarray(selected, dtype=int), extra)))
    return float(silhouette_score(values[indices], labels[indices]))


def find_optimal_k(
    X_scaled: np.ndarray,
    max_k: int = 10,
    *,
    random_state: int = 42,
    silhouette_sample_size: int = DEFAULT_SILHOUETTE_SAMPLE_SIZE,
    output_dir: Path | str | None = None,
) -> tuple[list[float], list[float], int]:
    """Select K by a deterministic, bounded silhouette score."""
    if len(X_scaled) < 3:
        raise ClusteringDataError("At least three rows are required to select K")
    largest_k = min(max_k, len(X_scaled) - 1)
    if largest_k < 2:
        raise ClusteringDataError("No valid K candidates are available")

    candidate_k = list(range(2, largest_k + 1))
    inertias: list[float] = []
    silhouette_scores: list[float] = []
    for k in candidate_k:
        model = KMeans(n_clusters=k, random_state=random_state, n_init=10, max_iter=300)
        labels = model.fit_predict(X_scaled)
        inertias.append(float(model.inertia_))
        silhouette_scores.append(
            _bounded_silhouette(
                X_scaled,
                labels,
                sample_size=silhouette_sample_size,
                random_state=random_state,
            )
        )

    optimal_k = candidate_k[int(np.argmax(silhouette_scores))]
    if output_dir is not None:
        destination = ensure_results_dir(output_dir) / "cluster_selection.png"
        figure, (inertia_axis, silhouette_axis) = plt.subplots(1, 2, figsize=(14, 5))
        inertia_axis.plot(candidate_k, inertias, "o-")
        inertia_axis.set(title="K-Means inertia", xlabel="K", ylabel="Inertia")
        silhouette_axis.plot(candidate_k, silhouette_scores, "o-")
        silhouette_axis.set(title="Bounded silhouette score", xlabel="K", ylabel="Score")
        figure.tight_layout()
        figure.savefig(destination, dpi=200, bbox_inches="tight")
        plt.close(figure)
    return inertias, silhouette_scores, optimal_k


def train_kmeans(
    frame: pd.DataFrame,
    n_clusters: int = 4,
    *,
    random_state: int = 42,
    silhouette_sample_size: int = DEFAULT_SILHOUETTE_SAMPLE_SIZE,
) -> tuple[pd.DataFrame, KMeans, StandardScaler, np.ndarray]:
    """Fit the selected K and return labels plus reusable preprocessing artifacts."""
    matrix = _feature_matrix(frame)
    if not 2 <= n_clusters < len(matrix):
        raise ValueError("n_clusters must be between 2 and number_of_users - 1")
    scaler = StandardScaler()
    scaled = scaler.fit_transform(matrix)
    model = KMeans(
        n_clusters=n_clusters,
        random_state=random_state,
        n_init=10,
        max_iter=300,
    )
    clustered = frame.copy()
    clustered["cluster"] = model.fit_predict(scaled)
    model.training_metrics_ = {
        "silhouette": _bounded_silhouette(
            scaled,
            model.labels_,
            sample_size=silhouette_sample_size,
            random_state=random_state,
        ),
        "davies_bouldin": float(davies_bouldin_score(scaled, model.labels_)),
        "inertia": float(model.inertia_),
    }
    return clustered, model, scaler, scaled


def visualize_clusters(
    frame: pd.DataFrame,
    X_scaled: np.ndarray,
    *,
    output_dir: Path | str | None = None,
    random_state: int = 42,
    max_points: int = 20_000,
) -> dict[str, float]:
    """Save a bounded PCA projection without changing training labels."""
    destination = ensure_results_dir(output_dir)
    pca = PCA(n_components=2, random_state=random_state)
    projection = pca.fit_transform(X_scaled)
    if len(frame) > max_points:
        rng = np.random.default_rng(random_state)
        selected = np.sort(rng.choice(len(frame), size=max_points, replace=False))
    else:
        selected = np.arange(len(frame))

    figure, axis = plt.subplots(figsize=(11, 8))
    scatter = axis.scatter(
        projection[selected, 0],
        projection[selected, 1],
        c=frame.iloc[selected]["cluster"],
        cmap="viridis",
        alpha=0.55,
        s=18,
    )
    axis.set(title="Customer clusters (PCA projection)", xlabel="PC1", ylabel="PC2")
    figure.colorbar(scatter, ax=axis, label="Cluster")
    figure.tight_layout()
    figure.savefig(destination / "clusters_pca.png", dpi=200, bbox_inches="tight")
    plt.close(figure)
    return {
        "pc1_explained_variance": float(pca.explained_variance_ratio_[0]),
        "pc2_explained_variance": float(pca.explained_variance_ratio_[1]),
    }


def _cluster_name(mean_orders: float) -> str:
    if mean_orders >= 50:
        return "VIP Customers"
    if mean_orders >= 20:
        return "Frequent Shoppers"
    if mean_orders >= 10:
        return "Regular Customers"
    return "Occasional Buyers"


def profile_clusters(
    frame: pd.DataFrame,
    *,
    output_dir: Path | str | None = None,
) -> pd.DataFrame:
    required = {"user_id", "cluster", *FEATURE_COLUMNS}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ClusteringDataError(f"Missing profile columns: {', '.join(missing)}")
    profiles = (
        frame.groupby("cluster", as_index=False)
        .agg(
            num_users=("user_id", "count"),
            total_orders_mean=("total_orders", "mean"),
            total_orders_median=("total_orders", "median"),
            avg_basket_size_mean=("avg_basket_size", "mean"),
            avg_reorder_ratio_mean=("avg_reorder_ratio", "mean"),
            avg_days_between_orders_mean=("avg_days_between_orders", "mean"),
        )
        .sort_values("cluster")
    )
    profiles.insert(
        1,
        "cluster_name",
        profiles["total_orders_mean"].map(_cluster_name),
    )
    profiles.to_csv(ensure_results_dir(output_dir) / "cluster_profiles.csv", index=False)
    return profiles


def save_cluster_labels(
    frame: pd.DataFrame,
    *,
    output_dir: Path | str | None = None,
) -> Path:
    missing = {"user_id", "cluster"}.difference(frame.columns)
    if missing:
        raise ClusteringDataError(f"Missing label columns: {', '.join(sorted(missing))}")
    path = ensure_results_dir(output_dir) / "cluster_labels.csv"
    frame.loc[:, ["user_id", "cluster"]].sort_values("user_id").to_csv(path, index=False)
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-orders", type=int, default=3)
    parser.add_argument("--max-k", type=int, default=10)
    parser.add_argument("--clusters", type=int, help="Explicit K override; default uses selected K")
    parser.add_argument("--silhouette-sample-size", type=int, default=10_000)
    parser.add_argument("--seed", type=int, help="Override MINING_RANDOM_STATE")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--no-plots", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = get_settings()
    random_state = settings.mining_random_state if args.seed is None else args.seed
    output_dir = ensure_results_dir(args.output_dir)
    features = extract_features(min_orders=args.min_orders, settings=settings)
    scaler_for_selection = StandardScaler()
    scaled_for_selection = scaler_for_selection.fit_transform(_feature_matrix(features))
    inertias, silhouette_scores, optimal_k = find_optimal_k(
        scaled_for_selection,
        max_k=args.max_k,
        random_state=random_state,
        silhouette_sample_size=args.silhouette_sample_size,
        output_dir=None if args.no_plots else output_dir,
    )
    selected_k = args.clusters if args.clusters is not None else optimal_k
    clustered, model, scaler, scaled = train_kmeans(
        features,
        n_clusters=selected_k,
        random_state=random_state,
        silhouette_sample_size=args.silhouette_sample_size,
    )
    pca_metrics = (
        {}
        if args.no_plots
        else visualize_clusters(
            clustered,
            scaled,
            output_dir=output_dir,
            random_state=random_state,
        )
    )
    profiles = profile_clusters(clustered, output_dir=output_dir)
    labels_path = save_cluster_labels(clustered, output_dir=output_dir)
    model_path = dump_joblib(output_dir / "kmeans_model.joblib", model)
    scaler_path = dump_joblib(output_dir / "standard_scaler.joblib", scaler)

    candidate_k = list(range(2, 2 + len(inertias)))
    metadata = {
        "artifact_schema_version": 1,
        "created_at": utc_timestamp(),
        "feature_columns": list(FEATURE_COLUMNS),
        "min_orders": args.min_orders,
        "n_users": len(clustered),
        "random_state": random_state,
        "silhouette_sample_size": min(args.silhouette_sample_size, len(clustered)),
        "selected_k": selected_k,
        "selected_k_source": "cli_override" if args.clusters is not None else "silhouette",
        "selection": [
            {"k": k, "inertia": inertia, "silhouette": score}
            for k, inertia, score in zip(candidate_k, inertias, silhouette_scores, strict=True)
        ],
        "training_metrics": model.training_metrics_,
        "pca_metrics": pca_metrics,
        "cluster_profiles": profiles.to_dict(orient="records"),
        "artifacts": {
            "model": model_path.name,
            "scaler": scaler_path.name,
            "labels": labels_path.name,
        },
    }
    write_json(output_dir / "clustering_metadata.json", metadata)
    print(
        f"Clustered {len(clustered):,} users with K={selected_k}; "
        f"silhouette={model.training_metrics_['silhouette']:.3f}. Artifacts: {output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
