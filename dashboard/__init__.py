"""Public package surface for the Instacart analytics dashboard."""

from .data import (
    AnalyticsRepository,
    DemoAnalyticsRepository,
    MariaDBAnalyticsRepository,
    RepositoryConfigurationError,
    RepositoryHealth,
    RepositoryUnavailableError,
    SourceMetadata,
    TableMetadata,
    create_repository,
)

__all__ = [
    "AnalyticsRepository",
    "DemoAnalyticsRepository",
    "MariaDBAnalyticsRepository",
    "RepositoryConfigurationError",
    "RepositoryHealth",
    "RepositoryUnavailableError",
    "SourceMetadata",
    "TableMetadata",
    "create_repository",
]
