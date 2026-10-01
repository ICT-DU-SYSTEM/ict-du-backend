from fastapi import APIRouter

from app.api.routes import attendance, auth, content, dashboard, face, reports, teams, users

api = APIRouter()
for r in (auth.router, users.router, content.announcements, content.deadlines, content.events, teams.router, teams.projects,
          reports.router, reports.archives, face.router, attendance.router, dashboard.router):
    api.include_router(r)
