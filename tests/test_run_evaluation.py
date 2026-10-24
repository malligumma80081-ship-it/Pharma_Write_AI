import pytest

from evals.run_evaluation import _get_project_id, _normalize_case


@pytest.mark.parametrize(
    "query_key",
    ["query", "question"],
)
def test_normalize_case_supports_query_field_names(query_key):
    case = {
        "case_id": "R001",
        query_key: "  What was the study population?  ",
        "relevant_chunk_ids": ["document-1_0"],
    }

    normalized = _normalize_case(case, 1)

    assert normalized == {
        "case_id": "R001",
        "query": "What was the study population?",
        "relevant_chunk_ids": ["document-1_0"],
        "k": 5,
        "placeholders": [],
    }


def test_normalize_case_identifies_placeholder_chunk_ids():
    normalized = _normalize_case(
        {
            "case_id": "R001",
            "question": "What was the sample size?",
            "relevant_chunk_ids": ["REPLACE_WITH_RELEVANT_CHUNK_ID"],
        },
        1,
    )

    assert normalized["placeholders"] == [
        "REPLACE_WITH_RELEVANT_CHUNK_ID"
    ]


def test_normalize_case_rejects_missing_query():
    with pytest.raises(ValueError, match="'query' or 'question'"):
        _normalize_case(
            {
                "case_id": "R001",
                "relevant_chunk_ids": ["document-1_0"],
            },
            1,
        )


def test_evaluation_project_id_must_be_numeric(monkeypatch):
    monkeypatch.setenv("EVAL_PROJECT_ID", "your-test-project-uuid")

    with pytest.raises(RuntimeError, match="numeric project ID"):
        _get_project_id()


def test_evaluation_project_id_is_normalized_to_string(monkeypatch):
    monkeypatch.setenv("EVAL_PROJECT_ID", "2")

    assert _get_project_id() == "2"


def test_placeholder_cases_are_skipped_and_reported(
    monkeypatch,
    tmp_path,
    capsys,
):
    import json

    from evals import run_evaluation

    cases_path = tmp_path / "cases.json"
    cases_path.write_text(
        json.dumps(
            [
                {
                    "case_id": "template-case",
                    "query": "What was reported?",
                    "relevant_chunk_ids": [
                        "REPLACE_WITH_RELEVANT_CHUNK_ID"
                    ],
                },
                {
                    "case_id": "ready-case",
                    "question": "Which chunk is relevant?",
                    "relevant_chunk_ids": ["doc-1_0"],
                    "k": 3,
                },
            ]
        ),
        encoding="utf-8",
    )
    reports_dir = tmp_path / "reports"
    monkeypatch.setattr(run_evaluation, "CASES_PATH", cases_path)
    monkeypatch.setattr(run_evaluation, "REPORTS_DIR", reports_dir)
    monkeypatch.setenv("EVAL_PROJECT_ID", "2")
    monkeypatch.setattr(
        run_evaluation,
        "search_chunks",
        lambda **kwargs: [{"chunk_id": "doc-1_0"}],
    )

    run_evaluation.main()

    report = json.loads(
        (reports_dir / "retrieval_evaluation.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["case_count"] == 1
    assert report["skipped_case_count"] == 1
    assert report["cases"][0]["case_id"] == "ready-case"
    assert report["skipped_cases"][0]["case_id"] == "template-case"
    assert "Skipped 1 case(s)" in capsys.readouterr().out


def test_all_placeholder_cases_report_null_metrics(
    monkeypatch,
    tmp_path,
):
    import json

    from evals import run_evaluation

    cases_path = tmp_path / "cases.json"
    cases_path.write_text(
        json.dumps(
            [
                {
                    "case_id": "template-case",
                    "question": "What was reported?",
                    "relevant_chunk_ids": ["replace-with-real-chunk-id"],
                }
            ]
        ),
        encoding="utf-8",
    )
    reports_dir = tmp_path / "reports"
    monkeypatch.setattr(run_evaluation, "CASES_PATH", cases_path)
    monkeypatch.setattr(run_evaluation, "REPORTS_DIR", reports_dir)
    monkeypatch.setenv("EVAL_PROJECT_ID", "2")
    monkeypatch.setattr(
        run_evaluation,
        "search_chunks",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("skipped case should not be searched")
        ),
    )

    run_evaluation.main()

    report = json.loads(
        (reports_dir / "retrieval_evaluation.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["case_count"] == 0
    assert report["skipped_case_count"] == 1
    assert report["mean_recall"] is None
    assert report["mean_precision"] is None
    assert report["mean_reciprocal_rank"] is None
