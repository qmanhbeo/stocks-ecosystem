from __future__ import annotations

from pathlib import Path

from data_tools import fetch_hnx_official_disclosures as hnx


def test_normalize_universe_rows_maps_market_and_detail_url():
    frame = hnx.normalize_universe_rows(
        [
            {
                "STOCK_CODE": "DL1",
                "MARKETCODE": "NY",
                "NAME": "Cong ty A",
                "NAME_ENG": "Company A",
                "Link_To_Detail": "ny-dl1",
            },
            {
                "STOCK_CODE": "VE9",
                "MARKETCODE": "UC",
                "NAME": "Cong ty B",
                "NAME_ENG": None,
                "Link_To_Detail": "uc-ve9",
            },
        ]
    )

    assert frame["ticker"].tolist() == ["DL1", "VE9"]
    assert frame["market_bucket"].tolist() == ["listed", "upcom"]
    assert frame.loc[0, "detail_url"].endswith("/m-tim-kiem-ny-dl1.html")


def test_parse_listing_html_extracts_rows_and_next_page():
    html = """
    <table class="tb-data">
      <tbody>
        <tr>
          <td>21/04/2026 16:39 </td>
          <td class="td-left"><a class="news-link" href="/m-niem-yet/tin-tuc/Bao cao thuong nien 2025-610279-1.html">Bao cao thuong nien 2025</a></td>
        </tr>
      </tbody>
    </table>
    <div class="mb-page"><a href="javascript:ChangePageTCB(2);" class="btn-next-page">Sau</a></div>
    """

    rows, next_page = hnx.parse_listing_html(html, ticker="DL1", market_code="NY", page=1)

    assert len(rows) == 1
    assert rows[0]["ticker"] == "DL1"
    assert rows[0]["article_url"].endswith("/m-niem-yet/tin-tuc/Bao%20cao%20thuong%20nien%202025-610279-1.html")
    assert rows[0]["listing_page"] == 1
    assert next_page == 2


def test_parse_article_html_extracts_attachments_and_keywords():
    html = """
    <div class="content-news">
      <div class="main-header">
        <div class="mh-small">Niem yet</div>
      </div>
      <div class="news-container">
        <div class="news-title">Bao cao ket qua giao dich co phieu cua nguoi noi bo</div>
        <div class="news-public-time">03/02/2026 15:51 </div>
        <div class="news-content">Noi dung thong bao giao dich cua nguoi noi bo.</div>
        <div class="news-file-attach">
          <p><a href="https://owa.hnx.vn/ftp///cims/2026/2_W1/000000015841952_Bao_cao_giao_dich__Nguyen_Dinh_Trac_1.pdf">1. DL1_2026.2.3_Bao_cao_giao_dich.pdf</a></p>
        </div>
      </div>
    </div>
    """
    listing_row = {
        "ticker": "DL1",
        "market_code": "NY",
        "market_bucket": "listed",
        "listing_page": 1,
        "article_path": "/m-niem-yet/tin-tuc/Bao cao ket qua giao dich-596966-1.html",
        "article_url": "https://hnx.vn/m-niem-yet/tin-tuc/Bao%20cao%20ket%20qua%20giao%20dich-596966-1.html",
        "title": "placeholder",
        "listing_published_at": "2026-02-03T15:51:00+07:00",
    }

    news_row, attachments = hnx.parse_article_html(html, listing_row=listing_row)

    assert news_row["published_date"] == "2026-02-03"
    assert news_row["attachment_count"] == 1
    assert news_row["has_transaction_keywords"] is True
    assert news_row["has_insider_related_keywords"] is True
    assert attachments[0]["attachment_ticker_hint"] == "DL1"
    assert attachments[0]["attachment_is_pdf"] is True


def test_classify_text_distinguishes_large_holder_signal():
    result = hnx.classify_text("Dang ky giao dich cua co dong lon")

    assert result["has_transaction_keywords"] is True
    assert result["has_large_holder_keywords"] is True
    assert result["has_insider_related_keywords"] is False


def test_should_download_attachment_for_transaction_parse():
    attachment = {
        "attachment_is_pdf": True,
        "has_transaction_keywords": True,
    }

    assert (
        hnx.should_download_attachment(
            attachment,
            download_attachments=False,
            download_transaction_attachments=False,
            parse_transaction_attachments=True,
        )
        is True
    )


def test_parse_transaction_attachment_extracts_structured_fields(monkeypatch, tmp_path: Path):
    attachment_path = tmp_path / "tx.pdf"
    attachment_path.write_bytes(b"%PDF-1.4 mock")

    def fake_extract_attachment_text(path: Path, *, use_ocr: bool, ocr_languages, ocr_gpu: bool):
        assert path == attachment_path
        assert use_ocr is False
        return (
            "\n".join(
                [
                    "Ho va ten nguoi thuc hien giao dich: Nguyen Dinh Trac",
                    "Chuc vu hien nay tai cong ty dai chung: Tong Giam doc",
                    "So luong quyen mua dang ky mua: 3.200.000",
                    "So luong quyen mua da thuc hien: 3.200.000",
                    "So luong quyen mua co phieu nam giu truoc khi thuc hien giao dich: 0",
                    "So luong quyen mua co phieu nam giu sau khi thuc hien giao dich: 3.200.000",
                    "Ty le so huu truoc khi thuc hien giao dich: 0,00%",
                    "Ty le so huu sau khi thuc hien giao dich: 3,84%",
                ]
            ),
            "text_extracted",
            "pdfplumber",
        )

    monkeypatch.setattr(hnx, "extract_attachment_text", fake_extract_attachment_text)
    monkeypatch.setattr(hnx, "TEXT_ROOT", tmp_path / "text")

    article_lookup = {
        "https://hnx.vn/article": {
            "title": "Bao cao ket qua giao dich quyen mua co phieu cua nguoi noi bo",
            "published_at": "2026-02-03T15:51:00+07:00",
            "published_date": "2026-02-03",
            "section_label": "Niem yet",
        }
    }
    row = hnx.parse_transaction_attachment(
        {
            "ticker": "DL1",
            "market_code": "NY",
            "market_bucket": "listed",
            "source": hnx.SOURCE,
            "article_url": "https://hnx.vn/article",
            "article_path": "/m-niem-yet/tin-tuc/tx.html",
            "attachment_index": 1,
            "attachment_label": "1. DL1_tx.pdf",
            "attachment_url": "https://owa.hnx.vn/dl1.pdf",
            "attachment_filename": "DL1_tx.pdf",
            "attachment_storage_path": str(attachment_path),
            "attachment_sha256": "abc",
            "attachment_bytes": 12,
            "keyword_hits": "insider_related|transaction_notice",
        },
        article_lookup=article_lookup,
        ocr_transaction_attachments=False,
        ocr_languages=("vi", "en"),
        ocr_gpu=False,
    )

    assert row["filing_stage"] == "result"
    assert row["filing_subject_scope"] == "insider"
    assert row["transaction_instrument"] == "subscription_rights"
    assert row["parser_status"] == "structured_fields_extracted"
    assert row["text_extraction_status"] == "text_extracted"
    assert row["actor_name"] == "Nguyen Dinh Trac"
    assert row["actor_position"] == "Tong Giam doc"
    assert row["planned_buy_volume"] == 3200000
    assert row["actual_buy_volume"] == 3200000
    assert row["holding_after_volume"] == 3200000
    assert row["holding_after_pct"] == 3.84
    assert row["execution_rate_buy"] == 1.0
    assert row["text_storage_path"] is not None


def test_parse_transaction_attachment_marks_needs_ocr(monkeypatch, tmp_path: Path):
    attachment_path = tmp_path / "scan.pdf"
    attachment_path.write_bytes(b"%PDF-1.4 mock")
    monkeypatch.setattr(hnx, "TEXT_ROOT", tmp_path / "text")

    monkeypatch.setattr(
        hnx,
        "extract_attachment_text",
        lambda path, *, use_ocr, ocr_languages, ocr_gpu: ("", "needs_ocr", "none"),
    )

    row = hnx.parse_transaction_attachment(
        {
            "ticker": "DL1",
            "market_code": "NY",
            "market_bucket": "listed",
            "source": hnx.SOURCE,
            "article_url": "https://hnx.vn/article",
            "article_path": "/m-niem-yet/tin-tuc/tx.html",
            "attachment_index": 1,
            "attachment_label": "1. DL1_tx.pdf",
            "attachment_url": "https://owa.hnx.vn/dl1.pdf",
            "attachment_filename": "DL1_tx.pdf",
            "attachment_storage_path": str(attachment_path),
            "attachment_sha256": "abc",
            "attachment_bytes": 12,
            "keyword_hits": "insider_related|transaction_notice",
        },
        article_lookup={"https://hnx.vn/article": {"title": "Thong bao giao dich quyen mua co phieu cua nguoi noi bo"}},
        ocr_transaction_attachments=False,
        ocr_languages=("vi", "en"),
        ocr_gpu=False,
    )

    assert row["parser_status"] == "needs_ocr"
    assert row["text_extraction_status"] == "needs_ocr"
    assert row["actor_name"] is None


def test_parse_transaction_attachment_accepts_ocr_text(monkeypatch, tmp_path: Path):
    attachment_path = tmp_path / "scan.pdf"
    attachment_path.write_bytes(b"%PDF-1.4 mock")
    monkeypatch.setattr(hnx, "TEXT_ROOT", tmp_path / "text")

    monkeypatch.setattr(
        hnx,
        "extract_attachment_text",
        lambda path, *, use_ocr, ocr_languages, ocr_gpu: (
            "Ho va ten nguoi thuc hien giao dich: Bui Phap\nSo luong quyen mua da thuc hien: 100.000",
            "ocr_text_extracted",
            "easyocr",
        ),
    )

    row = hnx.parse_transaction_attachment(
        {
            "ticker": "DL1",
            "market_code": "NY",
            "market_bucket": "listed",
            "source": hnx.SOURCE,
            "article_url": "https://hnx.vn/article",
            "article_path": "/m-niem-yet/tin-tuc/tx.html",
            "attachment_index": 1,
            "attachment_label": "1. DL1_tx.pdf",
            "attachment_url": "https://owa.hnx.vn/dl1.pdf",
            "attachment_filename": "DL1_tx.pdf",
            "attachment_storage_path": str(attachment_path),
            "attachment_sha256": "abc",
            "attachment_bytes": 12,
            "keyword_hits": "insider_related|transaction_notice",
        },
        article_lookup={"https://hnx.vn/article": {"title": "Bao cao ket qua giao dich quyen mua co phieu cua nguoi noi bo"}},
        ocr_transaction_attachments=True,
        ocr_languages=("vi", "en"),
        ocr_gpu=False,
    )

    assert row["text_extraction_status"] == "ocr_text_extracted"
    assert row["text_extraction_method"] == "easyocr"
    assert row["actor_name"] == "Bui Phap"
