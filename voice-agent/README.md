# Voice Agent Backend

A production-ready realtime multi-agent AI voice system using remote LiveKit, Sarvam AI, and Groq.

## Architecture

```
User Speech → Sarvam STT → Groq LLM → Sarvam TTS → LiveKit Audio Output
                        ↓
                  Orchestrator (Intent Detection)
                        ↓
        ┌───────────────┼───────────────┐
        ↓               ↓               ↓
   Booking Agent   Sales Agent   Support Agent
```

## Features

- **Multi-Agent Architecture**: Orchestrator dynamically routes queries to specialized agents
- **Realtime Voice Pipeline**: STT → LLM → TTS with LiveKit audio transport
- **Intent Detection**: Automatic classification of booking, sales, and support queries
- **Shared Session Context**: Redis-backed session management with conversation history
- **Agent Handoff**: Smooth transitions between agents with context preservation
- **FastAPI REST API**: Comprehensive endpoints for all functionality
- **WebSocket Support**: Realtime bidirectional communication
- **Remote LiveKit Integration**: Connects to deployed LiveKit server at wss://ws.42voice.com

## Tech Stack

- **Python 3.11**
- **FastAPI** - Web framework
- **LiveKit** - Realtime audio transport (remote server)
- **Sarvam AI** - STT and TTS
- **Groq** - LLM inference
- **Redis** - Session management

## Project Structure

```
voice-agent/
├── agents/
│   ├── booking_agent.py      # Booking-related conversations
│   ├── sales_agent.py        # Sales and product inquiries
│   └── support_agent.py      # Technical support and troubleshooting
├── services/
│   ├── sarvam_stt.py         # Speech-to-Text service
│   ├── sarvam_tts.py         # Text-to-Speech service
│   ├── groq_llm.py           # LLM inference service
│   └── livekit_service.py    # LiveKit audio transport
├── prompts/
│   ├── orchestrator.txt      # Orchestrator system prompt
│   ├── booking_agent.txt     # Booking agent prompt
│   ├── sales_agent.txt       # Sales agent prompt
│   ├── support_agent.txt     # Support agent prompt
│   └── intent_detection.txt  # Intent classification prompt
├── config.py                 # Configuration management
├── session_manager.py        # Session and context management
├── orchestrator.py           # Intent detection and agent routing
├── main.py                   # FastAPI application
├── requirements.txt          # Python dependencies
├── .env.example             # Environment variables template
└── README.md                # This file
```

## Setup

### Prerequisites

- Python 3.11+
- Redis server (local or remote)
- Sarvam AI API key
- Groq API key
- Remote LiveKit server access

### Installation

1. **Navigate to the project**:
   ```bash
   cd voice-agent
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

4. **Start Redis** (if using local Redis):
   ```bash
   redis-server
   ```

5. **Run the application**:
   ```bash
   python main.py
   ```

The backend will automatically connect to the remote LiveKit server at `wss://ws.42voice.com`.

## API Endpoints

### Health Check
- `GET /health` - Check service status and LiveKit connection

### Session Management
- `POST /sessions` - Create a new session
- `GET /sessions/{session_id}` - Get session data
- `DELETE /sessions/{session_id}` - Delete a session
- `GET /sessions/{session_id}/history` - Get conversation history

### Message Processing
- `POST /messages` - Process a text message through the agent system

### Speech Services
- `POST /stt/transcribe` - Transcribe audio to text
- `POST /tts/synthesize` - Convert text to speech

### LiveKit Integration
- `POST /livekit/connect` - Connect to a LiveKit room on remote server
- `POST /livekit/disconnect/{room_name}` - Disconnect from a room
- `GET /livekit/participants/{room_name}` - Get room participants

### Agent Management
- `POST /agents/handoff` - Request handoff to specific agent
- `POST /agents/return-to-orchestrator` - Return to orchestrator

### WebSocket
- `WS /ws/{session_id}` - Realtime bidirectional communication

## Usage Examples

### Create a Session
```bash
curl -X POST http://localhost:8000/sessions \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user123"}'
```

### Send a Message
```bash
curl -X POST http://localhost:8000/messages \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session-id-here",
    "message": "I want to book an appointment"
  }'
```

### Transcribe Audio
```bash
curl -X POST http://localhost:8000/stt/transcribe \
  -H "Content-Type: application/json" \
  -d '{
    "audio_data": "base64-encoded-audio",
    "language": "hi-IN"
  }'
```

### Synthesize Speech
```bash
curl -X POST http://localhost:8000/tts/synthesize \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello, how can I help you?",
    "language": "hi-IN"
  }'
```

### Connect to LiveKit Room
```bash
curl -X POST http://localhost:8000/livekit/connect \
  -H "Content-Type: application/json" \
  -d '{
    "room_name": "my-room",
    "participant_name": "agent-1"
  }'
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SARVAM_API_KEY` | Sarvam AI API key | Required |
| `GROQ_API_KEY` | Groq API key | Required |
| `LIVEKIT_URL` | LiveKit server URL | `wss://ws.42voice.com` |
| `LIVEKIT_API_KEY` | LiveKit API key | `devkey` |
| `LIVEKIT_API_SECRET` | LiveKit API secret | `secret` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379` |
| `HOST` | Server host | `0.0.0.0` |
| `PORT` | Server port | `8000` |
| `GROQ_MODEL` | Groq model name | `llama3-70b-8192` |
| `GROQ_TEMPERATURE` | LLM temperature | `0.7` |
| `SARVAM_STT_MODEL` | Sarvam STT model | `saarika:v1` |
| `SARVAM_TTS_MODEL` | Sarvam TTS model | `bulbul:v1` |

## Agent Descriptions

### Orchestrator
- Detects user intent from messages
- Routes conversations to appropriate specialized agents
- Handles general inquiries and greetings
- Manages agent handoffs

### Booking Agent
- Handles appointment bookings
- Manages booking modifications and cancellations
- Provides booking confirmations
- Collects necessary booking information

### Sales Agent
- Provides product information and recommendations
- Handles pricing inquiries
- Guides customers through purchase process
- Manages promotions and discounts

### Support Agent
- Troubleshoots technical issues
- Handles billing inquiries
- Manages account-related questions
- Escalates complex issues when needed

## Development

### Adding New Agents

1. Create a new agent file in `agents/`
2. Implement the agent class with `process_message` method
3. Add the agent to the orchestrator's intent mapping
4. Create a system prompt in `prompts/`
5. Update the orchestrator to initialize the new agent

### Modifying Prompts

Edit the prompt files in the `prompts/` directory. Changes will be reflected on the next restart.

### Testing

```bash
# Run tests (when implemented)
pytest

# Run with coverage
pytest --cov=.
```

## Remote LiveKit Configuration

The backend is configured to connect to a remote LiveKit server:
- **URL**: `wss://ws.42voice.com`
- **API Key**: `devkey`
- **API Secret**: `secret`

To change the LiveKit server, update the `LIVEKIT_URL` environment variable in your `.env` file.

## Troubleshooting

### Redis Connection Failed
- Ensure Redis is running: `redis-cli ping`
- Check REDIS_URL in .env

### LiveKit Connection Failed
- Verify remote LiveKit server is accessible
- Check LIVEKIT_URL and credentials in .env
- Ensure network connectivity to ws.42voice.com

### API Key Errors
- Verify SARVAM_API_KEY and GROQ_API_KEY are set correctly
- Check API key validity and permissions

### Port Already in Use
- Change PORT in .env if 8000 is occupied
- Or stop the process using port 8000

## Twilio SIP Integration

The backend supports phone call integration through Twilio SIP trunking.

### Architecture

```
Phone Call → Twilio → SIP Trunk → LiveKit SIP → LiveKit Room → Voice Agent Backend
                                                            ↓
                                                    AI Auto-Answer Pipeline
                                                    (STT → LLM → TTS)
                                                            ↓
                                                    LiveKit Room → SIP → Twilio → Phone
```

### Setup

1. **Configure Twilio SIP Trunk**:
   - Create SIP trunk in Twilio Console
   - Set SIP URI to your LiveKit SIP server
   - Configure termination and origination settings

2. **Configure LiveKit SIP**:
   - Update `sip.yaml` with your Twilio credentials
   - Set NAT configuration with your public IP
   - Start LiveKit SIP connector

3. **Configure Environment Variables**:
   ```bash
   TWILIO_SIP_USERNAME=your_username
   TWILIO_SIP_PASSWORD=your_password
   TWILIO_ACCOUNT_SID=your_account_sid
   TWILIO_AUTH_TOKEN=your_auth_token
   TWILIO_PHONE_NUMBER=+1234567890
   ```

For detailed setup instructions, see [TWILIO_SIP_SETUP.md](TWILIO_SIP_SETUP.md).

## Future Enhancements

- AWS deployment support
- Enhanced analytics and monitoring
- Multi-language support
- Voice activity detection
- Noise cancellation
- Call recording
- Call analytics dashboard

## License

MIT

## Support

For issues and questions, please refer to the project documentation or contact the development team.
