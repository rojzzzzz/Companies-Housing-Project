from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG
import pendulum


with DAG(
    dag_id="housing_pipeline",
    start_date=pendulum.datetime(2026, 10, 13, tz="America/Managua"),
    schedule="@monthly",
    catchup=False,
    max_active_runs=1,
    max_active_tasks=1,
    is_paused_upon_creation=True,) as dag:
    
    stages = [
        BashOperator(
            task_id=stage,
            bash_command=(
                "/opt/airflow/venvs/pipeline/bin/python -c "
                f"'from src.pipeline import {stage}; {stage}()'"
            ),
        )
        for stage in ("extract", "normalize", "validate", "load")
    ]
    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=(
            "/opt/airflow/venvs/pipeline/bin/dbt build "
            "--project-dir /dbt --profiles-dir /dbt-profile"
        ),
    )

    for upstream, downstream in zip(stages, stages[1:]):
        upstream >> downstream
    stages[-1] >> dbt_build

