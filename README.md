# Reddit Comment Analyzer

A FastAPI-based service that analyzes sentiment in Reddit comments using the Feddit API. This service provides a RESTful API for retrieving and analyzing comments from subfeddits, with features for sentiment analysis, pagination, sorting, and filtering.

## Features

- **Sentiment Analysis**: Uses TextBlob for accurate sentiment analysis of comments
- **Comment Retrieval**: Fetches comments from subfeddits with pagination support
- **Advanced Filtering**: Filter comments by sentiment classification (positive, negative, neutral)
- **Flexible Sorting**: Sort comments by polarity or creation date
- **High Performance**: Implements request deduplication and caching
- **Docker Support**: Easy deployment with Docker and Docker Compose
- **Health Monitoring**: Built-in health check endpoints
- **Comprehensive Testing**: Full test coverage with pytest
- **CI/CD Pipeline**: Automated testing and linting with GitHub Actions

## Prerequisites

- Python 3.11 or higher
- Docker and Docker Compose
- PostgreSQL (included in Docker setup)

## Getting Started

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd reddit-comment-analyzer
   ```

2. Start the services:
   ```bash
   docker compose up -d
   ```

3. The services will be available at:
   - PostgreSQL: localhost:5432
   - Feddit API: localhost:8080
   - Comment Analyzer: localhost:8082

## API Endpoints

### 1. Get Comments with Sentiment Analysis
```http
GET /api/subfeddit/{subfeddit_name}/comments
```

Query Parameters:
- `limit` (optional): Number of comments to return (default: 25, max: 100)
- `skip` (optional): Number of comments to skip (default: 0)
- `sort_by` (optional): Sort field ("polarity" or "created_at")
- `sort_order` (optional): Sort direction ("asc" or "desc", default: "desc")
- `filter_by` (optional): Filter by sentiment ("positive", "negative", or "neutral")

Example Response:
```json
{
    "subfeddit_id": 1,
    "subfeddit_name": "Dummy Topic 1",
    "limit": 25,
    "skip": 0,
    "sort_by": "polarity",
    "sort_order": "desc",
    "filter_by": null,
    "comments": [
        {
            "id": 1,
            "username": "user_0",
            "text": "It looks great!",
            "created_at": 1625360879,
            "sentiment": {
                "polarity": 1.0,
                "classification": "positive"
            }
        }
    ]
}
```

### 2. Analyze Sentiment
```http
POST /api/sentiment/analyze
```

Request Body:
```json
{
    "text": "This is a great comment!"
}
```

Response:
```json
{
    "polarity": 0.8125,
    "classification": "positive"
}
```

### 3. Health Check
```http
GET /healthz
```

Response:
```json
{
    "status": "ok",
    "service": "feddit"
}
```

## Configuration

The service can be configured using environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| FEDDIT_API_URL | URL of the Feddit API | http://localhost:8080 |
| TIMEOUT | Request timeout in seconds | 30.0 |
| MAX_CONNECTIONS | Maximum number of connections | 10 |
| KEEPALIVE_CONNECTIONS | Number of keepalive connections | 5 |
| CACHE_TTL | Cache time-to-live in seconds | 60 |
| CACHE_SIZE | Maximum cache size | 100 |
| COMMENT_LIMIT | Default number of comments to return | 25 |

## Docker Services

The application uses three Docker services:

1. **App Service** (Comment Analyzer)
   - Port: 8082
   - Dependencies: Feddit API, PostgreSQL
   - Features: Sentiment analysis, comment retrieval, caching

2. **Feddit API**
   - Port: 8080
   - Features: Comment storage and retrieval
   - Dependencies: PostgreSQL

3. **PostgreSQL**
   - Port: 5432
   - Features: Data persistence
   - Environment variables for database configuration

## Development

1. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the service:
   ```bash
   uvicorn feddit_api.main:app --reload --port 8082
   ```

## Testing

Run the test suite:
```bash
pytest tests/
```

The test suite includes:
- Unit tests for sentiment analysis
- Integration tests for API endpoints
- Tests for pagination, sorting, and filtering
- Error handling tests

## CI/CD Pipeline

The project includes a GitHub Actions workflow that:
- Runs on push to main and pull requests
- Executes the test suite with coverage reporting
- Performs linting (black, isort, flake8)
- Runs type checking (mypy)
- Uploads coverage reports to Codecov

## Error Handling

The API returns appropriate HTTP status codes:
- 200: Successful request
- 400: Invalid request parameters
- 404: Resource not found
- 422: Validation error
- 500: Internal server error

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

[Add your license information here] 