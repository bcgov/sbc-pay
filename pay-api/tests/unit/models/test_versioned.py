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

"""Unit tests for Versioned class with concurrent updates."""

import threading

import pytest
from sql_versioning import Versioned, versioned_session

from pay_api.models import db


class VersionedTestModel(Versioned, db.Model):
    """Simple test model inheriting from Versioned."""

    __tablename__ = "test_versioned"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    value = db.Column(db.Integer, nullable=False, default=0)


@pytest.mark.parametrize("use_lock,should_fail", [(True, False), (False, True)])
def test_concurrent_versioned_updates(
    app,
    use_lock,
    should_fail,  # noqa: ARG001
):
    """Test concurrent updates don't create duplicate history."""
    VersionedTestModel.__table__.create(db.engine, checkfirst=True)
    with db.engine.begin() as conn:
        conn.execute(
            db.text("""
            CREATE TABLE IF NOT EXISTS test_versioned_history (
                id INTEGER NOT NULL,
                name VARCHAR(100) NOT NULL,
                value INTEGER NOT NULL,
                version INTEGER NOT NULL,
                changed TIMESTAMP,
                PRIMARY KEY (id, version)
            )
        """)
        )

    with db.engine.begin() as conn:
        result = conn.execute(
            db.text("INSERT INTO test_versioned (name, value, version) VALUES ('test', 100, 1) RETURNING id")
        )
        test_id = result.fetchone()[0]

    errors = []
    lock = threading.Lock()
    barrier = threading.Barrier(2)

    def update_model(thread_id, new_value):
        """Update model in separate thread."""
        try:
            with app.app_context():
                with db.engine.connect() as conn:
                    session = db.sessionmaker(bind=conn)()
                    versioned_session(session)
                    try:
                        barrier.wait()
                        query = session.query(VersionedTestModel).filter_by(id=test_id)
                        if use_lock:
                            query = query.with_for_update()
                        record = query.first()
                        record.value = new_value
                        session.commit()
                    finally:
                        session.close()
        except Exception as e:  # noqa: BLE001
            with lock:
                errors.append(f"Thread {thread_id}: {str(e)}")

    thread1 = threading.Thread(target=update_model, args=(1, 50))
    thread2 = threading.Thread(target=update_model, args=(2, 75))
    thread1.start()
    thread2.start()
    thread1.join()
    thread2.join()

    with db.engine.connect() as conn:
        result = conn.execute(
            db.text("""
            SELECT id, version
            FROM test_versioned_history
            WHERE id = :test_id
        """),
            {"test_id": test_id},
        )
        history = result.fetchall()

    if should_fail:
        assert errors, "Expected errors due to race condition without locking"
        assert any(
            "unique" in str(err).lower() or "duplicate" in str(err).lower() for err in errors
        ), f"Expected unique constraint error, got: {errors}"
    else:
        assert not errors, f"Errors: {errors}"
        assert len(history) == 2, f"History should have 2 rows, got {len(history)}: {history}"

    VersionedTestModel.__table__.drop(db.engine)
