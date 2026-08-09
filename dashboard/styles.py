"""Shared visual language for the Instacart Decision Intelligence UI."""

from __future__ import annotations

from typing import Final

import plotly.graph_objects as go
import streamlit as st

COLORS: Final = {
    "ink": "#172033",
    "muted": "#5D6B82",
    "surface": "#FFFFFF",
    "canvas": "#F4F7F9",
    "border": "#DCE5EA",
    "primary": "#087F5B",
    "primary_dark": "#075E45",
    "blue": "#2F6BFF",
    "orange": "#D97706",
    "purple": "#7C3AED",
    "rose": "#C2416C",
    "cyan": "#0E7490",
}

# Okabe-Ito inspired categorical colors remain distinguishable for common
# forms of color-vision deficiency and still have sufficient visual separation.
CATEGORICAL_PALETTE: Final = [
    "#0072B2",
    "#E69F00",
    "#009E73",
    "#CC79A7",
    "#56B4E9",
    "#D55E00",
    "#F0E442",
    "#6B7280",
]
SEQUENTIAL_SCALE: Final = [
    [0.0, "#E8F3F1"],
    [0.35, "#9BD3C5"],
    [0.7, "#2A9D78"],
    [1.0, "#075E45"],
]


def inject_global_styles() -> None:
    """Apply restrained, responsive styles without generated class selectors."""

    st.markdown(
        """
        <style>
        :root {
            --id-ink: #172033;
            --id-muted: #5D6B82;
            --id-surface: #FFFFFF;
            --id-canvas: #F4F7F9;
            --id-border: #DCE5EA;
            --id-primary: #087F5B;
            --id-primary-dark: #075E45;
        }

        [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at 85% -10%, rgba(8, 127, 91, 0.10), transparent 32rem),
                var(--id-canvas);
        }

        [data-testid="stMainBlockContainer"] {
            max-width: 1440px;
            padding-top: 2rem;
            padding-bottom: 4rem;
        }

        [data-testid="stSidebar"] {
            border-right: 1px solid var(--id-border);
            background: rgba(255, 255, 255, 0.96);
        }

        h1, h2, h3 {
            color: var(--id-ink);
            letter-spacing: -0.025em;
        }

        h1 {
            font-size: clamp(2rem, 3vw, 3.35rem) !important;
            line-height: 1.08 !important;
            margin-bottom: 0.45rem !important;
        }

        p, label, [data-testid="stCaptionContainer"] {
            color: var(--id-muted);
        }

        [data-testid="stMetric"] {
            min-height: 8.5rem;
            padding: 1rem 1.1rem;
            border: 1px solid var(--id-border);
            border-radius: 1rem;
            background: rgba(255, 255, 255, 0.92);
            box-shadow: 0 10px 28px rgba(23, 32, 51, 0.055);
        }

        [data-testid="stMetricLabel"] {
            font-weight: 650;
        }

        [data-testid="stMetricValue"] {
            color: var(--id-ink);
            letter-spacing: -0.035em;
        }

        .id-eyebrow {
            margin: 0 0 0.4rem;
            color: var(--id-primary-dark);
            font-size: 0.76rem;
            font-weight: 800;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }

        .id-page-summary {
            max-width: 76ch;
            margin: 0 0 1.25rem;
            color: var(--id-muted);
            font-size: 1.02rem;
            line-height: 1.65;
        }

        .id-source-row {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 0.6rem;
            margin: 0.4rem 0 1.2rem;
        }

        .id-source-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.42rem;
            padding: 0.38rem 0.72rem;
            border: 1px solid #B8D7CE;
            border-radius: 999px;
            background: #EBF7F3;
            color: #075E45;
            font-size: 0.78rem;
            font-weight: 800;
            letter-spacing: 0.045em;
            text-transform: uppercase;
        }

        .id-source-badge.demo {
            border-color: #C9D5F5;
            background: #EEF3FF;
            color: #234EA4;
        }

        .id-source-dot {
            width: 0.5rem;
            height: 0.5rem;
            border-radius: 999px;
            background: currentColor;
        }

        .id-source-note {
            color: var(--id-muted);
            font-size: 0.82rem;
        }

        .id-insight {
            height: 100%;
            padding: 1rem 1.1rem;
            border: 1px solid var(--id-border);
            border-left: 4px solid var(--id-primary);
            border-radius: 0.85rem;
            background: rgba(255, 255, 255, 0.88);
        }

        .id-insight strong {
            display: block;
            margin-bottom: 0.3rem;
            color: var(--id-ink);
        }

        .id-insight span {
            color: var(--id-muted);
            line-height: 1.5;
        }

        [data-testid="stDataFrame"],
        [data-testid="stPlotlyChart"] {
            overflow: hidden;
            border: 1px solid var(--id-border);
            border-radius: 0.9rem;
            background: var(--id-surface);
        }

        button:focus-visible,
        input:focus-visible,
        [role="radio"]:focus-visible,
        [role="option"]:focus-visible {
            outline: 3px solid rgba(47, 107, 255, 0.35) !important;
            outline-offset: 2px !important;
        }

        @media (max-width: 768px) {
            [data-testid="stMainBlockContainer"] {
                padding: 1.15rem 1rem 3rem;
            }

            [data-testid="stMetric"] {
                min-height: 7.25rem;
            }

            .id-source-row {
                align-items: flex-start;
                flex-direction: column;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def style_figure(
    figure: go.Figure,
    *,
    height: int = 420,
    legend: bool = False,
    horizontal_legend: bool = False,
) -> go.Figure:
    """Apply the shared Plotly layout while preserving chart-specific choices."""

    legend_options: dict[str, object] = {}
    if horizontal_legend:
        legend_options = {
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
        }
    figure.update_layout(
        height=height,
        margin={"l": 28, "r": 24, "t": 56, "b": 36},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, system-ui, sans-serif", "color": COLORS["ink"]},
        title={"font": {"size": 17}, "x": 0.02, "xanchor": "left"},
        hoverlabel={"bgcolor": COLORS["ink"], "font_color": "#FFFFFF"},
        showlegend=legend,
        legend=legend_options,
    )
    figure.update_xaxes(
        showgrid=True,
        gridcolor="rgba(93,107,130,0.12)",
        zeroline=False,
        title_font={"size": 12},
    )
    figure.update_yaxes(
        showgrid=True,
        gridcolor="rgba(93,107,130,0.12)",
        zeroline=False,
        title_font={"size": 12},
    )
    return figure
