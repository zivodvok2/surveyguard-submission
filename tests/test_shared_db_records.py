"""Unit tests for the per-report-type record insert/get/delete functions
in shared_db.py: quality, backcheck, listen-in, performance, timing,
cancelled interviews, and the shared upload_log housekeeping around them."""
from conftest import unique


def _quality_record(**overrides):
    rec = {
        "instance_id": unique("inst"),
        "interviewer_id": "INT001",
        "interview_date": "2026-01-05",
        "start_time": "09:00",
        "end_time": "09:45",
        "duration_minutes": 45,
        "duration_flag": "Pass",
        "straight_lining": "Pass",
        "region": "North",
        "approval_status": "Approved",
    }
    rec.update(overrides)
    return rec


def test_insert_and_get_quality_records(db, make_project, make_user):
    project = make_project()
    uploader = make_user()
    records = [_quality_record(), _quality_record(duration_flag="Flag", approval_status="Cancelled")]
    upload_id = db.insert_quality_records(project["id"], uploader["id"], "wave1.xlsx", records)
    assert isinstance(upload_id, str) and upload_id

    stored = db.get_quality_records(project["id"])
    assert len(stored) == 2
    flagged = [r for r in stored if r["duration_flag"] == "Flag"]
    assert len(flagged) == 1


def test_insert_quality_records_stores_extra_fields_as_extra_data(db, make_project, make_user):
    project = make_project()
    uploader = make_user()
    records = [_quality_record(some_custom_column="custom-value")]
    db.insert_quality_records(project["id"], uploader["id"], "wave1.xlsx", records)
    stored = db.get_quality_records(project["id"])
    assert stored[0]["extra_data"] is not None
    assert "custom-value" in stored[0]["extra_data"]


def test_get_quality_instance_ids(db, make_project, make_user):
    project = make_project()
    uploader = make_user()
    r1, r2 = _quality_record(), _quality_record()
    db.insert_quality_records(project["id"], uploader["id"], "wave1.xlsx", [r1, r2])
    ids = db.get_quality_instance_ids(project["id"])
    assert r1["instance_id"] in ids
    assert r2["instance_id"] in ids


def test_insert_quality_records_logs_upload(db, make_project, make_user):
    project = make_project()
    uploader = make_user()
    upload_id = db.insert_quality_records(
        project["id"], uploader["id"], "wave1.xlsx", [_quality_record()], wave_label="W1"
    )
    log = db.get_upload_log(project["id"])
    entry = next(e for e in log if e["upload_id"] == upload_id)
    assert entry["report_type"] == "quality_report"
    assert entry["row_count"] == 1
    assert entry["wave_label"] == "W1"


def test_insert_and_get_backcheck_records(db, make_project, make_user):
    project = make_project()
    uploader = make_user()
    rec = {
        "bc_instance_id": unique("bc"),
        "interviewer_id": "INT001",
        "interview_date": "2026-01-05",
        "error_01": 1,
        "error_02": 0,
    }
    db.insert_backcheck_records(project["id"], uploader["id"], "bc.xlsx", [rec])
    stored = db.get_backcheck_records(project["id"])
    assert len(stored) == 1
    assert stored[0]["error_01"] == 1
    assert stored[0]["interviewer_id"] == "INT001"


def test_insert_listen_in_record_single(db, make_project, make_user):
    project = make_project()
    logger = make_user()
    db.insert_listen_in_record(
        project["id"], logger["id"], unique("inst"), "INT002", "South",
        "2026-01-06", "Full", "Pass", None, None,
    )
    stored = db.get_listen_in_records(project["id"])
    assert len(stored) == 1
    assert stored[0]["interviewer_id"] == "INT002"
    assert stored[0]["result"] == "Pass"


def test_insert_listen_in_batch_and_delete_record(db, make_project, make_user):
    project = make_project()
    logger = make_user()
    records = [
        {
            "instance_id": unique("inst"),
            "interviewer_id": "INT003",
            "region": "East",
            "listen_date": "2026-01-07",
            "listen_type": "Partial",
            "result": "Fail",
            "issues_noted": "Rushed answers",
            "action_taken": "Warned",
        }
    ]
    db.insert_listen_in_batch(project["id"], logger["id"], "listenin.xlsx", records)
    stored = db.get_listen_in_records(project["id"])
    assert len(stored) == 1
    record_id = stored[0]["id"]

    db.delete_listen_in_record(record_id)
    assert db.get_listen_in_records(project["id"]) == []


def test_insert_and_get_performance_records(db, make_project, make_user):
    project = make_project()
    uploader = make_user()
    rec = {
        "interviewer_id": "INT004",
        "region": "West",
        "interview_completes": 10,
        "accompaniments": 2,
    }
    db.insert_performance_records(project["id"], uploader["id"], "perf.xlsx", [rec])
    stored = db.get_performance_records(project["id"])
    assert len(stored) == 1
    assert stored[0]["interview_completes"] == 10
    assert stored[0]["accompaniments"] == 2


def test_insert_and_get_timing_records(db, make_project, make_user):
    project = make_project()
    uploader = make_user()
    rec = {
        "instance_id": unique("inst"),
        "interviewer_id": "INT005",
        "region": "North",
        "interview_date": "2026-01-08",
        "duration_minutes": 32.5,
    }
    db.insert_timing_records(project["id"], uploader["id"], "timing.xlsx", [rec])
    stored = db.get_timing_records(project["id"])
    assert len(stored) == 1
    assert stored[0]["duration_minutes"] == 32.5


def test_insert_and_get_cancelled_records(db, make_project, make_user):
    project = make_project()
    uploader = make_user()
    rec = {
        "instance_id": unique("inst"),
        "interviewer_id": "INT006",
        "region": "South",
        "interview_date": "2026-01-09",
        "interview_length": 4.0,
        "same_day_finish": "Yes",
    }
    db.insert_cancelled_records(project["id"], uploader["id"], "cancelled.xlsx", [rec])
    stored = db.get_cancelled_records(project["id"])
    assert len(stored) == 1
    assert stored[0]["same_day_finish"] == "Yes"


def test_upload_lock_flow(db, make_project, make_user):
    project = make_project()
    uploader = make_user()
    upload_id = db.insert_quality_records(project["id"], uploader["id"], "wave1.xlsx", [_quality_record()])
    assert db.is_upload_locked(upload_id) is False
    db.lock_upload(upload_id)
    assert db.is_upload_locked(upload_id) is True


def test_delete_upload_removes_records_and_log_entry(db, make_project, make_user):
    project = make_project()
    uploader = make_user()
    upload_id = db.insert_quality_records(project["id"], uploader["id"], "wave1.xlsx", [_quality_record()])
    assert len(db.get_quality_records(project["id"])) == 1

    db.delete_upload(upload_id, "quality_report")

    assert db.get_quality_records(project["id"]) == []
    log = db.get_upload_log(project["id"])
    assert not any(e["upload_id"] == upload_id for e in log)


def test_delete_wave_records_removes_only_that_wave(db, make_project, make_user):
    project = make_project()
    uploader = make_user()
    db.insert_quality_records(
        project["id"], uploader["id"], "wave1.xlsx", [_quality_record()], wave_label="W1"
    )
    db.insert_quality_records(
        project["id"], uploader["id"], "wave2.xlsx", [_quality_record()], wave_label="W2"
    )
    assert len(db.get_quality_records(project["id"])) == 2

    db.delete_wave_records(project["id"], "W1", "quality_report")

    remaining = db.get_quality_records(project["id"])
    assert len(remaining) == 1
    log = db.get_upload_log(project["id"])
    assert all(e["wave_label"] != "W1" for e in log)


def test_get_upload_log_without_project_id_returns_all(db, make_project, make_user):
    project = make_project()
    uploader = make_user()
    upload_id = db.insert_quality_records(project["id"], uploader["id"], "wave1.xlsx", [_quality_record()])
    log = db.get_upload_log()
    assert any(e["upload_id"] == upload_id for e in log)
    # The all-projects view also carries the project name.
    entry = next(e for e in log if e["upload_id"] == upload_id)
    assert entry["project_name"] == project["name"]
