"""X (Twitter) 自動投稿サービス — Free Tier API v2"""
import logging
import os

import tweepy

logger = logging.getLogger(__name__)


def post_to_x(text: str) -> dict:
    """X API v2でツイートを投稿する。

    Returns:
        {"status": "ok", "tweet_id": "..."} or {"status": "error", "message": "..."}
    """
    api_key = os.getenv("X_API_KEY")
    api_secret = os.getenv("X_API_SECRET")
    access_token = os.getenv("X_ACCESS_TOKEN")
    access_token_secret = os.getenv("X_ACCESS_TOKEN_SECRET")

    if not all([api_key, api_secret, access_token, access_token_secret]):
        return {"status": "error", "message": "X API credentials not configured"}

    try:
        client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
        )
        response = client.create_tweet(text=text)
        tweet_id = response.data["id"]
        logger.info(f"X投稿成功: tweet_id={tweet_id}")
        return {"status": "ok", "tweet_id": tweet_id}

    except tweepy.TweepyException as e:
        logger.error(f"X投稿失敗: {e}")
        return {"status": "error", "message": str(e)}
