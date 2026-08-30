"""Unit tests for supervisor and interviewer-registry functions in shared_db.py,
including cross-project interviewer metrics/analytics and the block/warn/escalate
action log."""
from conftest import unique


def test_create_supervisor_is_idempotent_by_name_case_insensitive(db):
    name = unique("Supervisor")
    sid1 = db.create_supervisor(name, email="sup@example.com")
    sid2 = db.create_supervisor(name.upper())
    assert sid1 == sid2


def test_get_all_supervisors_includes_created(db):
    name = unique("Listed Supervisor")
    sid = db.create_supervisor(name)
    all_sups = db.get_all_supervisors()
    assert any(s["id"] == sid and s["name"] == name for s in all_sups)


def test_update_supervisor(db):
    sid = db.create_supervisor(unique("Original Name"))
    db.update_supervisor(sid, region="Central")
    fetched = next(s for s in db.get_all_supervisors() if s["id"] == sid)
    assert fetched["region"] == "Central"


def test_delete_supervisor_unlinks_interviewers(db):
    sid = db.create_supervisor(unique("To Delete"))
    code = unique("INTX")
    db.upsert_interviewer(code, supervisor_id=sid)
    db.delete_supervisor(sid)
    interviewer = db.get_interviewer_by_code(code)
    assert interviewer["supervisor_id"] is None
    assert not any(s["id"] == sid for s in db.get_all_supervisors())


def test_dedup_supervisors_merges_case_insensitive_duplicates(db):
    base_name = unique("Dup Sup")
    sid_a = db.create_supervisor(base_name)
    # A duplicate row with different casing needs to be inserted directly,
    # since create_supervisor() itself already de-dupes case-insensitively.
    conn = db.get_conn()
    cur = conn.execute("INSERT INTO supervisors (name) VALUES (%s) RETURNING id", (base_name.upper(),))
    sid_b = cur.fetchone()["id"]
    conn.commit()
    conn.close()

    code = unique("INTY")
    db.upsert_interviewer(code, supervisor_id=sid_b)

    result = db.dedup_supervisors()
    assert result["groups_merged"] == 1
    assert result["supervisors_removed"] == 1

    remaining_ids = {s["id"] for s in db.get_all_supervisors() if s["name"].lower() == base_name.lower()}
    assert len(remaining_ids) == 1
    # The interviewer that pointed at the removed duplicate should now point
    # at whichever supervisor row survived the merge.
    interviewer = db.get_interviewer_by_code(code)
    assert interviewer["supervisor_id"] in remaining_ids


def test_upsert_supervisors_bulk_creates_and_reuses(db):
    name1 = unique("Bulk One")
    name2 = unique("Bulk Two")
    result = db.upsert_supervisors_bulk([name1, name2, name1, "", "none"])
    assert name1 in result and name2 in result
    assert len(result) == 2  # blanks / "none" filtered out, duplicate collapsed


def test_upsert_supervisors_bulk_empty_list_returns_empty_dict(db):
    assert db.upsert_supervisors_bulk([]) == {}


def test_upsert_interviewer_creates_then_updates(db):
    code = unique("INTZ")
    iid1 = db.upsert_interviewer(code, name="First Name", region="North")
    iid2 = db.upsert_interviewer(code, name="Updated Name", region="South")
    assert iid1 == iid2
    fetched = db.get_interviewer_by_code(code)
    assert fetched["name"] == "Updated Name"
    assert fetched["region"] == "South"


def test_upsert_interviewer_keeps_existing_name_when_none_given(db):
    code = unique("INTKEEP")
    db.upsert_interviewer(code, name="Keep Me")
    db.upsert_interviewer(code, name=None, region="East")
    fetched = db.get_interviewer_by_code(code)
    assert fetched["name"] == "Keep Me"
    assert fetched["region"] == "East"


def test_get_all_interviewers_includes_supervisor_name(db):
    sid = db.create_supervisor(unique("Sup For List"))
    code = unique("INTLIST")
    db.upsert_interviewer(code, name="Listed", supervisor_id=sid)
    all_interviewers = db.get_all_interviewers()
    row = next(i for i in all_interviewers if i["interviewer_code"] == code)
    assert row["supervisor_name"] is not None


def test_get_interviewer_code_set(db):
    code = unique("INTSET")
    db.upsert_interviewer(code)
    assert code in db.get_interviewer_code_set()


def test_get_interviewer_by_code_unknown_returns_none(db):
    assert db.get_interviewer_by_code(unique("no-such-code")) is None


def test_block_and_unblock_interviewer_logs_actions(db, make_user):
    code = unique("INTBLOCK")
    db.upsert_interviewer(code)
    admin = make_user(role="admin")

    db.block_interviewer(code, admin["id"], message="Fabrication suspected")
    assert db.get_interviewer_by_code(code)["is_blocked"] == 1

    db.unblock_interviewer(code, admin["id"])
    assert db.get_interviewer_by_code(code)["is_blocked"] == 0

    actions = db.get_interviewer_actions(code)
    action_types = [a["action_type"] for a in actions]
    assert "block" in action_types
    assert "unblock" in action_types
    block_action = next(a for a in actions if a["action_type"] == "block")
    assert block_action["message"] == "Fabrication suspected"
    assert block_action["performed_by_name"] == admin["full_name"]


def test_add_interviewer_warning_and_escalation(db, make_user):
    code = unique("INTWARN")
    db.upsert_interviewer(code)
    admin = make_user(role="admin")

    db.add_interviewer_warning(code, admin["id"], "Late submissions", email_sent=True)
    db.add_interviewer_escalation(code, admin["id"], "Repeated lateness")

    actions = db.get_interviewer_actions(code)
    warning = next(a for a in actions if a["action_type"] == "warning")
    escalation = next(a for a in actions if a["action_type"] == "escalation")
    assert warning["email_sent"] == 1
    assert escalation["message"] == "Repeated lateness"


def test_get_interviewer_actions_empty_for_unknown_code(db):
    assert db.get_interviewer_actions(unique("ghost-code")) == []


def test_get_interviewer_metrics_aggregates_across_sources(db, make_project, make_user):
    project = make_project()
    uploader = make_user()
    code = unique("INTMETRICS")
    db.upsert_interviewer(code, name="Metrics Person")

    db.insert_quality_records(
        project["id"], uploader["id"], "wave1.xlsx",
        [{
            "instance_id": unique("inst"), "interviewer_id": code,
            "duration_flag": "Flag", "straight_lining": "Pass",
            "approval_status": "Approved", "duration_minutes": 40,
        }],
    )
    # Real uploads always coerce every error_NN column to an int (see
    # _normalise_backcheck's fillna(0)) — a missing column stays NULL, and
    # SUM(a+b+...) is NULL as soon as any addend is NULL, so all 13 must be
    # given explicitly here to exercise the same path as production data.
    backcheck_record = {f"error_{i:02d}": 0 for i in range(1, 14)}
    backcheck_record.update({"bc_instance_id": unique("bc"), "interviewer_id": code, "error_01": 1})
    db.insert_backcheck_records(project["id"], uploader["id"], "bc.xlsx", [backcheck_record])
    db.insert_listen_in_record(
        project["id"], uploader["id"], unique("inst"), code, "North",
        "2026-01-05", "Full", "Pass", None, None,
    )

    metrics = db.get_interviewer_metrics(code)
    assert metrics["info"]["interviewer_code"] == code
    assert metrics["quality"]["total_interviews"] == 1
    assert metrics["quality"]["duration_flags"] == 1
    assert metrics["backcheck"]["bc_count"] == 1
    assert metrics["backcheck"]["total_errors"] == 1
    assert metrics["listen_in"]["li_count"] == 1
    assert len(metrics["by_project"]) == 1
    assert metrics["by_project"][0]["project_id"] == project["id"]


def test_get_interviewer_analytics_filters_by_region(db):
    code_north = unique("INTNORTH")
    code_south = unique("INTSOUTH")
    db.upsert_interviewer(code_north, region="North")
    db.upsert_interviewer(code_south, region="South")

    result = db.get_interviewer_analytics(region="North")
    codes = {i["code"] for i in result["interviewers"]}
    assert code_north in codes
    assert code_south not in codes
    assert "by_supervisor" in result
    assert "projects" in result


def test_get_interviewer_analytics_no_filters_includes_all(db):
    code = unique("INTALL")
    db.upsert_interviewer(code)
    result = db.get_interviewer_analytics()
    codes = {i["code"] for i in result["interviewers"]}
    assert code in codes
