#!/usr/bin/env python3
"""Convert .env file to Streamlit secrets.toml format."""

import os
import sys


def convert_env_to_toml(env_path, output_path):
    """
    Convert .env file to TOML format for Streamlit secrets.

    Groups variables by prefix:
    - AUTH_* -> [auth] section
    - DATABASE_* -> [database] section
    """
    if not os.path.exists(env_path):
        print(f"Warning: {env_path} does not exist, skipping conversion")
        return

    sections = {"auth": {}, "database": {}}

    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()

            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]

            if key.startswith("AUTH_"):
                section_key = key.replace("AUTH_", "").lower()
                sections["auth"][section_key] = value
            elif key.startswith("DATABASE_"):
                section_key = key.replace("DATABASE_", "").lower()
                sections["database"][section_key] = value

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        if sections["auth"]:
            f.write("[auth]\n")
            for key, val in sections["auth"].items():
                f.write(f'{key} = "{val}"\n')
            f.write("\n")

        if sections["database"]:
            f.write("[database]\n")
            for key, val in sections["database"].items():
                f.write(f'{key} = "{val}"\n')


if __name__ == "__main__":
    env_file = sys.argv[1] if len(sys.argv) > 1 else ".env"
    output_file = (
        sys.argv[2] if len(sys.argv) > 2 else ".streamlit/secrets.toml"
    )

    convert_env_to_toml(env_file, output_file)
    print(f"Converted {env_file} to {output_file}")
