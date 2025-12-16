# Polymarket Trading Admin Guide

## Features

1. ✅ **Localhost only** - For safety, accessible only from the local machine
2. ✅ **Username/password auth** - Configured via environment variables
3. ✅ **Auto order placement** - Choose number of orders and amount per order
4. ✅ **Live log viewer** - Stream monitor logs in real time
5. ✅ **Trading history** - View status and logs for all trade tasks

## Quick start

### 1. Configure credentials (optional)

Default username and password:

- Username: `admin`
- Password: `admin123`

**Strongly recommended:** change the default password. You can set it via environment variables:

```bash
export ADMIN_USERNAME="your_username"
export ADMIN_PASSWORD="your_strong_password"
```

Or add it to the `.env` file:

```bash
ADMIN_USERNAME=your_username
ADMIN_PASSWORD=your_strong_password
```

### 2. Start the service

```bash
# Option 1: use the start script (recommended; auto-kills processes occupying the port)
bash admin/start.sh

# Option 2: start via Python script
python admin/start.py

# Option 3: run the API directly
python admin/api.py

# Option 4: use uvicorn
cd admin
uvicorn api:app --host 127.0.0.1 --port 8888
```

**Recommended:** Option 1. `bash admin/start.sh` will automatically check and kill processes occupying port 8888 to ensure a clean start.

### 3. Open the admin UI

Open in your browser: http://127.0.0.1:8888

On first visit you will be prompted for username and password.

## Usage

### Auto buy

1. Enter number of orders (1-50)
2. Enter amount per order (USDC, 0.01-1000)
3. Choose whether to run in dry-run mode (no real trades will be executed)
4. Click the "Execute Trade" button

The system will automatically:

- Find short-term markets (ending within 48 hours)
- Use AI to select the best markets
- Analyze markets and decide trade direction
- Execute batch trades

### View monitor logs

1. Click "Start Monitor" to stream monitor logs
2. Logs will scroll in real time
3. Click "Stop Monitor" to stop
4. Click "Clear" to clear current logs

### View trading logs

1. In the "Trading History" section, view all trade tasks
2. Click a task card to view detailed logs
3. Logs update in real time until the task finishes

## Security

1. **Localhost only** - Server listens only on 127.0.0.1 and is not accessible externally
2. **Password auth** - Uses HTTP Basic auth and a session token
3. **Token expiry** - Session token is valid for 24 hours
4. **Password hygiene** - Use a strong password and avoid defaults

## Notes

1. Ensure `.env` is configured correctly and contains required API keys
2. Ensure the wallet has sufficient USDC balance
3. For first use, start with dry-run mode
4. Monitor logs come from `logs/monitor.log`
5. Trade logs are stored in `logs/batch_trade_*.log`

## API

### Auth

- `POST /api/auth/login` - login and get a token

### Trading

- `POST /api/trade/execute` - execute batch trade
- `GET /api/trade/list` - list trade tasks
- `GET /api/trade/status/{task_id}` - get trade task status

### Logs

- `GET /api/logs/monitor` - stream monitor logs (SSE)
- `GET /api/logs/trade/{task_id}` - stream trade logs (SSE)
- `GET /api/logs/monitor/history` - get monitor log history

## Troubleshooting

### Can't access the admin UI

- Check whether the service is running
- Confirm the URL is http://127.0.0.1:8888
- Check firewall settings

### Authentication failure

- Confirm username/password are correct
- Check that environment variables are set correctly
- Clear browser cache and localStorage, then log in again

### Trade execution failure

- Check wallet balance
- Inspect trade logs for detailed errors
- Confirm API keys are configured correctly

## Tech stack

- **Backend**: FastAPI
- **Frontend**: plain HTML/CSS/JavaScript
- **Real-time**: Server-Sent Events (SSE)
- **Auth**: HTTP Basic Auth + Session Token
