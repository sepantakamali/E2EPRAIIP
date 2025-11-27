import json
from pathlib import Path
from textclf.persistence import RUNLOG_PATH

def main() -> None:
    if not RUNLOG_PATH.exists():
        print("No runs yet.")
        return
    for line in RUNLOG_PATH.open():
        rec = json.loads(line)
        print(f"{rec['artifact']} | {rec['created_at']} | {rec['version']} | {rec.get('tag','-')}")

if __name__ == "__main__":
    main()