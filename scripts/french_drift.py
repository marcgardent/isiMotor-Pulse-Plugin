#!/usr/bin/env python3
"""
isiMotor-Pulse-Plugin — French Language Drift Scanner.
Scans the codebase for common French keywords, grammatical patterns, contractions,
and accented characters to identify files subject to language drift.

Copyright 2026 Marc GARDENT
Licensed under the Apache License, Version 2.0.
"""

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

# ── French Keywords & Linguistic Patterns ─────────────────────────────────────

FRENCH_PATTERNS: list[tuple[str, str]] = [
    # 1. High-confidence accented French terms (unique to French)
    (
        "accented_vocab",
        r"\b(télémesure|données|succès|introuvable|spécifier|numéro|déjà|répertoire|dépôt|exécuter|compilateur|généré|précondition|paramètres|état|système|durée|étape|français|départ|arrivée|température|fréquence|résumé|terminé|prêt|arrière-plan|échec|créé|modifié|enregistré|activé|désactivé|défaut|écrit|reçu|envoyé)\b",
    ),
    # 2. Common French functional words (prepositions, conjunctions, determiners)
    (
        "functional_words",
        r"\b(dans|avec|pour|sans|vers|chez|mais|donc|alors|aussi|cette|ceux|celui|celle|celles|aucun|aucune|plusieurs|chaque|notre|votre|leur|leurs)\b",
    ),
    # 3. Common French verbs & conjugations
    (
        "verbs_conjugation",
        r"\b(veuillez|est|sont|fait|faire|peut|peuvent|doit|doivent|existe|trouve|trouver|affiche|afficher|sauvegarde|sauvegarder|lance|lancer|arrête|arrêter|écrire|ajoute|ajouter|créer|vérifier|obtenir|supprimer|modifier)\b",
    ),
    # 4. French technical & domain terminology
    (
        "technical_terms",
        r"\b(fichier|fichiers|dossier|dossiers|erreur|erreurs|avertissement|avertissements|paquet|paquets|vitesse|voiture|véhicule|pneu|pneus|pluie|météo|changement|journal|racine|chemins|entrée|sortie|suivant|précédent)\b",
    ),
    # 5. French contractions (d', l', n', qu', c', s', j', m', t')
    (
        "contractions",
        r"\b[dDlLnNqQcCsSjJmMtT]'(?:est|un|une|autre|accès|erreur|ici|il|ils|elle|elles|en|on|y|a|au|aux|avec|été|info|option|objet|état|ordre)\b",
    ),
]

# Compiled regular expressions for fast multi-pattern scanning
COMPILED_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (category, re.compile(pattern, re.IGNORECASE)) for category, pattern in FRENCH_PATTERNS
]

DEFAULT_IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "build",
    "bin",
    "dist",
    "__pycache__",
    ".idea",
    ".vscode",
    ".ruff_cache",
    ".mypy_cache",
    ".pytest_cache",
    ".briefcase",
    "node_modules",
    "egg-info",
}

DEFAULT_EXTENSIONS = {
    ".py",
    ".cpp",
    ".hpp",
    ".h",
    ".c",
    ".md",
    ".txt",
    ".toml",
    ".json",
    ".yaml",
    ".yml",
    ".cmake",
    ".sh",
}

DEFAULT_EXCLUDED_FILES = {
    "scripts/french_drift.py",
    "tests/test_french_drift.py",
    "LICENSE",
    "uv.lock",
}


@dataclass
class DriftMatch:
    line_number: int
    matched_word: str
    category: str
    line_snippet: str


@dataclass
class FileDriftReport:
    file_path: str
    total_matches: int
    categories: dict[str, int]
    matches: list[DriftMatch]


def get_project_root() -> Path:
    """Returns the project root directory."""
    return Path(__file__).resolve().parent.parent


def scan_file(file_path: Path, root: Path) -> FileDriftReport | None:
    """Scans a single file for French language drift keywords."""
    rel_path = str(file_path.relative_to(root))
    if rel_path in DEFAULT_EXCLUDED_FILES or file_path.name in DEFAULT_EXCLUDED_FILES:
        return None

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None

    matches: list[DriftMatch] = []
    category_counts: dict[str, int] = {}

    lines = content.splitlines()
    for line_idx, line in enumerate(lines, start=1):
        # Skip empty lines or pure punctuation
        stripped = line.strip()
        if not stripped:
            continue

        for category, regex in COMPILED_PATTERNS:
            for match in regex.finditer(line):
                word = match.group(0)
                category_counts[category] = category_counts.get(category, 0) + 1
                snippet = stripped[:120] + ("..." if len(stripped) > 120 else "")
                matches.append(
                    DriftMatch(
                        line_number=line_idx,
                        matched_word=word,
                        category=category,
                        line_snippet=snippet,
                    )
                )

    if not matches:
        return None

    return FileDriftReport(
        file_path=rel_path,
        total_matches=len(matches),
        categories=category_counts,
        matches=matches,
    )


def scan_repository(
    root: Path,
    extensions: set[str] | None = None,
    extra_excludes: set[str] | None = None,
) -> list[FileDriftReport]:
    """Scans the repository for files containing French language drift."""
    allowed_exts = extensions or DEFAULT_EXTENSIONS
    excludes = extra_excludes or set()

    reports: list[FileDriftReport] = []

    for dirpath, dirnames, filenames in os.walk(root):
        # Filter ignored directories in-place
        dirnames[:] = [d for d in dirnames if d not in DEFAULT_IGNORED_DIRS and d not in excludes]

        for fname in filenames:
            file_path = Path(dirpath) / fname
            rel_str = str(file_path.relative_to(root))

            if rel_str in excludes:
                continue

            # Check extension or special files (e.g. Makefile)
            if file_path.suffix.lower() in allowed_exts or fname == "Makefile":
                report = scan_file(file_path, root)
                if report:
                    reports.append(report)

    # Sort reports by number of matches descending
    reports.sort(key=lambda r: r.total_matches, reverse=True)
    return reports


def print_detailed_report(reports: list[FileDriftReport]) -> None:
    """Prints a structured breakdown of French language drift."""
    print("==================================================================")
    print("  🔍 isiMotor-Pulse — French Language Drift Report")
    print("==================================================================")

    if not reports:
        print("  ✓ Aucun drift linguistique français détecté ! Codebase 100% propre.")
        print("==================================================================")
        return

    total_files = len(reports)
    total_occurrences = sum(r.total_matches for r in reports)

    for report in reports:
        print(f"\n📄 \033[1;36m{report.file_path}\033[0m (\033[1;33m{report.total_matches} occurrences\033[0m)")
        cats_str = ", ".join(f"{k}: {v}" for k, v in report.categories.items())
        print(f"   \033[2mCatégories: {cats_str}\033[0m")

        # Show up to 10 sample matches per file
        sample_matches = report.matches[:10]
        for m in sample_matches:
            print(f"   • Ligne {m.line_number:4d}: [\033[1;31m{m.matched_word}\033[0m] {m.line_snippet}")

        if len(report.matches) > 10:
            print(f"   \033[2m... et {len(report.matches) - 10} autre(s) occurrence(s)\033[0m")

    print("\n==================================================================")
    print(
        f"📊 Résumé : \033[1;31m{total_files} fichier(s)\033[0m touché(s) — \033[1;33m{total_occurrences} mots français détectés\033[0m"
    )
    print("==================================================================")


def print_summary_report(reports: list[FileDriftReport]) -> None:
    """Prints a concise summary table of files affected by drift."""
    print("==================================================================")
    print("  📋 isiMotor-Pulse — French Language Drift Summary")
    print("==================================================================")

    if not reports:
        print("  ✓ Aucun fichier touché par le drift.")
        print("==================================================================")
        return

    print(f"{'Fichier':<55} | {'Occurrences':<12}")
    print("-" * 70)
    for r in reports:
        print(f"{r.file_path:<55} | {r.total_matches:<12}")

    total_occurrences = sum(r.total_matches for r in reports)
    print("-" * 70)
    print(f"Total: {len(reports)} fichier(s) concerné(s) ({total_occurrences} occurrences)")
    print("==================================================================")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="isiMotor-Pulse-Plugin — French Language Drift Scanner",
    )
    parser.add_argument(
        "--root",
        type=str,
        default=None,
        help="Path to repository root directory (default: project root)",
    )
    parser.add_argument(
        "--files-only",
        action="store_true",
        help="Output only the list of affected file paths (one per line)",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Output a concise summary table instead of detailed line matches",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit with status code 1 if any French language drift is detected (CI mode)",
    )
    parser.add_argument(
        "--exclude",
        nargs="*",
        default=[],
        help="Additional file paths or directories to exclude from scanning",
    )

    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else get_project_root()
    extra_excludes = set(args.exclude)

    reports = scan_repository(root, extra_excludes=extra_excludes)

    if args.json:
        data: dict[str, Any] = {
            "total_files_affected": len(reports),
            "total_occurrences": sum(r.total_matches for r in reports),
            "files": [asdict(r) for r in reports],
        }
        print(json.dumps(data, indent=2, ensure_ascii=False))
    elif args.files_only:
        for r in reports:
            print(r.file_path)
    elif args.summary:
        print_summary_report(reports)
    else:
        print_detailed_report(reports)

    if args.check and reports:
        sys.exit(1)


if __name__ == "__main__":
    main()
