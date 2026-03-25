#!/usr/bin/env python3
"""
Setup script for O2C Graph Query System
Handles environment setup, dependency installation, and validation
"""

import os
import sys
import subprocess
import platform
from pathlib import Path

def print_header(text):
    """Print formatted header."""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")

def print_success(text):
    """Print success message."""
    print(f"✓ {text}")

def print_error(text):
    """Print error message."""
    print(f"✗ {text}")

def print_info(text):
    """Print info message."""
    print(f"ℹ {text}")

def check_python_version():
    """Check Python version."""
    print_header("Python Version Check")
    
    version = sys.version_info
    if version.major >= 3 and version.minor >= 10:
        print_success(f"Python {version.major}.{version.minor}.{version.micro} is compatible")
        return True
    else:
        print_error(f"Python {version.major}.{version.minor} detected. Requires 3.10+")
        return False

def check_groq_api_key():
    """Check if Groq API key is set."""
    print_header("Groq API Key Check")
    
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    
    if api_key:
        print_success(f"GROQ_API_KEY is set ({api_key[:10]}...)")
        return True
    else:
        print_error("GROQ_API_KEY is not set")
        print_info("Get a free key at: https://console.groq.com")
        print_info("Then set: export GROQ_API_KEY='your-key'")
        return False

def check_data_path():
    """Check if data path exists."""
    print_header("Data Path Check")
    
    data_path = os.getenv("DATA_PATH", "./sap-o2c-data")
    data_path_obj = Path(data_path)
    
    if data_path_obj.exists():
        jsonl_count = len(list(data_path_obj.glob("*/*.jsonl")))
        print_success(f"Data path found: {data_path}")
        print_success(f"Found {jsonl_count} JSONL files")
        return True
    else:
        print_error(f"Data path not found: {data_path}")
        print_info("Please download data from: https://drive.google.com/file/d/1UqaLbFaveV-3MEuiUrzKydhKmkeC1iAL/view?usp=sharing")
        return False

def create_venv():
    """Create virtual environment if it doesn't exist."""
    print_header("Virtual Environment Setup")
    
    venv_path = "venv"
    
    if Path(venv_path).exists():
        print_success(f"Virtual environment exists at {venv_path}")
        return True
    
    print_info("Creating virtual environment...")
    try:
        subprocess.run([sys.executable, "-m", "venv", venv_path], check=True)
        print_success("Virtual environment created")
        
        # Print activation command
        if platform.system() == "Windows":
            activate_cmd = f"{venv_path}\\Scripts\\activate"
        else:
            activate_cmd = f"source {venv_path}/bin/activate"
        
        print_info(f"Activate with: {activate_cmd}")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to create virtual environment: {e}")
        return False

def install_dependencies():
    """Install Python dependencies."""
    print_header("Dependencies Installation")
    
    try:
        print_info("Installing packages from requirements.txt...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
        print_success("All dependencies installed")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to install dependencies: {e}")
        return False

def test_imports():
    """Test if key packages can be imported."""
    print_header("Import Test")
    
    packages = [
        ("fastapi", "FastAPI"),
        ("pandas", "Pandas"),
        ("networkx", "NetworkX"),
        ("groq", "Groq"),
    ]
    
    all_ok = True
    for package, name in packages:
        try:
            __import__(package)
            print_success(f"{name} import successful")
        except ImportError:
            print_error(f"{name} import failed")
            all_ok = False
    
    return all_ok

def create_env_file():
    """Create .env file template."""
    print_header("Environment File Setup")
    
    env_content = """# Order-to-Cash Graph System Configuration

# Required: Groq API Key (get free key from https://console.groq.com)
GROQ_API_KEY=your-api-key-here

# Optional: Data path (defaults to ./sap-o2c-data)
DATA_PATH=./sap-o2c-data

# Optional: Server settings
PORT=8000
HOST=0.0.0.0
LOG_LEVEL=INFO
"""
    
    env_path = ".env"
    
    if Path(env_path).exists():
        print_info(f"{env_path} already exists, skipping")
    else:
        try:
            with open(env_path, "w") as f:
                f.write(env_content)
            print_success(f"Created {env_path} template")
            print_info(f"Edit {env_path} and set your GROQ_API_KEY")
        except IOError as e:
            print_error(f"Failed to create {env_path}: {e}")

def print_next_steps():
    """Print next steps."""
    print_header("Next Steps")
    
    print_info("1. Ensure GROQ_API_KEY is set in environment:")
    print("   export GROQ_API_KEY='your-key-from-console.groq.com'\n")
    
    print_info("2. Run the application:")
    print("   python main.py\n")
    
    print_info("3. Open browser:")
    print("   http://localhost:8000\n")
    
    print_info("4. Start asking questions about orders, deliveries, and billing!\n")

def main():
    """Main setup flow."""
    print("\n" + "="*60)
    print("  Order-to-Cash Graph Query System - Setup")
    print("="*60)
    
    checks = [
        ("Python Version", check_python_version),
        ("Virtual Environment", create_venv),
        ("Dependencies", install_dependencies),
        ("Import Test", test_imports),
        ("Groq API Key", check_groq_api_key),
        ("Data Path", check_data_path),
    ]
    
    results = []
    for check_name, check_func in checks:
        try:
            result = check_func()
            results.append((check_name, result))
        except Exception as e:
            print_error(f"Error in {check_name}: {e}")
            results.append((check_name, False))
    
    # Summary
    print_header("Setup Summary")
    
    for check_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{check_name:.<40} {status}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        print("\n" + "="*60)
        print("  ✓ All checks passed!")
        print("="*60)
        
        create_env_file()
        print_next_steps()
        return 0
    else:
        print("\n" + "="*60)
        print("  ✗ Some checks failed. Please fix the issues above.")
        print("="*60)
        return 1

if __name__ == "__main__":
    sys.exit(main())
