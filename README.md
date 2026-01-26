# YT Learning Platform

An AI-powered educational platform that transforms YouTube playlists into interactive learning experiences. Ask questions about any playlist and get precise answers with exact video timestamps.

## Features

- **Hybrid Search**: Combines BM25 lexical search with vector similarity for accurate retrieval
- **Automatic Citation**: Responses include direct links to specific video moments with timestamps
- **Conversation Memory**: Persistent chat history with automatic summarization for long conversations
- **Multi-Query Retrieval**: Reformulates queries to improve document matching
- **Async Transcript Loading**: Concurrent extraction with rate limiting and proxy support

## Architecture

```
src/
├── application/           # Business logic & workflows
│   ├── graph/            # LangGraph state machine
│   │   ├── nodes/        # Graph computation nodes
│   │   ├── state.py      # State definitions
│   │   ├── builder.py    # Graph compilation
│   │   └── edges.py      # Conditional routing
│   └── services/         # Core services
│       ├── playlist_loader.py
│       └── memory_manager.py
│
├── domain/               # Models, exceptions, prompts
│   ├── models/          # Pydantic models
│   ├── exceptions/      # Custom exceptions
│   └── prompts/         # LLM prompt templates
│
└── infrastructure/       # External integrations
    ├── config/          # Environment configuration
    └── extensions/      # Embeddings, loaders
```

## Tech Stack

- **Orchestration**: LangGraph, LangChain
- **Vector Store**: Chroma
- **LLM**: Provider-agnostic (Anthropic, OpenAI, Google, etc.)
- **Embeddings**: Provider-agnostic (VoyageAI, OpenAI, HuggingFace, etc.)
- **Persistence**: SQLite, SQLModel

## Setup

### Prerequisites

- Python 3.11+
- YouTube Data API key
- API key for your chosen LLM provider (Anthropic, OpenAI, etc.)
- API key for your chosen embedding provider (VoyageAI, OpenAI, etc.)

### Installation

```bash
# Clone the repository
git clone https://github.com/Iamzhitox/yt-learning-assistant.git
cd yt-learning-assistant

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

### Environment Variables

```env
GOOGLE_API_KEY=         # YouTube Data API

# LLM (provider-agnostic)
LLM_PROVIDER=anthropic  # or openai, google-genai, etc.
QUERY_MODEL=claude-haiku-4-5
GENERATION_MODEL=claude-sonnet-4-5

# Embeddings (provider-agnostic)
EMBEDDING_PROVIDER=voyage  # or openai, huggingface, etc.
EMBEDDING_MODEL=voyage-3.5

# Set the API key for your chosen providers
ANTHROPIC_API_KEY=
VOYAGE_API_KEY=
```

## Usage

```bash
python main.py
```

The application will prompt you to enter a YouTube playlist URL, then you can ask questions about the content.

## How It Works

1. **Playlist Loading**: Extracts video metadata and transcripts from YouTube
2. **Chunking**: Segments transcripts into overlapping chunks with timing metadata
3. **Indexing**: Stores chunks in Chroma with embeddings for similarity search
4. **Retrieval**: Uses an ensemble retriever (BM25 + semantic) to find relevant chunks
5. **Generation**: Produces answers with citations linking to specific video timestamps

## License

MIT
