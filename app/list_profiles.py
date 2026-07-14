#!/usr/bin/env python3
"""
list-profiles: inspect which profile is active and what all profiles look like.
Usage: docker exec <container> list-profiles
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import resolve_active_profile  # noqa: E402


def main():
    try:
        active_name, active_params, manifest = resolve_active_profile()
    except Exception as e:
        print(f"Error reading profile config: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Active profile: {active_name}")
    print(f"  {manifest['profiles'][active_name].get('description', '')}")
    print()
    print("Available profiles:")
    for name, params in manifest["profiles"].items():
        marker = "*" if name == active_name else " "
        print(f"  {marker} {name}")
        print(f"      {params.get('description', '')}")
        for key, val in params.items():
            if key == "description":
                continue
            print(f"      {key}: {val}")
        print()


if __name__ == "__main__":
    main()