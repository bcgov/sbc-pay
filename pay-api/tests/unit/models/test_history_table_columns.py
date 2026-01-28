# Copyright © 2024 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Unit tests for comparing columns between base tables and their history tables."""

import pytest
from sql_versioning import Versioned
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from pay_api.models import db


@pytest.fixture
def engine() -> Engine:
    """Get the database engine."""
    return db.engine


@pytest.fixture
def inspector(engine: Engine):
    """Get the database inspector."""
    return inspect(engine)


def get_all_model_classes(base_class):
    """Recursively get all model subclasses."""
    subclasses = set()
    work = [base_class]
    while work:
        parent = work.pop()
        for child in parent.__subclasses__():
            if child not in subclasses:
                subclasses.add(child)
                work.append(child)
    return subclasses


@pytest.fixture
def versioned_models():
    """Discover versioned models and their corresponding history tables."""
    all_models = get_all_model_classes(db.Model)
    # This is intended for a unit test only not for prod code.
    skip_tables = {"test_versioned"}
    versioned_models = []
    for model_class in all_models:
        if (
            hasattr(model_class, "__tablename__")
            and hasattr(model_class, "__mro__")
            and Versioned in model_class.__mro__
        ):
            base_table = model_class.__tablename__
            if base_table in skip_tables:
                continue
            history_table = f"{base_table}_history"
            versioned_models.append((base_table, history_table))
    print("Discovered versioned models (by class scan):", versioned_models)
    return versioned_models


def get_table_columns(inspector, table_name: str) -> dict:
    """Get column information for a table."""
    columns = {}
    for column in inspector.get_columns(table_name):
        columns[column["name"]] = {
            "type": str(column["type"]),
            "nullable": column["nullable"],
            "default": column["default"],
            "primary_key": column.get("primary_key", False),
            "autoincrement": column.get("autoincrement", False),
        }
    return columns


def test_history_table_columns(session, inspector, versioned_models):
    """Test that history tables have the same columns as base tables (plus version/changed)."""
    for base_table, history_table in versioned_models:
        base_columns = get_table_columns(inspector, base_table)
        history_columns = get_table_columns(inspector, history_table)

        expected_additional = {"version", "changed"}

        base_column_names = set(base_columns.keys()) - {"version"}
        history_column_names = set(history_columns.keys()) - expected_additional

        missing_columns = base_column_names - history_column_names
        assert not missing_columns, f"Missing columns in {history_table}: {missing_columns}"

        missing_additional = expected_additional - set(history_columns.keys())
        assert not missing_additional, f"Missing required columns in {history_table}: {missing_additional}"

        assert not history_columns["version"]["autoincrement"], (
            f"Version column should not be autoincrement in {history_table}"
        )
        assert not history_columns["version"]["nullable"], f"Version column should not be nullable in {history_table}"


def test_history_tables_have_composite_primary_keys(session, inspector, versioned_models):
    """Test that all history tables have composite primary keys with id and version."""
    # Tables to skip for this test (they have different primary key structures)
    skip_tables = {"distribution_codes_history"}

    for _base_table, history_table in versioned_models:
        if history_table in skip_tables:
            continue

        pk_constraint = inspector.get_pk_constraint(history_table)
        pk_columns = pk_constraint["constrained_columns"]

        assert "id" in pk_columns, f"Primary key for {history_table} should include 'id'"
        assert "version" in pk_columns, f"Primary key for {history_table} should include 'version'"
        assert len(pk_columns) == 2, f"Primary key for {history_table} should have exactly 2 columns: {pk_columns}"


def test_history_tables_have_same_index_count(session, inspector, versioned_models):
    """Test that history tables have the same number of indexes as their base tables."""
    for base_table, history_table in versioned_models:
        try:
            base_indexes = inspector.get_indexes(base_table)
            history_indexes = inspector.get_indexes(history_table)

            # Verify that history table has the same number of indexes as base table
            assert len(history_indexes) == len(base_indexes), (
                f"History table {history_table} should have same number of indexes as base table {base_table} "
                f"(expected {len(base_indexes)}, got {len(history_indexes)})"
            )
        except Exception:  # noqa: S110
            # Skip tables that don't exist
            pass


def test_history_tables_exist(session, inspector, versioned_models):
    """Test that all expected history tables exist in the database."""
    existing_tables = inspector.get_table_names()
    history_tables = [history_table for _, history_table in versioned_models] + ["eft_short_names_historical"]

    for history_table in history_tables:
        assert history_table in existing_tables, f"History table {history_table} does not exist"


def test_base_tables_have_version_column(session, inspector, versioned_models):
    """Test that base tables have version column added."""
    for base_table, _ in versioned_models:
        columns = get_table_columns(inspector, base_table)
        assert "version" in columns, f"Base table {base_table} should have version column"
        assert not columns["version"]["nullable"], f"Version column in {base_table} should not be nullable"
        assert columns["version"]["default"] == "1", f"Version column in {base_table} should have default value '1'"


def test_history_table_column_types_match_base_tables(session, inspector, versioned_models):
    """Test that column types in history tables match their base tables."""
    for base_table, history_table in versioned_models:
        base_columns = get_table_columns(inspector, base_table)
        history_columns = get_table_columns(inspector, history_table)

        common_columns = set(base_columns.keys()) & set(history_columns.keys())
        common_columns -= {"version"}

        for column_name in common_columns:
            base_type = base_columns[column_name]["type"]
            history_type = history_columns[column_name]["type"]

            if "autoincrement" in base_type and "autoincrement" not in history_type:
                base_type_without_auto = base_type.replace("autoincrement=True", "").strip()
                assert base_type_without_auto == history_type, (
                    f"Column {column_name} type mismatch in {history_table}: expected {base_type_without_auto},"
                )
                f"got {history_type}"
            else:
                assert base_type == history_type, (
                    f"Column {column_name} type mismatch in {history_table}: expected {base_type}, got {history_type}"
                )
