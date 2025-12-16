# Quick Start Guide

## 🔧 Fix Python module import issues

If you encounter `ModuleNotFoundError: No module named 'agents'`, follow these steps:

### Method 1: Run from the project root (recommended) ✅

```bash
# Make sure you are in the project root
cd /home/ericl/source_code/workspace_python/polymarket_agents

# Activate the virtual environment (if used)
source .venv/bin/activate  # Linux/Mac
# Or
.venv\Scripts\activate     # Windows

# Run the script
python scripts/python/buy_solana_up_down.py
```

### Method 2: Set the PYTHONPATH environment variable

```bash
# Linux/Mac
export PYTHONPATH=/home/ericl/source_code/workspace_python/polymarket_agents:$PYTHONPATH
python scripts/python/buy_solana_up_down.py

# Windows (PowerShell)
$env:PYTHONPATH="C:\path\to\polymarket_agents;$env:PYTHONPATH"
python scripts/python/buy_solana_up_down.py
```

### Method 3: Run with the -m option (recommended) ✅

```bash
# Run from the project root
cd /home/ericl/source_code/workspace_python/polymarket_agents
python -m scripts.python.buy_solana_up_down
```

## ✅ Fixed

I fixed the `buy_solana_up_down.py` script by adding automatic path setup code. The script should now work normally.

## 🧪 Test run

Run the following command to test:

```bash
# From the project root
cd /home/ericl/source_code/workspace_python/polymarket_agents

# Activate the virtual environment (if used)
source .venv/bin/activate

# Run the script (dry run mode; it will not actually buy)
python scripts/python/buy_solana_up_down.py
```

## 📝 Notes

1. **Run from the project root**: The script needs to find the `agents` and `scripts` directories
2. **Activate the virtual environment**: Ensure all dependencies are installed
3. **Check the .env file**: Ensure required environment variables are configured

## 🔍 If you still have problems

Check the following:

1. **Is the virtual environment activated?**

   ```bash
   which python  # should show the virtual environment path
   ```

2. **Are dependencies installed?**

   ```bash
   pip list | grep -E "dotenv|httpx"  # check key dependencies
   ```

3. **Is the project structure correct?**
   ```bash
   ls -la agents/  # should show the agents directory
   ```
