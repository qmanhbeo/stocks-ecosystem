"""
Fetch official HNX issuer-disclosure data from the HNX mobile site.

This source is useful for:
- official publication timestamps on HNX / UPCoM issuer disclosures
- raw attachment links for exchange-hosted PDFs
- a first local official-disclosure history surface that can support later
  timestamp and event-source audits
- selective download and structured parsing of transaction-related official
  filings when the attachment layer is locally accessible

Sources:
- issuer universe JSON:
  https://hnx.vn/Home/MobileSearchAutocompleteStockCode
- issuer disclosure list AJAX:
  https://hnx.vn/ModuleMobile/MobileIssuer/ChangePageTCB
- issuer disclosure article pages:
  https://hnx.vn/m-niem-yet/tin-tuc/... or https://hnx.vn/m-upcom/tin-tuc/...

Builds:
    data/official_disclosures/hnx/issuer_universe.json
    data/official_disclosures/hnx/issuer_universe.parquet
    data/official_disclosures/hnx/issuer_news.parquet
    data/official_disclosures/hnx/issuer_news_attachments.parquet
    data/official_disclosures/hnx/issuer_transaction_disclosures.parquet
    data/official_disclosures/hnx/issuer_transaction_attachment_extracts.parquet
    data/official_disclosures/hnx/manifest.json

Default behavior is intentionally conservative:
- always refresh the official HNX issuer universe
- only crawl per-ticker disclosure history when `--tickers` or
  `--fetch-all-linked` is supplied
- download attachments only when `--download-attachments` is supplied
- transaction-attachment parsing is opt-in and records whether a filing is
  text-extractable locally or still blocked on OCR
"""

from __future__ import annotations

import argparse
from functools import lru_cache
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit

import pandas as pd
import requests
from bs4 import BeautifulSoup
import cv2
import pdfplumber

try:
    import easyocr
except ModuleNotFoundError:
    easyocr = None

try:
    from cafef_history_common import atomic_write_json, utc_now_iso
except ModuleNotFoundError:
    from data_tools.cafef_history_common import atomic_write_json, utc_now_iso

try:
    from stock_refresh_utils import atomic_write_parquet
except ModuleNotFoundError:
    from data_tools.stock_refresh_utils import atomic_write_parquet

from path_utils import data_path


BASE_URL = "https://hnx.vn"
AUTOCOMPLETE_URL = f"{BASE_URL}/Home/MobileSearchAutocompleteStockCode"
DISCLOSURE_LIST_URL = f"{BASE_URL}/ModuleMobile/MobileIssuer/ChangePageTCB"
SOURCE = "hnx_mobile_official_disclosures"
OUTPUT_ROOT = data_path("official_disclosures/hnx")
ATTACHMENTS_ROOT = OUTPUT_ROOT / "attachments"
TEXT_ROOT = OUTPUT_ROOT / "extracted_text"
OCR_MODEL_ROOT = OUTPUT_ROOT / "_easyocr_models"

LOCAL_TZ = timezone(timedelta(hours=7))
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/135.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Referer": f"{BASE_URL}/",
    "Origin": BASE_URL,
}

MARKET_BUCKETS = {
    "NY": "listed",
    "UC": "upcom",
}

UNIVERSE_COLUMNS = [
    "ticker",
    "market_code",
    "market_bucket",
    "issuer_name",
    "issuer_name_en",
    "detail_slug",
    "detail_url",
    "source",
]

NEWS_COLUMNS = [
    "ticker",
    "market_code",
    "market_bucket",
    "source",
    "listing_page",
    "article_path",
    "article_url",
    "title",
    "listing_published_at",
    "article_published_at",
    "published_at",
    "published_date",
    "section_label",
    "content_text",
    "content_is_empty",
    "attachment_count",
    "has_transaction_keywords",
    "has_insider_related_keywords",
    "has_large_holder_keywords",
    "keyword_hits",
]

ATTACHMENT_COLUMNS = [
    "ticker",
    "market_code",
    "market_bucket",
    "source",
    "article_url",
    "article_path",
    "attachment_index",
    "attachment_label",
    "attachment_url",
    "attachment_filename",
    "attachment_ticker_hint",
    "attachment_is_pdf",
    "attachment_storage_path",
    "attachment_sha256",
    "attachment_bytes",
    "has_transaction_keywords",
    "has_insider_related_keywords",
    "has_large_holder_keywords",
    "keyword_hits",
]

TRANSACTION_COLUMNS = NEWS_COLUMNS

TRANSACTION_ATTACHMENT_EXTRACT_COLUMNS = [
    "ticker",
    "market_code",
    "market_bucket",
    "source",
    "article_url",
    "article_path",
    "title",
    "published_at",
    "published_date",
    "section_label",
    "attachment_index",
    "attachment_label",
    "attachment_url",
    "attachment_filename",
    "attachment_storage_path",
    "attachment_sha256",
    "attachment_bytes",
    "keyword_hits",
    "filing_stage",
    "filing_subject_scope",
    "transaction_instrument",
    "transaction_side_hint",
    "text_extraction_status",
    "text_extraction_method",
    "text_storage_path",
    "text_char_count",
    "text_preview",
    "parser_status",
    "parser_notes",
    "actor_name",
    "actor_position",
    "related_person_name",
    "planned_buy_volume",
    "planned_sell_volume",
    "actual_buy_volume",
    "actual_sell_volume",
    "planned_net_volume",
    "actual_net_volume",
    "holding_before_volume",
    "holding_after_volume",
    "holding_before_pct",
    "holding_after_pct",
    "execution_rate_buy",
]

TRANSACTION_KEYWORDS = {
    "insider_related": [
        "nguoi noi bo",
        "nguoi co lien quan",
        "giao dich co phieu cua nguoi noi bo",
        "giao dich quyen mua co phieu cua nguoi noi bo",
    ],
    "large_holder": [
        "co dong lon",
        "nha dau tu nhom co lien quan so huu",
        "thay doi so huu cua co dong lon",
    ],
    "transaction_notice": [
        "dang ky giao dich",
        "ket qua giao dich",
        "bao cao ket qua giao dich",
        "thong bao giao dich",
        "giao dich co phieu",
        "giao dich quyen mua co phieu",
    ],
}

ACTOR_NAME_LABELS = [
    "ho va ten nguoi thuc hien giao dich",
    "ten to chuc thuc hien giao dich",
    "ho va ten nguoi dang ky giao dich",
    "ten to chuc dang ky giao dich",
    "ten ca nhan",
    "ten to chuc",
]
ACTOR_POSITION_LABELS = [
    "chuc vu hien nay tai cong ty dai chung",
    "chuc vu hien nay tai cong ty dai chung cong ty quan ly quy",
    "chuc vu hien nay tai cong ty quan ly quy",
]
RELATED_PERSON_LABELS = [
    "ho va ten nguoi noi bo",
    "ten nguoi noi bo",
    "ho va ten nguoi co lien quan cua nguoi noi bo",
    "ten nguoi co lien quan cua nguoi noi bo",
]
PLANNED_BUY_LABELS = [
    "so luong co phieu dang ky mua",
    "so luong chung khoan dang ky mua",
    "so luong quyen mua dang ky mua",
]
PLANNED_SELL_LABELS = [
    "so luong co phieu dang ky ban",
    "so luong chung khoan dang ky ban",
    "so luong quyen mua dang ky chuyen nhuong",
    "so luong quyen mua dang ky ban",
]
ACTUAL_BUY_LABELS = [
    "so luong co phieu da mua",
    "so luong chung khoan da mua",
    "so luong quyen mua da mua",
    "so luong quyen mua da thuc hien",
]
ACTUAL_SELL_LABELS = [
    "so luong co phieu da ban",
    "so luong chung khoan da ban",
    "so luong quyen mua da chuyen nhuong",
    "so luong quyen mua da ban",
]
HOLDING_BEFORE_LABELS = [
    "so luong co phieu nam giu truoc khi thuc hien giao dich",
    "so luong chung khoan nam giu truoc khi thuc hien giao dich",
    "so luong quyen mua co phieu nam giu truoc khi thuc hien giao dich",
    "so luong quyen mua nam giu truoc khi thuc hien giao dich",
]
HOLDING_AFTER_LABELS = [
    "so luong co phieu nam giu sau khi thuc hien giao dich",
    "so luong chung khoan nam giu sau khi thuc hien giao dich",
    "so luong quyen mua co phieu nam giu sau khi thuc hien giao dich",
    "so luong quyen mua nam giu sau khi thuc hien giao dich",
]
HOLDING_BEFORE_PCT_LABELS = [
    "ty le so huu truoc khi thuc hien giao dich",
    "ty le nam giu truoc khi thuc hien giao dich",
]
HOLDING_AFTER_PCT_LABELS = [
    "ty le so huu sau khi thuc hien giao dich",
    "ty le nam giu sau khi thuc hien giao dich",
]
TEXT_FIELD_STOP_PATTERNS = [
    "quoc tich",
    "so cmnd",
    "so cccd",
    "ho chieu",
    "dia chi",
    "dien thoai",
    "email",
    "website",
    "chuc vu",
    "moi quan he",
    "so luong",
    "ty le",
]
TEXT_FIELD_SKIP_FRAGMENTS = {
    "ho",
    "va ten",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", help="Comma-separated HNX/UPCoM tickers to crawl.")
    parser.add_argument(
        "--fetch-all-linked",
        action="store_true",
        help="Crawl every symbol in the HNX official universe that exposes a detail page.",
    )
    parser.add_argument(
        "--max-tickers",
        type=int,
        help="Limit the number of tickers crawled after filtering.",
    )
    parser.add_argument(
        "--max-pages-per-ticker",
        type=int,
        default=1,
        help="Maximum disclosure listing pages to request per ticker.",
    )
    parser.add_argument(
        "--download-attachments",
        action="store_true",
        help="Download article attachments under data/official_disclosures/hnx/attachments/.",
    )
    parser.add_argument(
        "--download-transaction-attachments",
        action="store_true",
        help="Download keyword-positive transaction PDF attachments only.",
    )
    parser.add_argument(
        "--parse-transaction-attachments",
        action="store_true",
        help="Build a structured transaction-attachment extract table from local or newly downloaded PDFs.",
    )
    parser.add_argument(
        "--rebuild-transaction-extracts-from-local",
        action="store_true",
        help="Rebuild the transaction-attachment extract parquet from local news/attachment caches only.",
    )
    parser.add_argument(
        "--ocr-transaction-attachments",
        action="store_true",
        help="Use OCR on scanned transaction PDFs when embedded text extraction is empty.",
    )
    parser.add_argument(
        "--refresh-transaction-text-cache",
        action="store_true",
        help="Ignore cached extracted text and rebuild it from the local PDF attachments for this run.",
    )
    parser.add_argument(
        "--ocr-languages",
        default="vi,en",
        help="Comma-separated EasyOCR language list for scanned PDFs (default: vi,en).",
    )
    parser.add_argument(
        "--ocr-gpu",
        action="store_true",
        help="Allow EasyOCR to use GPU if available.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.0,
        help="Optional sleep between ticker requests.",
    )
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    session.verify = False
    requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]
    return session


def normalize_text(value: object) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", stripped)


def canonicalize_url(url_or_path: str) -> str:
    absolute = urljoin(BASE_URL, str(url_or_path).strip())
    split = urlsplit(absolute)
    safe_path = quote(unquote(split.path), safe="/._-()")
    safe_query = quote(unquote(split.query), safe="=&/%._-")
    return urlunsplit((split.scheme, split.netloc, safe_path, safe_query, split.fragment))


def parse_local_timestamp(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.strptime(text, "%d/%m/%Y %H:%M").replace(tzinfo=LOCAL_TZ)
    except ValueError:
        return None
    return dt.isoformat()


def extract_published_date(iso_value: str | None) -> str | None:
    if not iso_value:
        return None
    try:
        return datetime.fromisoformat(iso_value).date().isoformat()
    except ValueError:
        return None


def parse_tickers(value: str | None) -> list[str]:
    if not value:
        return []
    return sorted({item.strip().upper() for item in value.split(",") if item.strip()})


def parse_language_list(value: str | None) -> tuple[str, ...]:
    if not value:
        return ("vi", "en")
    languages = tuple(item.strip() for item in str(value).split(",") if item.strip())
    return languages or ("vi", "en")


def normalize_universe_rows(rows: list[dict[str, object]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=UNIVERSE_COLUMNS)

    frame = pd.DataFrame(rows).copy()
    out = pd.DataFrame(index=frame.index)
    out["ticker"] = frame.get("STOCK_CODE", pd.Series(index=frame.index)).astype(str).str.upper().str.strip()
    out["market_code"] = frame.get("MARKETCODE", pd.Series(index=frame.index)).astype(str).str.upper().str.strip()
    out["market_bucket"] = out["market_code"].map(MARKET_BUCKETS).fillna("unknown")
    out["issuer_name"] = frame.get("NAME")
    out["issuer_name_en"] = frame.get("NAME_ENG")
    out["detail_slug"] = frame.get("Link_To_Detail")
    out["detail_url"] = out["detail_slug"].map(lambda slug: canonicalize_url(f"/m-tim-kiem-{slug}.html") if isinstance(slug, str) and slug.strip() else None)
    out["source"] = SOURCE
    out = out[out["ticker"].notna() & (out["ticker"].astype(str) != "")]
    out = out.drop_duplicates(subset=["ticker", "market_code"], keep="last")
    return out[UNIVERSE_COLUMNS].sort_values(["market_code", "ticker"]).reset_index(drop=True)


def fetch_universe(session: requests.Session, *, timeout: float) -> pd.DataFrame:
    response = session.post(AUTOCOMPLETE_URL, data="", timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("lst") or []
    if not isinstance(rows, list):
        raise RuntimeError("Unexpected HNX autocomplete payload shape")
    return normalize_universe_rows(rows)


def parse_listing_html(html: str, *, ticker: str, market_code: str, page: int) -> tuple[list[dict[str, object]], int | None]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, object]] = []
    for tr in soup.select("table.tb-data tbody tr"):
        cells = tr.find_all("td")
        if len(cells) < 2:
            continue
        anchor = tr.find("a", class_="news-link")
        if anchor is None:
            continue
        listing_time_raw = cells[0].get_text(" ", strip=True)
        title = anchor.get_text(" ", strip=True)
        article_path = (anchor.get("href") or "").strip()
        if not article_path:
            continue
        rows.append(
            {
                "ticker": ticker.upper(),
                "market_code": market_code.upper(),
                "market_bucket": MARKET_BUCKETS.get(market_code.upper(), "unknown"),
                "source": SOURCE,
                "listing_page": page,
                "article_path": article_path,
                "article_url": canonicalize_url(article_path),
                "title": title,
                "listing_published_at": parse_local_timestamp(listing_time_raw),
            }
        )

    next_page = None
    next_anchor = soup.find("a", class_="btn-next-page")
    if next_anchor is not None:
        href = next_anchor.get("href") or ""
        match = re.search(r"ChangePageTCB\((\d+)\)", href)
        if match:
            next_page = int(match.group(1))

    return rows, next_page


def parse_attachment_ticker(label: str) -> str | None:
    match = re.match(r"\s*(?:\d+\.\s*)?([A-Z0-9]{2,8})_", str(label or "").strip())
    return match.group(1) if match else None


def classify_text(text: str) -> dict[str, object]:
    normalized = normalize_text(text)
    hits: list[str] = []
    for label, patterns in TRANSACTION_KEYWORDS.items():
        if any(pattern in normalized for pattern in patterns):
            hits.append(label)
    return {
        "has_transaction_keywords": bool(hits),
        "has_insider_related_keywords": "insider_related" in hits,
        "has_large_holder_keywords": "large_holder" in hits,
        "keyword_hits": "|".join(sorted(hits)),
    }


def parse_article_html(
    html: str,
    *,
    listing_row: dict[str, object],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.select_one(".news-title")
    public_time = soup.select_one(".news-public-time")
    content_node = soup.select_one(".news-content")
    section_node = soup.select_one(".main-header .mh-small")

    article_title = title.get_text(" ", strip=True) if title else str(listing_row.get("title") or "").strip()
    article_published_at = parse_local_timestamp(public_time.get_text(" ", strip=True) if public_time else None)
    published_at = article_published_at or str(listing_row.get("listing_published_at") or "") or None
    content_text = content_node.get_text(" ", strip=True) if content_node else ""
    section_label = section_node.get_text(" ", strip=True) if section_node else None

    attachment_nodes = soup.select(".news-file-attach a")
    attachments: list[dict[str, object]] = []
    attachment_labels: list[str] = []
    for index, anchor in enumerate(attachment_nodes, start=1):
        attachment_label = anchor.get_text(" ", strip=True)
        attachment_url = canonicalize_url(anchor.get("href") or "")
        split = urlsplit(attachment_url)
        attachment_filename = Path(unquote(split.path)).name if split.path else None
        attachment_labels.append(attachment_label)
        attachments.append(
            {
                "ticker": listing_row["ticker"],
                "market_code": listing_row["market_code"],
                "market_bucket": listing_row["market_bucket"],
                "source": SOURCE,
                "article_url": listing_row["article_url"],
                "article_path": listing_row["article_path"],
                "attachment_index": index,
                "attachment_label": attachment_label,
                "attachment_url": attachment_url,
                "attachment_filename": attachment_filename,
                "attachment_ticker_hint": parse_attachment_ticker(attachment_label),
                "attachment_is_pdf": str(attachment_filename or "").lower().endswith(".pdf"),
                "attachment_storage_path": None,
                "attachment_sha256": None,
                "attachment_bytes": None,
                "has_transaction_keywords": False,
                "has_insider_related_keywords": False,
                "has_large_holder_keywords": False,
                "keyword_hits": "",
            }
        )

    classifier = classify_text(" ".join([article_title, content_text, *attachment_labels]))
    for attachment in attachments:
        attachment.update(classifier)

    news_row = {
        "ticker": listing_row["ticker"],
        "market_code": listing_row["market_code"],
        "market_bucket": listing_row["market_bucket"],
        "source": SOURCE,
        "listing_page": listing_row["listing_page"],
        "article_path": listing_row["article_path"],
        "article_url": listing_row["article_url"],
        "title": article_title,
        "listing_published_at": listing_row.get("listing_published_at"),
        "article_published_at": article_published_at,
        "published_at": published_at,
        "published_date": extract_published_date(published_at),
        "section_label": section_label,
        "content_text": content_text,
        "content_is_empty": not bool(content_text.strip()),
        "attachment_count": len(attachments),
        **classifier,
    }
    return news_row, attachments


def sanitize_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip())
    return cleaned[:180] or "attachment"


def sanitize_text_filename(value: str) -> str:
    stem = sanitize_filename(Path(str(value or "document")).stem)
    return f"{stem}.txt"


def attachment_destination_path(attachment_row: dict[str, object]) -> Path:
    ticker = str(attachment_row["ticker"]).upper()
    filename = sanitize_filename(
        str(attachment_row.get("attachment_filename") or attachment_row.get("attachment_label") or "attachment")
    )
    return ATTACHMENTS_ROOT / ticker / filename


def text_destination_path(attachment_row: dict[str, object]) -> Path:
    ticker = str(attachment_row["ticker"]).upper()
    filename = sanitize_text_filename(
        str(attachment_row.get("attachment_filename") or attachment_row.get("attachment_label") or "attachment")
    )
    return TEXT_ROOT / ticker / filename


def download_attachment(
    session: requests.Session,
    attachment_row: dict[str, object],
    *,
    timeout: float,
) -> dict[str, object]:
    url = str(attachment_row["attachment_url"])
    if not url:
        return attachment_row

    destination = attachment_destination_path(attachment_row)
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.exists():
        payload = destination.read_bytes()
        attachment_row["attachment_storage_path"] = str(destination)
        attachment_row["attachment_sha256"] = hashlib.sha256(payload).hexdigest()
        attachment_row["attachment_bytes"] = len(payload)
        return attachment_row

    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    payload = response.content
    destination.write_bytes(payload)
    attachment_row["attachment_storage_path"] = str(destination)
    attachment_row["attachment_sha256"] = hashlib.sha256(payload).hexdigest()
    attachment_row["attachment_bytes"] = len(payload)
    return attachment_row


def should_download_attachment(
    attachment_row: dict[str, object],
    *,
    download_attachments: bool,
    download_transaction_attachments: bool,
    parse_transaction_attachments: bool,
) -> bool:
    if download_attachments:
        return True
    if not bool(attachment_row.get("attachment_is_pdf")):
        return False
    is_transaction = bool(attachment_row.get("has_transaction_keywords"))
    return is_transaction and (download_transaction_attachments or parse_transaction_attachments)


def extract_pdf_text_pdfplumber(path: Path) -> str:
    try:
        with pdfplumber.open(path) as pdf:
            parts = [(page.extract_text() or "").strip() for page in pdf.pages]
    except Exception:
        return ""
    return "\n".join(part for part in parts if part).strip()


def extract_pdf_text_pdftotext(path: Path) -> str:
    if shutil.which("pdftotext") is None:
        return ""
    try:
        result = subprocess.run(
            ["pdftotext", str(path), "-"],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except Exception:
        return ""
    if result.returncode != 0:
        return ""
    return (result.stdout or "").strip()


def render_pdf_pages_to_png(path: Path, *, dpi: int = 200) -> list[Path]:
    if shutil.which("pdftoppm") is None:
        return []
    with tempfile.TemporaryDirectory(prefix="hnx_ocr_") as temp_dir:
        prefix = Path(temp_dir) / "page"
        try:
            result = subprocess.run(
                ["pdftoppm", "-png", "-r", str(dpi), str(path), str(prefix)],
                check=False,
                capture_output=True,
                text=True,
                timeout=180,
            )
        except Exception:
            return []
        if result.returncode != 0:
            return []
        pages = sorted(Path(temp_dir).glob("page-*.png"))
        if not pages:
            return []
        persistent_dir = Path(tempfile.mkdtemp(prefix="hnx_ocr_pages_"))
        out_pages: list[Path] = []
        for page in pages:
            destination = persistent_dir / page.name
            shutil.copy2(page, destination)
            out_pages.append(destination)
    return out_pages


@lru_cache(maxsize=4)
def get_easyocr_reader(languages: tuple[str, ...], gpu: bool):
    if easyocr is None:
        return None
    OCR_MODEL_ROOT.mkdir(parents=True, exist_ok=True)
    return easyocr.Reader(
        list(languages),
        gpu=gpu,
        model_storage_directory=str(OCR_MODEL_ROOT),
        user_network_directory=str(OCR_MODEL_ROOT),
        download_enabled=True,
        verbose=False,
    )


def sort_easyocr_results(results: list[object]) -> list[str]:
    def key(row: object) -> tuple[float, float]:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            return (0.0, 0.0)
        bbox = row[0]
        if not isinstance(bbox, (list, tuple)) or not bbox:
            return (0.0, 0.0)
        point = bbox[0]
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            return (0.0, 0.0)
        return (float(point[1]), float(point[0]))

    ordered = sorted(results, key=key)
    texts: list[str] = []
    for row in ordered:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        text = compact_whitespace(row[1])
        if text:
            texts.append(text)
    return texts


def extract_pdf_text_easyocr(path: Path, *, languages: tuple[str, ...], gpu: bool) -> str:
    reader = get_easyocr_reader(languages, gpu)
    if reader is None:
        return ""
    page_paths = render_pdf_pages_to_png(path)
    if not page_paths:
        return ""
    try:
        text_parts: list[str] = []
        for page_path in page_paths:
            image = cv2.imread(str(page_path))
            if image is None:
                continue
            results = reader.readtext(image, detail=1, paragraph=False)
            page_lines = sort_easyocr_results(results)
            if page_lines:
                text_parts.append("\n".join(page_lines))
        return "\n\n".join(part for part in text_parts if part).strip()
    finally:
        for page_path in page_paths:
            try:
                parent = page_path.parent
                page_path.unlink(missing_ok=True)
                parent.rmdir()
            except Exception:
                continue


def extract_attachment_text(
    path: Path,
    *,
    use_ocr: bool,
    ocr_languages: tuple[str, ...],
    ocr_gpu: bool,
) -> tuple[str, str, str]:
    # Prefer embedded text first; many current HNX transaction PDFs are image
    # scans, so a clean "needs_ocr" status is more useful than silent empties.
    text = extract_pdf_text_pdfplumber(path)
    if text:
        return text, "text_extracted", "pdfplumber"
    text = extract_pdf_text_pdftotext(path)
    if text:
        return text, "text_extracted", "pdftotext"
    if use_ocr:
        text = extract_pdf_text_easyocr(path, languages=ocr_languages, gpu=ocr_gpu)
        if text:
            return text, "ocr_text_extracted", "easyocr"
        return "", "ocr_attempted_no_text", "easyocr"
    return "", "needs_ocr", "none"


def compact_whitespace(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def split_text_lines(text: str) -> list[tuple[str, str]]:
    lines: list[tuple[str, str]] = []
    for raw_line in str(text or "").splitlines():
        compact = compact_whitespace(raw_line)
        if not compact:
            continue
        lines.append((compact, normalize_text(compact)))
    return lines


def strip_label_prefix(raw_line: str) -> str:
    if ":" in raw_line:
        return raw_line.split(":", 1)[1].strip()
    return raw_line.strip()


def extract_text_field(lines: list[tuple[str, str]], labels: list[str]) -> str | None:
    for index, (raw_line, normalized_line) in enumerate(lines):
        if any(label in normalized_line for label in labels):
            parts: list[str] = []
            value = strip_label_prefix(raw_line)
            if value and value != raw_line:
                parts.append(value)
            for next_raw, next_normalized in lines[index + 1 : index + 5]:
                if next_normalized in TEXT_FIELD_SKIP_FRAGMENTS:
                    continue
                if any(pattern in next_normalized for pattern in TEXT_FIELD_STOP_PATTERNS):
                    break
                if ":" in next_raw and parts:
                    break
                parts.append(next_raw)
                if len(parts) >= 2:
                    break
            candidate = compact_whitespace(" ".join(parts))
            if candidate:
                return candidate
    return None


def parse_vn_number(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    cleaned = cleaned.replace("%", "").replace(" ", "")
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        cleaned = cleaned.replace(".", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def extract_numeric_field(lines: list[tuple[str, str]], labels: list[str]) -> float | None:
    number_pattern = re.compile(r"([0-9][0-9\.,]*)")
    for index, (raw_line, normalized_line) in enumerate(lines):
        if any(label in normalized_line for label in labels):
            match = number_pattern.search(strip_label_prefix(raw_line))
            if match:
                return parse_vn_number(match.group(1))
            if index + 1 < len(lines):
                next_line = lines[index + 1][0]
                match = number_pattern.search(next_line)
                if match:
                    return parse_vn_number(match.group(1))
    return None


def infer_filing_stage(title: str) -> str:
    normalized = normalize_text(title)
    if "ket qua giao dich" in normalized or "bao cao ket qua giao dich" in normalized:
        return "result"
    if "thong bao giao dich" in normalized or "dang ky giao dich" in normalized:
        return "notice"
    return "unknown"


def infer_filing_subject_scope(title: str) -> str:
    normalized = normalize_text(title)
    if "nguoi co lien quan" in normalized:
        return "related_person"
    if "co dong lon" in normalized:
        return "large_holder"
    if "nguoi noi bo" in normalized:
        return "insider"
    return "unknown"


def infer_transaction_instrument(title: str) -> str:
    normalized = normalize_text(title)
    if "quyen mua" in normalized:
        return "subscription_rights"
    if "co phieu" in normalized:
        return "stock"
    if "chung khoan" in normalized:
        return "security"
    return "unknown"


def infer_transaction_side_hint(title: str) -> str:
    normalized = normalize_text(title)
    has_buy = any(token in normalized for token in (" mua", "dang ky mua", "da mua"))
    has_sell = any(token in normalized for token in (" ban", "dang ky ban", "da ban", "chuyen nhuong"))
    if has_buy and has_sell:
        return "mixed"
    if has_buy:
        return "buy"
    if has_sell:
        return "sell"
    return "unknown"


def to_int_or_none(value: float | None) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(round(float(value)))


def to_float_or_none(value: float | None) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def parse_transaction_attachment(
    attachment_row: dict[str, object],
    *,
    article_lookup: dict[str, dict[str, object]],
    ocr_transaction_attachments: bool,
    ocr_languages: tuple[str, ...],
    ocr_gpu: bool,
    refresh_transaction_text_cache: bool,
) -> dict[str, object]:
    # Article-title metadata is always available; the PDF text layer only
    # fills the actor/volume fields when the attachment is machine-readable.
    article_url = str(attachment_row.get("article_url") or "")
    article_row = article_lookup.get(article_url, {})
    title = str(article_row.get("title") or "")
    published_at = article_row.get("published_at")
    published_date = article_row.get("published_date")
    section_label = article_row.get("section_label")
    local_path = attachment_row.get("attachment_storage_path")

    text = ""
    text_status = "not_downloaded"
    text_method = "none"
    text_storage_path = None
    parser_notes: list[str] = []
    cached_text_path = text_destination_path(attachment_row)
    if cached_text_path.exists() and not refresh_transaction_text_cache:
        cached_text = cached_text_path.read_text(encoding="utf-8").strip()
        if cached_text:
            text = cached_text
            text_status = "cached_text"
            text_method = "cached"
            text_storage_path = str(cached_text_path)
    if local_path and Path(str(local_path)).exists():
        if not text:
            extracted_text, text_status, text_method = extract_attachment_text(
                Path(str(local_path)),
                use_ocr=ocr_transaction_attachments,
                ocr_languages=ocr_languages,
                ocr_gpu=ocr_gpu,
            )
            text = str(extracted_text or "").strip()
            if text:
                cached_text_path.parent.mkdir(parents=True, exist_ok=True)
                cached_text_path.write_text(text + "\n", encoding="utf-8")
                text_storage_path = str(cached_text_path)
            elif refresh_transaction_text_cache and cached_text_path.exists():
                cached_text_path.unlink(missing_ok=True)
            elif text_status == "needs_ocr":
                parser_notes.append("attachment_downloaded_but_image_only")
            elif text_status == "ocr_attempted_no_text":
                parser_notes.append("ocr_attempted_but_no_text")
    else:
        parser_notes.append("attachment_not_downloaded")

    lines = split_text_lines(text)
    actor_name = extract_text_field(lines, ACTOR_NAME_LABELS)
    actor_position = extract_text_field(lines, ACTOR_POSITION_LABELS)
    related_person_name = extract_text_field(lines, RELATED_PERSON_LABELS)
    planned_buy = extract_numeric_field(lines, PLANNED_BUY_LABELS)
    planned_sell = extract_numeric_field(lines, PLANNED_SELL_LABELS)
    actual_buy = extract_numeric_field(lines, ACTUAL_BUY_LABELS)
    actual_sell = extract_numeric_field(lines, ACTUAL_SELL_LABELS)
    before_volume = extract_numeric_field(lines, HOLDING_BEFORE_LABELS)
    after_volume = extract_numeric_field(lines, HOLDING_AFTER_LABELS)
    before_pct = extract_numeric_field(lines, HOLDING_BEFORE_PCT_LABELS)
    after_pct = extract_numeric_field(lines, HOLDING_AFTER_PCT_LABELS)

    planned_net = None
    if planned_buy is not None or planned_sell is not None:
        planned_net = float(planned_buy or 0.0) - float(planned_sell or 0.0)
    actual_net = None
    if actual_buy is not None or actual_sell is not None:
        actual_net = float(actual_buy or 0.0) - float(actual_sell or 0.0)

    execution_rate_buy = None
    if planned_buy and planned_buy > 0 and actual_buy is not None:
        execution_rate_buy = float(min(actual_buy, planned_buy) / planned_buy)

    identity_fields = (
        actor_name,
        actor_position,
        related_person_name,
    )
    transaction_fields = (
        planned_buy,
        planned_sell,
        actual_buy,
        actual_sell,
        before_volume,
        after_volume,
        before_pct,
        after_pct,
        execution_rate_buy,
    )

    if text and any(value is not None for value in transaction_fields):
        parser_status = "transaction_fields_extracted"
    elif text and any(value is not None for value in identity_fields):
        parser_status = "identity_fields_extracted"
    elif text:
        parser_status = "text_only_no_structured_fields"
    elif text_status in {"needs_ocr", "ocr_attempted_no_text"}:
        parser_status = "needs_ocr"
    else:
        parser_status = "metadata_only"

    return {
        "ticker": attachment_row.get("ticker"),
        "market_code": attachment_row.get("market_code"),
        "market_bucket": attachment_row.get("market_bucket"),
        "source": attachment_row.get("source"),
        "article_url": article_url,
        "article_path": attachment_row.get("article_path"),
        "title": title,
        "published_at": published_at,
        "published_date": published_date,
        "section_label": section_label,
        "attachment_index": attachment_row.get("attachment_index"),
        "attachment_label": attachment_row.get("attachment_label"),
        "attachment_url": attachment_row.get("attachment_url"),
        "attachment_filename": attachment_row.get("attachment_filename"),
        "attachment_storage_path": local_path,
        "attachment_sha256": attachment_row.get("attachment_sha256"),
        "attachment_bytes": attachment_row.get("attachment_bytes"),
        "keyword_hits": attachment_row.get("keyword_hits"),
        "filing_stage": infer_filing_stage(title),
        "filing_subject_scope": infer_filing_subject_scope(title),
        "transaction_instrument": infer_transaction_instrument(title),
        "transaction_side_hint": infer_transaction_side_hint(title),
        "text_extraction_status": text_status,
        "text_extraction_method": text_method,
        "text_storage_path": text_storage_path,
        "text_char_count": len(text),
        "text_preview": compact_whitespace(text)[:500] if text else "",
        "parser_status": parser_status,
        "parser_notes": "|".join(parser_notes),
        "actor_name": actor_name,
        "actor_position": actor_position,
        "related_person_name": related_person_name,
        "planned_buy_volume": to_int_or_none(planned_buy),
        "planned_sell_volume": to_int_or_none(planned_sell),
        "actual_buy_volume": to_int_or_none(actual_buy),
        "actual_sell_volume": to_int_or_none(actual_sell),
        "planned_net_volume": to_int_or_none(planned_net),
        "actual_net_volume": to_int_or_none(actual_net),
        "holding_before_volume": to_int_or_none(before_volume),
        "holding_after_volume": to_int_or_none(after_volume),
        "holding_before_pct": to_float_or_none(before_pct),
        "holding_after_pct": to_float_or_none(after_pct),
        "execution_rate_buy": to_float_or_none(execution_rate_buy),
    }


def fetch_ticker_history(
    session: requests.Session,
    *,
    ticker: str,
    market_code: str,
    max_pages_per_ticker: int,
    download_attachments: bool,
    download_transaction_attachments: bool,
    parse_transaction_attachments: bool,
    timeout: float,
    sleep: float,
) -> tuple[list[dict[str, object]], list[dict[str, object]], int]:
    ticker_news: list[dict[str, object]] = []
    ticker_attachments: list[dict[str, object]] = []
    page = 1
    pages_fetched = 0
    seen_paths: set[str] = set()

    while page is not None and pages_fetched < max_pages_per_ticker:
        response = session.post(
            DISCLOSURE_LIST_URL,
            data={"StockCode": ticker.upper(), "MarketCode": market_code.upper(), "Page": page},
            timeout=timeout,
        )
        response.raise_for_status()
        listing_rows, next_page = parse_listing_html(response.text, ticker=ticker, market_code=market_code, page=page)
        pages_fetched += 1
        if not listing_rows:
            break

        for listing_row in listing_rows:
            article_path = str(listing_row["article_path"])
            if article_path in seen_paths:
                continue
            seen_paths.add(article_path)
            article_response = session.get(str(listing_row["article_url"]), timeout=timeout)
            article_response.raise_for_status()
            news_row, attachments = parse_article_html(article_response.text, listing_row=listing_row)
            attachments = [
                download_attachment(session, attachment, timeout=timeout)
                if should_download_attachment(
                    attachment,
                    download_attachments=download_attachments,
                    download_transaction_attachments=download_transaction_attachments,
                    parse_transaction_attachments=parse_transaction_attachments,
                )
                else attachment
                for attachment in attachments
            ]
            ticker_news.append(news_row)
            ticker_attachments.extend(attachments)

        if sleep > 0:
            time.sleep(sleep)
        page = next_page

    return ticker_news, ticker_attachments, pages_fetched


def ensure_contract_shape(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=columns)
    for column in columns:
        if column not in frame.columns:
            frame[column] = pd.NA
    return frame[columns]


def build_transaction_extracts(
    *,
    news: pd.DataFrame,
    attachments: pd.DataFrame,
    ocr_transaction_attachments: bool,
    ocr_languages: tuple[str, ...],
    ocr_gpu: bool,
    refresh_transaction_text_cache: bool,
) -> pd.DataFrame:
    if news.empty or attachments.empty:
        return ensure_contract_shape(pd.DataFrame(), TRANSACTION_ATTACHMENT_EXTRACT_COLUMNS)
    article_lookup = {str(row["article_url"]): row for row in news.to_dict(orient="records")}
    transaction_attachments = attachments[
        attachments["has_transaction_keywords"].fillna(False) & attachments["attachment_is_pdf"].fillna(False)
    ].copy()
    extract_rows = [
        parse_transaction_attachment(
            row,
            article_lookup=article_lookup,
            ocr_transaction_attachments=ocr_transaction_attachments,
            ocr_languages=ocr_languages,
            ocr_gpu=ocr_gpu,
            refresh_transaction_text_cache=refresh_transaction_text_cache,
        )
        for row in transaction_attachments.to_dict(orient="records")
    ]
    extracts = ensure_contract_shape(pd.DataFrame(extract_rows), TRANSACTION_ATTACHMENT_EXTRACT_COLUMNS)
    if extracts.empty:
        return extracts
    return extracts.sort_values(["ticker", "published_at", "article_url", "attachment_index"]).reset_index(drop=True)


def prepare_news_output(news_rows: list[dict[str, object]]) -> pd.DataFrame:
    news = ensure_contract_shape(pd.DataFrame(news_rows), NEWS_COLUMNS)
    if news.empty:
        return news
    return (
        news.sort_values(["ticker", "published_at", "article_url"])
        .drop_duplicates(subset=["ticker", "article_url"], keep="last")
        .reset_index(drop=True)
    )


def prepare_attachment_output(attachment_rows: list[dict[str, object]]) -> pd.DataFrame:
    attachments = ensure_contract_shape(pd.DataFrame(attachment_rows), ATTACHMENT_COLUMNS)
    if attachments.empty:
        return attachments
    return (
        attachments.sort_values(["ticker", "article_url", "attachment_index"])
        .drop_duplicates(subset=["ticker", "article_url", "attachment_index"], keep="last")
        .reset_index(drop=True)
    )


def prepare_transaction_output(news: pd.DataFrame) -> pd.DataFrame:
    if news.empty:
        return ensure_contract_shape(pd.DataFrame(), TRANSACTION_COLUMNS)
    transactions = news[news["has_transaction_keywords"].fillna(False)].copy()
    return ensure_contract_shape(transactions.reset_index(drop=True), TRANSACTION_COLUMNS)


def main() -> None:
    args = parse_args()
    ocr_languages = parse_language_list(args.ocr_languages)
    output_root = Path(OUTPUT_ROOT)
    output_root.mkdir(parents=True, exist_ok=True)

    universe_json_path = output_root / "issuer_universe.json"
    universe_parquet_path = output_root / "issuer_universe.parquet"
    news_parquet_path = output_root / "issuer_news.parquet"
    attachment_parquet_path = output_root / "issuer_news_attachments.parquet"
    transaction_parquet_path = output_root / "issuer_transaction_disclosures.parquet"
    transaction_extract_path = output_root / "issuer_transaction_attachment_extracts.parquet"
    manifest_path = output_root / "manifest.json"

    if args.rebuild_transaction_extracts_from_local:
        news = ensure_contract_shape(
            pd.read_parquet(news_parquet_path) if news_parquet_path.exists() else pd.DataFrame(),
            NEWS_COLUMNS,
        )
        attachments = ensure_contract_shape(
            pd.read_parquet(attachment_parquet_path) if attachment_parquet_path.exists() else pd.DataFrame(),
            ATTACHMENT_COLUMNS,
        )
        transaction_extracts = build_transaction_extracts(
            news=news,
            attachments=attachments,
            ocr_transaction_attachments=args.ocr_transaction_attachments,
            ocr_languages=ocr_languages,
            ocr_gpu=args.ocr_gpu,
            refresh_transaction_text_cache=args.refresh_transaction_text_cache,
        )
        atomic_write_parquet(transaction_extracts, transaction_extract_path)

        manifest = {}
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                manifest = {}
        notes = list(manifest.get("notes") or [])
        local_note = "Transaction attachment extracts can be rebuilt locally from cached news/attachment parquets plus any saved OCR text files."
        if local_note not in notes:
            notes.append(local_note)
        manifest.update(
            {
                "fetched_at_utc": utc_now_iso(),
                "source": SOURCE,
                "notes": notes,
                "run_mode": "local_rebuild_transaction_extracts",
                "ocr_transaction_attachments": bool(args.ocr_transaction_attachments),
                "refresh_transaction_text_cache": bool(args.refresh_transaction_text_cache),
                "ocr_languages": list(ocr_languages),
                "outputs": {
                    **(manifest.get("outputs") or {}),
                    "issuer_transaction_attachment_extracts_parquet": str(transaction_extract_path)
                    if transaction_extract_path.exists()
                    else None,
                },
                "transaction_attachment_extract_rows": int(len(transaction_extracts)),
                "transaction_attachment_extract_status_counts": transaction_extracts["parser_status"].value_counts(dropna=False).to_dict()
                if not transaction_extracts.empty
                else {},
                "transaction_text_extraction_status_counts": transaction_extracts["text_extraction_status"].value_counts(dropna=False).to_dict()
                if not transaction_extracts.empty
                else {},
            }
        )
        atomic_write_json(manifest, manifest_path)
        print("HNX local transaction extract rebuild complete")
        print(f"Transaction extracts: {len(transaction_extracts)}")
        return

    session = build_session()
    started_at_utc = utc_now_iso()

    universe = fetch_universe(session, timeout=args.timeout)
    universe_payload = {
        "fetched_at_utc": started_at_utc,
        "source": SOURCE,
        "row_count": int(len(universe)),
        "market_counts": universe["market_code"].value_counts(dropna=False).to_dict(),
        "items": universe.to_dict(orient="records"),
    }

    if args.dry_run:
        target = universe.copy()
        if args.fetch_all_linked:
            target = target[target["detail_url"].notna()].copy()
        elif args.tickers:
            requested = parse_tickers(args.tickers)
            target = target[target["ticker"].isin(requested)].copy()
        else:
            target = target.iloc[0:0].copy()
        if args.max_tickers:
            target = target.head(args.max_tickers)
        print("HNX official disclosure fetch dry run")
        print(f"universe rows         : {len(universe)}")
        print(f"tickers to crawl      : {len(target)}")
        print(f"max pages per ticker  : {args.max_pages_per_ticker}")
        print(f"download attachments  : {args.download_attachments}")
        print(f"download tx pdfs      : {args.download_transaction_attachments}")
        print(f"parse tx attachments  : {args.parse_transaction_attachments}")
        print(f"ocr tx attachments    : {args.ocr_transaction_attachments}")
        print(f"refresh text cache    : {args.refresh_transaction_text_cache}")
        print(f"ocr languages         : {','.join(ocr_languages)}")
        return

    atomic_write_json(universe_payload, universe_json_path)
    atomic_write_parquet(universe, universe_parquet_path)

    requested_tickers = parse_tickers(args.tickers)
    if args.fetch_all_linked:
        target = universe[universe["detail_url"].notna()].copy()
    elif requested_tickers:
        target = universe[universe["ticker"].isin(requested_tickers)].copy()
    else:
        target = universe.iloc[0:0].copy()
    if args.max_tickers:
        target = target.head(args.max_tickers)

    news_rows: list[dict[str, object]] = []
    attachment_rows: list[dict[str, object]] = []
    pages_fetched = 0
    failures: list[dict[str, object]] = []

    for row in target.to_dict(orient="records"):
        try:
            ticker_news, ticker_attachments, ticker_pages = fetch_ticker_history(
                session,
                ticker=str(row["ticker"]),
                market_code=str(row["market_code"]),
                max_pages_per_ticker=args.max_pages_per_ticker,
                download_attachments=args.download_attachments,
                download_transaction_attachments=args.download_transaction_attachments,
                parse_transaction_attachments=args.parse_transaction_attachments,
                timeout=args.timeout,
                sleep=args.sleep,
            )
            news_rows.extend(ticker_news)
            attachment_rows.extend(ticker_attachments)
            pages_fetched += ticker_pages
        except Exception as exc:
            failures.append(
                {
                    "ticker": row["ticker"],
                    "market_code": row["market_code"],
                    "error": str(exc),
                }
            )

    news = prepare_news_output(news_rows)
    atomic_write_parquet(news, news_parquet_path)

    attachments = prepare_attachment_output(attachment_rows)
    atomic_write_parquet(attachments, attachment_parquet_path)

    transactions = prepare_transaction_output(news)
    atomic_write_parquet(transactions, transaction_parquet_path)

    transaction_extracts = ensure_contract_shape(pd.DataFrame(), TRANSACTION_ATTACHMENT_EXTRACT_COLUMNS)
    if args.parse_transaction_attachments:
        transaction_extracts = build_transaction_extracts(
            news=news,
            attachments=attachments,
            ocr_transaction_attachments=args.ocr_transaction_attachments,
            ocr_languages=ocr_languages,
            ocr_gpu=args.ocr_gpu,
            refresh_transaction_text_cache=args.refresh_transaction_text_cache,
        )
    atomic_write_parquet(transaction_extracts, transaction_extract_path)

    manifest = {
        "fetched_at_utc": utc_now_iso(),
        "started_at_utc": started_at_utc,
        "source": SOURCE,
        "run_mode": "network_fetch",
        "requested_tickers": requested_tickers,
        "resolved_target_tickers": target["ticker"].tolist(),
        "fetch_all_linked": bool(args.fetch_all_linked),
        "max_tickers": args.max_tickers,
        "max_pages_per_ticker": int(args.max_pages_per_ticker),
        "parse_transaction_attachments": bool(args.parse_transaction_attachments),
        "ocr_transaction_attachments": bool(args.ocr_transaction_attachments),
        "refresh_transaction_text_cache": bool(args.refresh_transaction_text_cache),
        "ocr_languages": list(ocr_languages),
        "notes": [
            "Universe refresh is full; per-ticker disclosure history is only fetched for the requested ticker set.",
            "The HNX mobile site requires TLS verification to be disabled in this environment.",
            "HSX official disclosures are not part of this fetcher because the current HSX SPA/API route is still unresolved.",
            "Latest-run parquet outputs are rewritten to match the current request scope; they are not append-only history stores.",
        ],
        "outputs": {
            "issuer_universe_json": str(universe_json_path),
            "issuer_universe_parquet": str(universe_parquet_path),
            "issuer_news_parquet": str(news_parquet_path),
            "issuer_news_attachments_parquet": str(attachment_parquet_path),
            "issuer_transaction_disclosures_parquet": str(transaction_parquet_path),
            "issuer_transaction_attachment_extracts_parquet": str(transaction_extract_path),
        },
        "universe_rows": int(len(universe)),
        "target_tickers": int(len(target)),
        "pages_fetched": int(pages_fetched),
        "news_rows": int(len(news)),
        "attachment_rows": int(len(attachments)),
        "transaction_rows": int(len(transactions)),
        "transaction_attachment_extract_rows": int(len(transaction_extracts)),
        "attachments_downloaded": int(attachments["attachment_storage_path"].notna().sum()) if not attachments.empty else 0,
        "transaction_attachment_extract_status_counts": transaction_extracts["parser_status"].value_counts(dropna=False).to_dict()
        if not transaction_extracts.empty
        else {},
        "transaction_text_extraction_status_counts": transaction_extracts["text_extraction_status"].value_counts(dropna=False).to_dict()
        if not transaction_extracts.empty
        else {},
        "failures": failures,
        "status": "success" if not failures else "partial",
    }
    atomic_write_json(manifest, manifest_path)

    print("HNX official disclosure fetch complete")
    print(f"Universe rows       : {len(universe)}")
    print(f"Target tickers      : {len(target)}")
    print(f"News rows           : {len(news)}")
    print(f"Attachment rows     : {len(attachments)}")
    print(f"Transaction rows    : {len(transactions)}")
    print(f"Transaction extracts: {len(transaction_extracts)}")
    print(f"Failures            : {len(failures)}")


if __name__ == "__main__":
    main()
