# Email Monitor Service

Real-time Outlook email monitoring and classification service. Monitors your inbox for incoming emails, classifies them as service-related or non-service using your Ollama LLM, and displays notifications on a live dashboard.

## Features

- **Live Email Monitoring**: Checks Outlook inbox every 5 minutes for new emails
- **AI Classification**: Uses Ollama (llama3.1:8b) to classify emails as service-related or not
- **Zero Database**: No persistent storage—just real-time notifications
- **Real-time Dashboard**: Beautiful UI at `/emails` showing notifications with auto-refresh
- **HTTP API**: Simple REST endpoints for integration

## Configuration

Set these environment variables in `.env`:

```env
# Outlook credentials (IMAP)
OUTLOOK_EMAIL=fjodor.smorodins@student.nhlstenden.com
OUTLOOK_PASSWORD=your_app_password_here

# Ollama LLM endpoint and model
OLLAMA_URL=http://ollama:11434
OLLAMA_MODEL=llama3.1:8b
```

### Important: Outlook App Password

For Microsoft/Outlook accounts, use an **App Password** instead of your main password:

1. Go to [https://myaccount.microsoft.com/security](https://myaccount.microsoft.com/security)
2. Enable 2-factor authentication if not already enabled
3. Create an App Password for "Mail"
4. Use this password in `.env`

## API Endpoints

### `GET /health`
Health check endpoint.

```bash
curl http://localhost:5003/health
```

### `GET /notifications`
Get all current notifications (in-memory queue, last 20).

```bash
curl http://localhost:5003/notifications
```

Response:
```json
{
  "notifications": [
    {
      "type": "service",
      "sender": "customer@example.com",
      "subject": "Machine breakdown urgent!",
      "body_preview": "Our production line stopped...",
      "reason": "Email mentions machine problems",
      "timestamp": "2024-05-08T14:32:15.123456"
    },
    {
      "type": "non_service",
      "sender": "newsletter@company.com",
      "subject": "Monthly Newsletter - May 2024",
      "body_preview": "Check out this month's highlights...",
      "reason": "Regular newsletter, not urgent",
      "timestamp": "2024-05-08T14:31:42.654321"
    }
  ]
}
```

### `POST /notifications/clear`
Clear all notifications from the queue.

```bash
curl -X POST http://localhost:5003/notifications/clear
```

## How It Works

1. **Email Fetching**: Connects to Outlook via IMAP, checks for unseen emails from the last 2 hours
2. **Deduplication**: Prevents processing the same email multiple times
3. **Classification**: Sends each email subject + body to Ollama for classification as service-related
4. **Notification Queue**: Stores last 20 notifications in memory
5. **Dashboard**: Real-time HTML dashboard at `/emails` displays notifications with auto-refresh

## Dashboard

Access the real-time dashboard at:
```
http://localhost:5000/emails
```

Features:
- Live notification feed with service alerts highlighted in red
- Auto-refresh every 5 seconds (toggle on/off)
- Manual refresh button
- Clear all notifications button
- Statistics: total, service-related, and regular emails

## Service Classification

The LLM is asked to determine if an email is **service-related**:

**Examples of SERVICE-RELATED:**
- Machine breakdown
- Equipment repair needed
- Technical issue
- System error
- Maintenance problem

**Examples of NON-SERVICE:**
- Newsletters
- Marketing
- Thank you emails
- Appointment confirmations
- General inquiries

## Docker Compose Integration

The service is automatically included in `docker-compose.yml`:

```yaml
email-monitor:
  build:
    context: ./email-monitor
    dockerfile: Dockerfile
  container_name: support-email-monitor
  environment:
    OUTLOOK_EMAIL: ${OUTLOOK_EMAIL}
    OUTLOOK_PASSWORD: ${OUTLOOK_PASSWORD}
    OLLAMA_URL: http://ollama:11434
    OLLAMA_MODEL: ${OLLAMA_MODEL}
  ports:
    - "5003:5003"
  depends_on:
    ollama:
      condition: service_healthy
```

Start with the stack:
```bash
docker compose up email-monitor
```

## Voice App Integration

The main voice-app provides these endpoints:

- `GET /emails` - Displays the email notifications dashboard
- `GET /email-notifications` - Proxy to email-monitor's `/notifications` endpoint

This allows the voice app to display email notifications alongside call transcription forms.

## Performance & Resource Usage

- **Memory**: ~50-100MB (in-memory queue of 20 notifications)
- **CPU**: Minimal when idle, spikes during LLM classification (shared with Ollama)
- **Network**: IMAP polling every 5 minutes, Ollama API calls on new emails

## Troubleshooting

### No emails being detected
1. Check Outlook credentials in `.env`
2. Verify IMAP is enabled in your Outlook account settings
3. Check firewall allows IMAP port 993
4. View logs: `docker compose logs email-monitor`

### Classification not working
1. Verify Ollama is running: `http://ollama:11434/api/tags`
2. Check Ollama model is loaded: `docker compose exec ollama ollama list`
3. Check logs: `docker compose logs email-monitor`

### Dashboard not updating
1. Verify email-monitor container is healthy: `docker compose ps`
2. Check browser console for JS errors
3. Manually trigger refresh with the "Refresh Now" button
4. Try `curl http://localhost:5003/notifications`

## Future Enhancements

- Database persistence option
- Webhook notifications to external services
- Custom classification rules
- Email forwarding on service alerts
- Multi-mailbox monitoring
