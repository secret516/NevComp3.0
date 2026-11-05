import os
import random
import re
import sqlite3
import subprocess
import time
import uuid
from datetime import datetime, timedelta
from urllib.parse import unquote

import jwt
from flask import (
    Flask, request, redirect, url_for, render_template,
    make_response, g
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "nevcloud.db")
LOGS_DIR = os.path.join(BASE_DIR, "instance_logs")
KB_DIR = os.path.join(BASE_DIR, "kb_articles")
ENV_PATH = os.path.join(BASE_DIR, ".env")

ADMIN_USERNAME = "Luna Rubinance"

SECRET = "trustno1"

INSTANCE_KINDS = ["web", "db", "cache", "worker", "staging"]
REGIONS = ["ap-southeast-jkt", "ap-southeast-sgp", "ap-east-hkg"]
PLANS_BY_KIND = {
    "web": ["Standard-2vCPU-4GB", "Standard-4vCPU-8GB"],
    "db": ["Memory-4vCPU-16GB", "Memory-8vCPU-32GB"],
    "cache": ["Standard-1vCPU-2GB", "Standard-2vCPU-4GB"],
    "worker": ["Standard-2vCPU-4GB", "Compute-4vCPU-4GB"],
    "staging": ["Standard-1vCPU-2GB"],
}
STATUS_WEIGHTS = [("running", 70), ("running", 70), ("stopped", 20), ("degraded", 10)]


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_db(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def init_db():
    first_time = not os.path.exists(DB_PATH)
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user'
        );
        CREATE TABLE IF NOT EXISTS instances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            kind TEXT NOT NULL,
            ip TEXT NOT NULL,
            region TEXT NOT NULL,
            plan TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'running'
        );
        """
    )
    if first_time:
        admin_pw = generate_password_hash(uuid.uuid4().hex)
        db.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, 'admin')",
            (ADMIN_USERNAME, admin_pw),
        )
        admin_id = db.execute(
            "SELECT id FROM users WHERE username = ?", (ADMIN_USERNAME,)
        ).fetchone()[0]
        db.commit()
        db.close()
        seed_instances_for_user("luna-ops", admin_id)
        return
    db.close()


def _random_ip():
    return f"10.{random.randint(10,99)}.{random.randint(0,255)}.{random.randint(2,254)}"


def seed_instances_for_user(username, user_id):
    """Create a plausible, non-identical set of cloud instances (and their
    log files) for a freshly registered account. Uses its own standalone
    connection so it works both inside a request (register()) and at
    startup, outside any Flask app/request context (init_db())."""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    count = random.randint(5, 8)
    kinds = random.sample(INSTANCE_KINDS, k=min(count, len(INSTANCE_KINDS)))
    while len(kinds) < count:
        kinds.append(random.choice(INSTANCE_KINDS))

    used_suffixes = {}
    for kind in kinds:
        used_suffixes[kind] = used_suffixes.get(kind, 0) + 1
        suffix = f"{kind}-{used_suffixes[kind]:02d}"
        name = f"{username}-{suffix}"
        status = random.choices(
            [s for s, _ in STATUS_WEIGHTS],
            weights=[w for _, w in STATUS_WEIGHTS],
            k=1,
        )[0]
        plan = random.choice(PLANS_BY_KIND[kind])
        region = random.choice(REGIONS)
        ip = _random_ip()
        db.execute(
            "INSERT INTO instances (user_id, name, kind, ip, region, plan, status) VALUES (?,?,?,?,?,?,?)",
            (user_id, name, kind, ip, region, plan, status),
        )
        write_instance_log(name, kind, status)
    db.commit()
    db.close()


def write_env_file():
    """
    A leftover .env in the app directory — one of the most common real
    LFI targets there is. USERNAME is the line that matters; the rest is
    realistic filler so it's not the only thing on the page.
    """
    with open(ENV_PATH, "w") as f:
        f.write(
            "# NevCloud — production environment\n"
            "FLASK_ENV=production\n"
            "FLASK_DEBUG=0\n"
            "DATABASE_URL=sqlite:///nevcloud.db\n"
            "SESSION_COOKIE_SECURE=true\n"
            "SUPPORT_EMAIL=support@nevcloud.local\n"
            "DEFAULT_REGION=ap-southeast-jkt\n"
            f"USERNAME={ADMIN_USERNAME}\n"
            "BILLING_PROVIDER=stripe\n"
        )


def write_kb_articles():
    os.makedirs(KB_DIR, exist_ok=True)
    articles = {
        "getting-started": (
            "Getting Started with NevCloud\n\n"
            "Create your first instance from the Dashboard, pick a region "
            "close to your users, and you're live in under a minute."
        ),
        "billing": (
            "Billing & Invoices\n\n"
            "Invoices are generated on the 1st of every month. You can "
            "change your payment method from Account Settings."
        ),
        "ssh-keys": (
            "Managing SSH Keys\n\n"
            "Add a public key under Account Settings > SSH Keys before "
            "provisioning a new instance so it's injected automatically."
        ),
        "backups": (
            "Automatic Backups\n\n"
            "Standard and Memory plans include daily snapshots retained "
            "for 7 days. Snapshots can be restored from the instance page."
        ),
        "networking": (
            "Private Networking\n\n"
            "All instances in the same region share a private 10.0.0.0/8 "
            "network by default, reachable without extra configuration."
        ),
    }
    for slug, body in articles.items():
        with open(os.path.join(KB_DIR, slug + ".txt"), "w") as f:
            f.write(body + "\n")


def _fmt_ts(minutes_ago):
    return (datetime.now() - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%d %H:%M:%S")


def write_instance_log(instance_name, kind, status):
    """Build a log that actually looks like it came from this specific
    instance — content varies by kind, status, and random jitter, so no
    two instances read the same. Lines are grouped into boot / service /
    health sections with a blank line between them so a longer log still
    reads easily instead of becoming a wall of text."""
    os.makedirs(LOGS_DIR, exist_ok=True)
    sections = []

    boot = []
    t = random.randint(180, 1440)
    boot.append(f"[{_fmt_ts(t)}] [boot] {instance_name} provisioning started")
    boot.append(f"[{_fmt_ts(t-1)}] [boot] network interface eth0 up, assigned private IP")
    boot.append(f"[{_fmt_ts(t-2)}] [boot] filesystem mounted, cgroup limits applied")
    boot.append(f"[{_fmt_ts(t-3)}] [boot] {instance_name} started successfully")
    sections.append(boot)

    svc = []
    if kind == "web":
        svc.append(f"[{_fmt_ts(t-4)}] [nginx] worker processes: {random.randint(2,8)}")
        svc.append(f"[{_fmt_ts(t-5)}] [nginx] TLS certificate valid, auto-renew enabled")
        for _ in range(random.randint(6, 11)):
            tt = random.randint(1, 170)
            path = random.choice(
                ["/", "/api/health", "/static/app.js", "/login", "/favicon.ico",
                 "/dashboard", "/help", "/api/instances", "/static/style.css"]
            )
            code = random.choice([200, 200, 200, 200, 304, 404, 500])
            ms = random.randint(4, 220)
            svc.append(f'[{_fmt_ts(tt)}] [access] GET {path} {code} {ms}ms')
        if random.random() < 0.4:
            svc.append(f"[{_fmt_ts(random.randint(1,170))}] [nginx] WARNING slow upstream response ({random.randint(800,2400)}ms)")
    elif kind == "db":
        svc.append(f"[{_fmt_ts(t-4)}] [postgres] database system is ready to accept connections")
        svc.append(f"[{_fmt_ts(t-5)}] [postgres] autovacuum launcher started")
        for _ in range(random.randint(5, 9)):
            tt = random.randint(1, 170)
            conns = random.randint(3, 40)
            svc.append(f"[{_fmt_ts(tt)}] [postgres] active connections: {conns}, checkpoint completed")
        if random.random() < 0.3:
            svc.append(f"[{_fmt_ts(random.randint(1,170))}] [postgres] nightly backup snapshot completed ({round(random.uniform(0.2,4.5),1)}GiB)")
    elif kind == "cache":
        svc.append(f"[{_fmt_ts(t-4)}] [redis] Ready to accept connections")
        for _ in range(random.randint(5, 8)):
            tt = random.randint(1, 170)
            hits = random.randint(100, 9000)
            keys = random.randint(50, 4000)
            svc.append(f"[{_fmt_ts(tt)}] [redis] keyspace hits={hits} keys={keys}")
        if random.random() < 0.35:
            svc.append(f"[{_fmt_ts(random.randint(1,170))}] [redis] evicted {random.randint(10,900)} keys (maxmemory policy allkeys-lru)")
    elif kind == "worker":
        svc.append(f"[{_fmt_ts(t-4)}] [queue] worker pool size: {random.randint(1,6)}")
        for _ in range(random.randint(5, 9)):
            tt = random.randint(1, 170)
            job = random.choice(["send_email", "generate_invoice", "resize_image", "cleanup_tmp", "sync_backup", "export_report"])
            dur = random.randint(10, 900)
            svc.append(f"[{_fmt_ts(tt)}] [queue] job={job} completed in {dur}ms")
        if random.random() < 0.3:
            svc.append(f"[{_fmt_ts(random.randint(1,170))}] [queue] job=send_email retried after transient SMTP timeout")
    elif kind == "staging":
        svc.append(f"[{_fmt_ts(t-4)}] [deploy] staging environment synced from main branch")
        svc.append(f"[{_fmt_ts(t-5)}] [deploy] build #{random.randint(100,999)} deployed")
        svc.append(f"[{_fmt_ts(t-6)}] [deploy] running post-deploy smoke tests")
        svc.append(f"[{_fmt_ts(t-7)}] [deploy] smoke tests passed, traffic shifted to new build")
        if random.random() < 0.3:
            svc.append(f"[{_fmt_ts(t-8)}] [deploy] canary rollback window closed, promoting to stable")
    sections.append(svc)

    health = []
    cpu = random.randint(1, 95) if status != "stopped" else 0
    mem = random.randint(80, 7800) if status != "stopped" else 0
    disk = round(random.uniform(0.5, 18.0), 1)
    if status == "stopped":
        health.append(f"[{_fmt_ts(6)}] [health] shutdown signal received")
        health.append(f"[{_fmt_ts(5)}] [health] instance stopped by user")
    elif status == "degraded":
        health.append(f"[{_fmt_ts(6)}] [health] cpu {cpu}%  mem {mem}MiB  disk {disk}GiB")
        health.append(f"[{_fmt_ts(3)}] [health] WARNING high memory pressure detected")
        health.append(f"[{_fmt_ts(2)}] [health] scheduled auto-restart queued")
        health.append(f"[{_fmt_ts(1)}] [health] monitoring agent heartbeat ok")
    else:
        health.append(f"[{_fmt_ts(6)}] [health] cpu {cpu}%  mem {mem}MiB  disk {disk}GiB")
        health.append(f"[{_fmt_ts(3)}] [health] monitoring agent heartbeat ok")
        health.append(f"[{_fmt_ts(1)}] [health] all checks passed")
    sections.append(health)

    content = "\n\n".join("\n".join(section) for section in sections)
    path = os.path.join(LOGS_DIR, f"{instance_name}.log")
    with open(path, "w") as f:
        f.write(content + "\n")


def create_token(username, role):
    payload = {"username": username, "role": role, "iat": int(time.time())}
    return jwt.encode(payload, SECRET, algorithm="HS256")


def verify_token(token):
    if not token:
        return None
    try:
        return jwt.decode(token, SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def current_user():
    """
    A valid signature only proves the token wasn't tampered with *after*
    being signed with the known secret — it says nothing about whether
    the claimed identity is real. So rather than trusting the token's
    `role` claim at face value, we look the claimed username up and use
    the DB's role as the source of truth. Practical effect: forging a
    token for a username that doesn't exist (e.g. a guessed "admin")
    gets you nowhere — you need the *real* privileged account's username.
    """
    claims = verify_token(request.cookies.get("token"))
    if not claims or not claims.get("username"):
        return None
    db = get_db()
    row = db.execute(
        "SELECT id, username, role FROM users WHERE username = ?",
        (claims["username"],),
    ).fetchone()
    if not row:
        return None
    return {"id": row["id"], "username": row["username"], "role": row["role"]}


@app.route("/")
def index():
    return redirect(url_for("dashboard"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            return render_template("register.html", error="All fields are required.")
        db = get_db()
        existing = db.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if existing:
            return render_template("register.html", error="Username already taken.")
        db.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, 'user')",
            (username, generate_password_hash(password)),
        )
        db.commit()
        user_id = db.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()["id"]
        seed_instances_for_user(username, user_id)
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        if user and check_password_hash(user["password"], password):
            token = create_token(user["username"], user["role"])
            resp = make_response(redirect(url_for("dashboard")))
            resp.set_cookie("token", token, httponly=False)
            return resp
        return render_template("login.html", error="Invalid credentials.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    resp = make_response(redirect(url_for("login")))
    resp.delete_cookie("token")
    return resp


@app.route("/dashboard")
def dashboard():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    db = get_db()
    instances = db.execute(
        "SELECT * FROM instances WHERE user_id = ?", (user["id"],)
    ).fetchall()
    return render_template("dashboard.html", user=user, instances=instances)


@app.route("/logs")
def view_logs():
    """
    Log viewer, scoped strictly to the logged-in user's own instances —
    the filename is resolved against a whitelist built from the DB, not
    taken as a free-form path, so there's nothing to traverse here.
    """
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    db = get_db()
    instances = db.execute(
        "SELECT * FROM instances WHERE user_id = ?", (user["id"],)
    ).fetchall()
    valid_files = {f"{i['name']}.log": i["name"] for i in instances}

    requested = request.args.get("file", "")
    content = None
    error = None
    if requested:
        if requested not in valid_files:
            error = "Unknown log file."
        else:
            try:
                with open(os.path.join(LOGS_DIR, requested), "r", errors="replace") as f:
                    content = f.read()
            except Exception as e:
                error = f"Could not read log: {e}"
    return render_template(
        "logs.html", user=user, instances=instances, requested=requested,
        content=content, error=error,
    )

_KB_CHARSET = re.compile(r"^[A-Za-z0-9._\-/%]+$")
_KB_DECOY_BLOCKLIST = ("etc/passwd", "etc/shadow", "proc/self", "win.ini", "boot.ini")


def resolve_kb_path(raw_query):
    q = raw_query.strip().lstrip("/")

    if not q or not _KB_CHARSET.match(q):
        raise ValueError("rejected by character filter")

    lowered = q.lower()
    if any(bad in lowered for bad in _KB_DECOY_BLOCKLIST):
        raise ValueError("rejected by blocklist")

    while "../" in q:   
        q = q.replace("../", "")

    q = unquote(q)  
    if "." not in q:
        q += ".txt"
    return os.path.join(KB_DIR, q)


SUGGESTED_TOPICS = ["getting-started", "billing", "ssh-keys", "backups", "networking"]


@app.route("/help")
def help_center():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    query = request.args.get("q", "")
    content = None
    error = None
    if query:
        try:
            path = resolve_kb_path(query)
        except ValueError:
            error = "Search query rejected by content filter."
        else:
            try:
                with open(path, "r", errors="replace") as f:
                    content = f.read()
            except Exception:
                error = f'No article found for "{query}".'
    return render_template(
        "help.html", user=user, query=query, content=content, error=error,
        topics=SUGGESTED_TOPICS,
    )


@app.route("/admin")
def admin():
    user = current_user()
    if not user or user.get("role") != "admin":
        return render_template("forbidden.html"), 403
    db = get_db()
    users = db.execute("SELECT id, username, role FROM users").fetchall()
    return render_template("admin.html", user=user, users=users)

CMD_BLACKLIST_CHARS = ["&", "|", "`", "(", ")", " "]


def is_cmd_blacklisted(value):
    return any(c in value for c in CMD_BLACKLIST_CHARS)


@app.route("/admin/diagnostics", methods=["GET", "POST"])
def admin_diagnostics():
    user = current_user()
    if not user or user.get("role") != "admin":
        return render_template("forbidden.html"), 403

    result = None
    host = ""
    error = None
    if request.method == "POST":
        host = request.form.get("host", "")
        if is_cmd_blacklisted(host):
            error = "Blocked character detected in hostname."
        else:
            cmd = "getent hosts " + host
            try:
                proc = subprocess.run(
                    cmd, shell=True, cwd=BASE_DIR,
                    capture_output=True, text=True, timeout=5,
                )
                result = proc.stdout or proc.stderr or "(no output / resolution failed)"
            except Exception as e:
                result = f"Lookup failed: {e}"
    return render_template("admin_diagnostics.html", user=user, result=result, host=host, error=error)


if __name__ == "__main__":
    init_db()
    write_env_file()
    write_kb_articles()
    app.run(host="0.0.0.0", port=5000, debug=False)
