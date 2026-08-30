"""
Unit tests for scripts/french_drift.py.
Validates French language drift detection, keyword categories, and reporting.

Copyright 2026 Marc GARDENT
Licensed under the Apache License, Version 2.0.
"""

import sys
import tempfile
import unittest
from pathlib import Path

# Add project root and scripts to sys.path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
_scripts_dir = _project_root / "scripts"
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

from french_drift import scan_file, scan_repository


class TestFrenchDrift(unittest.TestCase):
    """Test suite for French language drift scanner."""

    def test_pure_english_file_has_no_drift(self) -> None:
        """Tests that a clean English source file reports zero drift."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "clean.py"
            f.write_text(
                '"""High performance telemetry client."""\n'
                "def compute_speed(local_vel: tuple[float, float, float]) -> float:\n"
                "    return (local_vel[0]**2 + local_vel[1]**2 + local_vel[2]**2)**0.5\n",
                encoding="utf-8",
            )
            report = scan_file(f, Path(tmp_dir))
            self.assertIsNone(report)

    def test_french_keywords_detection(self) -> None:
        """Tests detection of various categories of French keywords."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "drift_example.py"
            f.write_text(
                "# ❌ Erreur : Le fichier de télémesure est introuvable.\n"
                "# Veuillez spécifier le répertoire avec les données.\n"
                "# Cliquez sur sauvegarder pour mettre à jour le paquet.\n"
                "# Ce n'est pas un problème de configuration.\n",
                encoding="utf-8",
            )
            report = scan_file(f, Path(tmp_dir))
            self.assertIsNotNone(report)
            assert report is not None

            # Verify categories detected
            self.assertIn("accented_vocab", report.categories)
            self.assertIn("verbs_conjugation", report.categories)
            self.assertIn("technical_terms", report.categories)
            self.assertIn("contractions", report.categories)

            # Check specific words matched
            matched_words = [m.matched_word.lower() for m in report.matches]
            self.assertIn("erreur", matched_words)
            self.assertIn("fichier", matched_words)
            self.assertIn("télémesure", matched_words)
            self.assertIn("introuvable", matched_words)
            self.assertIn("veuillez", matched_words)
            self.assertIn("spécifier", matched_words)
            self.assertIn("répertoire", matched_words)
            self.assertIn("données", matched_words)
            self.assertIn("n'est", matched_words)

    def test_scan_repository(self) -> None:
        """Tests repository-wide directory walk and exclusion filtering."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)

            # File with drift
            (root / "src").mkdir()
            drift_f = root / "src" / "module.py"
            drift_f.write_text("# Erreur critique lors de la sauvegarde\n", encoding="utf-8")

            # Clean file
            clean_f = root / "src" / "clean.py"
            clean_f.write_text("# Standard English comment\n", encoding="utf-8")

            # Ignored folder
            (root / ".venv").mkdir()
            venv_f = root / ".venv" / "drift.py"
            venv_f.write_text("# Erreur dans venv\n", encoding="utf-8")

            reports = scan_repository(root)
            self.assertEqual(len(reports), 1)
            self.assertEqual(reports[0].file_path, "src/module.py")


if __name__ == "__main__":
    unittest.main()
