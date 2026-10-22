"""Conservative pre-commit/CI check; not a comprehensive DLP scanner."""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOCKED = re.compile(r"(?i)(^|/)(?:vault|knowledge-base|evidence|assessments|documents|confidential|secrets?)(?:/|$)|\.(?:pdf|docx?|xlsx?|pptx?|zip|7z|p12|pfx|pem|key|sqlite3?|db)$|(^|/)\.env(?:\.|$)")
SECRET = re.compile(r"(?i)(?:-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\s*[:=]\s*['\"][^'\"]{8,}['\"])")
def main():
    mode = "--staged" if "--staged" in sys.argv else "--tracked"
    command = ["git", "diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR"] if mode == "--staged" else ["git", "ls-files", "-z"]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, check=True)
    paths = [p.decode("utf-8", "replace") for p in result.stdout.split(b"\0") if p]
    errors = []
    for name in paths:
        if BLOCKED.search(name):
            errors.append(f"Forbidden file category: {name}")
            continue
        if mode == "--staged":
            blob = subprocess.run(["git", "show", ":" + name], cwd=ROOT, capture_output=True)
            if blob.returncode: continue
            content = blob.stdout
        else:
            try: content = (ROOT / name).read_bytes()
            except (OSError, IsADirectoryError): continue
        if len(content) > 1_000_000:
            errors.append(f"File requires manual review (>1MB): {name}")
        elif b"\0" in content:
            errors.append(f"Binary file requires manual review: {name}")
        elif SECRET.search(content.decode("utf-8", "replace")):
            errors.append(f"Possible credential: {name}")
    for e in errors: print(e, file=sys.stderr)
    if errors:
        print("Security scan failed. Review files; do not bypass for sensitive content.",file=sys.stderr)
    else: print("Security scan passed (limited checks; not DLP).")
    return int(bool(errors))
if __name__ == "__main__": raise SystemExit(main())
