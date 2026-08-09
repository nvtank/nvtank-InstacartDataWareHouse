# syntax=docker/dockerfile:1

FROM python:3.12.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=0 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    INSTACART_PROJECT_ROOT=/app \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501

WORKDIR /app

RUN groupadd --system --gid 10001 instacart \
    && useradd --system --uid 10001 --gid instacart --home-dir /app instacart

COPY pyproject.toml ./

# Resolve the dependency layer from metadata before copying application code,
# so normal source edits do not trigger a complete third-party reinstall.
RUN python -c "import tomllib; data = tomllib.load(open('pyproject.toml', 'rb')); print(*(data['build-system']['requires'] + data['project']['dependencies']), sep='\n')" \
        > /tmp/runtime-requirements.txt \
    && python -m pip install --requirement /tmp/runtime-requirements.txt

COPY README.md ./
COPY dashboard ./dashboard
COPY etl ./etl
COPY mining ./mining
COPY .streamlit ./.streamlit
COPY run_dashboard.sh ./run_dashboard.sh

# Dependencies are resolved while building the image; startup never mutates the
# environment or reaches a package index.
RUN python -m pip install --no-deps --no-build-isolation . \
    && chmod 0755 /app/run_dashboard.sh \
    && chown -R instacart:instacart /app

USER instacart

EXPOSE 8501

ENTRYPOINT ["/app/run_dashboard.sh"]
