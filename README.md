# ICT DU Management System — Backend (FastAPI)

REST API for student/professor/secretary management, teams, GitHub projects, reports (Student → Secretary → Professor → Archive),
announcements, deadlines, events, dashboards, and **GPS-gated AI face attendance**.

```
1. python -m venv .venv - virtual environment
2. cpo .env.example = cp .env.example .env
3. password = username: admin@school.spcf  password: StrongPassword1
app/
  main.py                  FastAPI app, CORS, rate-limit handler, access log, security headers
  core/                    config (env), security (JWT/bcrypt), limiter, logging, time helpers
  db/                      engine/session, Base
  models/                  SQLAlchemy models (users, content, teams, reports/archives/audit, attendance/face)
  schemas/                 Pydantic request/response models
  api/deps.py              auth + role dependencies
  api/routes/              auth, users, content, teams(+github), reports(+archives), face, attendance, dashboard
  services/                gps, face (InsightFace), antispoof (liveness), attendance rules, drive, dashboard, audit, storage
  scripts/create_admin.py  bootstrap first admin
alembic/                   migrations (0001 = full initial schema)
tests/                     19 tests (auth, RBAC, workflow, geofence, attendance rules)
```

## Attendance flow (server-enforced, not just UI)

```
POST /face/register        once per student: 4-12 frames (blink + turn head)      -> embedding saved
POST /attendance/gps-check lat/lon/accuracy -> outside 100 m: REJECTED (logged), camera_enabled=false
                                            -> inside: camera_enabled=true + 2-minute signed token
POST /attendance/check-in  token + 4-12 frames -> liveness -> ArcFace match -> present (<08:15) / late / rejected
```
* Rule 1 is enforced by the API: `/check-in` refuses any request without a valid, unexpired, same-user GPS token
  (an ordinary login token is rejected). Time is taken from the **server** clock (Asia/Manila), never the client.
* 5 rejected attempts/day locks the student out until a professor intervenes.
* Every accepted/rejected attempt writes an `attendance` row (with `reject_reason`) and an `audit_logs` row.

## Setup — required before first run

1. **Campus coordinates**: set `CAMPUS_LATITUDE` / `CAMPUS_LONGITUDE` in `.env` (Google Maps → right-click campus centre).
   The app refuses to start while they are 0,0.
2. **MiniFASNet models** (passive photo/screen-replay detection): put ONNX exports of Silent-Face-Anti-Spoofing's
   `2.7_80x80_MiniFASNetV2` and `4_0_80x80_MiniFASNetV1SE` in `./models/` and list them in `ANTISPOOF_MODEL_PATHS`.
   The upstream weights are PyTorch `.pth`; export with `torch.onnx.export` (input `1x3x80x80`, output 3 logits, class 1 = real).
   With `ANTISPOOF_REQUIRE_PASSIVE=true` (default) attendance **fails closed** until these exist.
3. **Google Drive** (optional): create a service account, download its JSON to `./secrets/service-account.json`,
   share your Drive folder with the service account's email, set `DRIVE_ENABLED=true` and `GOOGLE_DRIVE_FOLDER_ID`.
   Files are always stored locally too, so a Drive outage never loses a report.

## Run locally (no Docker)
```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env            # edit DATABASE_URL (e.g. sqlite:///./dev.db), SECRET_KEY, campus coords
alembic upgrade head
python -m app.scripts.create_admin admin@school.edu 'StrongPassword1' 'Admin'
uvicorn app.main:app --reload   # docs at http://localhost:8000/docs
pytest
```

## Deploy on Ubuntu 22.04/24.04 with Docker
```bash
# 1. Docker
sudo apt update && sudo apt install -y ca-certificates curl git ufw
curl -fsSL https://get.docker.com | sudo sh && sudo usermod -aG docker $USER && newgrp docker

# 2. App
git clone <your-repo> ict-du && cd ict-du
cp .env.example .env
nano .env        # SECRET_KEY=$(openssl rand -hex 32), DB passwords, CAMPUS_* coords, CORS_ORIGINS=https://your-frontend, ENVIRONMENT=production
# copy MiniFASNet .onnx files into ./models and (optionally) the Drive JSON into ./secrets
docker compose up -d --build
docker compose exec api python -m app.scripts.create_admin admin@school.edu 'StrongPassword1' 'Admin'
curl http://127.0.0.1:8000/health

# 3. Firewall: only SSH + HTTPS/HTTP are public (MySQL is not published; API binds to 127.0.0.1)
sudo ufw allow OpenSSH && sudo ufw allow 80,443/tcp && sudo ufw enable

# 4. HTTPS reverse proxy (REQUIRED: browsers only expose GPS + camera on HTTPS)
sudo apt install -y nginx certbot python3-certbot-nginx
```
`/etc/nginx/sites-available/ictdu`:
```nginx
server {
  server_name api.yourdomain.edu;
  client_max_body_size 12m;
  location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}
```
```bash
sudo ln -s /etc/nginx/sites-available/ictdu /etc/nginx/sites-enabled/ && sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d api.yourdomain.edu
```
Backups: `docker compose exec db sh -c 'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" ictdu' > backup.sql` and back up the `storage` volume
(it holds uploads and face embeddings — treat as sensitive biometric data).

## Roles
| Role | Can |
|---|---|
| admin | everything (all role checks pass) |
| professor | announcements/deadlines/events CRUD, professor report review, view attendance, dashboard, mark absent |
| secretary | secretary report review, download reports, archives, view attendance, dashboard |
| student | register face, submit attendance, teams, GitHub projects, upload/see own reports, read announcements/deadlines/events |

## Known limitations (read before production)
* **Browser GPS is client-supplied.** A determined student can spoof it (mock-location apps, devtools). The 50 m accuracy gate,
  face liveness, and audit trail raise the bar, but for hard guarantees use a native app with mock-location detection,
  or add a second on-campus factor (campus Wi-Fi SSID/IP allow-list, or a rotating QR shown in class).
* Blink/head-turn checks alone can be beaten by a replayed video; the passive MiniFASNet layer is what covers that. Tune
  `FACE_MATCH_THRESHOLD` and `ANTISPOOF_THRESHOLD` on real student data before relying on them.
* Face embeddings are biometric personal data (Philippine Data Privacy Act of 2012): get written consent, restrict
  access to the `storage` volume, and define a retention/deletion policy. Encrypting the `.npy` files at rest is a sensible next step.
* Tests mock the ML layer (no GPU/weights in CI); the InsightFace + MiniFASNet path needs a manual test on real webcam frames.
* The Alembic migration was verified on SQLite (up/down). Run it against MySQL 8 in staging before go-live.
