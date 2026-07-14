import os
import yaml

MANIFEST_PATH = os.environ.get(
    "MANIFEST_PATH", "model_manifest.yaml"
)


def load_manifest() -> dict:
    with open(MANIFEST_PATH, "r") as f:
        return yaml.safe_load(f)


def resolve_active_profile():
    """Returns (profile_name, profile_params, full_manifest)."""
    manifest = load_manifest()
    default_profile = manifest["default_profile"]
    profiles = manifest["profiles"]

    name = os.environ.get("PROFILE", default_profile)
    if name not in profiles:
        raise ValueError(
            f"PROFILE '{name}' not found in manifest. "
            f"Valid: {list(profiles.keys())}"
        )

    return name, profiles[name], manifest