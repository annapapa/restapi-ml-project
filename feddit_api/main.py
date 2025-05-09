from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional, Literal
import httpx
import logging
import os
import asyncio
from cachetools import TTLCache
from textblob import TextBlob

# Configure logging with more detail
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_FEDDIT_API_URL = "http://localhost:8080"  # Docker container URL
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_CONNECTIONS = 10
DEFAULT_KEEPALIVE_CONNECTIONS = 5
DEFAULT_CACHE_TTL = 60
DEFAULT_CACHE_SIZE = 100
DEFAULT_COMMENT_LIMIT = 25

# Load configuration from environment variables
FEDDIT_API_URL = os.getenv("FEDDIT_API_URL", DEFAULT_FEDDIT_API_URL)
TIMEOUT = float(os.getenv("TIMEOUT", DEFAULT_TIMEOUT))
MAX_CONNECTIONS = int(os.getenv("MAX_CONNECTIONS", DEFAULT_MAX_CONNECTIONS))
KEEPALIVE_CONNECTIONS = int(os.getenv("KEEPALIVE_CONNECTIONS", DEFAULT_KEEPALIVE_CONNECTIONS))
CACHE_TTL = int(os.getenv("CACHE_TTL", DEFAULT_CACHE_TTL))
CACHE_SIZE = int(os.getenv("CACHE_SIZE", DEFAULT_CACHE_SIZE))
COMMENT_LIMIT = int(os.getenv("COMMENT_LIMIT", DEFAULT_COMMENT_LIMIT))

app = FastAPI(title="Feddit API")

# Request deduplication cache
request_cache = TTLCache(maxsize=CACHE_SIZE, ttl=CACHE_TTL)

class SentimentAnalysis(BaseModel):
    polarity: float
    classification: str

class CommentInfo(BaseModel):
    id: int
    username: str
    text: str
    created_at: int
    sentiment: SentimentAnalysis

class CommentsResponse(BaseModel):
    subfeddit_id: int
    subfeddit_name: str
    limit: int = DEFAULT_COMMENT_LIMIT
    skip: int = 0
    sort_by: Optional[Literal["polarity", "created_at"]] = None
    sort_order: Optional[Literal["asc", "desc"]] = "desc"
    filter_by: Optional[Literal["positive", "negative", "neutral"]] = None
    comments: List[CommentInfo]

class SentimentRequest(BaseModel):
    text: str

def analyze_sentiment(text: str) -> SentimentAnalysis:
    """Analyze the sentiment of a text using TextBlob."""
    analysis = TextBlob(text)
    polarity = analysis.sentiment.polarity
    classification = "positive" if polarity > 0 else "negative" if polarity < 0 else "neutral"
    return SentimentAnalysis(polarity=polarity, classification=classification)

# Feddit API client
class FedditClient:
    def __init__(self):
        self.base_url = FEDDIT_API_URL
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=TIMEOUT,
            verify=True,
            limits=httpx.Limits(
                max_keepalive_connections=KEEPALIVE_CONNECTIONS,
                max_connections=MAX_CONNECTIONS
            )
        )
        self._request_locks = {}
        logger.info(f"Initialized FedditClient with base URL: {self.base_url}")

    def _get_cache_key(self, url: str, params: dict) -> str:
        """Generate a cache key for a request."""
        return f"{url}:{str(sorted(params.items()))}"

    async def _get_request_lock(self, cache_key: str) -> asyncio.Lock:
        """Get or create a lock for a request."""
        if cache_key not in self._request_locks:
            self._request_locks[cache_key] = asyncio.Lock()
        return self._request_locks[cache_key]

    async def _make_request(self, url: str, params: dict) -> dict:
        """Make a cached HTTP request."""
        cache_key = self._get_cache_key(url, params)
        
        if cache_key in request_cache:
            return request_cache[cache_key]
        
        async with await self._get_request_lock(cache_key):
            if cache_key in request_cache:
                return request_cache[cache_key]
            
            try:
                response = await self.client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                request_cache[cache_key] = data
                return data
            except httpx.HTTPError as e:
                error_msg = f"Error making request to {url}: {str(e)}"
                logger.error(error_msg)
                raise HTTPException(status_code=500, detail=str(e))

    async def get_subfeddit_by_name(self, subfeddit_name: str) -> dict:
        """Get subfeddit information by name."""
        try:
            # First get all subfeddits
            subfeddits_data = await self._make_request("/api/v1/subfeddits/", {"limit": 100})
            subfeddits = subfeddits_data.get('subfeddits', [])
            
            # Find the subfeddit by name (case-insensitive)
            subfeddit = next(
                (s for s in subfeddits if s['title'].lower() == subfeddit_name.lower()),
                None
            )
            
            if not subfeddit:
                raise HTTPException(
                    status_code=404,
                    detail=f"Subfeddit with name '{subfeddit_name}' not found"
                )
            
            # Get detailed subfeddit information
            return await self._make_request("/api/v1/subfeddit/", {"subfeddit_id": subfeddit['id']})
            
        except HTTPException:
            raise
        except Exception as e:
            error_msg = f"Error finding subfeddit by name: {str(e)}"
            logger.error(error_msg)
            raise HTTPException(status_code=500, detail=str(e))

    async def get_comments(self, subfeddit_id: int, limit: int = DEFAULT_COMMENT_LIMIT, skip: int = 0) -> dict:
        """Get comments for a subfeddit."""
        return await self._make_request(
            "/api/v1/comments/",
            {"subfeddit_id": subfeddit_id, "limit": limit, "skip": skip}
        )

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

# Initialize Feddit client
feddit_client = FedditClient()

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    await feddit_client.close()

@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Welcome to Feddit API"}

@app.get("/healthz")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "feddit"}

@app.get("/api/subfeddit/{subfeddit_name}/comments", response_model=CommentsResponse)
async def get_subfeddit_comments(
    subfeddit_name: str,
    limit: int = Query(DEFAULT_COMMENT_LIMIT, ge=1, le=100),
    skip: int = Query(0, ge=0),
    sort_by: Optional[Literal["polarity", "created_at"]] = None,
    sort_order: Optional[Literal["asc", "desc"]] = "desc",
    filter_by: Optional[Literal["positive", "negative", "neutral"]] = None
):
    """Get comments for a specific subfeddit by name with sentiment analysis."""
    try:
        # Get subfeddit information by name
        subfeddit_data = await feddit_client.get_subfeddit_by_name(subfeddit_name)
        
        # Get comments for the subfeddit
        comments_data = await feddit_client.get_comments(subfeddit_data['id'], limit, skip)
        
        # Add sentiment analysis to each comment
        for comment in comments_data['comments']:
            sentiment = analyze_sentiment(comment['text'])
            comment['sentiment'] = sentiment.dict()
        
        # Filter comments if requested
        if filter_by:
            comments_data['comments'] = [
                comment for comment in comments_data['comments']
                if comment['sentiment']['classification'] == filter_by
            ]
        
        # Sort comments if requested
        if sort_by:
            reverse = sort_order == "desc"
            if sort_by == "polarity":
                comments_data['comments'].sort(
                    key=lambda x: x['sentiment']['polarity'],
                    reverse=reverse
                )
            elif sort_by == "created_at":
                comments_data['comments'].sort(
                    key=lambda x: x['created_at'],
                    reverse=reverse
                )
        
        # Add subfeddit name and sorting/filtering info to the response
        comments_data['subfeddit_name'] = subfeddit_name
        comments_data['sort_by'] = sort_by
        comments_data['sort_order'] = sort_order
        comments_data['filter_by'] = filter_by
        
        return CommentsResponse(**comments_data)
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error getting subfeddit comments: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sentiment/analyze", response_model=SentimentAnalysis)
async def analyze_sentiment_endpoint(request: SentimentRequest):
    """Analyze the sentiment of a given text."""
    try:
        return analyze_sentiment(request.text)
    except Exception as e:
        error_msg = f"Error analyzing sentiment: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=str(e)) 