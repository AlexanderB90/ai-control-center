"""Start the local development servers: python3 dev.py (Ubuntu/WSL)."""
import argparse
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent


def preflight():
    if sys.platform != "linux":
        raise RuntimeError("Kør startkommandoen i Ubuntu/WSL.")
    python = ROOT / ".venv/bin/python"
    if not python.is_file():
        raise RuntimeError("Projektets .venv mangler. Følg opsætningen i README.")
    for executable in ("node", "npm", "codex"):
        if shutil.which(executable) is None:
            raise RuntimeError(f"{executable} blev ikke fundet i PATH i denne terminal.")
    next_cli = ROOT / "frontend/node_modules/next/dist/bin/next"
    if not next_cli.is_file():
        raise RuntimeError("Frontendpakker mangler. Kør npm ci i frontend-mappen.")
    check = subprocess.run(
        [str(python), "-c", "import uvicorn, fastapi, pydantic"],
        cwd=ROOT, capture_output=True, timeout=15,
    )
    if check.returncode:
        raise RuntimeError(
            "Backendpakker mangler. Kør .venv/bin/python -m pip install "
            "-r backend/requirements.txt fra projektmappen."
        )
    for port in (8000, 3000):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(("127.0.0.1", port))
            except OSError as error:
                raise RuntimeError(
                    f"Port {port} er optaget eller utilgængelig. "
                    "Stop den eksisterende server med Ctrl+C i dens terminal, "
                    "og prøv igen. Ingen eksisterende processer er stoppet."
                ) from error
    return python, next_cli


def signal_group(process, sig):
    try:
        os.killpg(process.pid, sig)
    except ProcessLookupError:
        pass


def stop_servers(processes):
    # Signal only sessions created by this launcher, never port owners.
    for _, process in processes:
        signal_group(process, signal.SIGTERM)
    deadline = time.monotonic() + 8
    for _, process in processes:
        try:
            process.wait(timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            pass
    # Also remove any remaining children (e.g. Next.js workers).
    for _, process in processes:
        signal_group(process, signal.SIGKILL)
        process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="Kontrollér opsætning og porte uden at starte servere.")
    args = parser.parse_args()
    try:
        python, next_cli = preflight()
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        print(f"Kan ikke starte: {error}", file=sys.stderr, flush=True)
        return 1
    if args.check:
        print("Opsætning og porte er klar. Codex-login er ikke testet.")
        return 0

    processes = []

    def interrupted(signum, frame):
        raise KeyboardInterrupt

    previous = {sig: signal.signal(sig, interrupted)
                for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        commands = (
            ("Backend", [str(python), "-m", "uvicorn", "backend.main:app",
                         "--host", "127.0.0.1", "--port", "8000"], ROOT),
            ("Frontend", [shutil.which("node"), str(next_cli), "dev",
                          "--hostname", "127.0.0.1", "--port", "3000"],
             ROOT / "frontend"),
        )
        for name, command, directory in commands:
            # Block termination just while registering the child, so it cannot
            # be orphaned by Ctrl+C between Popen and appending its handle.
            blocked = {signal.SIGINT, signal.SIGTERM}
            old_mask = signal.pthread_sigmask(signal.SIG_BLOCK, blocked)
            try:
                # Restore the parent's mask before exec in the single-threaded
                # launcher; children must receive normal termination signals.
                def restore_mask():
                    signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
                process = subprocess.Popen(
                    command, cwd=directory, stdin=subprocess.DEVNULL,
                    start_new_session=True, preexec_fn=restore_mask,
                )
                processes.append((name, process))
            finally:
                signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
        print(
            "\nStarter AI Control Center. Vent på servernes klar-meldinger."
            "\nDashboard: http://localhost:3000"
            "\nBackend: http://127.0.0.1:8000/health"
            "\nLad terminalen være åben. Ctrl+C stopper begge servere.\n",
            flush=True,
        )
        while True:
            for name, process in processes:
                result = process.poll()
                if result is not None:
                    print(f"{name} stoppede (kode {result}). Stopper begge servere.",
                          file=sys.stderr, flush=True)
                    return 1
            time.sleep(0.25)
    except KeyboardInterrupt:
        print("\nStopper serverne ...", flush=True)
        return 0
    except OSError as error:
        print(f"Opstart fejlede: {error}", file=sys.stderr, flush=True)
        return 1
    finally:
        for sig in previous:
            signal.signal(sig, signal.SIG_IGN)
        try:
            stop_servers(processes)
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)


if __name__ == "__main__":
    sys.exit(main())
