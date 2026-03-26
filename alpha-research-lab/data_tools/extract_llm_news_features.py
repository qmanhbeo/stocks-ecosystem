"""
Extract structured LLM features from CafeF daily news JSONL files.

Input:
- data/news/cafef/raw/YYYY-MM-DD.jsonl

Output:
- data/llm_cache/YYYY-MM-DD.jsonl (one JSON object per filtered article)

Design:
- Resume-safe: skip existing day outputs unless --overwrite
- Atomic writes: write .tmp then rename
- Robust parse: accept imperfect LLM outputs, salvage partial objects where possible
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import math
import re
import threading
import time
import unicodedata
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "news" / "cafef" / "raw"
CACHE_DIR = REPO_ROOT / "data" / "llm_cache"

EVENT_TYPES = {
    "earnings_beat", "earnings_miss", "earnings_neutral", "revenue_growth",
    "revenue_decline", "guidance_raise", "guidance_cut", "dividend_announce",
    "debt_issue", "debt_concern", "rights_issue", "buyback", "merger_acquisition",
    "divestiture", "ipo_listing", "management_change", "insider_buy", "insider_sell",
    "contract_win", "contract_loss", "partnership", "expansion", "legal_issue",
    "regulatory_approval", "regulatory_block", "policy_positive", "policy_negative",
    "rate_change", "fx_move", "commodity_price", "macro_indicator",
    "index_inclusion", "index_exclusion", "other", "no_event",
}

PROMPT_TAXONOMY = (
    "earnings_beat, earnings_miss, earnings_neutral, revenue_growth, revenue_decline, "
    "guidance_raise, guidance_cut, dividend_announce, debt_issue, debt_concern, "
    "rights_issue, buyback, merger_acquisition, divestiture, ipo_listing, "
    "management_change, insider_buy, insider_sell, contract_win, contract_loss, "
    "partnership, expansion, legal_issue, regulatory_approval, regulatory_block, "
    "policy_positive, policy_negative, rate_change, fx_move, commodity_price, "
    "macro_indicator, index_inclusion, index_exclusion, other, no_event"
)

# Archive files do not include section/category; filter using URL/title/summary/body text.
FIN_KEYWORDS = [
    "chung khoan", "co phieu", "doanh nghiep", "tai chinh", "ngan hang",
    "bat dong san", "dau tu", "ipo", "co tuc", "loi nhuan", "doanh thu",
    "phat hanh", "mua lai", "sap nhap", "trai phieu", "tin dung", "vn-index",
]

_LOG_LOCK = threading.Lock()


def _log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _LOG_LOCK:
        print(f"[{ts}] {msg}", flush=True)


def _strip_vi(s: str) -> str:
    s = str(s).replace("đ", "d").replace("Đ", "D")
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii").lower()


def _iter_dates(date_from: str, date_to: str) -> list[Path]:
    files = sorted(p for p in RAW_DIR.glob("*.jsonl") if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.stem))
    if date_from:
        files = [p for p in files if p.stem >= date_from]
    if date_to:
        files = [p for p in files if p.stem <= date_to]
    return files


def _load_articles(path: Path) -> list[dict]:
    out = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _is_financial_article(article: dict) -> bool:
    text = " ".join(
        [
            str(article.get("url", "") or ""),
            str(article.get("title", "") or ""),
            str(article.get("summary", "") or ""),
            str(article.get("body_text", "") or ""),
            " ".join(article.get("tags") or []),
            str(article.get("section", "") or ""),
            str(article.get("category", "") or ""),
        ]
    )
    norm = _strip_vi(text)
    return any(k in norm for k in FIN_KEYWORDS)


def _chunk(seq: list[dict], n: int) -> Iterable[list[dict]]:
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def _build_prompt(batch: list[dict], max_summary_chars: int) -> str:
    lines = [
        "You are a Vietnamese financial news analyzer.",
        "For each numbered article, output a JSON object with fields:",
        "id, tickers, sentiment (-1/0/1), confidence (0-2), event_type, magnitude (0-2),",
        "is_forward_looking (bool), market_tone (-1/0/1).",
        "",
        f"Event types: {PROMPT_TAXONOMY}",
        "Output ONLY a JSON array of objects, one per article. No explanation.",
        "",
    ]
    for i, a in enumerate(batch, start=1):
        title = str(a.get("title", "") or "").strip()
        summary = str(a.get("summary", "") or "").strip()
        if max_summary_chars > 0:
            summary = summary[:max_summary_chars]
        aid = a["id"]
        lines.extend(
            [
                f"[{i}] id={aid}",
                f"Tieu de: {title}",
                f"Tom tat: {summary}",
                "",
            ]
        )
    return "\n".join(lines)


def _call_ollama(prompt: str, model: str, timeout: int, num_predict: int) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0, "num_predict": num_predict},
    }
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8", errors="replace"))
    return str(body.get("response", "") or "")


def _extract_json_array(text: str) -> list[dict] | None:
    text = text.strip()
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return None
    chunk = text[start : end + 1]
    try:
        arr = json.loads(chunk)
        if isinstance(arr, list):
            return [x for x in arr if isinstance(x, dict)]
    except Exception:
        pass

    # salvage: split top-level object slices by brace depth
    objs: list[dict] = []
    depth = 0
    obj_start = -1
    for i, ch in enumerate(chunk):
        if ch == "{":
            if depth == 0:
                obj_start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and obj_start != -1:
                cand = chunk[obj_start : i + 1]
                try:
                    parsed = json.loads(cand)
                    if isinstance(parsed, dict):
                        objs.append(parsed)
                except Exception:
                    continue
    return objs or None


def _norm_tickers(v: object) -> list[str]:
    if not isinstance(v, list):
        return []
    out = []
    for t in v:
        s = str(t).strip().upper()
        if re.fullmatch(r"[A-Z0-9]{2,6}", s):
            out.append(s)
    return sorted(set(out))


def _norm_small_int(v: object, allowed: set[int]) -> int | None:
    try:
        x = int(v)
    except Exception:
        return None
    return x if x in allowed else None


def _norm_bool(v: object) -> bool | None:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"true", "1", "yes"}:
            return True
        if s in {"false", "0", "no"}:
            return False
    if isinstance(v, (int, float)):
        if v == 1:
            return True
        if v == 0:
            return False
    return None


def _normalize_record(raw: dict, fallback_id: str) -> dict:
    ev = str(raw.get("event_type", "") or "").strip().lower()
    if ev not in EVENT_TYPES:
        ev = None
    rid = str(raw.get("id", "") or fallback_id).strip() or fallback_id
    return {
        "id": rid,
        "tickers": _norm_tickers(raw.get("tickers")),
        "sentiment": _norm_small_int(raw.get("sentiment"), {-1, 0, 1}),
        "confidence": _norm_small_int(raw.get("confidence"), {0, 1, 2}),
        "event_type": ev,
        "magnitude": _norm_small_int(raw.get("magnitude"), {0, 1, 2}),
        "is_forward_looking": _norm_bool(raw.get("is_forward_looking")),
        "market_tone": _norm_small_int(raw.get("market_tone"), {-1, 0, 1}),
    }


def _blank_record(article: dict, err: str) -> dict:
    return {
        "id": article["id"],
        "tickers": [],
        "sentiment": None,
        "confidence": None,
        "event_type": None,
        "magnitude": None,
        "is_forward_looking": None,
        "market_tone": None,
        "llm_error": err,
    }


def process_day(
    path: Path,
    batch_size: int,
    model: str,
    timeout: int,
    num_predict: int,
    max_summary_chars: int,
    log_every_batches: int,
) -> dict:
    date = path.stem
    day_t0 = time.time()
    _log(f"[{date}] start")
    articles = _load_articles(path)
    filtered = [a for a in articles if _is_financial_article(a)]
    for i, a in enumerate(filtered, start=1):
        a["id"] = f"{date}_{i:04d}"
    _log(f"[{date}] loaded total={len(articles):,} filtered={len(filtered):,}")

    parsed_ok = 0
    parse_fail = 0
    timeout_fail = 0
    rows: list[dict] = []
    n_batches = max(1, math.ceil(len(filtered) / batch_size)) if filtered else 0
    done_batches = 0

    for batch in _chunk(filtered, batch_size):
        b_t0 = time.time()
        prompt = _build_prompt(batch, max_summary_chars=max_summary_chars)
        by_id = {a["id"]: a for a in batch}
        try:
            resp = _call_ollama(prompt, model=model, timeout=timeout, num_predict=num_predict)
        except Exception:
            timeout_fail += len(batch)
            rows.extend(_blank_record(a, "ollama_timeout_or_error") for a in batch)
            continue

        arr = _extract_json_array(resp)
        if not arr:
            parse_fail += len(batch)
            rows.extend(_blank_record(a, "json_parse_fail") for a in batch)
            continue

        seen = set()
        for obj in arr:
            rid = str(obj.get("id", "") or "").strip()
            if rid in by_id:
                norm = _normalize_record(obj, rid)
                norm["llm_error"] = None
                rows.append(norm)
                seen.add(rid)
                parsed_ok += 1
        for a in batch:
            if a["id"] not in seen:
                parse_fail += 1
                rows.append(_blank_record(a, "missing_object_in_batch"))
        done_batches += 1
        if log_every_batches > 0 and (
            done_batches == 1
            or done_batches % log_every_batches == 0
            or done_batches == n_batches
        ):
            elapsed = time.time() - day_t0
            b_elapsed = time.time() - b_t0
            done_items = parsed_ok + parse_fail + timeout_fail
            rate = done_items / elapsed if elapsed > 0 else 0.0
            rem = max(0, len(filtered) - done_items)
            eta = rem / rate if rate > 0 else float("inf")
            eta_s = "inf" if not math.isfinite(eta) else f"{eta:.1f}s"
            _log(
                f"[{date}] batch {done_batches}/{n_batches} "
                f"batch_sec={b_elapsed:.2f} elapsed={elapsed:.1f}s "
                f"done={done_items:,}/{len(filtered):,} rate={rate:.2f} art/s eta={eta_s} "
                f"ok={parsed_ok:,} parse_fail={parse_fail:,} timeout={timeout_fail:,}"
            )

    # Keep deterministic order.
    order = {a["id"]: i for i, a in enumerate(filtered)}
    rows.sort(key=lambda x: order.get(x["id"], 10**9))

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_DIR / f"{date}.jsonl.tmp"
    out = CACHE_DIR / f"{date}.jsonl"
    with tmp.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(out)
    day_elapsed = time.time() - day_t0
    done_items = parsed_ok + parse_fail + timeout_fail
    rate = done_items / day_elapsed if day_elapsed > 0 else 0.0
    _log(
        f"[{date}] done sec={day_elapsed:.1f} total={len(articles):,} filtered={len(filtered):,} "
        f"ok={parsed_ok:,} parse_fail={parse_fail:,} timeout={timeout_fail:,} "
        f"rate={rate:.2f} art/s out={out}"
    )

    return {
        "date": date,
        "articles_total": len(articles),
        "articles_filtered": len(filtered),
        "parsed_ok": parsed_ok,
        "parse_fail": parse_fail,
        "timeout_fail": timeout_fail,
        "out_path": str(out),
        "elapsed_sec": day_elapsed,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date-from", type=str, default="")
    ap.add_argument("--date-to", type=str, default="")
    ap.add_argument("--batch-size", type=int, default=10)
    ap.add_argument("--model", type=str, default="qwen2.5-coder:7b")
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--num-predict", type=int, default=2048)
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--workers", type=int, default=1,
                    help="Number of parallel day workers (default 1).")
    ap.add_argument("--max-summary-chars", type=int, default=600,
                    help="Truncate article summary in prompt to this many chars (0 = no truncation).")
    ap.add_argument("--log-every-batches", type=int, default=10,
                    help="Log progress every N batches within each day (default 10).")
    args = ap.parse_args()

    files = _iter_dates(args.date_from, args.date_to)
    if not files:
        print("No input files matched date filters.")
        return

    _log(
        f"Run config: files={len(files)} from={args.date_from or '-'} to={args.date_to or '-'} "
        f"model={args.model} batch_size={args.batch_size} workers={args.workers} "
        f"timeout={args.timeout}s num_predict={args.num_predict} "
        f"max_summary_chars={args.max_summary_chars} overwrite={args.overwrite}"
    )

    total_days = 0
    total_filtered = 0
    total_ok = 0
    total_fail = 0
    total_timeout = 0
    total_elapsed = 0.0
    skipped = 0
    pending: list[Path] = []
    for p in files:
        out = CACHE_DIR / f"{p.stem}.jsonl"
        if out.exists() and not args.overwrite:
            skipped += 1
        else:
            pending.append(p)

    _log(f"Days pending={len(pending)} skipped_existing={skipped}")

    start = time.time()
    if args.workers <= 1:
        for i, p in enumerate(pending, start=1):
            stats = process_day(
                p,
                batch_size=args.batch_size,
                model=args.model,
                timeout=args.timeout,
                num_predict=args.num_predict,
                max_summary_chars=args.max_summary_chars,
                log_every_batches=args.log_every_batches,
            )
            total_days += 1
            total_filtered += stats["articles_filtered"]
            total_ok += stats["parsed_ok"]
            total_fail += stats["parse_fail"]
            total_timeout += stats["timeout_fail"]
            total_elapsed += stats["elapsed_sec"]
            wall = time.time() - start
            day_rate = total_days / wall if wall > 0 else 0.0
            rem_days = len(pending) - total_days
            eta_days = rem_days / day_rate if day_rate > 0 else float("inf")
            eta_s = "inf" if not math.isfinite(eta_days) else f"{eta_days/60:.1f}m"
            _log(
                f"[progress] {i}/{len(pending)} days done | "
                f"filtered={total_filtered:,} ok={total_ok:,} parse_fail={total_fail:,} timeout={total_timeout:,} "
                f"day_rate={day_rate:.3f} days/s eta={eta_s}"
            )
    else:
        with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {
                ex.submit(
                    process_day,
                    p,
                    args.batch_size,
                    args.model,
                    args.timeout,
                    args.num_predict,
                    args.max_summary_chars,
                    args.log_every_batches,
                ): p.stem
                for p in pending
            }
            for i, fut in enumerate(cf.as_completed(futs), start=1):
                try:
                    stats = fut.result()
                except Exception as e:
                    _log(f"[{futs[fut]}] worker_error: {e}")
                    continue
                total_days += 1
                total_filtered += stats["articles_filtered"]
                total_ok += stats["parsed_ok"]
                total_fail += stats["parse_fail"]
                total_timeout += stats["timeout_fail"]
                total_elapsed += stats["elapsed_sec"]
                wall = time.time() - start
                day_rate = total_days / wall if wall > 0 else 0.0
                rem_days = len(pending) - total_days
                eta_days = rem_days / day_rate if day_rate > 0 else float("inf")
                eta_s = "inf" if not math.isfinite(eta_days) else f"{eta_days/60:.1f}m"
                _log(
                    f"[progress] {i}/{len(pending)} days done | "
                    f"filtered={total_filtered:,} ok={total_ok:,} parse_fail={total_fail:,} timeout={total_timeout:,} "
                    f"day_rate={day_rate:.3f} days/s eta={eta_s}"
                )

    wall_total = time.time() - start
    art_rate_wall = total_filtered / wall_total if wall_total > 0 else 0.0
    _log("Done.")
    _log(f"Processed days: {total_days} | skipped existing: {skipped}")
    _log(f"Filtered articles: {total_filtered:,}")
    _log(f"Parsed ok: {total_ok:,} | parse_fail: {total_fail:,} | timeout_fail: {total_timeout:,}")
    _log(
        f"Wall time: {wall_total:.1f}s | sum(day elapsed): {total_elapsed:.1f}s | "
        f"wall throughput: {art_rate_wall:.2f} filtered art/s"
    )


if __name__ == "__main__":
    main()
