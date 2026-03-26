from __future__ import annotations


def print_training_start(log_dir: str, run_dir: str, checkpoints_dir: str):
    print("\n" + "=" * 60)
    print("Starting Training")
    print("=" * 60)
    print("\nMonitor training progress:")
    print(f"  - Tensorboard: tensorboard --logdir {log_dir}")
    print(f"  - Run directory: {run_dir}")
    print(f"  - Checkpoints saved to: {checkpoints_dir}")
    print("  - Validation return logs: eval/mean_return")
    print("  - Training return logs: train_episode/return_*")
    print("=" * 60 + "\n")


def print_training_complete(final_path: str, best_dst: str | None):
    print(f"\n{'=' * 60}")
    print("Training complete!")
    print(f"Final model saved to: {final_path}.zip")
    if best_dst:
        print(f"Best model saved to: {best_dst}")
    print(f"{'=' * 60}")
