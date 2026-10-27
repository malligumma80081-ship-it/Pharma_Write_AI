import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.models import (
    Base,
    DraftRevision,
    LiteratureWorkflow,
    Project,
    User,
    WorkflowAssignment,
)
from app.services.workflow_assignments import (
    AssignmentError,
    complete_writer_assignment,
    forward_assignment,
    record_review_decision,
    start_workflow_assignment,
)


@pytest.fixture
def assignment_case():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        users = {
            role: [
                User(
                    id=uuid.uuid4(),
                    email=f"{role}-{index}@example.test",
                    hashed_password="not-used",
                    role=role,
                    is_active=True,
                )
                for index in range(count)
            ]
            for role, count in (
                ("admin", 2),
                ("project_manager", 2),
                ("reviewer", 2),
                ("writer", 2),
            )
        }
        for role_users in users.values():
            db.add_all(role_users)
        db.flush()

        project = Project(
            name="Assignment test",
            research_question="How does the workflow advance?",
            owner_id=users["writer"][0].id,
        )
        db.add(project)
        db.flush()
        workflow = LiteratureWorkflow(
            project_id=project.id,
            research_question=project.research_question,
            status="completed",
            current_stage="pending_human_review",
            result_json={"draft": {"title": "Initial draft"}},
        )
        db.add(workflow)
        db.flush()
        revision = DraftRevision(
            project_id=project.id,
            workflow_id=workflow.id,
            version_number=1,
            content_json={"title": "Initial draft"},
            status="pending_review",
        )
        db.add(revision)
        db.commit()
        yield db, users, workflow, revision
    engine.dispose()


def test_all_assignees_must_act_before_final_admin_approval(assignment_case):
    db, users, workflow, revision = assignment_case
    admins = users["admin"]
    managers = users["project_manager"]
    team_leaders = users["reviewer"]
    writers = users["writer"]

    assert start_workflow_assignment(
        db, workflow, admins[0], [item.id for item in managers]
    ) == "assigned_to_project_manager"
    assert forward_assignment(
        db, workflow, managers[0], [team_leaders[0].id]
    ) == "assigned_to_project_manager"
    assert forward_assignment(
        db, workflow, managers[1], [team_leaders[1].id]
    ) == "assigned_to_team_leader"

    assert forward_assignment(
        db, workflow, team_leaders[0], [writers[0].id]
    ) == "assigned_to_team_leader"
    assert forward_assignment(
        db, workflow, team_leaders[1], [writers[1].id]
    ) == "assigned_to_writer"
    writer_assignments = db.scalars(
        select(WorkflowAssignment).where(
            WorkflowAssignment.workflow_id == workflow.id,
            WorkflowAssignment.stage == "assigned_to_writer",
            WorkflowAssignment.round_number == 1,
        )
    ).all()
    assert {
        item.assigned_user_id: item.assigned_by_id
        for item in writer_assignments
    } == {
        writers[0].id: team_leaders[0].id,
        writers[1].id: team_leaders[1].id,
    }

    assert complete_writer_assignment(db, workflow, writers[0]) == "assigned_to_writer"
    assert complete_writer_assignment(db, workflow, writers[1]) == "team_lead_review"

    assert record_review_decision(
        db, workflow, team_leaders[0], "approved", "Reviewed."
    ) == "team_lead_review"
    assert record_review_decision(
        db, workflow, team_leaders[1], "approved", "Reviewed."
    ) == "project_manager_review"
    assert record_review_decision(
        db, workflow, managers[0], "approved", "Reviewed."
    ) == "project_manager_review"
    assert record_review_decision(
        db, workflow, managers[1], "approved", "Reviewed."
    ) == "admin_review"
    assert record_review_decision(
        db, workflow, admins[0], "approved", "Approved."
    ) == "admin_review"
    assert record_review_decision(
        db, workflow, admins[1], "approved", "Approved."
    ) == "approved_by_admin"

    db.refresh(revision)
    assert revision.status == "approved"
    assert workflow.current_stage == "approved_by_admin"


def test_team_lead_changes_request_returns_to_all_assigned_writers(
    assignment_case,
):
    db, users, workflow, _revision = assignment_case
    admin = users["admin"][0]
    manager = users["project_manager"][0]
    team_leader = users["reviewer"][0]
    writer = users["writer"][0]

    start_workflow_assignment(db, workflow, admin, [manager.id])
    forward_assignment(db, workflow, manager, [team_leader.id])
    forward_assignment(db, workflow, team_leader, [writer.id])
    complete_writer_assignment(db, workflow, writer)

    assert record_review_decision(
        db,
        workflow,
        team_leader,
        "changes_requested",
        "Please revise the conclusion.",
    ) == "assigned_to_writer"
    current_assignment = db.scalar(
        select(WorkflowAssignment).where(
            WorkflowAssignment.workflow_id == workflow.id,
            WorkflowAssignment.stage == "assigned_to_writer",
            WorkflowAssignment.round_number == 2,
        )
    )
    assert current_assignment is not None
    assert current_assignment.assigned_user_id == writer.id
    assert current_assignment.comment is None


def test_user_cannot_act_for_another_role_or_repeat_a_completed_action(
    assignment_case,
):
    db, users, workflow, _revision = assignment_case
    admin = users["admin"][0]
    manager = users["project_manager"][0]
    team_leader = users["reviewer"][0]
    writer = users["writer"][0]

    start_workflow_assignment(db, workflow, admin, [manager.id])
    with pytest.raises(AssignmentError, match="cannot forward"):
        forward_assignment(db, workflow, writer, [team_leader.id])

    forward_assignment(db, workflow, manager, [team_leader.id])
    with pytest.raises(AssignmentError, match="not assigned"):
        forward_assignment(db, workflow, users["reviewer"][1], [writer.id])


def test_project_manager_and_admin_can_return_work_to_previous_review_stages(
    assignment_case,
):
    db, users, workflow, _revision = assignment_case
    admin = users["admin"][0]
    second_admin = users["admin"][1]
    manager = users["project_manager"][0]
    team_leader = users["reviewer"][0]
    writer = users["writer"][0]

    start_workflow_assignment(db, workflow, admin, [manager.id])
    forward_assignment(db, workflow, manager, [team_leader.id])
    forward_assignment(db, workflow, team_leader, [writer.id])
    complete_writer_assignment(db, workflow, writer)
    record_review_decision(db, workflow, team_leader, "approved", "")

    assert record_review_decision(
        db,
        workflow,
        manager,
        "changes_requested",
        "Revise the evidence summary.",
    ) == "assigned_to_writer"
    complete_writer_assignment(db, workflow, writer)
    record_review_decision(db, workflow, team_leader, "approved", "")
    record_review_decision(db, workflow, manager, "approved", "")

    assert record_review_decision(
        db,
        workflow,
        admin,
        "changes_requested",
        "Return to Team Lead for another review.",
    ) == "admin_review"
    assert record_review_decision(
        db,
        workflow,
        second_admin,
        "approved",
        "Approved after the return request.",
    ) == "team_lead_review"
    returned_assignment = db.scalar(
        select(WorkflowAssignment).where(
            WorkflowAssignment.workflow_id == workflow.id,
            WorkflowAssignment.stage == "team_lead_review",
            WorkflowAssignment.round_number == 2,
        )
    )
    assert returned_assignment is not None
    assert returned_assignment.assigned_user_id == team_leader.id
