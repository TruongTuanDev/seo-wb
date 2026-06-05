from __future__ import annotations

import os
import posixpath
import sys
from pathlib import Path

import paramiko


HOST = os.environ["VPS_HOST"]
USER = os.environ.get("VPS_USER", "root")
PASSWORD = os.environ["VPS_PASSWORD"]
PORT = int(os.environ.get("VPS_PORT", "22"))
APP_DIR = os.environ.get("VPS_APP_DIR", "/opt/seo-wb")
BRANCH = os.environ.get("VPS_BRANCH", "main")

REPO_SSH_URL = os.environ.get("VPS_REPO_SSH_URL", "git@github.com:TruongTuanDev/seo-wb.git")

LOCAL_BACKEND_ENV = Path("deploy/env/backend.env")
LOCAL_COMPOSE_ENV = Path("deploy/env/compose.env")


def run(ssh: paramiko.SSHClient, command: str, *, check: bool = True) -> tuple[int, str, str]:
    stdin, stdout, stderr = ssh.exec_command(command)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if check and exit_code != 0:
        raise RuntimeError(f"Command failed ({exit_code}): {command}\nSTDOUT:\n{out}\nSTDERR:\n{err}")
    return exit_code, out, err


def ensure_remote_repo(ssh: paramiko.SSHClient) -> None:
    run(ssh, "mkdir -p /opt")
    code, _, _ = run(ssh, f"test -d {APP_DIR}/.git", check=False)
    if code != 0:
        run(ssh, f"rm -rf {APP_DIR}")
        run(ssh, f"git clone {REPO_SSH_URL} {APP_DIR}")
    else:
        run(ssh, f"cd {APP_DIR} && git remote set-url origin {REPO_SSH_URL}")
    run(ssh, f"cd {APP_DIR} && git fetch --prune origin")
    run(ssh, f"cd {APP_DIR} && git checkout {BRANCH}")
    run(ssh, f"cd {APP_DIR} && git reset --hard origin/{BRANCH}")


def ensure_runtime(ssh: paramiko.SSHClient) -> None:
    run(ssh, "export DEBIAN_FRONTEND=noninteractive && apt-get update && apt-get install -y git curl")
    docker_ok = run(ssh, "command -v docker >/dev/null 2>&1", check=False)[0] == 0
    compose_ok = run(ssh, "docker compose version >/dev/null 2>&1", check=False)[0] == 0
    if not docker_ok:
        run(
            ssh,
            "export DEBIAN_FRONTEND=noninteractive && "
            "apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin",
        )
    elif not compose_ok:
        run(
            ssh,
            "export DEBIAN_FRONTEND=noninteractive && "
            "apt-get install -y docker-compose-plugin",
        )
    run(ssh, "systemctl enable --now docker")


def upload_file(sftp: paramiko.SFTPClient, local_path: Path, remote_path: str) -> None:
    remote_dir = posixpath.dirname(remote_path)
    run(ssh, f"mkdir -p {remote_dir}")
    sftp.put(str(local_path), remote_path)


if not LOCAL_BACKEND_ENV.exists() or not LOCAL_COMPOSE_ENV.exists():
    raise SystemExit("Missing local deploy env files.")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30, banner_timeout=30, auth_timeout=30)

try:
    ensure_runtime(ssh)
    ensure_remote_repo(ssh)

    with ssh.open_sftp() as sftp:
        upload_file(sftp, LOCAL_BACKEND_ENV, f"{APP_DIR}/deploy/env/backend.env")
        upload_file(sftp, LOCAL_COMPOSE_ENV, f"{APP_DIR}/deploy/env/compose.env")

    run(ssh, f"cd {APP_DIR} && BRANCH={BRANCH} bash deploy/vps-deploy.sh")

    _, ps_out, _ = run(
        ssh,
        f"cd {APP_DIR} && docker compose --env-file deploy/env/compose.env -f docker-compose.production.yml ps",
    )
    _, backend_health, _ = run(ssh, "curl -fsS http://127.0.0.1:8000/health", check=False)
    _, frontend_head, _ = run(ssh, "curl -I -s http://127.0.0.1:3000", check=False)

    print("=== docker compose ps ===")
    print(ps_out.strip())
    print("=== backend health ===")
    print(backend_health.strip())
    print("=== frontend head ===")
    print(frontend_head.strip())
finally:
    ssh.close()
