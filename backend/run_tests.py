"""
Run tests for Intelli-Job Backend

Usage:
    python run_tests.py                    # Run all tests
    python run_tests.py --unit             # Run unit tests only
    python run_tests.py --integration      # Run integration tests only
    python run_tests.py --cov              # Run with coverage report
    python run_tests.py test_auth          # Run specific test file
"""
import sys
import subprocess


def run_tests(args=None):
    """Run pytest with specified arguments"""
    
    # Base pytest command
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-v",  # Verbose output
        "--tb=short",  # Short traceback format
    ]
    
    # Add custom arguments
    if args:
        cmd.extend(args)
    
    print(f"Running: {' '.join(cmd)}")
    print("=" * 80)
    
    # Run pytest
    result = subprocess.run(cmd)
    
    return result.returncode


if __name__ == "__main__":
    # Parse command line arguments
    test_args = sys.argv[1:]
    
    # Default arguments if none provided
    if not test_args:
        test_args = [
            "tests/",
            "--cov=app",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov",
        ]
    
    exit_code = run_tests(test_args)
    sys.exit(exit_code)
