import os
import sys
import yaml

MANIFEST_PATH = os.environ.get("MANIFEST_PATH", "model_manifest.yaml")


def main():
    if not os.path.exists(MANIFEST_PATH):
        print(f"FATAL: manifest not found at {MANIFEST_PATH}", file=sys.stderr)
        sys.exit(1)

    with open(MANIFEST_PATH, "r") as f:
        manifest = yaml.safe_load(f)

    valid_profiles = list(manifest.get("profiles", {}).keys())
    default_profile = manifest.get("default_profile")
    requested = os.environ.get("PROFILE", default_profile)

    if requested not in valid_profiles:
        print(
            f"FATAL: invalid PROFILE '{requested}'. "
            f"Valid profiles are: {', '.join(valid_profiles)}. "
            f"Set PROFILE to one of these, e.g. -e PROFILE={default_profile}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Profile '{requested}' validated OK.")


if __name__ == "__main__":
    main()