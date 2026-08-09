from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import mining.customer_clustering as clustering


@pytest.fixture
def customer_features() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "user_id": range(12, 0, -1),
            "total_orders": [4, 5, 6, 7, 8, 9, 42, 45, 48, 51, 54, 57],
            "avg_basket_size": [3.0, 3.2, 3.4, 3.6, 3.8, 4.0, 13, 14, 15, 16, 17, 18],
            "avg_reorder_ratio": [
                0.10,
                0.12,
                0.14,
                0.16,
                0.18,
                0.20,
                0.70,
                0.72,
                0.74,
                0.76,
                0.78,
                0.80,
            ],
            "avg_days_between_orders": [
                30,
                29,
                28,
                27,
                26,
                25,
                9,
                8,
                7,
                6,
                5,
                4,
            ],
        }
    )


def test_train_kmeans_is_deterministic_for_a_fixed_seed(
    customer_features: pd.DataFrame,
) -> None:
    first, first_model, first_scaler, first_scaled = clustering.train_kmeans(
        customer_features,
        n_clusters=2,
        random_state=17,
        silhouette_sample_size=6,
    )
    second, second_model, second_scaler, second_scaled = clustering.train_kmeans(
        customer_features,
        n_clusters=2,
        random_state=17,
        silhouette_sample_size=6,
    )

    assert first["cluster"].tolist() == second["cluster"].tolist()
    np.testing.assert_allclose(first_model.cluster_centers_, second_model.cluster_centers_)
    np.testing.assert_allclose(first_scaler.mean_, second_scaler.mean_)
    np.testing.assert_allclose(first_scaled, second_scaled)
    assert first_model.training_metrics_ == pytest.approx(second_model.training_metrics_)
    assert set(first_model.training_metrics_) == {"silhouette", "davies_bouldin", "inertia"}
    assert "cluster" not in customer_features


def test_find_optimal_k_bounds_candidates_by_available_rows(
    customer_features: pd.DataFrame,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scaled = clustering.StandardScaler().fit_transform(
        customer_features.loc[:, clustering.FEATURE_COLUMNS]
    )
    original_silhouette_score = clustering.silhouette_score
    calls: list[dict[str, int]] = []

    def record_silhouette_call(
        values: np.ndarray,
        labels: np.ndarray,
        **kwargs: int,
    ) -> float:
        calls.append(kwargs)
        return float(original_silhouette_score(values, labels, **kwargs))

    monkeypatch.setattr(clustering, "silhouette_score", record_silhouette_call)

    inertias, scores, optimal_k = clustering.find_optimal_k(
        scaled,
        max_k=50,
        random_state=23,
        silhouette_sample_size=len(customer_features),
    )

    assert len(inertias) == len(scores) == len(customer_features) - 2
    assert optimal_k in range(2, len(customer_features))
    assert len(calls) == len(customer_features) - 2
    assert all(call == {} for call in calls)


def test_bounded_silhouette_expands_a_too_small_sample_deterministically() -> None:
    values = np.asarray([[0.0], [0.1], [5.0], [5.1], [10.0], [10.1]])
    labels = np.asarray([0, 0, 1, 1, 2, 2])

    first = clustering._bounded_silhouette(
        values,
        labels,
        sample_size=2,
        random_state=11,
    )
    second = clustering._bounded_silhouette(
        values,
        labels,
        sample_size=2,
        random_state=11,
    )

    assert first == pytest.approx(second)
    assert -1 <= first <= 1


def test_cluster_profiles_and_labels_are_written_to_requested_directory(
    customer_features: pd.DataFrame,
    tmp_path: Path,
) -> None:
    clustered, _, _, _ = clustering.train_kmeans(
        customer_features,
        n_clusters=2,
        random_state=31,
        silhouette_sample_size=6,
    )

    profiles = clustering.profile_clusters(clustered, output_dir=tmp_path)
    labels_path = clustering.save_cluster_labels(clustered, output_dir=tmp_path)

    profiles_path = tmp_path / "cluster_profiles.csv"
    assert profiles_path.is_file()
    assert labels_path == tmp_path / "cluster_labels.csv"
    assert labels_path.is_file()
    assert profiles["num_users"].sum() == len(customer_features)
    assert profiles["cluster"].is_monotonic_increasing
    assert profiles["cluster_name"].notna().all()

    saved_labels = pd.read_csv(labels_path)
    assert saved_labels.columns.tolist() == ["user_id", "cluster"]
    assert saved_labels["user_id"].tolist() == sorted(customer_features["user_id"])


def test_clustering_parser_accepts_reproducibility_controls() -> None:
    args = clustering.build_parser().parse_args(
        [
            "--min-orders",
            "5",
            "--max-k",
            "7",
            "--clusters",
            "3",
            "--silhouette-sample-size",
            "500",
            "--seed",
            "99",
            "--no-plots",
        ]
    )

    assert (args.min_orders, args.max_k, args.clusters) == (5, 7, 3)
    assert (args.silhouette_sample_size, args.seed, args.no_plots) == (500, 99, True)
