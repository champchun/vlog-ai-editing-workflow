---
name: local-editing-toolkit
description: >-
  Integrates private local video-editing utilities with this repository's
  Stage 0A-3 Vlog workflow when running in Claude Code (Windows or macOS).
  Use when Claude Code needs local transcription, audio inspection,
  deduplication, beat analysis, rendering, captions, motion cards, or
  editor-timeline export while preserving the approved Stage decisions and
  validation gates.
---

# Local Editing Toolkit (Claude Code)

Use installed local utilities as implementation tools for this repository. The Stage workflow remains the director and source of truth; a tool may analyze, transform, preview, render, or export, but may not make an unapproved editorial decision.

This is the Claude Code variant of this repository's local-editing-toolkit bridge. It is discovered from `.claude/skills/` when Claude Code opens this repository. A separate variant for other runtimes (Antigravity/Gemini CLI) may exist under `.agents/skills/` — the two are read by different tools and are kept independently self-contained; if they ever disagree, follow the current Stage Prompt, not either bridge file.

## Read the governing specification

Before using a tool, read:

1. `PROJECT_INSTRUCTIONS.md`
2. `process/README.md`
3. `process/WORKSPACE_RULES.md`
4. The current `process/stage-*/PROMPT.md`
5. Upstream validation and Human Review artifacts required by that Stage

When this Skill conflicts with a current Stage Prompt, follow the Stage Prompt. Do not invoke an umbrella coordinator persona or an installer persona to run the project. Select individual utilities by capability.

## Authority order

Apply this order whenever inputs disagree:

1. Explicit Human Review and user instructions
2. Current Stage Prompt and approved Stage JSON
3. Storyboard/Human Gate tied to the same content hashes
4. Local tool output
5. Automatic scores, beat estimates, suggested filters, or generated labels

Tools must not overwrite formal upstream facts or silently repair invalid editorial input. Write adapted results, manifests, execution logs, and validation reports to the current Stage's official output path.

## Private tool boundary

Private purchased tools, music, sound effects, templates, and their original instructions remain outside this repository — normally in Claude Code's personal skills directory (`~/.claude/skills/` on macOS/Linux, `%USERPROFILE%\.claude\skills\` on Windows) or another private local directory. Do not copy or commit them into this repository. It is safe to commit this bridge Skill because it contains no private implementation or media asset.

Discover a tool by its capability and available files under the personal skills directory; do not assume a fixed absolute path or a specific vendor/brand name — a given capability may come from any installed skill that fills that role. Record the exact script/tool path, version or content hash, command parameters, and output path when a tool affects an official result. Check dependencies before use (see "Windows and macOS conventions" below). Do not install packages or download models unless that action is already authorized.

## Capability routing

### Stage 0A — objective preprocessing

Local tools may provide exact-duplicate detection, metadata probing, transcription, VAD, audio inspection, scene detection, frame extraction, and proxy pairing.

- Adapt results to the Stage 0A schema; a private tool's JSON is not automatically a formal Stage output.
- Preserve original-media-relative timestamps.
- Transcription must satisfy the Stage 0A VAD, uncertainty, language, and provenance rules. A transcription tool without required VAD or confidence handling needs an adapter or follow-up validation.
- A sampled file hash may propose duplicates; only verified duplicates/proxies are excluded from Source Clip Count.
- Audio inspection may recommend processing, but it must not alter original media or pre-approve a Stage 3 filter chain.

### Stage 0B — visual understanding and Hero Scene review

Local tools may extract frames, contact strips, or short review clips. VLM findings are candidate evidence. The reviewing Agent must open the candidate media itself as required by the Stage 0B Prompt.

- A single midpoint frame cannot prove a dynamic action, reaction, or full Hero Scene.
- Keep VLM nomination and Agent review as separate provenance.
- Extraction tools must preserve source file and source-relative timestamps.
- Tools cannot select the story or convert Hero candidates into approved Shots.

### Stage 0C — event fusion

Use local utilities only for deterministic validation or format conversion. Event boundaries, causality, identity, and Hero Scene handoff follow the Stage 0C evidence rules; tool labels do not override them.

### Stage 0D — full-footage review

Local tools may generate Hero/Contact frames, review proxies, manifests, and the local review interface.

- Every Original Source Video must remain represented.
- Review proxies require verified 1:1 time mapping and never become a Stage 1/2/3 render source.
- Hero Frame and Hero Scene remain distinct concepts.
- Human Review must persist to the official Stage 0D output, not only browser storage.

### Stage 1 — editorial decisions

Automatic beat, frame, transcript, and quality analysis may assist the director Agent but cannot choose the final story.

- Scene Coverage, Human Review, interaction completeness, and Hero Scene director review take priority over music beats.
- Use `process/stage-3-final-color-mix/assets/bgm/*.beats.json` only after source-hash validation and selected-range audition.
- Record music source/timeline mapping and beat alignment in the formal Stage 1 artifacts.
- Local EDL formats are export or execution formats. `edit_decisions.json` and its approved hashes remain authoritative.

### Stage 1R — review before render

Local tools may create storyboards, audiovisual previews, caption/card previews, or crop previews. They may not edit approved decisions in place. Save requested changes, return them to Stage 1, regenerate affected evidence, and obtain a new Human PASS.

### Stage 2 — faithful rough-cut execution

A renderer must execute the approved `edit_decisions.json` exactly.

- Read Original Source paths, never review proxies, storyboard images, or an old render.
- Validate source existence, cut ranges, speed, reframe, audio segments, ordering, duration, and decision hashes before rendering.
- Invalid ranges or unsupported instructions are blocking errors. Do not clamp ranges, drop missing audio/SFX, substitute clips, or continue with a silent downgrade.
- Reusable rendered segments require a cache manifest covering source/content hashes and every render-affecting parameter.
- Save per-Shot execution evidence and run the Stage 2 validation even when a local renderer exits successfully.

### Stage 3 — color, sound, packaging, and delivery

Local tools may provide audio measurements, cleanup filters, ducking, captions, motion cards, final-cache helpers, and editor-timeline export.

- Rebuild picture from Original Source and preserve the approved timeline.
- Treat audio-processing suggestions as candidates; audition important dialogue, children's speech, laughter, ambience, and artifacts before accepting them.
- Sidechain ducking still requires dialogue intelligibility and pumping checks.
- Preview captions, reframes, and cards before final render when they may cover a subject or key action.
- Motion graphics and sound effects are optional packaging, not a reason to change Shot selection or timing.
- Timeline exports must derive from the approved formal decisions and state their target editor/version; an export is a handoff artifact, not a replacement source of truth.

## Adapter and execution records

Whenever a local tool participates in an official Stage result, record:

- capability and concrete tool/script used
- tool version or content hash
- input paths and relevant input hashes
- parameters and environment assumptions
- output paths and output hashes when practical
- schema/timebase conversions
- warnings, unsupported features, and any fallback
- the validation that proves the adapted result is acceptable

If an optional tool is unavailable, follow the Stage Prompt's safe fallback and report the limitation. Do not report a skipped or unavailable capability as PASS.

## Windows and macOS conventions

Discover the actual interpreter and `ffmpeg` location rather than embedding a machine-specific path: use `python3` on macOS/Linux and `python` on Windows when `python3` is unavailable, and check whether a private skill vendors its own `ffmpeg` (e.g. via `static_ffmpeg`) before assuming one on system PATH. Quote paths containing spaces or non-ASCII characters — this repository's own path (`AI VLOG\vlog-ai-editing-workflow`) needs it on Windows. Resolve the personal skills directory per OS (`~/.claude/skills/` vs `%USERPROFILE%\.claude\skills\`) rather than hardcoding one form. Keep generated intermediates under `process/workspace/temp/` and formal outputs under the Stage-specific `process/workspace/project-output/` directory, using whatever path form the invoked tool actually expects on this machine.
