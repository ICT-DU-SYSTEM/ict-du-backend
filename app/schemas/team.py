from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl

from app.models.user import Position
from app.schemas.common import ORM
from app.schemas.user import UserOut


class TeamIn(BaseModel):
    team_name: str = Field(min_length=2, max_length=150)
    description: str | None = None
    event_id: int
    leader_position: Position  # position the creator takes in their own team


class TeamUpdate(BaseModel):
    team_name: str | None = Field(default=None, min_length=2, max_length=150)
    description: str | None = None


class MemberIn(BaseModel):
    position: Position


class MemberOut(ORM):
    id: int
    team_id: int
    user_id: int
    position: Position
    user: UserOut


class TeamOut(ORM):
    id: int
    team_name: str
    description: str | None
    event_id: int
    leader_id: int
    created_at: datetime
    members: list[MemberOut] = []


class GithubProjectIn(BaseModel):
    project_name: str = Field(min_length=1, max_length=150)
    github_url: HttpUrl
    description: str | None = None
    status: str = Field(default="active", max_length=50)


class GithubProjectUpdate(BaseModel):
    project_name: str | None = Field(default=None, min_length=1, max_length=150)
    github_url: HttpUrl | None = None
    description: str | None = None
    status: str | None = Field(default=None, max_length=50)


class GithubProjectOut(ORM):
    id: int
    project_name: str
    github_url: str
    description: str | None
    status: str
    user_id: int
    created_at: datetime
