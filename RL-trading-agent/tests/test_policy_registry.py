import json
from pathlib import Path

from vn_stock_rl.policies import normalize_policy, policy_display_name, read_policy_from_metadata


def test_policy_normalization_round_trip():
    assert normalize_policy("cnn-lstm") == "cnn_lstm"
    assert policy_display_name("cnn_lstm") == "cnn-lstm"


def test_policy_metadata_reader(tmp_path: Path):
    model_path = tmp_path / "demo.zip"
    model_path.write_text("", encoding="utf-8")
    meta_path = tmp_path / "demo_meta.json"
    meta_path.write_text(json.dumps({"policy": "cnn_lstm"}), encoding="utf-8")

    assert read_policy_from_metadata(str(model_path)) == "cnn-lstm"
