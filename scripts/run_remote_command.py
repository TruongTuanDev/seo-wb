from __future__ import annotations

import os
import sys

import paramiko


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_remote_command.py <command>", file=sys.stderr)
        return 2

    host = os.environ["VPS_HOST"]
    user = os.environ.get("VPS_USER", "root")
    password = os.environ["VPS_PASSWORD"]
    port = int(os.environ.get("VPS_PORT", "22"))
    command = sys.argv[1]

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, port=port, username=user, password=password, timeout=30, banner_timeout=30, auth_timeout=30)
    try:
        stdin, stdout, stderr = ssh.exec_command(command)
        exit_code = stdout.channel.recv_exit_status()
        sys.stdout.write(stdout.read().decode("utf-8", errors="replace"))
        sys.stderr.write(stderr.read().decode("utf-8", errors="replace"))
        return exit_code
    finally:
        ssh.close()


if __name__ == "__main__":
    raise SystemExit(main())
