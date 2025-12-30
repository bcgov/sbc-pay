#!/usr/bin/env python3
"""Generate Streamlit secrets.toml from environment variables."""

import os
from pathlib import Path


def generate_toml_secrets(output_path):
    """
    Generate secrets.toml from STREAMLIT_* environment variables.

    Environment variables format: STREAMLIT_[SECTION]_[KEY]
    Example: STREAMLIT_AUTH_CLIENT_ID -> [auth][client_id]
    """
    sections = {}

    for key, value in os.environ.items():
        if not key.startswith("STREAMLIT_"):
            continue

        key_part = key[10:]
        if "_" not in key_part:
            continue

        section_key = key_part.split("_", 1)
        if len(section_key) != 2:
            continue

        section = section_key[0].lower()
        env_key = section_key[1].lower()

        if section not in sections:
            sections[section] = {}

        sections[section][env_key] = value

    if not sections:
        return

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total_secrets = 0
    with open(output_path, "w", encoding="utf-8") as f:
        for section, secrets in sections.items():
            f.write(f"[{section}]\n")
            for key, val in secrets.items():
                if val.startswith('"') and val.endswith('"'):
                    val = val[1:-1]
                f.write(f'{key} = "{val}"\n')
                total_secrets += 1
            f.write("\n")

    return total_secrets


if __name__ == "__main__":
    output_file = os.environ.get(
        "STREAMLIT_SECRETS_FILE", ".streamlit/secrets.toml"
    )
    count = generate_toml_secrets(output_file)
    if count:
        print(
            f"Generated {output_file} with {count} secrets from environment variables"
        )
    else:
        print(f"No secrets found to generate {output_file}")
