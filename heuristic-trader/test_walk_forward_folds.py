from walk_forward_validate import FOLDS, build_active_folds


def test_build_active_folds_default_lockbox() -> None:
    folds = build_active_folds(allow_2026=False, dev_end_date=None)
    assert len(folds) == len(FOLDS)
    assert folds[-1]["name"] == "fold_2025"


def test_build_active_folds_with_2026_extension() -> None:
    folds = build_active_folds(allow_2026=True, dev_end_date="2026-03-31")
    assert len(folds) == len(FOLDS) + 1
    assert folds[-1]["name"] == "fold_2026"
    assert folds[-1]["test_start"] == "2026-01-01"
    assert folds[-1]["test_end"] == "2026-03-31"
