"""Unit tests for ``app.services.schema_readiness``."""

from app.services.schema_readiness import (
    expected_media_runtime_indexes,
    missing_media_runtime_indexes,
)

EXPECTED_INDEXES = {
    "ix_media_generation_jobs_provider_external",
    "ix_media_generation_jobs_running_department_updated",
    "ix_media_generation_jobs_running_user_updated",
    "ix_media_generation_jobs_tenant_department_created",
    "ix_media_generation_jobs_tenant_user_created",
}


def test_expected_media_runtime_indexes_returns_complete_set() -> None:
    assert expected_media_runtime_indexes() == EXPECTED_INDEXES


def test_expected_media_runtime_indexes_returns_set_type() -> None:
    assert isinstance(expected_media_runtime_indexes(), set)


def test_missing_media_runtime_indexes_when_all_present_returns_empty() -> None:
    assert missing_media_runtime_indexes(EXPECTED_INDEXES) == []


def test_missing_media_runtime_indexes_when_none_present_returns_all_sorted() -> None:
    assert missing_media_runtime_indexes(set()) == sorted(EXPECTED_INDEXES)


def test_missing_media_runtime_indexes_when_some_missing_returns_sorted_missing() -> None:
    missing = {
        "ix_media_generation_jobs_provider_external",
        "ix_media_generation_jobs_tenant_user_created",
    }
    present = EXPECTED_INDEXES - missing
    result = missing_media_runtime_indexes(present)
    assert result == sorted(missing)


def test_missing_media_runtime_indexes_with_custom_expected_set() -> None:
    custom_expected = {"ix_a", "ix_b", "ix_c"}
    index_names = {"ix_a", "ix_c"}
    assert missing_media_runtime_indexes(index_names, custom_expected) == ["ix_b"]


def test_missing_media_runtime_indexes_with_custom_expected_overrides_default() -> None:
    custom_expected = {"ix_custom_only"}
    # Even though default indexes are all absent, custom overrides entirely.
    result = missing_media_runtime_indexes(EXPECTED_INDEXES, custom_expected)
    assert result == ["ix_custom_only"]


def test_missing_media_runtime_indexes_returns_list_type() -> None:
    result = missing_media_runtime_indexes(set())
    assert isinstance(result, list)


def test_missing_media_runtime_indexes_sorted_order() -> None:
    result = missing_media_runtime_indexes(set())
    assert result == sorted(result)


def test_expected_media_runtime_indexes_immutability_of_returned_value() -> None:
    first = expected_media_runtime_indexes()
    first.add("ix_mutated_by_caller")
    second = expected_media_runtime_indexes()
    assert "ix_mutated_by_caller" not in second
    assert second == EXPECTED_INDEXES
