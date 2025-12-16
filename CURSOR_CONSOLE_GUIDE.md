# Cursor Console/Terminal Guide

## 📺 How to open the terminal/console

### Method 1: Keyboard shortcuts (fastest) ⚡

- **Windows/Linux**: `Ctrl + ` ` (backtick, above Tab)
- **Mac**: `Ctrl + ` `or`Cmd + J`
- Quickly toggle the terminal panel show/hide

### Method 2: Via menu 📋

1. Click the top menu bar
2. Select `Terminal` → `New Terminal`
3. Or select `View` → `Terminal`

### Method 3: Command palette 🎯

1. Press `Ctrl + Shift + P` (Mac: `Cmd + Shift + P`)
2. Type "Terminal"
3. Select `Terminal: Create New Terminal`

### Method 4: Bottom panel button 🔘

- Click the `Terminal` icon in Cursor's bottom status bar
- Or click the small icon next to tabs like `Problems` and `Output`

## 🔍 Viewing different types of output

### 1. Python script output

```bash
# Run in the terminal
python scripts/python/buy_solana_up_down.py

# Or use python3
python3 scripts/python/buy_solana_up_down.py
```

### 2. Log file output

```bash
# View live logs (if the script is running)
tail -f admin/logs/batch_trade_*.log

# View latest logs
ls -lt admin/logs/ | head -5
cat admin/logs/batch_trade_<latest_filename>.log
```

### 3. Service output (Admin backend)

- Admin backend runs at `http://localhost:8888`
- Logs are printed to the terminal; you can see:
  - startup info
  - API request logs
  - error messages

### 4. Debug output (Debug Console)

- Press `F5` to start debugging
- Output will appear in the "Debug Console" panel

## 📊 Terminal panel layout

After opening the terminal, you will see something like:

```
┌─────────────────────────────────────┐
│  Terminal                            │
│  ─────────────────────────────────  │
│  $ pwd                               │
│  /home/ericl/source_code/...        │
│                                      │
│  $ python script.py                  │
│  [script output]                     │
│                                      │
│  ┌────────────────────────────────┐ │
│  │ >                               │ │ ← command input area
│  └────────────────────────────────┘ │
└─────────────────────────────────────┘
```

## 🎯 Tips

### Tip 1: Split terminal

- Click the `+` button in the top-right of the terminal
- Or press `Ctrl + Shift + ` ` to create a new terminal
- You can run multiple commands simultaneously

### Tip 2: Clear terminal

- Run the `clear` command
- Or press `Ctrl + L`

### Tip 3: Search output

- Press `Ctrl + F` in the terminal
- Search through previous output

### Tip 4: Scroll history

- Use the mouse wheel
- Or the terminal scroll bar

### Tip 5: Copy terminal content

- Select text to copy
- Or right-click and choose "Copy"

## 📝 Viewing project logs

### Admin backend logs

```bash
# List all log files
ls -la admin/logs/

# Tail latest logs
tail -f admin/logs/batch_trade_*.log
```

### Monitor logs

```bash
# View monitor log
cat scripts/python/monitor.log

# Tail live (if monitor is running)
tail -f scripts/python/monitor.log
```

## 🔧 Running test scripts

### Test Solana market search

```bash
# Go to project directory
cd /home/ericl/source_code/workspace_python/polymarket_agents

# Run test scripts (activate venv first)
source venv/bin/activate  # Linux/Mac
# Or
.\venv\Scripts\activate   # Windows

# Run script
python scripts/python/buy_solana_up_down.py
```

### Start Admin backend

```bash
cd admin
./start.sh

# Or
python start.py
```

## ⚠️ FAQ

### Q: The terminal shows no output?

- Check whether the script is actually running
- Check whether the script has `print()` statements
- Try adding `flush=True` to `print()`

### Q: How do I view previous output?

- Scroll up using the terminal scroll bar
- The terminal keeps output history

### Q: Too much output—how do I filter?

```bash
# Filter with grep
python script.py | grep "error"
python script.py | grep -i "success"
```

### Q: How do I save output to a file?

```bash
# Save all output
python script.py > output.txt 2>&1

# Show and save at the same time
python script.py | tee output.txt
```

## 🎨 Terminal styling

### Colored output

```python
# Use colors in Python scripts
print("\033[92m✅ Success\033[0m")  # green
print("\033[91m❌ Failure\033[0m")  # red
print("\033[93m⚠️  Warning\033[0m")  # yellow
```

## 📚 Related shortcuts

- `Ctrl + ``: Toggle terminal show/hide
- `Ctrl + Shift + ``: Create new terminal
- `Ctrl + L`: Clear terminal
- `Ctrl + F`: Search terminal output
- `Ctrl + C`: Interrupt current command
- `Ctrl + D`: Close current terminal

## 💡 Recommended settings

1. **Persist terminal history**: enable in settings
2. **Increase terminal font size**: Settings → Terminal → Font Size
3. **Enable auto-scroll**: enabled by default

---

Hope this guide helps you use Cursor's terminal features more effectively!
