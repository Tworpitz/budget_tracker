from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from db.storage import (backup_database, backup_project_databases, inspect_database,
                        legacy_database_paths, prepare_database, user_database_path)


def make_legacy(path, populated=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    for table in ("assets", "subscriptions", "one_time_expenses"):
        conn.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, name TEXT)")
    if populated:
        conn.execute("INSERT INTO assets VALUES (1, 'original')")
    conn.commit()
    return conn


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_backup_contains_committed_wal_and_is_standalone(self):
        source, target = self.root / "source.db", self.root / "backup.db"
        with closing(make_legacy(source)) as conn:
            conn.execute("INSERT INTO assets VALUES (2, 'wal row')")
            conn.commit()
            self.assertGreater(Path(str(source) + "-wal").stat().st_size, 0)
            self.assertEqual(backup_database(source, target)["assets"], 2)
            with closing(sqlite3.connect(target)) as check:
                self.assertEqual(check.execute("SELECT name FROM assets WHERE id=2").fetchone()[0], "wal row")
                self.assertEqual(check.execute("PRAGMA journal_mode").fetchone()[0], "delete")
            self.assertEqual(conn.execute("SELECT count(*) FROM assets").fetchone()[0], 2)
        self.assertEqual(list(self.root.glob(".budget-backup-*")), [])

    def test_backup_does_not_overwrite_existing_destination(self):
        source, target = self.root / "source.db", self.root / "backup.db"
        with closing(make_legacy(source)):
            target.write_bytes(b"keep me")
            with self.assertRaises(FileExistsError):
                backup_database(source, target)
        self.assertEqual(target.read_bytes(), b"keep me")

    def test_migration_preserves_original_and_does_not_overwrite_new_database(self):
        source, target = self.root / "dist" / "budget.db", self.root / "user" / "budget.db"
        with closing(make_legacy(source)):
            self.assertEqual(prepare_database(target, [source]), source.resolve())
            self.assertEqual(inspect_database(target)["assets"], 1)
            self.assertTrue(source.is_file())
            self.assertEqual(len(list((target.parent / "backups").glob("*.db"))), 1)
            with closing(sqlite3.connect(target)) as conn:
                conn.execute("INSERT INTO assets VALUES (2, 'new data')")
                conn.commit()
            self.assertIsNone(prepare_database(target, [source]))
            self.assertEqual(inspect_database(target)["assets"], 2)

    def test_populated_legacy_preferred_over_empty_database(self):
        empty, full, target = self.root / "empty.db", self.root / "full.db", self.root / "user.db"
        with closing(make_legacy(empty, False)), closing(make_legacy(full)):
            self.assertEqual(prepare_database(target, [empty, full]), full.resolve())
            self.assertEqual(inspect_database(target)["assets"], 1)

    def test_multiple_populated_sources_stop_migration(self):
        one, two, target = self.root / "one.db", self.root / "two.db", self.root / "user.db"
        with closing(make_legacy(one)), closing(make_legacy(two)):
            with self.assertRaises(ValueError):
                prepare_database(target, [one, two])
        self.assertFalse(target.exists())

    def test_corrupt_source_does_not_create_target(self):
        source, target = self.root / "corrupt.db", self.root / "user.db"
        source.write_bytes(b"not sqlite")
        with self.assertRaises(sqlite3.DatabaseError):
            backup_database(source, target)
        self.assertFalse(target.exists())

    def test_project_backup_covers_dist_and_root(self):
        source = self.root / "budget.db"
        nested = self.root / "dist" / "BudgetTracker" / "budget.db"
        with closing(make_legacy(source)), closing(make_legacy(nested)):
            output = backup_project_databases(self.root, self.root / "backups")
        self.assertTrue((output / "budget.db").exists())
        self.assertTrue((output / "dist" / "BudgetTracker" / "budget.db").exists())
        self.assertTrue((output / "manifest.json").exists())

    def test_platform_paths_are_outside_build_directory(self):
        with patch("db.storage.sys.platform", "win32"), patch.dict("os.environ", {"LOCALAPPDATA": str(self.root)}):
            self.assertEqual(user_database_path(), self.root / "BudgetTracker" / "budget.db")
        with patch("db.storage.sys.platform", "linux"), patch.dict("os.environ", {"XDG_DATA_HOME": str(self.root)}):
            self.assertEqual(user_database_path(), self.root / "budgettracker" / "budget.db")

    def test_new_packaged_locations_find_legacy_dist_databases(self):
        for relative in ("dist/windows/BudgetTracker.exe", "dist/linux/BudgetTracker/BudgetTracker",
                         "dist/BudgetTracker.exe", "dist/BudgetTracker/BudgetTracker"):
            with self.subTest(executable=relative), patch("db.storage.sys.frozen", True, create=True), \
                    patch("db.storage.sys.executable", str(self.root / relative)):
                paths = legacy_database_paths(self.root)
                self.assertIn(self.root / "dist" / "budget.db", paths)
                self.assertIn(self.root / "dist" / "BudgetTracker" / "budget.db", paths)
                self.assertIn(self.root / "budget.db", paths)
