"""
Apply Adaptive Parameters
Updates execution config based on recent performance
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.execution.adaptive_controller import AdaptiveController


def main():
    controller = AdaptiveController()
    result = controller.run()
    
    # Exit with appropriate code
    if result['adjustments']:
        sys.exit(0)  # Changes made
    else:
        sys.exit(1)  # No changes needed


if __name__ == "__main__":
    main()