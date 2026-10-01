from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, owner_or_admin, require_roles
from app.db.session import get_db
from app.models import Event, GithubProject, Role, Team, TeamMember, User
from app.schemas.common import Message
from app.schemas.team import (GithubProjectIn, GithubProjectOut, GithubProjectUpdate, MemberIn, MemberOut, TeamIn,
                              TeamOut, TeamUpdate)

router = APIRouter(prefix="/teams", tags=["Teams"])
student = require_roles(Role.student)


def _team(db: Session, team_id: int) -> Team:
    t = db.scalar(select(Team).where(Team.id == team_id).options(selectinload(Team.members).selectinload(TeamMember.user)))
    if not t:
        raise HTTPException(404, "Team not found")
    return t


@router.get("", response_model=list[TeamOut])
def list_teams(event_id: int | None = None, skip: int = 0, limit: int = Query(50, le=200),
               _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = select(Team).options(selectinload(Team.members).selectinload(TeamMember.user)).order_by(Team.id).offset(skip).limit(limit)
    if event_id:
        q = q.where(Team.event_id == event_id)
    return db.scalars(q).all()


@router.post("", response_model=TeamOut, status_code=201)
def create_team(body: TeamIn, user: User = Depends(student), db: Session = Depends(get_db)):
    if not db.get(Event, body.event_id):
        raise HTTPException(404, "Event not found")
    team = Team(team_name=body.team_name, description=body.description, event_id=body.event_id, leader_id=user.id)
    team.members.append(TeamMember(user_id=user.id, position=body.leader_position))
    db.add(team)
    db.commit()
    return _team(db, team.id)


@router.get("/{team_id}", response_model=TeamOut)
def get_team(team_id: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _team(db, team_id)


@router.patch("/{team_id}", response_model=TeamOut)
def update_team(team_id: int, body: TeamUpdate, user: User = Depends(student), db: Session = Depends(get_db)):
    t = _team(db, team_id)
    owner_or_admin(user, t.leader_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    db.commit()
    return _team(db, team_id)


@router.delete("/{team_id}", response_model=Message)
def delete_team(team_id: int, user: User = Depends(student), db: Session = Depends(get_db)):
    t = _team(db, team_id)
    owner_or_admin(user, t.leader_id)
    db.delete(t)
    db.commit()
    return Message(detail="Team deleted")


# ---- Team members ----
@router.post("/{team_id}/members", response_model=MemberOut, status_code=201, summary="Join a team")
def join_team(team_id: int, body: MemberIn, user: User = Depends(student), db: Session = Depends(get_db)):
    _team(db, team_id)
    m = TeamMember(team_id=team_id, user_id=user.id, position=body.position)
    db.add(m)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "You are already in this team")
    db.refresh(m)
    return m


@router.get("/{team_id}/members", response_model=list[MemberOut])
def list_members(team_id: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _team(db, team_id).members


@router.patch("/{team_id}/members/{user_id}", response_model=MemberOut)
def update_member(team_id: int, user_id: int, body: MemberIn, user: User = Depends(student), db: Session = Depends(get_db)):
    t = _team(db, team_id)
    if user.role != Role.admin and user.id not in (t.leader_id, user_id):
        raise HTTPException(403, "Only the team leader or the member can change a position")
    m = next((m for m in t.members if m.user_id == user_id), None)
    if not m:
        raise HTTPException(404, "Member not found")
    m.position = body.position
    db.commit()
    return m


@router.delete("/{team_id}/members/{user_id}", response_model=Message, summary="Leave team / remove member")
def remove_member(team_id: int, user_id: int, user: User = Depends(student), db: Session = Depends(get_db)):
    t = _team(db, team_id)
    if user.role != Role.admin and user.id not in (t.leader_id, user_id):
        raise HTTPException(403, "Only the team leader or the member can remove a member")
    if user_id == t.leader_id:
        raise HTTPException(400, "The leader cannot leave; delete the team or hand over leadership first")
    m = next((m for m in t.members if m.user_id == user_id), None)
    if not m:
        raise HTTPException(404, "Member not found")
    db.delete(m)
    db.commit()
    return Message(detail="Member removed")


# ---- GitHub projects ----
projects = APIRouter(prefix="/github-projects", tags=["GitHub Projects"])


@projects.get("", response_model=list[GithubProjectOut])
def list_projects(mine: bool = False, skip: int = 0, limit: int = Query(50, le=200),
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = select(GithubProject).order_by(GithubProject.id.desc()).offset(skip).limit(limit)
    if mine:
        q = q.where(GithubProject.user_id == user.id)
    return db.scalars(q).all()


@projects.post("", response_model=GithubProjectOut, status_code=201)
def create_project(body: GithubProjectIn, user: User = Depends(student), db: Session = Depends(get_db)):
    p = GithubProject(**{**body.model_dump(), "github_url": str(body.github_url)}, user_id=user.id)
    db.add(p)
    db.commit()
    return p


def _proj(db: Session, pid: int) -> GithubProject:
    p = db.get(GithubProject, pid)
    if not p:
        raise HTTPException(404, "Project not found")
    return p


@projects.get("/{pid}", response_model=GithubProjectOut)
def get_project(pid: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _proj(db, pid)


@projects.patch("/{pid}", response_model=GithubProjectOut)
def update_project(pid: int, body: GithubProjectUpdate, user: User = Depends(student), db: Session = Depends(get_db)):
    p = _proj(db, pid)
    owner_or_admin(user, p.user_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(p, k, str(v) if k == "github_url" else v)
    db.commit()
    return p


@projects.delete("/{pid}", response_model=Message)
def delete_project(pid: int, user: User = Depends(student), db: Session = Depends(get_db)):
    p = _proj(db, pid)
    owner_or_admin(user, p.user_id)
    db.delete(p)
    db.commit()
    return Message(detail="Project deleted")
