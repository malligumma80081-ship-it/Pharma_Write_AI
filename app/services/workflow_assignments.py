import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    DraftRevision,
    LiteratureWorkflow,
    User,
    WorkflowAssignment,
)

FORWARD_STAGES = {
    "assigned_to_project_manager": ("project_manager", "assigned_to_team_leader"),
    "assigned_to_team_leader": ("reviewer", "assigned_to_writer"),
}
REVIEW_ROLES = {
    "team_lead_review": "reviewer",
    "project_manager_review": "project_manager",
    "admin_review": "admin",
}


class AssignmentError(ValueError):
    pass


def _lock_workflow(
    db: Session,
    workflow: LiteratureWorkflow,
) -> LiteratureWorkflow:
    locked_workflow = db.scalar(
        select(LiteratureWorkflow)
        .where(LiteratureWorkflow.id == workflow.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if locked_workflow is None:
        raise AssignmentError("Workflow not found.")
    return locked_workflow


def current_group(
    db: Session,
    workflow: LiteratureWorkflow,
) -> list[WorkflowAssignment]:
    stage = workflow.current_stage
    latest_round = db.scalar(
        select(func.max(WorkflowAssignment.round_number)).where(
            WorkflowAssignment.workflow_id == workflow.id,
            WorkflowAssignment.stage == stage,
        )
    )
    if latest_round is None:
        return []

    return list(
        db.scalars(
            select(WorkflowAssignment)
            .where(
                WorkflowAssignment.workflow_id == workflow.id,
                WorkflowAssignment.stage == stage,
                WorkflowAssignment.round_number == latest_round,
            )
            .order_by(WorkflowAssignment.created_at, WorkflowAssignment.id)
        ).all()
    )


def _latest_group(
    db: Session,
    workflow_id: uuid.UUID,
    stage: str,
) -> list[WorkflowAssignment]:
    latest_round = db.scalar(
        select(func.max(WorkflowAssignment.round_number)).where(
            WorkflowAssignment.workflow_id == workflow_id,
            WorkflowAssignment.stage == stage,
        )
    )
    if latest_round is None:
        return []
    return list(
        db.scalars(
            select(WorkflowAssignment).where(
                WorkflowAssignment.workflow_id == workflow_id,
                WorkflowAssignment.stage == stage,
                WorkflowAssignment.round_number == latest_round,
            )
        ).all()
    )


def assign_group(
    db: Session,
    workflow: LiteratureWorkflow,
    stage: str,
    user_ids: list[uuid.UUID],
    assigned_by: uuid.UUID,
    assigned_by_user: dict[uuid.UUID, uuid.UUID] | None = None,
) -> list[WorkflowAssignment]:
    unique_ids = list(dict.fromkeys(user_ids))
    if not unique_ids:
        raise AssignmentError("Assign at least one user.")

    expected_role = {
        "assigned_to_project_manager": "project_manager",
        "assigned_to_team_leader": "reviewer",
        "assigned_to_writer": "writer",
        "team_lead_review": "reviewer",
        "project_manager_review": "project_manager",
        "admin_review": "admin",
    }[stage]
    users = list(
        db.scalars(
            select(User).where(
                User.id.in_(unique_ids),
                User.role == expected_role,
                User.is_active.is_(True),
            )
        ).all()
    )
    user_lookup = {user.id: user for user in users}
    if set(user_lookup) != set(unique_ids):
        raise AssignmentError(
            f"Every assignee must be an active {expected_role} account."
        )

    next_round = (
        db.scalar(
            select(func.max(WorkflowAssignment.round_number)).where(
                WorkflowAssignment.workflow_id == workflow.id,
                WorkflowAssignment.stage == stage,
            )
        )
        or 0
    ) + 1
    assignments = [
        WorkflowAssignment(
            workflow_id=workflow.id,
            assigned_user_id=user_id,
            assigned_by_id=(
                assigned_by_user.get(user_id, assigned_by)
                if assigned_by_user is not None
                else assigned_by
            ),
            stage=stage,
            round_number=next_round,
            status="pending",
        )
        for user_id in unique_ids
    ]
    workflow.current_stage = stage
    db.add_all(assignments)
    return assignments


def _assignment_for_user(
    db: Session,
    workflow: LiteratureWorkflow,
    user: User,
) -> WorkflowAssignment:
    assignments = current_group(db, workflow)
    assignment = next(
        (
            item
            for item in assignments
            if item.assigned_user_id == user.id
        ),
        None,
    )
    if assignment is None:
        raise AssignmentError("You are not assigned to this workflow stage.")
    if assignment.status != "pending":
        raise AssignmentError("You have already completed this workflow stage.")
    return assignment


def assignable_role(
    db: Session,
    workflow: LiteratureWorkflow,
    user: User,
) -> str:
    if user.role == "admin" and workflow.current_stage in (
        "pending_human_review",
        "submitted_to_team_lead",
        "changes_requested_by_team_lead",
    ):
        existing = db.scalar(
            select(WorkflowAssignment.id)
            .where(WorkflowAssignment.workflow_id == workflow.id)
            .limit(1)
        )
        if existing is None:
            return "project_manager"

    next_stage = FORWARD_STAGES.get(workflow.current_stage)
    if next_stage is None or user.role != next_stage[0]:
        raise AssignmentError("You cannot assign users at this workflow stage.")
    _assignment_for_user(db, workflow, user)
    role_by_stage = {
        "assigned_to_team_leader": "reviewer",
        "assigned_to_writer": "writer",
    }
    return role_by_stage[next_stage[1]]


def forward_assignment(
    db: Session,
    workflow: LiteratureWorkflow,
    user: User,
    target_user_ids: list[uuid.UUID],
) -> str:
    workflow = _lock_workflow(db, workflow)
    expected = FORWARD_STAGES.get(workflow.current_stage)
    if expected is None:
        raise AssignmentError("This workflow stage cannot be forwarded.")
    required_role, next_stage = expected
    if user.role != required_role:
        raise AssignmentError("Your role cannot forward this workflow stage.")

    target_role = {
        "assigned_to_team_leader": "reviewer",
        "assigned_to_writer": "writer",
    }[next_stage]
    unique_ids = list(dict.fromkeys(target_user_ids))
    if not unique_ids:
        raise AssignmentError("Assign at least one user.")
    eligible = set(
        db.scalars(
            select(User.id).where(
                User.id.in_(unique_ids),
                User.role == target_role,
                User.is_active.is_(True),
            )
        ).all()
    )
    if eligible != set(unique_ids):
        raise AssignmentError(
            f"Every assignee must be an active {target_role} account."
        )

    assignment = _assignment_for_user(db, workflow, user)
    assignment.status = "forwarded"
    assignment.target_user_ids = [str(value) for value in unique_ids]
    db.flush()

    assignments = current_group(db, workflow)
    if all(item.status == "forwarded" for item in assignments):
        assigned_by_user: dict[uuid.UUID, uuid.UUID] = {}
        for item in assignments:
            for target_id in item.target_user_ids:
                assigned_by_user.setdefault(
                    uuid.UUID(target_id),
                    item.assigned_user_id,
                )
        forwarded_ids = list(assigned_by_user)
        assign_group(
            db,
            workflow,
            next_stage,
            forwarded_ids,
            user.id,
            assigned_by_user,
        )
    db.commit()
    return workflow.current_stage


def complete_writer_assignment(
    db: Session,
    workflow: LiteratureWorkflow,
    user: User,
    comment: str = "",
) -> str:
    workflow = _lock_workflow(db, workflow)
    if workflow.current_stage != "assigned_to_writer":
        raise AssignmentError("This workflow is not waiting for writers.")
    if user.role != "writer":
        raise AssignmentError("Only assigned writers can complete this stage.")

    assignment = _assignment_for_user(db, workflow, user)
    assignment.status = "completed"
    assignment.comment = comment
    db.flush()

    assignments = current_group(db, workflow)
    if all(item.status == "completed" for item in assignments):
        team_leaders = _latest_group(
            db,
            workflow.id,
            "assigned_to_team_leader",
        )
        if not team_leaders:
            raise AssignmentError("No Team Leader is assigned to this workflow.")
        assign_group(
            db,
            workflow,
            "team_lead_review",
            [item.assigned_user_id for item in team_leaders],
            user.id,
        )
    db.commit()
    return workflow.current_stage


def record_review_decision(
    db: Session,
    workflow: LiteratureWorkflow,
    user: User,
    decision: str,
    comment: str,
) -> str:
    workflow = _lock_workflow(db, workflow)
    expected_role = REVIEW_ROLES.get(workflow.current_stage)
    if expected_role is None:
        raise AssignmentError("This workflow is not waiting for a review.")
    if user.role != expected_role:
        raise AssignmentError("Your role cannot review this workflow stage.")
    if decision not in ("approved", "changes_requested"):
        raise AssignmentError("Decision must be approved or changes_requested.")

    assignment = _assignment_for_user(db, workflow, user)
    assignment.status = decision
    assignment.comment = comment
    db.flush()

    assignments = current_group(db, workflow)
    if not all(
        item.status in ("approved", "changes_requested")
        for item in assignments
    ):
        db.commit()
        return workflow.current_stage

    if any(item.status == "changes_requested" for item in assignments):
        if workflow.current_stage == "admin_review":
            team_leaders = _latest_group(
                db,
                workflow.id,
                "assigned_to_team_leader",
            )
            assign_group(
                db,
                workflow,
                "team_lead_review",
                [item.assigned_user_id for item in team_leaders],
                user.id,
            )
        else:
            writers = _latest_group(
                db,
                workflow.id,
                "assigned_to_writer",
            )
            assign_group(
                db,
                workflow,
                "assigned_to_writer",
                [item.assigned_user_id for item in writers],
                user.id,
            )
    elif workflow.current_stage == "team_lead_review":
        project_managers = _latest_group(
            db,
            workflow.id,
            "assigned_to_project_manager",
        )
        assign_group(
            db,
            workflow,
            "project_manager_review",
            [item.assigned_user_id for item in project_managers],
            user.id,
        )
    elif workflow.current_stage == "project_manager_review":
        admin_ids = list(
            db.scalars(
                select(User.id).where(
                    User.role == "admin",
                    User.is_active.is_(True),
                )
            ).all()
        )
        assign_group(
            db,
            workflow,
            "admin_review",
            admin_ids,
            user.id,
        )
    else:
        workflow.current_stage = "approved_by_admin"
        revision = db.scalar(
            select(DraftRevision)
            .where(DraftRevision.workflow_id == workflow.id)
            .order_by(DraftRevision.version_number.desc())
            .limit(1)
        )
        if revision is not None:
            revision.status = "approved"
            revision.reviewer_comment = comment or "Approved by administrator."

    db.commit()
    return workflow.current_stage


def start_workflow_assignment(
    db: Session,
    workflow: LiteratureWorkflow,
    admin: User,
    project_manager_ids: list[uuid.UUID],
) -> str:
    workflow = _lock_workflow(db, workflow)
    if admin.role != "admin":
        raise AssignmentError("Only an administrator can assign work to managers.")
    existing = db.scalar(
        select(WorkflowAssignment.id)
        .where(WorkflowAssignment.workflow_id == workflow.id)
        .limit(1)
    )
    if existing is not None:
        raise AssignmentError("This workflow already has an assignment history.")
    assign_group(
        db,
        workflow,
        "assigned_to_project_manager",
        project_manager_ids,
        admin.id,
    )
    db.commit()
    return workflow.current_stage


def list_my_assignments(db: Session, user: User) -> list[dict]:
    rows = db.execute(
        select(WorkflowAssignment, LiteratureWorkflow)
        .join(
            LiteratureWorkflow,
            LiteratureWorkflow.id == WorkflowAssignment.workflow_id,
        )
        .where(
            WorkflowAssignment.assigned_user_id == user.id,
            WorkflowAssignment.status == "pending",
            WorkflowAssignment.stage == LiteratureWorkflow.current_stage,
        )
        .order_by(WorkflowAssignment.created_at.desc())
    ).all()

    result = []
    for assignment, workflow in rows:
        if workflow.status not in ("completed", "draft_requires_human_review"):
            continue
        result.append(
            {
                "assignment_id": str(assignment.id),
                "workflow_id": str(workflow.id),
                "project_id": workflow.project_id,
                "research_question": workflow.research_question,
                "stage": assignment.stage,
                "status": assignment.status,
                "created_at": assignment.created_at.isoformat(),
            }
        )
    return result
