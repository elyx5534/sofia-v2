#!/usr/bin/env python3
"""
ONE-BAR ONLY pre-commit hook
Checks that child templates don't include navbar.html directly
"""

import sys
import re
from pathlib import Path

FORBIDDEN_PATTERN = r'include\s+["\']partials/navbar\.html["\']'
ALLOWED_FILES = {'base.html', 'base_modern.html', 'base_ultimate.html', 'base_next.html'}

def check_one_bar_violation(file_path: Path) -> bool:
    """Check if file violates ONE-BAR rule"""
    if file_path.name in ALLOWED_FILES:
        return False  # Base templates can include navbar
        
    try:
        content = file_path.read_text(encoding='utf-8')
        matches = re.findall(FORBIDDEN_PATTERN, content, re.IGNORECASE)
        
        if matches:
            print(f"❌ ONE-BAR VIOLATION in {file_path}")
            print(f"   Found: {matches[0]}")
            print(f"   Rule: Child templates MUST NOT include navbar directly")
            print(f"   Fix: Use {% extends 'base.html' %} instead")
            return True
            
    except Exception as e:
        print(f"⚠️  Warning: Could not read {file_path}: {e}")
        
    return False

def main():
    """Check all provided files"""
    violations = 0
    
    for file_path in sys.argv[1:]:
        path_obj = Path(file_path)
        
        if path_obj.suffix == '.html':
            if check_one_bar_violation(path_obj):
                violations += 1
                
    if violations > 0:
        print(f"\n❌ ONE-BAR CHECK FAILED: {violations} violation(s)")
        print("   All child templates must extend base.html instead of including navbar")
        sys.exit(1)
    else:
        print("✅ ONE-BAR CHECK PASSED: No violations found")
        sys.exit(0)

if __name__ == "__main__":
    main()