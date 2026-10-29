# Email Sender Troubleshooting Guide

## Connection Refused Error (ECONNREFUSED)

If you're seeing an error like `[vite] http proxy error: /api/send-email AggregateError [ECONNREFUSED]` or a 500 Internal Server Error, follow these steps:

### 1. Ensure the Backend Server is Running

The application consists of two parts:
- Frontend (Vite React app)
- Backend (Express server)

Both need to be running simultaneously. The easiest way to do this is:

```bash
# Run both frontend and backend
npm run start
```

If you need to run them separately:

```bash
# Terminal 1 - Run the backend only
npm run start-backend

# Terminal 2 - Run the frontend only
npm run dev
```

### 2. Check for Port Conflicts

The server runs on port 3001 by default. Make sure nothing else is using this port:

#### On Windows:
```
netstat -ano | findstr :3001
```
If you see something using port 3001, you'll need to stop that process or change the port in `server.js`.

### 3. Test the Backend Directly

You can test if the backend is running correctly with:

```bash
node test-endpoint.js
```

This should connect to the server and return a success message.

You can also try accessing the health check endpoint in your browser:
http://localhost:3001/api/status

### 4. Check Server Logs

If the server is starting but encounters errors, check the console where you started the server for error messages.

### 5. Environment Variables

Make sure your `.env` file exists with a valid SendGrid API key:

```
SENDGRID_API_KEY=SG.your_api_key_here
```

### 6. Firewall / Antivirus Issues

Temporarily disable any firewall or antivirus software that might be blocking connections.

### 7. Restart Your Development Environment

Sometimes a simple restart is all that's needed:
1. Close all terminals and stop all running processes
2. Close your code editor/IDE
3. Restart and try again

## If All Else Fails

Try the following advanced steps:

1. Clear node_modules and reinstall
```bash
rm -rf node_modules
npm install
```

2. Check for global port conflicts
```bash
# On Windows
netstat -ano | findstr :3001
```

3. Use a different port by changing the port in server.js and vite.config.js 