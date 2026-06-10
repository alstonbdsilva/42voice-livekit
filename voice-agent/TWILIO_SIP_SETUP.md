# Twilio SIP Integration Setup

This guide explains how to integrate Twilio SIP trunking with the voice agent backend for phone call support.

## Architecture

```
Phone Call → Twilio → SIP Trunk → LiveKit SIP → LiveKit Room → Voice Agent Backend
                                                            ↓
                                                    AI Auto-Answer Pipeline
                                                    (STT → LLM → TTS)
                                                            ↓
                                                    LiveKit Room → SIP → Twilio → Phone
```

## Prerequisites

- Twilio account with SIP trunking enabled
- LiveKit server with SIP connector running
- Voice agent backend configured and running
- Public IP address or domain for SIP traffic

## Step 1: Configure Twilio SIP Trunk

### 1.1 Create SIP Trunk in Twilio Console

1. Go to Twilio Console → SIP Trunking
2. Click "Create New SIP Trunk"
3. Configure the following:

**SIP Trunk Settings:**
- **Friendly Name**: Voice Agent SIP Trunk
- **SIP URI**: `sip.your-domain.com` (your domain)
- **SIP Registration**: Enabled (if using registration)
- **Credential List**: Create a new credential list

**Credential List:**
- **Username**: Your SIP username
- **Password**: Your SIP password (generate a strong one)
- **Realm**: Your SIP domain

### 1.2 Configure SIP Trunking

**Termination Settings:**
- **SIP URI**: `sip:livekit-sip@your-server-ip:5060`
- **Domain**: Your LiveKit SIP server domain
- **IP Address**: Your LiveKit SIP server public IP

**Origination Settings:**
- **SIP URI**: `sip:+1234567890@your-twilio-sip-domain`
- **From**: Your Twilio phone number

## Step 2: Configure LiveKit SIP

### 2.1 Update sip.yaml

Edit `voice-agent/sip.yaml`:

```yaml
sip_port: 5060
sip_address: 0.0.0.0

# NAT configuration
nat_external_ip: "your-public-ip"  # Your public IP address

# Twilio SIP Trunking Configuration
sip_trunk:
  enabled: true
  username: "your-twilio-sip-username"
  password: "your-twilio-sip-password"

# LiveKit connection
livekit:
  url: ws://3.102.122.36:7880
  api_key: devkey
  api_secret: secret

# Room configuration
room:
  prefix: "sip-"
  create_if_not_exists: true
  empty_timeout: 300

# Audio configuration
audio:
  sample_rate: 8000  # 8kHz for telephony
  channels: 1
  frame_duration: 20
```

### 2.2 Start LiveKit SIP Connector

If using the remote LiveKit server, ensure the SIP connector is configured and running. Otherwise, run locally:

```bash
livekit-sip --config sip.yaml
```

## Step 3: Configure Environment Variables

Add Twilio credentials to your `.env` file:

```bash
# Twilio SIP Configuration
TWILIO_SIP_USERNAME=your_twilio_sip_username
TWILIO_SIP_PASSWORD=your_twilio_sip_password
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=+1234567890
```

## Step 4: Test the Integration

### 4.1 Test SIP Registration

Verify SIP registration:

```bash
# Check if SIP is listening
netstat -an | grep 5060
```

### 4.2 Test Phone Call

1. Call your Twilio phone number
2. The call should route through SIP trunk to LiveKit
3. LiveKit creates a room (e.g., `sip-call-12345`)
4. Voice agent backend joins the room
5. AI auto-answers and begins conversation

### 4.3 Monitor Logs

Check backend logs for:

```
INFO: Audio track subscribed for participant: sip-user
INFO: STT transcript: Hello
INFO: LLM response: Hi! How can I help you today?
INFO: TTS audio generated: 12345 bytes
INFO: Audio sent back to room: sip-call-12345
```

## Step 5: Configure Voice Agent for Phone Calls

### 5.1 Auto-Join SIP Rooms

Update the backend to automatically join SIP rooms when calls come in. Add this to `main.py`:

```python
@app.post("/sip/incoming")
async def handle_sip_call(request: dict):
    """Handle incoming SIP call from Twilio."""
    room_name = request.get("room_name", f"sip-call-{uuid.uuid4()}")
    
    # Create session
    session_id = str(uuid.uuid4())
    session_manager.create_session(session_id=session_id)
    
    # Connect to LiveKit room
    await livekit_service.create_session(
        room_name=room_name,
        participant_name="voice-agent"
    )
    
    # Setup audio pipeline
    await livekit_service.setup_audio_handler(room_name, session_id)
    
    return {"room_name": room_name, "session_id": session_id}
```

### 5.2 Configure Twilio Webhook

Set up a Twilio webhook to notify your backend of incoming calls:

1. In Twilio Console → Phone Numbers → Your Number
2. Configure "Voice & Fax" → "A call comes in"
3. Set webhook URL: `https://your-domain.com/sip/incoming`
4. Method: POST

## Troubleshooting

### SIP Registration Fails

- Check firewall allows UDP/TCP on port 5060
- Verify public IP is correct in `sip.yaml`
- Ensure Twilio credentials are correct
- Check DNS resolution for SIP domain

### No Audio in Call

- Verify audio sample rate is 8000Hz (telephony standard)
- Check codec compatibility (G.711, G.722)
- Ensure NAT traversal is configured
- Verify LiveKit SIP connector is running

### AI Not Responding

- Check backend logs for errors
- Verify session creation
- Ensure audio pipeline is active
- Check LiveKit room connectivity

## Security Considerations

1. **Firewall Configuration**: Only allow SIP traffic from Twilio IPs
2. **Authentication**: Use strong SIP passwords
3. **Encryption**: Enable TLS for SIP (SIPS) if supported
4. **Rate Limiting**: Implement rate limiting on webhook endpoints
5. **Validation**: Validate incoming SIP requests

## Advanced Configuration

### Custom SIP Headers

Add custom SIP headers in `sip.yaml`:

```yaml
sip_headers:
  X-Custom-Header: value
```

### Codec Selection

Configure preferred codecs:

```yaml
audio:
  codecs:
    - PCMU
    - PCMA
    - G722
```

### Call Recording

Enable call recording:

```yaml
recording:
  enabled: true
  format: wav
  directory: /recordings
```

## Production Deployment

### AWS Deployment

1. Deploy backend to EC2 or ECS
2. Use Elastic IP for SIP server
3. Configure Security Groups for SIP ports (5060/5061)
4. Use ALB for HTTP traffic
5. Set up CloudWatch monitoring

### Load Balancing

For high availability:
- Deploy multiple SIP servers
- Use DNS round-robin
- Configure Twilio with multiple SIP URIs
- Implement health checks

## Monitoring

### Key Metrics to Monitor

- SIP registration status
- Call success rate
- Audio latency
- Room creation rate
- AI response time

### Logging

Enable detailed SIP logging:

```yaml
log_level: debug
```

## Cost Considerations

- Twilio SIP trunking costs per minute
- LiveKit server costs
- Backend infrastructure costs
- AI API costs (Groq, Sarvam)

## Next Steps

1. Test with a Twilio trial account
2. Implement call recording
3. Add call analytics
4. Set up monitoring and alerts
5. Configure failover mechanisms
