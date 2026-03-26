"""Launch the Dash manual signal-labelling UI."""

from __future__ import annotations

import argparse
import secrets
import threading
import webbrowser

from manual_label_factory.config import get_default_config
from manual_label_factory.core.chunk_sampler import ChunkSampler
from manual_label_factory.core.label_storage import create_session_record
from manual_label_factory.split_utils import create_or_load_splits


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch the manual signal-labelling Dash UI.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind the Dash server to.")
    parser.add_argument("--port", type=int, default=8050, help="Port to bind the Dash server to.")
    parser.add_argument("--debug", action="store_true", help="Run Dash in debug mode.")
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional sampler seed. If omitted, use a fresh random seed for each UI launch.",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Start the local server without trying to open a browser tab.",
    )
    return parser


def main() -> None:
    try:
        from dash import Dash
    except ImportError as exc:
        raise ImportError("Dash is required for the labeling UI. Install dependencies from requirements.txt.") from exc

    from .callbacks import register_callbacks
    from .layout import build_layout
    from .state import chunk_sample_to_store

    parser = build_arg_parser()
    args = parser.parse_args()

    config = get_default_config()
    split_map = create_or_load_splits(config=config, overwrite=False)
    session = create_session_record(config=config)
    sampler_seed = args.seed if args.seed is not None else secrets.randbelow(2**32)
    sampler = ChunkSampler(config=config, split_name="train", seed=sampler_seed)
    initial_chunk = sampler.sample_chunk()
    url = f"http://{args.host}:{args.port}"

    app = Dash(__name__)
    app.title = "Manual Signal Label UI"
    app.layout = build_layout(chunk_sample_to_store(initial_chunk), session.session_id)
    register_callbacks(app=app, sampler=sampler, session_id=session.session_id, config=config)
    print(f"Launching Manual Signal Label UI at {url}")
    print(f"Session: {session.session_id}")
    print(f"Sampler seed: {sampler_seed}")
    print(f"Train tickers available for labeling: {len(split_map.get('train', []))}")
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
