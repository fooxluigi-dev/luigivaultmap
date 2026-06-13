#!/usr/bin/env python3
"""
Luigi Vault Map — Live data generator
Scans the leads-vault directory and emits a JSON file with:
  - folder stats (file counts, latest mtime)
  - canonical pain files (mention counts, edge scores, freshness)
  - recent inbox files (with post age, category, slug)
  - scan pipeline status (last 4 cron runs from output dir)
  - aggregate stats (total files, total mentions, average edge score)

Output: vault-data.json
"""
import json
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta
import os

VAULT = Path('/Users/openclaw/.hermes/leads-vault')
CRON_OUTPUT = Path('/Users/openclaw/.hermes/cron/output')
TZ_ROME = timezone(timedelta(hours=2))  # CEST

# 10 vault folders (00-Archive added Jun 13: keeps Inbox clean, preserves history)
FOLDERS = [
    ("00-Archive", "🗄️", "Immutable history. Previous scans auto-archived here. Inbox stays clean (~6h).", "#666666"),
    ("01-Inbox", "📥", "Fresh findings, last 6 hours only. Older scans auto-archived to 00-Archive.", "#00f0ff"),
    ("02-Founder-Pain", "🎯", "Categorized pain points. 6 canonical names. Raw, not qualified. Encyclopedia of pain.", "#ff00ff"),
    ("03-Leads", "🚀", "Qualified leads ready for outreach. Status: 🆕🔥📤⏳🏆❌", "#ffaa00"),
    ("04-Patterns", "🔁", "Pain that hits 10+ mentions = service candidate. Tracked weekly with trend arrows.", "#aa00ff"),
    ("05-Services", "🛠️", "Service ideas from patterns. 4 stages: Ideas → Drafts → Tested → Validated.", "#00ff88"),
    ("06-Ideas", "💡", "Free-form inspiration. Not services yet. Random sparks.", "#ffff00"),
    ("07-Playbooks", "📚", "Reusable templates + cold reply scripts.", "#ff6600"),
    ("08-Wins", "🏆", "Closed deals. Case studies. The proof that works.", "#ffd700"),
    ("09-Proof-of-Payment", "💰", "Proof of Payment · screenshots · testimonials · monthly € total.", "#00ff00"),
]

CANONICAL_PAIN_FILES = [
    "ai-automation-implementation-gap",
    "b2b-lead-generation",
    "competitor-and-market-research",
    "eu-market-entry-compliance",
    "indie-launch-distribution",
    "supplier-distributor-search",
]


def parse_pain_file(path: Path) -> dict:
    """Extract mention count, edge score, and pain severity from a canonical pain file."""
    if not path.exists():
        return None
    text = path.read_text()
    info = {"name": path.stem, "path": f"02-Founder-Pain/{path.name}"}
    # Extract total mentions
    m = re.search(r"\*\*Total mentions:\*\*\s*(\d+)", text)
    info["total_mentions"] = int(m.group(1)) if m else 0
    # Extract Luigi Edge Score
    m = re.search(r"Luigi's edge:\s*(\d+)/70", text)
    info["edge_score"] = int(m.group(1)) if m else None
    # Extract pain severity
    m = re.search(r"Pain severity:\s*(\d+)/10", text)
    info["pain_severity"] = int(m.group(1)) if m else None
    # First seen date
    m = re.search(r"\*\*First seen:\*\*\s*(\d{4}-\d{2}-\d{2})", text)
    info["first_seen"] = m.group(1) if m else None
    # Last 7 days delta
    m = re.search(r"Last 7 days.*?\+(\d+)", text)
    info["last_7_delta"] = int(m.group(1)) if m else 0
    # Count source files
    src_files = re.findall(r"^-\s+01-Inbox/.*\.md$", text, re.MULTILINE)
    info["source_file_count"] = len(src_files)
    return info


def parse_inbox_file(path: Path) -> dict:
    """Extract metadata from an inbox lead file."""
    text = path.read_text()
    info = {
        "filename": path.name,
        "path": f"01-Inbox/{path.name}",
        "mtime": path.stat().st_mtime,
    }
    # Extract post age
    m = re.search(r"\*\*Post age:\*\*\s*([^\n]+)", text)
    info["post_age"] = m.group(1).strip() if m else "UNKNOWN"
    # Extract title
    m = re.search(r"\*\*Title:\*\*\s*([^\n]+)", text)
    info["title"] = m.group(1).strip() if m else path.stem
    # Extract category
    m = re.search(r"Canonical pain:\s*([^\n(]+)", text)
    if m:
        info["category"] = m.group(1).strip()
    else:
        # Try to infer from filename
        parts = path.stem.split("-")
        info["category"] = parts[3] if len(parts) > 3 else "unknown"
    # Extract URL
    m = re.search(r"\*\*URL.*?:\*\*\s*(\S+)", text)
    info["url"] = m.group(1).strip() if m else None
    # Extract pain score
    m = re.search(r"Pain score:\s*(\d+)/10", text)
    info["pain_score"] = int(m.group(1)) if m else None
    # Extract Luigi Edge Score total
    m = re.search(r"\*\*Total:\*\*\s*(\d+)/70", text)
    info["edge_score"] = int(m.group(1)) if m else None
    return info


def get_cron_runs() -> list:
    """Get the 4 pain-mining cron runs from ~/.hermes/cron/output/."""
    runs = []
    if not CRON_OUTPUT.exists():
        return runs
    for job_dir in CRON_OUTPUT.iterdir():
        if not job_dir.is_dir():
            continue
        # Get the most recent .md file
        md_files = sorted(job_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not md_files:
            continue
        latest = md_files[0]
        mtime = latest.stat().st_mtime
        runs.append({
            "job_id": job_dir.name,
            "latest_file": latest.name,
            "mtime": mtime,
            "iso": datetime.fromtimestamp(mtime, tz=TZ_ROME).isoformat(),
        })
    # Sort by mtime desc
    runs.sort(key=lambda r: r["mtime"], reverse=True)
    return runs[:4]


def build_graph() -> dict:
    """Build the node/edge graph for the mind map."""
    nodes = []
    edges = []

    # Add folder nodes
    folder_index = {}
    for i, (name, emoji, desc, color) in enumerate(FOLDERS):
        path = VAULT / name
        if not path.exists():
            md_files = []
        elif name == "00-Archive":
            # Archive has date subfolders — recurse to find all .md
            md_files = list(path.rglob("*.md"))
        else:
            # Other folders are flat (top-level only)
            md_files = list(path.glob("*.md"))
        nodes.append({
          "id": name,
          "label": f"{emoji} {name}",
          "type": "folder",
          "color": color,
          "file_count": len(md_files),
          "description": desc,
          "size": 25 + min(len(md_files), 60) * 0.4,  # Scale by file count, capped
        })
        folder_index[name] = i

        # Add ecosystem edges connecting folders in the natural flow
        ecosystem_flow = [
            ("00-Archive", "01-Inbox"),       # archive flows back to inbox for re-emerging pain
            ("01-Inbox", "00-Archive"),       # inbox auto-archives after 6h
            ("01-Inbox", "02-Founder-Pain"),  # inbox updates pain scores
            ("02-Founder-Pain", "04-Patterns"),
            ("04-Patterns", "05-Services"),
            ("02-Founder-Pain", "03-Leads"),
            ("03-Leads", "08-Wins"),
            ("08-Wins", "09-Proof-of-Payment"),
            ("06-Ideas", "05-Services"),
        ]
        for src, tgt in ecosystem_flow:
            if src == name:
                edges.append({"source": src, "target": tgt, "type": "ecosystem"})

    # Add canonical pain file nodes
    for pain_name in CANONICAL_PAIN_FILES:
        path = VAULT / "02-Founder-Pain" / f"{pain_name}.md"
        info = parse_pain_file(path)
        if not info:
            continue
        nodes.append({
            "id": f"pain-{pain_name}",
            "label": f"{pain_name}",
            "type": "pain",
            "color": "#ff00ff",
            "file_count": 1,
            "mentions": info.get("total_mentions", 0),
            "edge_score": info.get("edge_score"),
            "pain_severity": info.get("pain_severity"),
            "last_7_delta": info.get("last_7_delta", 0),
            "first_seen": info.get("first_seen"),
            "size": 12 + min(info.get("total_mentions", 0), 50) * 0.4,
        })
        # Edge: pain file -> 02-Founder-Pain folder
        edges.append({
            "source": f"pain-{pain_name}",
            "target": "02-Founder-Pain",
            "type": "belongs",
        })

    # Add recent inbox files (last 10)
    inbox_path = VAULT / "01-Inbox"
    if inbox_path.exists():
        md_files = sorted(inbox_path.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        for f in md_files[:10]:
            info = parse_inbox_file(f)
            if not info:
                continue
            cat = info.get("category", "unknown")
            # Map category to canonical pain name (best-effort)
            pain_target = None
            for p in CANONICAL_PAIN_FILES:
                if cat in p or p.replace("-", " ") in cat:
                    pain_target = f"pain-{p}"
                    break
            nodes.append({
                "id": f"inbox-{f.stem}",
                "label": info.get("title", f.stem)[:50],
                "type": "inbox",
                "color": "#00f0ff",
                "file_count": 1,
                "category": cat,
                "post_age": info.get("post_age", "UNKNOWN"),
                "edge_score": info.get("edge_score"),
                "pain_score": info.get("pain_score"),
                "size": 8,
                "mtime": info["mtime"],
            })
            # Edge: inbox file -> 01-Inbox folder
            edges.append({"source": f"inbox-{f.stem}", "target": "01-Inbox", "type": "in"})
            # Edge: inbox file -> canonical pain (if matched)
            if pain_target:
                edges.append({"source": f"inbox-{f.stem}", "target": pain_target, "type": "categorize"})

    return {"nodes": nodes, "edges": edges}


def main():
    out = {
        "generated_at": datetime.now(tz=TZ_ROME).isoformat(),
        "vault_path": str(VAULT),
        "folders": [],
        "canonical_pains": [],
        "recent_inbox": [],
        "cron_runs": get_cron_runs(),
        "stats": {},
        "graph": build_graph(),
    }

    total_files = 0
    total_mentions = 0
    edge_scores = []
    for name, emoji, desc, color in FOLDERS:
        path = VAULT / name
        if not path.exists():
            out["folders"].append({
                "name": name, "emoji": emoji, "description": desc, "color": color,
                "file_count": 0, "latest_mtime": None,
            })
            continue
        # Use the same recursive logic for archive, flat for others
        if name == "00-Archive":
            files = list(path.rglob("*.md"))
        else:
            files = [f for f in path.iterdir() if f.suffix == '.md']
        latest_mtime = max((f.stat().st_mtime for f in files), default=None)
        out["folders"].append({
            "name": name,
            "emoji": emoji,
            "description": desc,
            "color": color,
            "file_count": len(files),
            "latest_mtime": latest_mtime,
            "latest_iso": datetime.fromtimestamp(latest_mtime, tz=TZ_ROME).isoformat() if latest_mtime else None,
        })
        total_files += len(files)

    # Canonical pain files
    for pain_name in CANONICAL_PAIN_FILES:
        path = VAULT / "02-Founder-Pain" / f"{pain_name}.md"
        info = parse_pain_file(path)
        if info:
            out["canonical_pains"].append(info)
            total_mentions += info.get("total_mentions", 0)
            if info.get("edge_score"):
                edge_scores.append(info["edge_score"])

    # Recent inbox (last 20)
    inbox_path = VAULT / "01-Inbox"
    if inbox_path.exists():
        md_files = sorted(inbox_path.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        for f in md_files[:20]:
            info = parse_inbox_file(f)
            if info:
                info["iso_mtime"] = datetime.fromtimestamp(info["mtime"], tz=TZ_ROME).isoformat()
                out["recent_inbox"].append(info)

    out["stats"] = {
        "total_files": total_files,
        "total_mentions": total_mentions,
        "avg_edge_score": round(sum(edge_scores) / len(edge_scores), 1) if edge_scores else 0,
        "canonical_pain_count": len(out["canonical_pains"]),
        "graph_node_count": len(out["graph"]["nodes"]),
        "graph_edge_count": len(out["graph"]["edges"]),
    }

    # Write to a stable path
    out_path = Path('/tmp/luigivaultmap/vault-data.json')
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"Wrote {out_path} with {out['stats']['graph_node_count']} nodes, {out['stats']['graph_edge_count']} edges.")
    print(f"Total vault files: {total_files}, total pain mentions: {total_mentions}")


if __name__ == "__main__":
    main()
