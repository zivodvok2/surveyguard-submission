"""Unit tests for dashboard summary / activity feed and misc helpers in shared_db.py."""
from conftest import unique


def test_db_available_is_true_in_sqlite_mode(db):
    assert db.db_available() is True


def test_get_dashboard_summary_computes_rates(db, make_project, make_user):
    project = db.get_project(
        db.create_project_full(
            name=unique("Summary Project"), client=None, sample_target=2,
            start_date=None, end_date=None, backcheck_target=0.2,
            listenin_target=0.1, accompaniment_target=0.2,
            created_by=make_user(role="admin")["id"],
        )
    )
    uploader = make_user()

    db.insert_quality_records(
        project["id"], uploader["id"], "wave1.xlsx",
        [
            {"instance_id": unique("inst"), "approval_status": "Approved", "duration_flag": "Pass"},
            {"instance_id": unique("inst"), "approval_status": "Approved", "duration_flag": "Flag"},
        ],
    )
    db.insert_backcheck_records(
        project["id"], uploader["id"], "bc.xlsx",
        [{"bc_instance_id": unique("bc")}],
    )

    summary = db.get_dashboard_summary()
    row = next(r for r in summary if r["id"] == project["id"])
    assert row["approved"] == 2
    assert row["completion_pct"] == 100.0  # 2 approved / sample_target 2
    assert row["backcheck_count"] == 1
    assert row["backcheck_rate"] == 50.0  # 1 backcheck / 2 approved
    assert row["flagged"] == 1
    assert row["total_submitted"] == 2


def test_get_dashboard_summary_zero_target_gives_zero_pct(db, make_project):
    project = make_project()  # sample_target defaults to 0
    summary = db.get_dashboard_summary()
    row = next(r for r in summary if r["id"] == project["id"])
    assert row["completion_pct"] == 0
    assert row["approved"] == 0


def test_get_project_activity_reflects_recent_uploads(db, make_project, make_user):
    project = make_project()
    uploader = make_user()
    upload_id = db.insert_quality_records(
        project["id"], uploader["id"], "recent.xlsx",
        [{"instance_id": unique("inst")}],
    )
    activity = db.get_project_activity(project_id=project["id"], limit=5)
    assert any(a["filename"] == "recent.xlsx" for a in activity)
    entry = next(a for a in activity if a["filename"] == "recent.xlsx")
    assert entry["uploader"] == uploader["full_name"]
    assert entry["project_name"] == project["name"]


def test_get_project_activity_respects_limit(db, make_project, make_user):
    project = make_project()
    uploader = make_user()
    for i in range(3):
        db.insert_timing_records(
            project["id"], uploader["id"], f"timing{i}.xlsx",
            [{"instance_id": unique("inst"), "interviewer_id": "INT001"}],
        )
    activity = db.get_project_activity(project_id=project["id"], limit=2)
    assert len(activity) == 2


def test_get_project_activity_without_project_id_spans_all_projects(db, make_project, make_user):
    project_a = make_project()
    project_b = make_project()
    uploader = make_user()
    db.insert_timing_records(project_a["id"], uploader["id"], "a.xlsx", [{"instance_id": unique("inst")}])
    db.insert_timing_records(project_b["id"], uploader["id"], "b.xlsx", [{"instance_id": unique("inst")}])
    activity = db.get_project_activity(limit=100)
    filenames = {a["filename"] for a in activity}
    assert "a.xlsx" in filenames
    assert "b.xlsx" in filenames
