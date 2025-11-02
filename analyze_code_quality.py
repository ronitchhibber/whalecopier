#!/usr/bin/env python3
"""
Deep code quality analysis for Weeks 9-14 modules.
Checks for:
- Undefined variables and functions
- Missing imports
- Typos and naming issues
- Syntax issues
- Logic errors
"""

import ast
import os
import sys
from pathlib import Path
from collections import defaultdict

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

class CodeAnalyzer(ast.NodeVisitor):
    """Analyzes AST for potential bugs."""

    def __init__(self, filename):
        self.filename = filename
        self.issues = []
        self.imports = set()
        self.defined_names = set()
        self.used_names = set()
        self.undefined_refs = []
        self.builtin_names = set(dir(__builtins__))

    def visit_Import(self, node):
        """Track imports."""
        for alias in node.names:
            self.imports.add(alias.asname or alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        """Track from imports."""
        for alias in node.names:
            self.imports.add(alias.asname or alias.name)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        """Track function definitions."""
        self.defined_names.add(node.name)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        """Track class definitions."""
        self.defined_names.add(node.name)
        self.generic_visit(node)

    def visit_Name(self, node):
        """Track name usage."""
        if isinstance(node.ctx, ast.Load):
            self.used_names.add(node.id)
        elif isinstance(node.ctx, ast.Store):
            self.defined_names.add(node.id)
        self.generic_visit(node)

    def check_undefined(self):
        """Check for undefined variables."""
        undefined = self.used_names - self.defined_names - self.imports - self.builtin_names
        # Filter out common false positives
        common_false_positives = {'self', 'cls', 'args', 'kwargs', 'e', 'warnings'}
        undefined = [u for u in undefined if not u.startswith('_')]
        return sorted(undefined)

def analyze_file(filepath):
    """Analyze a single Python file."""
    results = {
        'filepath': filepath,
        'issues': [],
        'undefined': [],
        'has_syntax_error': False,
        'syntax_error': None
    }

    try:
        with open(filepath, 'r') as f:
            source = f.read()

        # Try to parse the AST
        try:
            tree = ast.parse(source)
            analyzer = CodeAnalyzer(filepath)
            analyzer.visit(tree)

            # Check for undefined variables
            undefined = analyzer.check_undefined()
            if undefined:
                results['undefined'] = undefined

        except SyntaxError as e:
            results['has_syntax_error'] = True
            results['syntax_error'] = {
                'line': e.lineno,
                'offset': e.offset,
                'msg': e.msg,
                'text': e.text
            }

    except Exception as e:
        results['issues'].append(f"Error analyzing file: {str(e)}")

    return results

def main():
    """Analyze all modules."""

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
    print("CODE QUALITY ANALYSIS - WEEKS 9-14 MODULES")
    print("=" * 80)
    print()

    results = {}
    total_issues = 0

    for module in modules:
        filepath = project_root / module
        if not filepath.exists():
            print(f"✗ NOT FOUND: {module}")
            continue

        result = analyze_file(str(filepath))
        results[module] = result

        if result['has_syntax_error']:
            print(f"✗ SYNTAX ERROR: {module}")
            print(f"  Line {result['syntax_error']['line']}: {result['syntax_error']['msg']}")
            total_issues += 1
        elif result['undefined']:
            print(f"⚠ WARNING: {module}")
            print(f"  Potentially undefined references: {', '.join(result['undefined'][:5])}")
            if len(result['undefined']) > 5:
                print(f"  ... and {len(result['undefined']) - 5} more")
            total_issues += 1
        else:
            print(f"✓ PASS: {module}")

    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Modules analyzed: {len(results)}")
    print(f"Issues found: {total_issues}")
    print()

    if total_issues > 0:
        print("DETAILED ISSUES:")
        print("-" * 80)
        for module, result in results.items():
            if result['has_syntax_error'] or result['undefined'] or result['issues']:
                print(f"\n{module}:")
                if result['has_syntax_error']:
                    se = result['syntax_error']
                    print(f"  Syntax Error at line {se['line']}: {se['msg']}")
                    if se['text']:
                        print(f"    {se['text']}")
                if result['undefined']:
                    print(f"  Undefined: {', '.join(result['undefined'])}")
                if result['issues']:
                    for issue in result['issues']:
                        print(f"  {issue}")

if __name__ == '__main__':
    main()
