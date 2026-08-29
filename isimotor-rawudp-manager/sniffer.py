#!/usr/bin/env python3
"""CLI wrapper for running the sniffer directly."""
import sys
from pathlib import Path

_manager_dir = Path(__file__).resolve().parent
if str(_manager_dir) not in sys.path:
    sys.path.insert(0, str(_manager_dir))

from isimotor_rawudp_manager.sniffer import *  # noqa: F403
from isimotor_rawudp_manager.sniffer import main

if __name__ == "__main__":
    main()
