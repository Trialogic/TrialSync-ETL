from unittest.mock import MagicMock
from src.etl.parameterized_executor import ParameterizedJobExecutor


def test_parameterized_empty_set():
    db = MagicMock()
    api = MagicMock()
    loader = MagicMock()

    exe = ParameterizedJobExecutor(db, api, loader)
    exe.fetch_parameters = MagicMock(return_value=[])

    job = {
        "id": 27,
        "source_endpoint": "/studies/{studyId}/subjects",
        "target_table": "subjects_staging",
        "parameter_source_table": "dim_study",
        "parameter_source_column": "studyId",
    }

    total = exe.run(job, run_id=1)
    assert total == 0
    api.get_odata.assert_not_called()
    loader.load_to_staging.assert_not_called()


def test_parameterized_multiple_values():
    db = MagicMock()
    api = MagicMock()
    loader = MagicMock()

    exe = ParameterizedJobExecutor(db, api, loader)
    exe.fetch_parameters = MagicMock(return_value=[101, 102, 103])
    api.get_odata.side_effect = [[{"id": 1}], [{"id": 2}, {"id": 3}], []]

    job = {
        "id": 27,
        "source_endpoint": "/studies/{studyId}/subjects",
        "target_table": "subjects_staging",
        "parameter_source_table": "dim_study",
        "parameter_source_column": "studyId",
    }

    total = exe.run(job, run_id=2)

    assert total == 3  # 1 + 2 + 0
    assert api.get_odata.call_count == 3
    assert loader.load_to_staging.call_count == 2  # only when records non-empty
