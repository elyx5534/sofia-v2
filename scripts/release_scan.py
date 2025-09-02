#!/usr/bin/env python3
"""
Release Security Scanner
Scans repository for secrets, large files, and sensitive data before release
"""

import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

# Configuration
MAX_FILE_SIZE = 100 * 1024  # 100KB
REPORT_DIR = Path("artifacts")
REPORT_FILE = REPORT_DIR / "release_scan_report.txt"

# Secret patterns to check (optimized for speed)
SECRET_PATTERNS = [
    (r'API[_-]?KEY\s*=\s*["\']?[A-Za-z0-9_\-]{20,}', "API Key"),
    (r'SECRET[_-]?KEY\s*=\s*["\']?[A-Za-z0-9_\-]{20,}', "Secret Key"),
    (r'TOKEN\s*=\s*["\']?[A-Za-z0-9_\-]{20,}', "Token"),
    (r'PASSWORD\s*=\s*["\']?\S+["\']?', "Password"),
    (r"-----BEGIN (RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY", "Private Key"),
    (r"Bearer\s+[A-Za-z0-9_\-\.]+", "Bearer Token"),
    (r"aws_access_key_id\s*=\s*[A-Z0-9]{20}", "AWS Access Key"),
    (r"aws_secret_access_key\s*=\s*[A-Za-z0-9/+=]{40}", "AWS Secret Key"),
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID"),
    (r"sk_live_[0-9a-zA-Z]{24,}", "Stripe Live Key"),
    (r"github_pat_[0-9a-zA-Z_]{82}", "GitHub Personal Access Token"),
    (r"ghp_[0-9a-zA-Z]{36}", "GitHub Personal Access Token"),
    (r"mongodb(\+srv)?://[^:]+:[^@]+@[^/]+", "MongoDB Connection String"),
    (r"postgres://[^:]+:[^@]+@[^/]+", "PostgreSQL Connection String"),
]

# Files to skip
SKIP_PATTERNS = [
    ".git/",
    ".venv/",
    "venv/",
    "node_modules/",
    "__pycache__/",
    ".pytest_cache/",
    "htmlcov/",
    "dist/",
    "build/",
    ".eggs/",
    "*.egg-info/",
    "artifacts/",
    "logs/",
    "reports/",
]

# File extensions to check for secrets
CHECK_EXTENSIONS = [
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".java",
    ".go",
    ".rb",
    ".php",
    ".yml",
    ".yaml",
    ".json",
    ".xml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".sh",
    ".bash",
    ".zsh",
    ".fish",
    ".ps1",
    ".bat",
    ".cmd",
    ".env",
    ".env.*",
    ".envrc",
    ".secrets",
    ".md",
    ".txt",
    ".rst",
]


class ReleaseScanner:
    def __init__(self):
        self.issues = []
        self.large_files = []
        self.potential_secrets = []
        self.env_files = []
        self.stats = {
            "total_files": 0,
            "files_scanned": 0,
            "large_files": 0,
            "potential_secrets": 0,
            "env_files": 0,
        }

    def should_skip(self, path: Path) -> bool:
        """Check if path should be skipped"""
        path_str = str(path).replace("\\", "/")

        for pattern in SKIP_PATTERNS:
            if pattern in path_str:
                return True

        # Skip binary files (except those we want to flag as large)
        if path.suffix in [".pyc", ".pyo", ".pyd", ".so", ".dll", ".exe", ".bin"]:
            return True

        return False

    def should_check_content(self, path: Path) -> bool:
        """Check if file content should be scanned for secrets"""
        # Check by extension
        if path.suffix in CHECK_EXTENSIONS:
            return True

        # Check extensionless files that might contain secrets
        if path.name in [".env", "Dockerfile", "docker-compose", "Makefile"]:
            return True

        # Check if filename contains sensitive keywords
        sensitive_names = ["secret", "password", "token", "key", "credential", "auth"]
        if any(keyword in path.name.lower() for keyword in sensitive_names):
            return True

        return False

    def scan_file_for_secrets(self, path: Path) -> List[Tuple[str, int, str]]:
        """Scan file content for potential secrets"""
        secrets_found = []

        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

                for line_num, line in enumerate(lines, 1):
                    # Skip comments
                    if line.strip().startswith("#") or line.strip().startswith("//"):
                        continue

                    for pattern, secret_type in SECRET_PATTERNS:
                        if re.search(pattern, line, re.IGNORECASE):
                            # Skip if it's an example or placeholder
                            if any(
                                placeholder in line.lower()
                                for placeholder in [
                                    "example",
                                    "placeholder",
                                    "your_",
                                    "xxx",
                                    "...",
                                    "<",
                                    ">",
                                ]
                            ):
                                continue

                            secrets_found.append((secret_type, line_num, line.strip()[:100]))
                            break
        except Exception:
            pass  # Skip files that can't be read

        return secrets_found

    def scan_directory(self, root_dir: Path):
        """Scan directory recursively"""
        max_files = 500  # Limit number of files to scan for speed

        for root, dirs, files in os.walk(root_dir):
            if self.stats["total_files"] > max_files:
                break
            root_path = Path(root)

            # Remove directories to skip from dirs list (modifies in-place)
            dirs[:] = [d for d in dirs if not self.should_skip(root_path / d)]

            for file in files:
                file_path = root_path / file

                if self.should_skip(file_path):
                    continue

                self.stats["total_files"] += 1

                # Check file size
                try:
                    file_size = file_path.stat().st_size

                    if file_size > MAX_FILE_SIZE:
                        self.large_files.append(
                            {
                                "path": str(file_path.relative_to(root_dir)),
                                "size": file_size,
                                "size_mb": round(file_size / (1024 * 1024), 2),
                            }
                        )
                        self.stats["large_files"] += 1
                except:
                    continue

                # Check for .env files
                if ".env" in file_path.name and file_path.name != ".env.example":
                    self.env_files.append(str(file_path.relative_to(root_dir)))
                    self.stats["env_files"] += 1

                # Scan content for secrets
                if self.should_check_content(file_path):
                    self.stats["files_scanned"] += 1
                    secrets = self.scan_file_for_secrets(file_path)

                    if secrets:
                        self.potential_secrets.append(
                            {"file": str(file_path.relative_to(root_dir)), "secrets": secrets}
                        )
                        self.stats["potential_secrets"] += len(secrets)

    def generate_report(self) -> str:
        """Generate scan report"""
        report = []
        report.append("=" * 70)
        report.append(" RELEASE SECURITY SCAN REPORT")
        report.append("=" * 70)
        report.append(f"Scan Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("Repository: sofia-v2")
        report.append("")

        # Statistics
        report.append("STATISTICS:")
        report.append(f"  Total files found: {self.stats['total_files']}")
        report.append(f"  Files scanned for secrets: {self.stats['files_scanned']}")
        report.append(f"  Large files (>100KB): {self.stats['large_files']}")
        report.append(f"  Potential secrets found: {self.stats['potential_secrets']}")
        report.append(f"  .env files found: {self.stats['env_files']}")
        report.append("")

        # Large files
        if self.large_files:
            report.append("LARGE FILES (>100KB):")
            report.append("-" * 50)
            for file in sorted(self.large_files, key=lambda x: x["size"], reverse=True)[:20]:
                report.append(f"  {file['size_mb']:.2f} MB - {file['path']}")
            if len(self.large_files) > 20:
                report.append(f"  ... and {len(self.large_files) - 20} more")
            report.append("")

        # Potential secrets
        if self.potential_secrets:
            report.append("[WARNING] POTENTIAL SECRETS DETECTED:")
            report.append("-" * 50)
            for item in self.potential_secrets[:10]:
                report.append(f"  File: {item['file']}")
                for secret_type, line_num, line_content in item["secrets"][:3]:
                    report.append(f"    Line {line_num}: {secret_type}")
                    report.append(f"      {line_content[:80]}...")
                report.append("")
            if len(self.potential_secrets) > 10:
                report.append(f"  ... and {len(self.potential_secrets) - 10} more files")
            report.append("")

        # .env files
        if self.env_files:
            report.append("[WARNING] .ENV FILES DETECTED (should be in .gitignore):")
            report.append("-" * 50)
            for env_file in self.env_files:
                report.append(f"  {env_file}")
            report.append("")

        # Summary
        report.append("SUMMARY:")
        report.append("-" * 50)

        has_issues = bool(self.potential_secrets or self.env_files)

        if has_issues:
            report.append("[ERROR] CRITICAL ISSUES FOUND - DO NOT PROCEED WITH RELEASE")
            report.append("")
            report.append("Required Actions:")
            if self.potential_secrets:
                report.append("  1. Remove or rotate all detected secrets")
                report.append("  2. Add sensitive files to .gitignore")
                report.append("  3. Run 'git rm --cached' on sensitive files")
            if self.env_files:
                report.append("  4. Remove all .env files from repository")
                report.append("  5. Ensure .env is in .gitignore")
        else:
            report.append("[OK] No critical security issues detected")
            if self.large_files:
                report.append(
                    f"[WARNING] {len(self.large_files)} large files detected - consider using Git LFS"
                )

        report.append("")
        report.append("=" * 70)

        return "\n".join(report)

    def run(self) -> bool:
        """Run the scan and return True if safe to proceed"""
        print("[SCAN] Starting release security scan...")

        # Scan repository
        root_dir = Path.cwd()
        self.scan_directory(root_dir)

        # Generate report
        report = self.generate_report()

        # Create artifacts directory
        REPORT_DIR.mkdir(exist_ok=True)

        # Save report
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            f.write(report)

        print(f"\n[REPORT] Report saved to: {REPORT_FILE}")

        # Print summary to console
        print("\n" + "=" * 50)
        print(" SCAN RESULTS")
        print("=" * 50)
        print(f"Files scanned: {self.stats['files_scanned']}")
        print(f"Large files: {self.stats['large_files']}")
        print(f"Potential secrets: {self.stats['potential_secrets']}")
        print(f".env files: {self.stats['env_files']}")

        # Determine if safe to proceed
        has_critical_issues = bool(self.potential_secrets or self.env_files)

        if has_critical_issues:
            print("\n[ERROR] CRITICAL ISSUES FOUND - Release blocked!")
            print("Check the report for details.")
            return False
        else:
            print("\n[OK] No critical issues found - Safe to proceed")
            if self.large_files:
                print(f"[WARNING] {len(self.large_files)} large files detected")
            return True


def main():
    scanner = ReleaseScanner()
    safe_to_proceed = scanner.run()

    # Exit with appropriate code
    sys.exit(0 if safe_to_proceed else 1)


if __name__ == "__main__":
    main()
