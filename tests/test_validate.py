"""Quality scoring, threshold boundaries, health aggregation, and CSV validation."""

from dataclasses import FrozenInstanceError

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from src.transform import validate as validation
from src.transform.validate import DatasetHealth, QualityResult, Table


def quality_contract(check, columns, minimum=0.75, warning=1.0):
    """A minimal contract rule, expressed in the same units as the YAML."""
    return {
        "quality": {check: [{"columns": columns, "min": minimum, "warning": warning}]}
    }


def make_table(scores=(), minimum=90, warning=95):
    return Table(
        name="example",
        columns={"id": "integer"},
        df=pd.DataFrame({"id": [1]}),
        quality_contract={},
        quality_results=[
            QualityResult("completeness", minimum, warning, score, ("id",))
            for score in scores
        ],
    )


@pytest.mark.parametrize(
    "score, passed, status",
    [
        (0, False, "FAILED"),
        (89.99, False, "FAILED"),
        (90, True, "WARNING"),
        (94.99, True, "WARNING"),
        (95, True, "PASSED"),
        (100, True, "PASSED"),
    ],
)
def test_quality_result_threshold_boundaries(score, passed, status):
    result = QualityResult("completeness", 90, 95, score, ("id",))
    assert result.passed is passed
    assert result.status == status


def test_quality_result_is_immutable():
    result = QualityResult("uniqueness", 90, 95, 100)
    with pytest.raises(FrozenInstanceError):
        result.score = 0


@pytest.mark.parametrize(
    "scores, passed, status",
    [
        ([], False, "NOT_EVALUATED"),
        ([100, 95], True, "HEALTHY"),
        ([100, 92], True, "WARNING"),
        ([100, 92, 80], False, "CRITICAL"),
    ],
)
def test_table_aggregates_quality_results(scores, passed, status):
    table = make_table(scores)
    assert table.passed_quality_checks is passed
    assert table.status == status


def test_tables_have_independent_result_lists():
    first = make_table()
    second = make_table()
    first.quality_results.append(QualityResult("completeness", 90, 95, 100))
    assert second.quality_results == []


@pytest.mark.parametrize(
    "score_groups, expected",
    [
        ([], "NOT_EVALUATED"),
        ([[]], "NOT_EVALUATED"),
        ([[100], [95]], "HEALTHY"),
        ([[100], [92]], "WARNING"),
        ([[92], []], "NOT_EVALUATED"),
        ([[80], [92], []], "CRITICAL"),
    ],
)
def test_dataset_health_uses_most_severe_table_status(score_groups, expected):
    dataset = DatasetHealth(
        "Example Dataset", [make_table(scores) for scores in score_groups]
    )
    assert dataset.health == expected


@pytest.mark.parametrize("missing", [None, float("nan"), pd.NA, "", " ", "\t\n"])
def test_completeness_counts_null_and_blank_values_as_missing(missing):
    df = pd.DataFrame({"name": ["Alice", "Bob", "Carol", missing]})
    results = validation.measure_completeness(
        df, quality_contract("completeness", ["name"])
    )
    assert results == [QualityResult("completeness", 75, 100, 75, ("name",))]
    assert results[0].status == "WARNING"


def test_completeness_uses_least_complete_column():
    df = pd.DataFrame({"id": [1, 2, 3, 4], "name": ["A", "B", None, None]})
    result = validation.measure_completeness(
        df, quality_contract("completeness", ["id", "name"])
    )[0]
    assert result.score == 50
    assert result.columns == ("id", "name")
    assert result.status == "FAILED"


def test_completeness_preserves_valid_zero_and_false_values():
    df = pd.DataFrame({"value": [0, False, "valid"]})
    assert (
        validation.measure_completeness(
            df, quality_contract("completeness", ["value"])
        )[0].score
        == 100
    )


def test_completeness_does_not_mutate_input():
    df = pd.DataFrame({"name": ["Alice", " "]})
    original = df.copy(deep=True)
    validation.measure_completeness(df, quality_contract("completeness", ["name"]))
    assert_frame_equal(df, original)


def test_uniqueness_counts_duplicate_rows():
    df = pd.DataFrame({"id": ["a", "a", "b", "c"]})
    results = validation.measure_uniqueness(df, quality_contract("uniqueness", ["id"]))
    assert results == [QualityResult("uniqueness", 75, 100, 75, ("id",))]


def test_uniqueness_uses_composite_keys():
    df = pd.DataFrame({"company": ["a", "a", "b", "b"], "id": [1, 2, 1, 1]})
    result = validation.measure_uniqueness(
        df, quality_contract("uniqueness", ["company", "id"])
    )[0]
    assert result.score == 75
    assert result.columns == ("company", "id")


@pytest.mark.parametrize(
    "ids, expected",
    [
        ([1, 2, 3], 100),
        ([1, 1, 1], 33.33),
        ([None, None, 1], 66.67),
    ],
)
def test_uniqueness_handles_distinct_repeated_and_null_keys(ids, expected):
    df = pd.DataFrame({"id": ids})
    assert (
        validation.measure_uniqueness(df, quality_contract("uniqueness", ["id"]))[
            0
        ].score
        == expected
    )


@pytest.mark.parametrize(
    "measure, check",
    [
        (validation.measure_completeness, "completeness"),
        (validation.measure_uniqueness, "uniqueness"),
    ],
)
class TestQualityRuleValidation:
    def test_no_rules_returns_no_results(self, measure, check):
        assert measure(pd.DataFrame(), {}) == []
        assert measure(pd.DataFrame(), {"quality": {check: []}}) == []

    def test_empty_dataframe_is_rejected(self, measure, check):
        with pytest.raises(ValueError, match="empty DataFrame"):
            measure(pd.DataFrame(columns=["id"]), quality_contract(check, ["id"]))

    def test_missing_columns_are_rejected(self, measure, check):
        with pytest.raises(ValueError, match="Missing columns.*absent"):
            measure(pd.DataFrame({"id": [1]}), quality_contract(check, ["absent"]))

    def test_rules_require_columns(self, measure, check):
        with pytest.raises(ValueError, match="rule must contain columns"):
            measure(pd.DataFrame({"id": [1]}), quality_contract(check, []))

    def test_multiple_rules_are_evaluated_independently(self, measure, check):
        df = pd.DataFrame({"id": [1, 2], "name": ["A", "A"]})
        contract = {
            "quality": {
                check: [
                    {"columns": ["id"], "min": 0.9, "warning": 1.0},
                    {"columns": ["name"], "min": 0.5, "warning": 0.9},
                ]
            }
        }
        results = measure(df, contract)
        assert [result.columns for result in results] == [("id",), ("name",)]
        assert [result.min_value for result in results] == [90, 50]
        assert [result.warning_threshold for result in results] == [100, 90]
        assert results[0].score == 100
        assert results[1].score == (100 if check == "completeness" else 50)


@pytest.mark.xfail(
    strict=True,
    reason="Validator currently ignores completeness 'when' conditions from the YAML contract.",
)
def test_completeness_applies_conditional_rules_only_to_matching_rows():
    df = pd.DataFrame({"ceased": [True, False], "ceased_on": ["2024-01-01", None]})
    contract = quality_contract("completeness", ["ceased_on"])
    contract["quality"]["completeness"][0]["when"] = {
        "column": "ceased",
        "equals": True,
    }
    assert validation.measure_completeness(df, contract)[0].score == 100


@pytest.fixture
def staged_dataset(tmp_path, monkeypatch):
    """Create CSVs only inside pytest's temporary directory."""
    monkeypatch.setattr(validation, "STAGING_DIR", tmp_path)
    contract = {
        "columns": {"id": "integer", "name": "string"},
        "quality": {
            "completeness": [{"columns": ["id", "name"], "min": 0.75, "warning": 1.0}],
            "uniqueness": [{"columns": ["id"], "min": 0.75, "warning": 1.0}],
        },
    }
    data_contract = {"silver_schema": {"example": {"tables": {"records": contract}}}}
    folder = tmp_path / "example"
    folder.mkdir()
    path = folder / "records.csv"
    pd.DataFrame({"id": [1, 2, 3, 4], "name": ["A", "B", "C", "D"]}).to_csv(
        path, index=False
    )
    return data_contract, path


def test_validate_returns_healthy_dataset_and_table_results(staged_dataset):
    contract, _ = staged_dataset
    dataset = validation.validate(contract)
    assert dataset.name == "Companies Dataset"
    assert dataset.health == "HEALTHY"
    assert len(dataset.tables) == 1
    table = dataset.tables[0]
    assert table.name == "records"
    assert table.columns == {"id": "integer", "name": "string"}
    assert table.passed_quality_checks is True
    assert [result.score for result in table.quality_results] == [100, 100]
    assert len(table.df) == 4


@pytest.mark.parametrize(
    "names, expected",
    [
        (["A", "B", "C", None], "WARNING"),
        (["A", None, None, None], "CRITICAL"),
    ],
)
def test_validate_reports_warning_and_critical_quality(staged_dataset, names, expected):
    contract, path = staged_dataset
    pd.DataFrame({"id": [1, 2, 3, 4], "name": names}).to_csv(path, index=False)
    assert validation.validate(contract).health == expected


@pytest.mark.parametrize(
    "contract", [{}, {"silver_schema": {}}, {"silver_schema": None}]
)
def test_validate_requires_schema(contract):
    with pytest.raises(ValueError, match="No schema contract was declared"):
        validation.validate(contract)


def test_validate_requires_existing_csv(staged_dataset):
    contract, path = staged_dataset
    path.unlink()
    with pytest.raises(FileNotFoundError, match="Table file not found.*records.csv"):
        validation.validate(contract)


def test_validate_rejects_header_only_csv(staged_dataset):
    contract, path = staged_dataset
    path.write_text("id,name\n", encoding="utf-8")
    with pytest.raises(ValueError, match="DataFrame for table 'records' is empty"):
        validation.validate(contract)


def test_validate_requires_declared_columns(staged_dataset):
    contract, _ = staged_dataset
    contract["silver_schema"]["example"]["tables"]["records"]["columns"] = {}
    with pytest.raises(ValueError, match="No columns defined for table 'records'"):
        validation.validate(contract)


def test_validate_rejects_missing_csv_columns(staged_dataset):
    contract, path = staged_dataset
    path.write_text("id\n1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Missing columns in 'records'.*name"):
        validation.validate(contract)


def test_validate_accepts_additional_csv_columns(staged_dataset):
    contract, path = staged_dataset
    pd.DataFrame({"id": [1], "name": ["A"], "extra": ["allowed"]}).to_csv(
        path, index=False
    )
    assert validation.validate(contract).health == "HEALTHY"


def test_validate_without_quality_rules_is_not_evaluated(staged_dataset):
    contract, _ = staged_dataset
    del contract["silver_schema"]["example"]["tables"]["records"]["quality"]
    assert validation.validate(contract).health == "NOT_EVALUATED"


def test_validate_schema_without_tables_is_not_evaluated():
    assert (
        validation.validate({"silver_schema": {"example": {}}}).health
        == "NOT_EVALUATED"
    )


@pytest.mark.integration
def test_validate_aggregates_tables_across_schema_folders(staged_dataset):
    contract, path = staged_dataset
    folder = path.parent.parent / "second"
    folder.mkdir()
    pd.DataFrame({"id": [1, 1, 1, 1], "name": ["A", "B", "C", "D"]}).to_csv(
        folder / "duplicates.csv", index=False
    )
    table_contract = contract["silver_schema"]["example"]["tables"]["records"]
    contract["silver_schema"]["second"] = {"tables": {"duplicates": table_contract}}
    dataset = validation.validate(contract)
    assert [table.status for table in dataset.tables] == ["HEALTHY", "CRITICAL"]
    assert dataset.health == "CRITICAL"
