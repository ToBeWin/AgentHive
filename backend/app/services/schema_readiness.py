def expected_media_runtime_indexes() -> set[str]:
    return {
        "ix_media_generation_jobs_provider_external",
        "ix_media_generation_jobs_running_department_updated",
        "ix_media_generation_jobs_running_user_updated",
        "ix_media_generation_jobs_tenant_department_created",
        "ix_media_generation_jobs_tenant_user_created",
    }


def missing_media_runtime_indexes(
    index_names: set[str],
    expected_indexes: set[str] | None = None,
) -> list[str]:
    expected = (
        expected_indexes if expected_indexes is not None else expected_media_runtime_indexes()
    )
    return sorted(expected - index_names)
