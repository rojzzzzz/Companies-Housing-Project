FROM apache/airflow:3.3.2-python3.12

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

USER airflow
COPY requirements.txt /tmp/requirements.txt

# Keep pipeline and dbt packages isolated from Airflow's dependencies.
RUN umask 0002 \
    && python -m venv /opt/airflow/venvs/pipeline \
    && /opt/airflow/venvs/pipeline/bin/pip install --no-cache-dir -r /tmp/requirements.txt

COPY --chown=airflow:root src/ /app/src/
COPY --chown=airflow:root sql/ /app/sql/
COPY --chown=airflow:root airflow/dags/ /opt/airflow/dags/

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    DBT_PROFILES_DIR=/dbt-profile \
    DBT_ENGINE_TARGET_PATH=/opt/airflow/dbt-target \
    DBT_ENGINE_LOG_PATH=/opt/airflow/logs/dbt

CMD ["standalone"]
