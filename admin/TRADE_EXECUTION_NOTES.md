# Trading Execution Notes

## How to execute live trades

### Important notes

1. **Dry run mode**: If the "Dry Run (Simulation Mode)" checkbox is selected, the system will only simulate and **will not execute real trades**.

2. **Live trading mode**: To execute real trades, you must **uncheck** the "Dry Run (Simulation Mode)" checkbox.

### Steps

1. **Open the Buy tab**: Click the "Buy" tab at the top of the page

2. **Fill in trading parameters**:

   - Number of Orders: 1-5 markets
   - Amount per Order: amount per order (max 1.0 USDC)

3. **Confirm execution mode**:

   - ✅ **Live trading**: do **not** check "Dry Run (Simulation Mode)"
   - 🔒 **Dry run**: check "Dry Run (Simulation Mode)"

4. **Click the "Execute Buy" button**

5. **Check the confirmation dialog**:

   - If it shows "⚠️ ⚠️ ⚠️ LIVE TRADING MODE - Real money will be used! ⚠️ ⚠️ ⚠️" (red background), it will execute real trades
   - If it shows "🔒 DRY RUN MODE - No real trades will be executed!" (yellow background), it is simulation only

6. **Confirm execution**: Click the "Confirm Execute" button

7. **View execution logs**:
   - Logs are shown in real time in the "Trading Logs" panel at the bottom of the page
   - Logs show detailed information for each step

### FAQ

**Q: Why did no real trade happen after clicking buy?**

A: Check the following:

1. Is the "Dry Run (Simulation Mode)" checkbox selected? If yes, it will only simulate
2. Check the mode shown in the confirmation dialog
3. Check the logs in the "Trading Logs" panel for errors
4. Check whether your wallet balance is sufficient

**Q: How can I confirm the trade executed successfully?**

A:

1. Check the "Trading Logs" panel; it will show execution results for each trade
2. Check the task status in "Trading History"
3. If successful, the position will be automatically added to the monitor list

**Q: What if an error happens during execution?**

A:

1. Check error messages in the "Trading Logs" panel
2. Check whether the task status is "Failed"
3. Common errors:
   - Insufficient balance
   - Market does not exist or is closed
   - Network connectivity issues

### Technical notes

- Trade execution is asynchronous and runs in a background thread
- Logs are streamed to the frontend in real time
- Even if execution fails, detailed error information will be shown in the logs
