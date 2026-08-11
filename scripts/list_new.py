#!/usr/bin/env python3
"""
Research Pilot - List New Captures Helper
==============================================
Finds unprocessed capture files in ~/.ra/captures/
Outputs JSON with new file paths for Agent to process.

Usage:
  python list_new.py                    # List all unprocessed
  python list_new.py --reset            # Reset polling state (re-process all)
  python list_new.py --stats            # Show stats only
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Paths
CAPTURES_DIR = Path(os.path.expanduser("~/.ra/captures"))
PROCESSED_DIR = Path(os.path.expanduser("~/.ra/processed"))
STATE_FILE = Path(os.path.expanduser("~/.ra/polling_state.json"))

# Supported filename prefixes (research_ from extension standard captures,
# capture_ from legacy/alt-format captures)
CAPTURE_PREFIXES = ("research_", "capture_")


def load_state():
    """Load or create default polling state."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "enabled": False,
        "interval_minutes": 5,
        "last_poll_time": None,
        "processed_ids": [],
    }


def save_state(state):
    """Save polling state."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def get_all_captures():
    """Get all capture files sorted by modification time (newest first)."""
    if not CAPTURES_DIR.exists():
        return []
    files = []
    for prefix in CAPTURE_PREFIXES:
        files.extend(CAPTURES_DIR.glob(f"{prefix}*.json"))
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return files


def get_new_captures(state):
    """Get captures not yet in processed_ids."""
    processed_set = set(state.get("processed_ids", []))
    all_files = get_all_captures()
    
    new_files = []
    for f in all_files:
        # Extract ID from filename: {prefix}{id}.json
        fname = f.stem  # e.g., "research_1786350258423_d650de9d" or "capture_20260810_171342"
        cid = None
        for prefix in CAPTURE_PREFIXES:
            if fname.startswith(prefix):
                cid = fname[len(prefix):]
                break
        if cid is None:
            continue
        if cid not in processed_set:
            new_files.append({
                "path": str(f),
                "id": cid,
                "mtime": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat(),
                "size": f.stat().st_size,
            })
    
    return new_files


def show_stats(state):
    """Show statistics about captures."""
    all_files = get_all_captures()
    processed_count = len(state.get("processed_ids", []))
    
    print("=" * 50)
    print("  拾知 - Stats")
    print("=" * 50)
    print(f"  Total captures:     {len(all_files)}")
    print(f"  Processed:          {processed_count}")
    print(f"  Unprocessed:        {max(0, len(all_files) - processed_count)}")
    print(f"  Polling enabled:    {state.get('enabled', False)}")
    print(f"  Last poll:          {state.get('last_poll_time', 'never')}")
    print(f"  Interval:           {state.get('interval_minutes', 5)} min")
    print("=" * 50)


def main():
    args = set(sys.argv[1:])
    
    state = load_state()
    
    # Handle --reset flag
    if "--reset" in args:
        state["processed_ids"] = []
        state["last_poll_time"] = None
        save_state(state)
        print("[RESET] Polling state cleared. All captures will be re-processed.")
        return
    
    # Handle --stats flag
    if "--stats" in args:
        show_stats(state)
        return
    
    # Default: list new captures
    new_captures = get_new_captures(state)
    
    output = {
        "ok": True,
        "new_count": len(new_captures),
        "total_captures": len(get_all_captures()),
        "already_processed": len(state.get("processed_ids", [])),
        "polling_enabled": state.get("enabled", False),
        "items": new_captures[:20],  # Limit to 20 per query
        "has_more": len(new_captures) > 20,
    }
    
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
