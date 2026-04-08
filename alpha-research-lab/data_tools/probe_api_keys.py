"""
Probe all configured LLM API keys and optionally toggle them on/off in .env.

Usage:
    python data_tools/probe_api_keys.py
    python data_tools/probe_api_keys.py --timeout 15
    python data_tools/probe_api_keys.py --provider google nvidia
    python data_tools/probe_api_keys.py --no-toggle   # skip interactive toggle
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import NamedTuple

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH  = REPO_ROOT / ".env"

# ── Endpoints ────────────────────────────────────────────────────────────────

GOOGLE_GENERATE_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)
OPENAI_COMPAT_URLS: dict[str, str] = {
    "nvidia":      "https://integrate.api.nvidia.com/v1/chat/completions",
    "mistral":     "https://api.mistral.ai/v1/chat/completions",
    "huggingface": "https://router.huggingface.co/v1/chat/completions",
    "vercel":      "https://ai-gateway.vercel.sh/v1/chat/completions",
    "cerebras":    "https://api.cerebras.ai/v1/chat/completions",
    "fireworks":   "https://api.fireworks.ai/inference/v1/chat/completions",
    "groq":        "https://api.groq.com/openai/v1/chat/completions",
    "opencode":    "https://opencode.ai/zen/v1/chat/completions",
}
PROBE_MODELS: dict[str, str] = {
    "nvidia":      "stepfun-ai/step-3.5-flash",
    "mistral":     "mistral-small-latest",
    "huggingface": "meta-llama/Llama-3.1-8B-Instruct:cerebras",
    "vercel":      "google/gemini-2.5-flash-lite",
    "cerebras":    "llama3.1-8b",
    "fireworks":   "accounts/fireworks/models/llama-v3p1-8b-instruct",
    "groq":        "llama-3.1-8b-instant",
    "opencode":    "opencode/minimax-m2.5-free",
}
PROBE_GOOGLE_MODEL = "gemini-2.5-flash-lite"

# All known key names (used to build the toggle list)
ALL_KEY_NAMES: list[str] = [
    "GOOGLE_API_KEY", "GOOGLE_API_KEY_2", "GOOGLE_API_KEY_3",
    "GOOGLE_API_KEY_4", "GOOGLE_API_KEY_5",
    "NVIDIA_API_KEY", "NGC_API_KEY",
    "CEREBRAS_API_KEY",
    "GROQ_API_KEY",
    "MISTRAL_API_KEY", "MISTRAL_COSTRAL_API_KEY",
    "HUGGINGFACE_FINEGRAINED", "HF_TOKEN",
    "FIREWORKS_API_KEY",
    "VERCEL_AI_GATEWAY_API_KEY",
    "OPENCODE_ZEN_API_KEY", "OPENCODE_API_KEY",
    "BASETEN_NEMOTRON_API_KEY", "BASETEN_GLM_47_API_KEY",
]
KEY_PROVIDER: dict[str, str] = {
    "GOOGLE_API_KEY": "google", "GOOGLE_API_KEY_2": "google",
    "GOOGLE_API_KEY_3": "google", "GOOGLE_API_KEY_4": "google",
    "GOOGLE_API_KEY_5": "google",
    "NVIDIA_API_KEY": "nvidia", "NGC_API_KEY": "nvidia",
    "CEREBRAS_API_KEY": "cerebras",
    "GROQ_API_KEY": "groq",
    "MISTRAL_API_KEY": "mistral", "MISTRAL_COSTRAL_API_KEY": "mistral",
    "HUGGINGFACE_FINEGRAINED": "huggingface", "HF_TOKEN": "huggingface",
    "FIREWORKS_API_KEY": "fireworks",
    "VERCEL_AI_GATEWAY_API_KEY": "vercel",
    "OPENCODE_ZEN_API_KEY": "opencode", "OPENCODE_API_KEY": "opencode",
    "BASETEN_NEMOTRON_API_KEY": "baseten", "BASETEN_GLM_47_API_KEY": "baseten",
}


# ── .env file I/O ─────────────────────────────────────────────────────────────

class EnvLine(NamedTuple):
    raw: str        # original line text
    key: str        # key name, or "" for blank/comment
    active: bool    # True = uncommented KEY=val line


def _parse_env_file(path: Path) -> list[EnvLine]:
    lines: list[EnvLine] = []
    if not path.exists():
        return lines
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        # disabled entry: starts with one or more # then KEY=...
        if stripped.startswith("#"):
            rest = stripped.lstrip("#").strip()
            if "=" in rest:
                key = rest.split("=", 1)[0].strip()
                if re.match(r'^[A-Z][A-Z0-9_]*$', key):
                    lines.append(EnvLine(raw, key, False))
                    continue
            lines.append(EnvLine(raw, "", False))
            continue
        # active entry
        if "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if re.match(r'^[A-Z][A-Z0-9_]*$', key):
                lines.append(EnvLine(raw, key, True))
                continue
        lines.append(EnvLine(raw, "", False))
    return lines


def _write_env_file(path: Path, lines: list[EnvLine]) -> None:
    path.write_text("\n".join(line.raw for line in lines) + "\n", encoding="utf-8")


def _toggle_line(line: EnvLine) -> EnvLine:
    if line.active:
        return EnvLine("# " + line.raw, line.key, False)
    else:
        # strip leading #s and one optional space
        new_raw = re.sub(r'^#+\s?', '', line.raw)
        return EnvLine(new_raw, line.key, True)


# ── Flat env map for probing ──────────────────────────────────────────────────

def _active_env_map(env_lines: list[EnvLine]) -> dict[str, str]:
    """Returns {key: value} for all active (uncommented) entries."""
    out: dict[str, str] = {}
    for line in env_lines:
        if line.active and line.key:
            val = line.raw.split("=", 1)[1].strip().strip('"').strip("'")
            out[line.key] = val
    # merge with os.environ (os.environ wins)
    for k, v in os.environ.items():
        if v:
            out[k] = v
    return out


# ── Probe implementations ─────────────────────────────────────────────────────

class ProbeResult(NamedTuple):
    provider:   str
    key_name:   str
    ok:         bool
    latency_ms: int
    note:       str


def _probe_google(key_name: str, key: str, timeout: int) -> ProbeResult:
    url = GOOGLE_GENERATE_URL.format(model=PROBE_GOOGLE_MODEL)
    payload = {
        "contents": [{"parts": [{"text": "Hi"}]}],
        "generationConfig": {"maxOutputTokens": 4},
    }
    t0 = time.perf_counter()
    try:
        r = requests.post(url, json=payload, params={"key": key}, timeout=timeout)
        ms = int((time.perf_counter() - t0) * 1000)
        if r.status_code == 200:
            return ProbeResult("google", key_name, True, ms, PROBE_GOOGLE_MODEL)
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if not isinstance(body, dict):
            body = {}
        err = (body.get("error") or {}).get("message") or r.text[:100]
        return ProbeResult("google", key_name, False, ms, f"HTTP {r.status_code}: {err}")
    except requests.Timeout:
        return ProbeResult("google", key_name, False, timeout * 1000, "timeout")
    except Exception as exc:
        return ProbeResult("google", key_name, False, 0, str(exc)[:100])


def _probe_openai_compat(provider: str, key_name: str, key: str, timeout: int,
                          model: str | None = None) -> ProbeResult:
    url   = OPENAI_COMPAT_URLS[provider]
    model = model or PROBE_MODELS[provider]
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Hi"}],
        "max_tokens": 4,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    t0 = time.perf_counter()
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=timeout)
        ms = int((time.perf_counter() - t0) * 1000)
        if r.status_code == 200:
            return ProbeResult(provider, key_name, True, ms, model)
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if not isinstance(body, dict):
            body = {}
        err = (
            (body.get("error") or {}).get("message") if isinstance(body.get("error"), dict) else None
            or body.get("message")
            or r.text[:100]
        )
        return ProbeResult(provider, key_name, False, ms, f"HTTP {r.status_code}: {err}")
    except requests.Timeout:
        return ProbeResult(provider, key_name, False, timeout * 1000, "timeout")
    except Exception as exc:
        return ProbeResult(provider, key_name, False, 0, str(exc)[:100])


# ── Probe orchestration ───────────────────────────────────────────────────────

def _build_probes(env: dict[str, str], providers: list[str] | None) -> list[tuple]:
    """Return [(key_name, key, probe_fn)] for every active key."""
    want = set(providers) if providers else None

    def _want(p: str) -> bool:
        return want is None or p in want

    probes = []
    seen_keys: set[str] = set()

    for key_name in ALL_KEY_NAMES:
        key = env.get(key_name, "").strip()
        if not key or key in seen_keys:
            continue
        provider = KEY_PROVIDER.get(key_name, "")
        if not provider or not _want(provider):
            continue
        seen_keys.add(key)

        if provider == "google":
            probes.append((key_name, key, lambda kn=key_name, k=key: _probe_google(kn, k, _timeout)))
        elif provider in OPENAI_COMPAT_URLS:
            # mistral codestral key gets a different model
            model_override = "codestral-latest" if key_name == "MISTRAL_COSTRAL_API_KEY" else None
            probes.append((
                key_name, key,
                lambda kn=key_name, k=key, p=provider, mo=model_override:
                    _probe_openai_compat(p, kn, k, _timeout, mo),
            ))

    return probes


_timeout = 20  # module-level so lambdas above can capture it


def _run_probes(probes: list[tuple], timeout: int, color: bool) -> list[ProbeResult]:
    global _timeout
    _timeout = timeout

    ok_s   = "\033[32m OK \033[0m" if color else " OK "
    fail_s = "\033[31mFAIL\033[0m" if color else "FAIL"

    results: list[ProbeResult] = []
    print(f"\nProbing {len(probes)} key(s) with timeout={timeout}s ...\n")
    header = f"{'ST':<4}  {'PROVIDER':<12}  {'KEY_NAME':<30}  {'MS':>7}  NOTE"
    print(header)
    print("─" * (len(header) + 4))

    with ThreadPoolExecutor(max_workers=min(len(probes), 16)) as pool:
        futures = {pool.submit(fn): (kn, k) for kn, k, fn in probes}
        for fut in as_completed(futures):
            r: ProbeResult = fut.result()
            results.append(r)
            st = ok_s if r.ok else fail_s
            ms = f"{r.latency_ms}" if r.ok else f"~{r.latency_ms}"
            print(f"[{st}]  {r.provider:<12}  {r.key_label:<30}  {ms:>7}ms  {r.note}")

    return results


# ProbeResult.key_label alias
ProbeResult.key_label = property(lambda self: self.key_name)  # type: ignore[attr-defined]


# ── Interactive toggle ────────────────────────────────────────────────────────

def _toggle_menu(env_lines: list[EnvLine], results: list[ProbeResult], color: bool) -> None:
    """Show all .env keys with probe results and let the user toggle them."""
    if not ENV_PATH.exists():
        print(f"\n.env not found at {ENV_PATH} — nothing to toggle.")
        return

    result_by_key: dict[str, ProbeResult] = {r.key_name: r for r in results}

    # Build display list: all keys present in .env (active or disabled)
    entries: list[tuple[int, EnvLine]] = [
        (i, line) for i, line in enumerate(env_lines) if line.key
    ]
    if not entries:
        print("\nNo key entries found in .env.")
        return

    ok_c   = "\033[32m" if color else ""
    fail_c = "\033[31m" if color else ""
    off_c  = "\033[90m" if color else ""
    rst    = "\033[0m"  if color else ""

    def _render(entries: list[tuple[int, EnvLine]], env_lines: list[EnvLine]) -> None:
        print(f"\n{'─'*72}")
        print(f"  Manage .env keys  —  enter numbers to toggle, blank to finish")
        print(f"{'─'*72}")
        for num, (line_idx, line) in enumerate(entries, 1):
            state = f"{ok_c}ON {rst}" if line.active else f"{off_c}OFF{rst}"
            r = result_by_key.get(line.key)
            if r is None:
                probe_str = f"{off_c}(not probed){rst}"
            elif r.ok:
                probe_str = f"{ok_c}OK  {r.latency_ms}ms  {r.note}{rst}"
            else:
                note = r.note[:55]
                probe_str = f"{fail_c}FAIL  {note}{rst}"
            print(f"  {num:>2}  [{state}]  {line.key:<32}  {probe_str}")
        print()

    while True:
        _render(entries, env_lines)
        try:
            raw = input("toggle> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not raw:
            break

        tokens = raw.split()
        indices: list[int] = []
        bad: list[str] = []
        for t in tokens:
            try:
                n = int(t)
                if 1 <= n <= len(entries):
                    indices.append(n - 1)
                else:
                    bad.append(t)
            except ValueError:
                bad.append(t)
        if bad:
            print(f"  Ignored unrecognised: {', '.join(bad)}")
        if not indices:
            continue

        toggled: list[str] = []
        for idx in indices:
            line_idx, line = entries[idx]
            new_line = _toggle_line(line)
            env_lines[line_idx] = new_line
            entries[idx] = (line_idx, new_line)
            direction = "OFF" if line.active else "ON"
            toggled.append(f"{line.key} → {direction}")

        _write_env_file(ENV_PATH, env_lines)
        print(f"  Saved: {', '.join(toggled)}")


# ── Summary ───────────────────────────────────────────────────────────────────

def _summary(results: list[ProbeResult]) -> None:
    ok   = [r for r in results if r.ok]
    fail = [r for r in results if not r.ok]
    print(f"\n{'─'*60}")
    print(f"  {len(ok)}/{len(results)} keys OK")
    if fail:
        print(f"  Failed: {', '.join(r.key_name for r in fail)}")
    print(f"{'─'*60}\n")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Probe LLM API keys and optionally toggle them.")
    ap.add_argument(
        "--provider", nargs="+", metavar="PROVIDER",
        choices=sorted(set(KEY_PROVIDER.values())),
        help="Limit to specific providers (default: all).",
    )
    ap.add_argument("--timeout", type=int, default=20,
                    help="Per-request timeout in seconds (default 20).")
    ap.add_argument("--no-toggle", action="store_true",
                    help="Skip the interactive toggle menu.")
    ap.add_argument("--no-color", action="store_true")
    args = ap.parse_args()

    color = not args.no_color and sys.stdout.isatty()

    env_lines = _parse_env_file(ENV_PATH)
    env       = _active_env_map(env_lines)

    probes = _build_probes(env, args.provider)
    if not probes:
        print("No active API keys found for the requested providers.", file=sys.stderr)
        sys.exit(1)

    results = _run_probes(probes, args.timeout, color)
    _summary(results)

    if not args.no_toggle and sys.stdin.isatty():
        _toggle_menu(env_lines, results, color)

    sys.exit(0 if all(r.ok for r in results) else 1)


if __name__ == "__main__":
    main()
