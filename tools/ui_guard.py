import sys
import subprocess
import fnmatch
import os

PROTECTED = [
    "sofia_ui/index.html",
    "sofia_ui/**/*.html",
    "sofia_ui/css/**",
    "sofia_ui/js/**",
    "sofia_ui/assets/**",
    "sofia_ui/theme/**",
    "sofia_ui/tailwind.config.*",
    "sofia_ui/postcss.config.*",
]

def check_ui_changes():
    """Check for protected UI changes"""
    if not os.path.exists(".git"):
        print("UI GUARD: Not in a git repository")
        return 0
    
    try:
        diff = subprocess.check_output(["git", "diff", "--name-only", "--cached"], text=True).splitlines()
    except subprocess.CalledProcessError:
        diff = []

    bad = []
    for p in diff:
        for pat in PROTECTED:
            if fnmatch.fnmatch(p, pat):
                bad.append(p)
                break

    if bad:
        print("❌ UI GUARD: Bu dosyalara commit yasak:")
        for f in bad:
            print(f"  - {f}")
        return 1
    
    print("✅ UI GUARD: OK")
    return 0

if __name__ == "__main__":
    # Check for --check flag
    check_mode = "--check" in sys.argv
    sys.exit(check_ui_changes())