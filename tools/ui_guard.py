import sys
import subprocess
import fnmatch

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
    sys.exit(1)

print("✅ UI GUARD: OK")