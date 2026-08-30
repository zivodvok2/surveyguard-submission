"""Unit tests for project CRUD and assignment functions in shared_db.py."""
from conftest import unique


def test_create_project_minimal(db, make_user):
    owner = make_user(role="admin")
    name = unique("Wave 1 Tracking")
    project_id = db.create_project(name, owner["id"])
    project = db.get_project(project_id)
    assert project is not None
    assert project["name"] == name
    assert project["created_by"] == owner["id"]
    assert project["status"] == "active"


def test_get_project_unknown_id_returns_none(db):
    assert db.get_project(999999999) is None


def test_get_project_by_name(db, make_user):
    owner = make_user(role="admin")
    name = unique("Named Project")
    db.create_project(name, owner["id"])
    fetched = db.get_project_by_name(name)
    assert fetched is not None
    assert fetched["name"] == name


def test_get_project_by_name_unknown_returns_none(db):
    assert db.get_project_by_name(unique("nope-project")) is None


def test_create_project_full_sets_all_targets(db, make_user):
    owner = make_user(role="admin")
    name = unique("Full Project")
    project_id = db.create_project_full(
        name=name,
        client="Acme Research",
        sample_target=500,
        start_date="2026-01-01",
        end_date="2026-06-30",
        backcheck_target=0.25,
        listenin_target=0.15,
        accompaniment_target=0.30,
        created_by=owner["id"],
        job_number="J-1001",
        loi_min_minutes=5,
        loi_pct_threshold=0.6,
        flag_warning_pct=4.0,
        flag_critical_pct=8.0,
    )
    project = db.get_project(project_id)
    assert project["client"] == "Acme Research"
    assert project["sample_target"] == 500
    assert project["job_number"] == "J-1001"
    assert project["backcheck_target"] == 0.25
    assert project["flag_critical_pct"] == 8.0


def test_get_all_projects_includes_created_project(db, make_user):
    owner = make_user(role="admin")
    project_id = db.create_project(unique("List Me"), owner["id"])
    all_projects = db.get_all_projects()
    assert any(p["id"] == project_id for p in all_projects)


def test_update_project_changes_only_allowed_fields(db, make_project):
    project = make_project()
    db.update_project(project["id"], client="New Client", status="paused", not_a_real_column="ignored")
    fetched = db.get_project(project["id"])
    assert fetched["client"] == "New Client"
    assert fetched["status"] == "paused"


def test_update_project_with_no_recognised_fields_is_a_noop(db, make_project):
    project = make_project()
    # Only unknown keys — should not raise, and should not touch the row.
    db.update_project(project["id"], totally_unknown_field="x")
    fetched = db.get_project(project["id"])
    assert fetched["name"] == project["name"]


def test_assign_and_list_project_assignees(db, make_project, make_user):
    project = make_project()
    member = make_user()
    db.assign_user_to_project(project["id"], member["id"], project["created_by"])
    assignees = db.get_project_assignees(project["id"])
    assert any(a["id"] == member["id"] for a in assignees)


def test_assign_user_to_project_twice_does_not_duplicate(db, make_project, make_user):
    project = make_project()
    member = make_user()
    db.assign_user_to_project(project["id"], member["id"], project["created_by"])
    db.assign_user_to_project(project["id"], member["id"], project["created_by"])
    assignees = db.get_project_assignees(project["id"])
    matching = [a for a in assignees if a["id"] == member["id"]]
    assert len(matching) == 1


def test_remove_user_from_project(db, make_project, make_user):
    project = make_project()
    member = make_user()
    db.assign_user_to_project(project["id"], member["id"], project["created_by"])
    db.remove_user_from_project(project["id"], member["id"])
    assignees = db.get_project_assignees(project["id"])
    assert not any(a["id"] == member["id"] for a in assignees)


def test_get_project_assignees_empty_for_unassigned_project(db, make_project):
    project = make_project()
    assert db.get_project_assignees(project["id"]) == []
