"""Bounded guarded native API transport; credentials remain in memory."""
from contextlib import contextmanager
import http.client
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import time
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]


def need(value, message):
    if not value:
        raise RuntimeError(message)


def guarded(kubeconfig):
    path = Path(kubeconfig).resolve()
    need(path.is_file() and not (path.stat().st_mode & 0o077), "Private session input must exist with private permissions")
    script = 'set -euo pipefail; set +x; source "$1/scripts/shared/lib.sh"; REPO_ROOT="${RHOAI_ENV_ROOT:-$1}"; load_env >/dev/null; export KUBECONFIG="$2"; check_oc_logged_in >/dev/null; python3 -c "import os,json; print(json.dumps({k:os.environ[k] for k in (\'KUBECONFIG\',\'PATH\',\'HOME\',\'RHOAI_EXPECTED_API_SERVER\') if k in os.environ}))"'
    result = subprocess.run(["/bin/bash", "-c", script, "guard", str(ROOT), str(path)], capture_output=True, text=True, timeout=45)
    need(result.returncode == 0, "Project cluster guard rejected session")
    return {**os.environ, **json.loads(result.stdout)}


def oc(env, *args):
    result = subprocess.run(["oc", "--request-timeout=10s", *args], env=env, capture_output=True, text=True, timeout=25)
    need(result.returncode == 0, "Guarded native API read failed")
    return result.stdout.strip()


def persona(kubeconfig, expected):
    env = guarded(kubeconfig)
    need(oc(env, "whoami") == expected, "Session is not the exact requested persona")
    return env, oc(env, "whoami", "-t")


@contextmanager
def service_transport(env, service, namespace, port, uri, ca, auth_header="Authorization"):
    address = urlparse(uri)
    need(address.scheme == "https" and address.hostname and not address.username and not address.password and not address.query and not address.fragment, "Native service address must be credential-free HTTPS")
    context = ssl.create_default_context(cadata=ca)
    need(auth_header in ('Authorization', 'X-Forwarded-Access-Token'), 'Unreviewed native authentication header')
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        local = reserved.getsockname()[1]
    forward = subprocess.Popen(["oc", "--request-timeout=10s", "port-forward", "-n", namespace, "service/" + service, f"{local}:{port}", "--address=127.0.0.1"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    class NativeHTTPS(http.client.HTTPSConnection):
        def connect(self):
            self.sock = context.wrap_socket(socket.create_connection(("127.0.0.1", local), self.timeout), server_hostname=address.hostname)
    try:
        end = time.monotonic() + 20
        while True:
            need(forward.poll() is None and time.monotonic() < end, "Native service tunnel unavailable")
            try:
                with socket.create_connection(("127.0.0.1", local), timeout=.2):
                    break
            except OSError:
                time.sleep(.1)
        def request(method, path, token=None, workspace=None, body=None):
            need(path.startswith("/") and not path.startswith("//"), "Native API path is invalid")
            headers = {"Accept": "application/json", "Content-Type": "application/json"}
            if token is not None:
                headers[auth_header] = ('Bearer ' if auth_header == 'Authorization' else '') + token
            if workspace is not None:
                headers["X-MLFLOW-WORKSPACE"] = workspace
            connection = NativeHTTPS(address.hostname, timeout=20, context=context)
            try:
                connection.request(method, address.path.rstrip("/") + path, json.dumps(body) if body is not None else None, headers)
                response = connection.getresponse()
                data = response.read(2 * 1024 * 1024 + 1)
                need(len(data) <= 2 * 1024 * 1024, "Native API response exceeds limit")
                try:
                    payload = json.loads(data) if data else None
                except ValueError:
                    payload = None
                # Never return raw errors, URLs or credential-bearing headers.
                return response.status, payload
            finally:
                connection.close()
        yield request
    finally:
        forward.terminate()
        try:
            forward.wait(timeout=5)
        except subprocess.TimeoutExpired:
            forward.kill()
            forward.wait(timeout=5)


def private_receipt(path, data):
    destination = Path(path)
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")
