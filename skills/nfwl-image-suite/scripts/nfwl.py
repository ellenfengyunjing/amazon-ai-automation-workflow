from pathlib import Path
from _nfwl_core import cli

if __name__ == "__main__":
    raise SystemExit(cli(Path(__file__).resolve().parents[1]))
