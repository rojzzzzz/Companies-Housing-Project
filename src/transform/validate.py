from __future__ import annotations
from dataclasses import dataclass, field
from src.config import TABLE_NAMES, STAGING_DIR
from typing import Any, Literal
from pathlib import Path
import pandas as pd
import logging

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class QualityResult:
    """Represents the result of a quality check."""

    quality_check: str
    min_value: float
    warning_threshold: float
    score: float
    columns: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        """Checks if the result meets the minimum threshold."""
        return self.score >= self.min_value

    @property
    def status(self) -> Literal["PASSED", "WARNING", "FAILED"]:
        """Returns the quality check status."""
        if self.score < self.min_value:
            return "FAILED"

        if self.score < self.warning_threshold:
            return "WARNING"

        return "PASSED"


@dataclass
class Table:
    """Represents a table and its quality evaluation."""

    name: str
    columns: dict[str, str]
    df: pd.DataFrame
    quality_contract: dict[str, Any]
    quality_results: list[QualityResult] = field(default_factory=list)

    @property
    def passed_quality_checks(self) -> bool:
        """Checks if all evaluated quality checks meet their minimum thresholds."""
        return (
            bool(self.quality_results)
            and all(result.passed for result in self.quality_results)
        )

    @property
    def status(self) -> Literal["HEALTHY", "WARNING", "CRITICAL", "NOT_EVALUATED"]:
        """Returns the overall quality status of the table."""

        if not self.quality_results:
            return "NOT_EVALUATED"

        if any(result.status == "FAILED" for result in self.quality_results):
            return "CRITICAL"

        if any(result.status == "WARNING" for result in self.quality_results):
            return "WARNING"

        return "HEALTHY"


@dataclass
class DatasetHealth:
    """Represents a dataset and the quality status of its tables."""

    name: str
    tables: list[Table]

    @property
    def health(self) -> Literal[
        "HEALTHY", "WARNING", "CRITICAL", "NOT_EVALUATED"
    ]:
        """Returns the overall health of the dataset."""

        if not self.tables:
            return "NOT_EVALUATED"

        statuses = {table.status for table in self.tables}

        if "CRITICAL" in statuses:
            return "CRITICAL"

        if "NOT_EVALUATED" in statuses:
            return "NOT_EVALUATED"

        if "WARNING" in statuses:
            return "WARNING"

        return "HEALTHY"


def measure_completeness(df: pd.DataFrame, table_contract: dict) -> list[QualityResult]:
    """Measures completeness based on the YAML contract."""

    rules = table_contract.get("quality", {}).get("completeness", [])

    if not rules:
        return []

    if df.empty:
        raise ValueError("Cannot measure completeness of an empty DataFrame.")

    df = df.replace(r"^\s*$", pd.NA, regex=True)

    results = []

    for rule in rules:
        rule_columns = rule["columns"]

        missing = set(rule_columns) - set(df.columns)
        if missing:
            raise ValueError(f"Missing columns: {missing}")

        if not rule_columns:
            raise ValueError("Completeness rule must contain columns.")

        score = round(
            df[rule_columns].notna().mean().min() * 100,
            2
        )

        results.append(
            QualityResult(
                quality_check="completeness",
                columns=tuple(rule_columns),
                min_value=rule["min"] * 100,
                warning_threshold=rule["warning"] * 100,
                score=score
            )
        )

    return results
    
def measure_uniqueness(df: pd.DataFrame, table_contract: dict) -> list[QualityResult]:
    """Measures uniqueness based on the YAML contract."""

    rules = table_contract.get("quality", {}).get("uniqueness", [])

    if not rules:
        return []

    if df.empty:
        raise ValueError("Cannot measure uniqueness of an empty DataFrame.")

    results = []

    for rule in rules:
        rule_columns = rule["columns"]

        missing = set(rule_columns) - set(df.columns)
        if missing:
            raise ValueError(f"Missing columns: {missing}")

        if not rule_columns:
            raise ValueError("Uniqueness rule must contain columns.")

        score = round(
            (1 - df.duplicated(subset=rule_columns).mean()) * 100,
            2
        )

        results.append(
            QualityResult(
                quality_check="uniqueness",
                columns=tuple(rule_columns),
                min_value=rule["min"] * 100,
                warning_threshold=rule["warning"] * 100,
                score=score
            )
        )

    return results

def validate(data_contract: dict) -> DatasetHealth:
    """Validates all tables defined in the dataset contract."""

    logger.info("Starting dataset validation...")

    schema_contract = data_contract.get("silver_schema")

    if not schema_contract:
        raise ValueError("No schema contract was declared.")

    table_results: list[Table] = []

    for schema_name, schema in schema_contract.items():

        folder_path = STAGING_DIR / schema_name

        for table_name, table_contract in schema.get("tables", {}).items():

            table_path = folder_path / f"{table_name}.csv"

            if not table_path.is_file():
                raise FileNotFoundError(
                    f"Table file not found: {table_path}"
                )

            df = pd.read_csv(table_path)

            if df.empty:
                raise ValueError(
                    f"DataFrame for table '{table_name}' is empty."
                )

            expected_columns = set(table_contract.get("columns", {}))

            if not expected_columns:
                raise ValueError(
                    f"No columns defined for table '{table_name}'."
                )

            missing_columns = expected_columns - set(df.columns)

            if missing_columns:
                raise ValueError(
                    f"Missing columns in '{table_name}': {missing_columns}"
                )

            quality_results = [
                *measure_completeness(df, table_contract),
                *measure_uniqueness(df, table_contract)
            ]

            table = Table(
                name=table_name,
                columns=table_contract["columns"],
                df=df,
                quality_contract=table_contract,
                quality_results=quality_results
            )

            table_results.append(table)

            logger.info(
                f"Table '{table.name}' validated. "
                f"Quality checks passed: {table.passed_quality_checks}. "
                f"Status: {table.status}"
            )

    dataset_health = DatasetHealth(
        name="Companies Dataset",
        tables=table_results
    )

    logger.info(
        f"Dataset validation completed. "
        f"Overall status: {dataset_health.health}"
    )

    return dataset_health
