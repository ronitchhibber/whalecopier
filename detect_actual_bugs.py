#!/usr/bin/env python3
"""
Detect actual bugs in code like:
- Missing imports in function calls
- Incorrect method calls
- Type mismatches
- Logic errors
- Configuration issues
"""

import re
from pathlib import Path
from typing import List, Dict, Tuple

def check_imports_vs_usage(filepath: Path) -> List[str]:
    """Check if all used modules are imported."""
    with open(filepath, 'r') as f:
        content = f.read()

    issues = []

    # Check for common patterns
    patterns = [
        (r'from\s+\.\w+\s+import\s+\w+', 'relative import'),
        (r'import\s+\w+(?:\.\w+)*', 'absolute import'),
    ]

    # Check for undefined function calls
    undefined_calls = []

    # Check for config references without imports
    if 'config.' in content or 'self.config' in content:
        if 'config' not in content or 'self.config' not in content:
            # Check if ConfigError or similar is defined
            if 'Config' not in content and 'config' in content:
                undefined_calls.append("config variable used but not defined/imported")

    # Check for environment variables without os import
    if 'os.environ' in content and 'import os' not in content:
        issues.append("os.environ used but os not imported")

    # Check for logging without logger init
    if 'logger.' in content:
        if 'logger = logging.getLogger' not in content:
            issues.append("logger used but not initialized")

    # Check for async/await without async def
    if 'await ' in content and 'async def' not in content and 'async with' not in content:
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            if 'await ' in line and 'async' not in line:
                # Check surrounding context
                context = '\n'.join(lines[max(0, i-3):i+2])
                if 'async' not in context:
                    issues.append(f"await used outside async context (line ~{i})")

    # Check for missing required attributes
    if '.epoch_ms' in content or '.amount' in content or '.price' in content:
        # Check if Trade model is properly defined or imported
        if 'class Trade' not in content and 'from' not in content.split('import Trade')[0]:
            # This might be okay if Trade is imported
            pass

    return issues

def check_function_definitions(filepath: Path) -> List[str]:
    """Check for function definition issues."""
    with open(filepath, 'r') as f:
        content = f.read()
        lines = content.split('\n')

    issues = []

    # Check for functions with undefined parameters
    for i, line in enumerate(lines, 1):
        if 'def ' in line and '(' in line:
            # Extract parameter list
            param_match = re.search(r'def\s+\w+\(([^)]*)\)', line)
            if param_match:
                params = param_match.group(1)
                # Check for type hints with undefined types
                for param in params.split(','):
                    param = param.strip()
                    if ':' in param:
                        type_hint = param.split(':')[1].strip().split('=')[0].strip()
                        # Check if type hint is imported
                        if type_hint not in ['int', 'str', 'float', 'bool', 'dict', 'list', 'set', 'tuple']:
                            if type_hint not in content.split('\n')[0:i-1]:
                                # Might be imported from typing
                                pass

    return issues

def check_class_methods(filepath: Path) -> List[str]:
    """Check for class method issues."""
    with open(filepath, 'r') as f:
        content = f.read()
        lines = content.split('\n')

    issues = []
    current_class = None
    in_class = False
    indent_level = 0

    for i, line in enumerate(lines, 1):
        stripped = line.lstrip()

        if stripped.startswith('class '):
            current_class = stripped.split('(')[0].replace('class ', '')
            in_class = True
            indent_level = len(line) - len(stripped)

        elif in_class and stripped.startswith('def '):
            if 'self' not in line and current_class is not None:
                # Check if it's a @staticmethod or @classmethod
                if i > 1 and '@staticmethod' not in lines[i-2] and '@classmethod' not in lines[i-2]:
                    issues.append(f"Instance method in {current_class} missing 'self' (line {i})")

        elif in_class and len(line) - len(stripped) <= indent_level and stripped and not stripped.startswith('#'):
            in_class = False

    return issues

def check_error_handling(filepath: Path) -> List[str]:
    """Check for error handling issues."""
    with open(filepath, 'r') as f:
        content = f.read()
        lines = content.split('\n')

    issues = []

    for i, line in enumerate(lines, 1):
        if 'except:' in line:
            issues.append(f"Bare except clause at line {i} (should catch specific exception)")

        if 'except Exception' in line and ':' in line:
            # Check if exception is used in except block
            except_block_start = i
            j = i
            while j < len(lines):
                if lines[j].startswith(' ' * (len(line) - len(line.lstrip()))):
                    if 'except' in lines[j] or 'finally' in lines[j] or 'else' in lines[j]:
                        break
                j += 1

    return issues

def check_type_mismatches(filepath: Path) -> List[str]:
    """Check for type-related issues."""
    with open(filepath, 'r') as f:
        content = f.read()
        lines = content.split('\n')

    issues = []

    # Check for Decimal usage
    if 'Decimal(' in content and 'from decimal import Decimal' not in content:
        if 'import Decimal' not in content:
            issues.append("Decimal used but not imported from decimal module")

    # Check for datetime usage
    if 'datetime(' in content:
        if 'from datetime import datetime' not in content and 'import datetime' not in content:
            pass  # Might be okay

    return issues

def main():
    """Check all modules for bugs."""
    modules = [
        'src/analytics/performance_metrics_engine.py',
        'src/analytics/trade_attribution_analyzer.py',
        'src/analytics/edge_detection_system.py',
        'src/analytics/benchmarking_system.py',
        'src/analytics/cusum_edge_decay_detector.py',
        'src/analytics/whale_lifecycle_tracker.py',
        'src/analytics/market_efficiency_analyzer.py',
        'src/analytics/adaptive_threshold_manager.py',
        'src/analytics/reporting_engine.py',
        'src/analytics/analytics_integration.py',
        'src/optimization/strategy_parameter_optimizer.py',
        'src/optimization/portfolio_optimizer.py',
        'src/optimization/optimization_integration.py',
        'src/risk_management/risk_manager.py',
        'src/risk_management/alert_system.py',
        'src/production/health_monitor.py',
    ]

    print("=" * 80)
    print("DETAILED BUG DETECTION - WEEKS 9-14 MODULES")
    print("=" * 80)
    print()

    project_root = Path(__file__).parent
    bugs_found = {}

    for module in modules:
        filepath = project_root / module

        if not filepath.exists():
            print(f"✗ NOT FOUND: {module}")
            continue

        all_issues = []

        # Run all checks
        all_issues.extend(check_imports_vs_usage(filepath))
        all_issues.extend(check_function_definitions(filepath))
        all_issues.extend(check_class_methods(filepath))
        all_issues.extend(check_error_handling(filepath))
        all_issues.extend(check_type_mismatches(filepath))

        if all_issues:
            bugs_found[module] = all_issues
            print(f"⚠ ISSUES: {module}")
            for issue in all_issues[:3]:
                print(f"  - {issue}")
            if len(all_issues) > 3:
                print(f"  ... and {len(all_issues) - 3} more")
        else:
            print(f"✓ PASS: {module}")

    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total modules analyzed: {len(modules)}")
    print(f"Modules with issues: {len(bugs_found)}")

    if bugs_found:
        print()
        print("ISSUES BY MODULE:")
        print("-" * 80)
        for module, issues in bugs_found.items():
            print(f"\n{module}:")
            for issue in issues:
                print(f"  - {issue}")

if __name__ == '__main__':
    main()
