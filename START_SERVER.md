# Starting the MuseumHub Server

## Quick Start

Run the server with:
```bash
python3 app.py
```

## Server URLs

Once the server starts, you'll see these URLs:

- **Main Website**: http://127.0.0.1:5001
- **Admin Portal**: http://127.0.0.1:5001/admin
- **Chat API**: http://127.0.0.1:5001/api/chat
- **Instagram Webhook**: http://127.0.0.1:5001/api/instagram/webhook
- **Voice API**: http://127.0.0.1:5001/api/voice

## Expected Output

When you run `python3 app.py`, you should see:

```
======================================================================
🚀 MuseumHub Multi-Channel Communication System
======================================================================
📡 Main Server:     http://127.0.0.1:5001
🌐 Admin Portal:    http://127.0.0.1:5001/admin
💬 Chat API:        http://127.0.0.1:5001/api/chat
📱 Instagram Webhook: http://127.0.0.1:5001/api/instagram/webhook
🎤 Voice API:       http://127.0.0.1:5001/api/voice
======================================================================
💡 Press CTRL+C to stop the server
======================================================================

✅ Starting Flask-SocketIO server...

 * Restarting with stat
 * Debugger is active!
 * Debugger PIN: XXX-XXX-XXX
 * Running on http://127.0.0.1:5001
```

## Troubleshooting

### If server URL doesn't show:
1. Check if port 5001 is already in use
2. Make sure all dependencies are installed: `pip3 install -r requirements.txt`
3. Check for any import errors

### About the gevent error:
The gevent threading error when stopping the server (CTRL+C) is harmless - it's just a cleanup issue and doesn't affect functionality.

### If server won't start:
1. Check database connection settings in `.env`
2. Run migrations: `flask db upgrade`
3. Check Python version (requires 3.8+)

## Stopping the Server

Press `CTRL+C` to stop the server gracefully.

