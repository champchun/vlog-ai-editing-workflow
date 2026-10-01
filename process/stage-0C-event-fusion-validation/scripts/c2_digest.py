#!/usr/bin/env python3
"""Stage 0C step 2: compact per-session evidence digest for event writing.

Each session (group from c1) lists its units with: clip/time range, visual text
(agent-reviewed when available, else VLM), max people counts, final animal labels,
verified/corroborated readable text, overlapping hero candidates with agent status,
and overlapping transcript sentences (id, status, text) — audio context only.

Output: temp/stage0c/digest_<part>.md (split by date) + digest_index.json
"""
from __future__ import annotations

import sys
from pathlib import Path

PROCESS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROCESS / "stage-0A-local-pre-analysis" / "scripts"))
from common import read_json, write_json  # noqa: E402

W = PROCESS / "workspace"
IN0A, IN0B = W / "project-output/stage0a_output", W / "project-output/stage0b_output"
TEMP = W / "temp/stage0c"
PARTS = {"A": ["2026-09-14", "2026-09-24", "2026-09-25"], "B": ["2026-09-26", "2026-09-27"], "C": ["2026-09-28", "2026-09-29"]}


def main():
    groups = read_json(TEMP / "groups.json")["groups"]
    rev = read_json(IN0B / "ai_visual_review.json")
    regions = rev["regions"]
    hc = read_json(IN0B / "hero_scene_candidates.json")["candidates"]
    sents = read_json(IN0A / "transcript_sentences.json")["sentences"]
    by_clip_s = {}
    for s in sents:
        by_clip_s.setdefault(s["clip_id"], []).append(s)
    by_clip_r = {}
    for r in regions:
        by_clip_r.setdefault(r["clip_id"], []).append(r)

    def unit_facts(u):
        rs = [r for r in by_clip_r.get(u["clip_id"], []) if r["end"] >= u["start"] and r["start"] <= u["end"]]
        ad = max([r["visual_people"]["max_adults"] for r in rs] or [0])
        kd = max([r["visual_people"]["max_kids"] for r in rs] or [0])
        an = sorted({a for r in rs for a in r["visual_animals"]["final_visual_label"]})
        txt = sorted({t["text"] for r in rs for t in r["visual_objects"]["readable_text"]
                      if t.get("source") == "agent_review" or t.get("status") == "corroborated_by_0a_ocr"})
        return ad, kd, an, txt[:6]

    index = {}
    for part, days in PARTS.items():
        L = [f"# Stage 0C evidence digest part {part} ({', '.join(days)})",
             "畫面文字 = 視覺證據（agent=Claude 複核；vlm=qwen，可能籠統或人數少算）。台詞 = 聲音語境，R=reliable，U=uncertain（U 不得成為唯一證據）。", ""]
        n = 0
        for g in groups:
            if g["local_date"] not in days:
                continue
            n += 1
            L.append(f"## {g['group_id']}  {g['local_date']}  local {g['abs_start'][11:19]}Z → {g['abs_end'][11:19]}Z (UTC), tz {g['tz']}")
            for u in g["units"]:
                ad, kd, an, txt = unit_facts(u)
                vis = u["text"].replace("\n", " ")
                if len(vis) > 260:
                    vis = vis[:260] + "…"
                L.append(f"- unit {u['unit_id']} [{u['start']:.1f}-{u['end']:.1f}s] ({u['text_source']}) 畫面: {vis}")
                extra = f"  人數上限 大人{ad}/小孩{kd}"
                if an:
                    extra += f"；動物: {', '.join(an)}"
                if txt:
                    extra += f"；可讀文字: {' | '.join(txt)}"
                hs = [h for h in hc if h["clip_id"] == u["clip_id"] and h["candidate_end"] >= u["start"] and h["candidate_start"] <= u["end"]]
                for h in hs:
                    st = h["agent_review"].get("status")
                    if st in ("CONFIRMED", "NEEDS_MORE_REVIEW"):
                        extra += f"；Hero {h['candidate_id']} {st} {h['agent_review'].get('candidate_type')}: {str(h['agent_review'].get('visual_findings'))[:120]}"
                L.append(extra)
                ss = [s for s in by_clip_s.get(u["clip_id"], []) if s["end"] >= u["start"] and s["start"] <= u["end"]]
                ss.sort(key=lambda s: (s["transcript_status"] != "reliable", s["start"]))
                sel = sorted(ss[:8], key=lambda s: s["start"])
                if sel:
                    L.append("  台詞: " + " / ".join(f"{s['sentence_id']}[{'R' if s['transcript_status']=='reliable' else 'U'} {s['start']:.0f}s]{s['text']}" for s in sel)
                             + (f" (+{len(ss)-8} more)" if len(ss) > 8 else ""))
            L.append("")
        p = TEMP / f"digest_{part}.md"
        p.write_text("\n".join(L), encoding="utf-8")
        index[part] = {"days": days, "sessions": n, "chars": len("\n".join(L)), "path": str(p.relative_to(PROCESS.parent))}
    write_json(TEMP / "digest_index.json", index)
    print(index)


if __name__ == "__main__":
    main()
