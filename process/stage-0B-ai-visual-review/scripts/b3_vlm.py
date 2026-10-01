#!/usr/bin/env python3
"""Stage 0B step 3: VLM pixel review (round 1) via local Ollama.

Each planned request (<=2 consecutive frames of one clip) is sent to the VLM with
ONLY the images plus the Stage 0A local labels to confirm/reject. No transcript,
no GPS (audio context is attached later, labelled as audio). Structured output
via JSON schema. One checkpoint file per request; resource usage sampled around
each request; OOM/termination -> degrade ladder per PROMPT.md.

Checkpoints: temp/stage0b/vlm/<request_id>.json   Log: temp/stage0b/vlm_requests.jsonl
"""
from __future__ import annotations

import base64
import re
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from common0b import IN0A, REPO, TEMP, load_json, read_json, write_json

MODEL = "qwen2.5vl:7b"
HOST = "http://127.0.0.1:11434"
BUDGET = {"memory_limit_gb": 8, "limit_mode": "advisory", "max_parallel_jobs": 1, "max_frames_per_request": 1,
          "max_image_edge_px": 720, "context_tokens": 2048, "checkpoint_every_regions": 1, "oom_retry_limit": 3,
          "batch_size": None, "gpu_layers": None, "quantization": None, "model_keep_alive": "10m"}
LADDER = [  # plan A: 1 frame / 720 px / ctx 2048 (prompt ~1300 + output <=450 tokens fit); then shrink image
    (1, 720, 2048), (1, 640, 2048), (1, 560, 2048)]
PEOPLE_ANIMAL_KEYS = {"people", "adult", "child", "baby", "crowd", "teen"}

ENUM_Q = ["blur", "shake", "dark", "overexposed", "occlusion", "bad_framing", "noise"]
S = lambda n: {"type": "string", "maxLength": n}


def schema(n_labels):
    frame = {
        "d": S(70),                                    # visual summary (zh-TW), pixels only
        "adults": {"type": "integer"}, "kids": {"type": "integer"},
        "people_do": S(40),
        "animals": {"type": "array", "items": S(16), "maxItems": 3},
        "animal_sure": {"type": "boolean"},
        "objs": {"type": "array", "items": S(12), "maxItems": 5},
        "text": {"type": "array", "items": S(24), "maxItems": 3},
        "env": S(24),
        "set": {"enum": ["indoor", "outdoor", "underwater", "vehicle", "unknown"]},
        "shot": {"enum": ["extreme_wide", "wide", "medium", "close_up", "extreme_close_up"]},
        "light": {"enum": ["bright", "normal", "dim", "dark"]},
        "tone": {"enum": ["warm", "cool", "neutral", "mixed"]},
        "anchor": {"enum": ["center", "left", "right", "top", "bottom", "spread"]},
        "q": {"type": "array", "items": {"enum": ENUM_Q}, "maxItems": 3},
        "hero": {"type": "boolean"},
        "hero_type": {"enum": ["hook", "climax", "payoff", "emotional", "ending", "scenic", "none"]},
        "hero_why": S(30),
    }
    req = list(frame)
    if n_labels:
        frame["chk"] = {"type": "array", "minItems": n_labels, "maxItems": n_labels,
                        "items": {"enum": ["yes", "no", "unsure"]}}
        req.append("chk")
    return {"type": "object", "properties": frame, "required": req}


SYSTEM = (
    "你是家庭旅遊 Vlog 的影像複核員。只根據圖片實際像素作答，每個字串都要非常精簡。"
    "一律使用台灣繁體字（例如：貓、飲料、室內、販賣機、沒有），絕對不可使用簡體字。"
    "set 只有在明顯看得出是車內／機艙內才用 vehicle，看不出來就用 unknown。"
    "d：一句話描述畫面主體與場景。adults/kids：畫面中看得到的大人與小孩人數（小孩含嬰兒）。"
    "people_do：人物正在做什麼；沒有人寫「無人」。animals：看到的動物名稱，沒有就給空陣列；物種不確定時 animal_sure=false。"
    "objs、text 沒有就給空陣列，不要用「不確定」填充。text 只列清楚可讀的文字原文。不要猜人名、關係、地名。"
    "q 只列明顯的畫質問題，沒有就給空陣列。"
    "hero 只在畫面有明顯情緒、動作高潮、驚喜反應或特別壯觀景色時為 true，否則 false 且 hero_type=none。")


WIRED_BASELINE = None


def wired_gb():
    o = subprocess.run(["vm_stat"], capture_output=True, text=True).stdout
    ps = int(re.search(r"page size of (\d+)", o).group(1))
    return int(re.search(r"Pages wired down:\s+(\d+)", o).group(1)) * ps / 2**30


def mem_sample():
    """Primary metric: system wired-memory delta vs a baseline taken with the model unloaded
    (Metal/unified allocations of llama-server are wired). Approximate: other processes can
    also change wired memory. footprint/ollama ps are recorded for reference only."""
    w = wired_gb()
    fp = None
    pid = subprocess.run(["pgrep", "-f", "llama-server"], capture_output=True, text=True).stdout.split()
    if pid:
        l = subprocess.run(["footprint", "-p", pid[0]], capture_output=True, text=True).stdout.splitlines()
        if len(l) > 1 and "Footprint:" in l[1]:
            fp = l[1].split("Footprint:")[1].split("(")[0].strip()
    mp = subprocess.run(["memory_pressure"], capture_output=True, text=True).stdout.strip().splitlines()
    return {"wired_gb": round(w, 2), "vlm_wired_delta_gb": round(w - WIRED_BASELINE, 2) if WIRED_BASELINE is not None else None,
            "llama_server_footprint": fp,
            "system_free_pct": next((x.split(":")[1].strip() for x in mp if "free percentage" in x), None)}


def resize_b64(path, edge):
    if edge >= 960:
        return base64.b64encode((REPO / path).read_bytes()).decode()
    import cv2
    img = cv2.imread(str(REPO / path))
    h, w = img.shape[:2]
    s = edge / max(h, w)
    img = cv2.resize(img, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA)
    return base64.b64encode(cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])[1].tobytes()).decode()


def call(frames, labels, gap, edge, ctx):
    assert len(frames) == 1
    lb = labels[0]
    lines = ["請描述這張圖。"]
    if lb:
        lines.append("自動標籤（依序判斷是否真的在圖中，chk 依相同順序回答 yes/no/unsure）：" +
                     "；".join(f"{i}. {x}" for i, x in enumerate(lb, 1)))
    body = {"model": MODEL, "stream": False, "keep_alive": BUDGET["model_keep_alive"], "format": schema(len(lb)),
            "options": {"num_ctx": ctx, "temperature": 0, "num_predict": 450},
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": "\n".join(lines),
                          "images": [resize_b64(frames[0]["path"], edge)]}]}
    req = urllib.request.Request(HOST + "/api/chat", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        d = json.loads(r.read())
    out = json.loads(d["message"]["content"])
    filler = {"無", "无", "無人", "无人", "不確定", "不确定", "none", "None", "N/A", ""}
    for k in ("objs", "text", "animals"):
        out[k] = [x for x in out.get(k, []) if x.strip() not in filler]
    if lb:
        out["chk"] = [{"label": l, "verdict": v} for l, v in zip(lb, out.get("chk", []))]
    out["local_labels_given"] = lb
    return {"frames": [out]}, {k: d.get(k) for k in ("total_duration", "load_duration", "prompt_eval_count",
                                                   "prompt_eval_duration", "eval_count", "eval_duration")}


def local_labels(vision, t):
    fr = min(vision["frames"], key=lambda f: abs(f["t"] - t)) if vision and vision.get("frames") else None
    if not fr or abs(fr["t"] - t) > 1.0:
        return []
    ids = [c["id"] for c in fr.get("classes", []) if c["conf"] >= 0.3][:3]
    for a in fr.get("animals", []):
        ids += [l["id"] for l in a["labels"][:1]]
    seen, uniq = set(), []
    for i in ids:
        if i.lower() not in seen:
            seen.add(i.lower())
            uniq.append(i)
    return uniq[:4]


def main():
    plan = read_json(TEMP / "plan.json")
    fman = {f["frame_id"]: f for f in read_json(TEMP / "frames_manifest.json")["frames"]}
    vis0a = {}
    only = set(sys.argv[1:])
    ck = TEMP / "vlm"
    ck.mkdir(parents=True, exist_ok=True)
    log = open(TEMP / "vlm_requests.jsonl", "a", encoding="utf-8")
    global WIRED_BASELINE
    subprocess.run(["ollama", "stop", MODEL], capture_output=True)
    time.sleep(4)
    WIRED_BASELINE = wired_gb()
    write_json(TEMP / "vlm_wired_baseline.json", {"wired_baseline_gb": round(WIRED_BASELINE, 3), "taken": time.time()})
    peak = {"vlm_wired_delta_gb": 0.0}
    t0 = time.time()
    todo = [r for r in plan["requests"] if (not only or r["request_id"] in only or r["clip_id"] in only)
            and not (ck / f"{r['request_id']}.json").exists()]
    print(f"todo {len(todo)} requests", flush=True)
    for k, rq in enumerate(todo):
        cid = rq["clip_id"]
        if cid not in vis0a:
            vis0a[cid] = read_json(REPO / "process/workspace/temp/stage0a/vision" / f"{cid}.json")
        frames = [fman[f] for f in rq["frame_ids"]]
        if any(f.get("error") for f in frames):
            write_json(ck / f"{rq['request_id']}.json", {"request": rq, "status": "FRAME_ERROR"})
            continue
        level, attempts, results = 0, [], None
        while level < len(LADDER):
            nper, edge, ctx = LADDER[level]
            groups = [frames[i:i + nper] for i in range(0, len(frames), nper)]
            before = mem_sample()
            if (before["vlm_wired_delta_gb"] or 0) >= BUDGET["memory_limit_gb"]:
                subprocess.run(["ollama", "stop", MODEL], capture_output=True)
                attempts.append({"level": level, "error": "memory budget reached before request; model unloaded", "mem": before})
                level += 1
                continue
            try:
                results = []
                for g in groups:
                    gap = g[-1]["t"] - g[0]["t"]
                    c, stats = call(g, [local_labels(vis0a[cid], f["t"]) for f in g], gap, edge, ctx)
                    results.append({"frame_ids": [f["frame_id"] for f in g], "times": [f["t"] for f in g],
                                    "output": c, "stats": stats})
                after = mem_sample()
                attempts.append({"level": level, "ok": True, "mem_before": before, "mem_after": after})
                peak["vlm_wired_delta_gb"] = max(peak["vlm_wired_delta_gb"], after["vlm_wired_delta_gb"] or 0)
                break
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ConnectionError, ValueError, json.JSONDecodeError) as e:
                attempts.append({"level": level, "error": repr(e)[:300], "mem": mem_sample()})
                results = None
                if len([a for a in attempts if "error" in a]) > BUDGET["oom_retry_limit"]:
                    break
                level += 1   # OOM/termination/malformed output -> next degrade level (fewer frames, smaller image, smaller ctx)
                time.sleep(3)
        status = "OK" if results else "RESOURCE_BLOCKED"
        rec = {"request": rq, "status": status, "degrade_level": level if results else None,
               "params": {"model": MODEL, "frames_per_call": LADDER[min(level, len(LADDER)-1)][0],
                          "image_edge_px": LADDER[min(level, len(LADDER)-1)][1], "num_ctx": LADDER[min(level, len(LADDER)-1)][2]},
               "attempts": attempts, "results": results}
        write_json(ck / f"{rq['request_id']}.json", rec)
        log.write(json.dumps({"request_id": rq["request_id"], "clip_id": cid, "frames": len(frames), "status": status,
                              "level": rec["degrade_level"], "attempts": len(attempts),
                              "sec": round(sum((r["stats"]["total_duration"] or 0) for r in results) / 1e9, 1) if results else None,
                              "mem": attempts[-1].get("mem_after") or attempts[-1].get("mem")}, ensure_ascii=False) + "\n")
        log.flush()
        el = time.time() - t0
        print(f"[{k+1}/{len(todo)}] {rq['request_id']} {cid[-9:]} {status} L{rec['degrade_level']} "
              f"{el/60:.1f}m eta={(el/(k+1))*(len(todo)-k-1)/3600:.1f}h peak={peak}", flush=True)
    write_json(TEMP / "vlm_peak.json", peak)


if __name__ == "__main__":
    main()
