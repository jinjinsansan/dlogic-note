"""X (Twitter) 自動投稿サービス — Free Tier API v2"""
import logging
import os
from datetime import datetime

import tweepy

logger = logging.getLogger(__name__)

MAX_TWEET_LENGTH = 280


def _normalize_text(text: str) -> str:
    lines = [line.rstrip() for line in text.strip().splitlines()]
    return "\n".join(lines).strip()


def _truncate_text(text: str, suffix: str = "") -> str:
    if suffix:
        max_len = MAX_TWEET_LENGTH - len(suffix)
        if max_len <= 0:
            return suffix[:MAX_TWEET_LENGTH]
        if len(text) > max_len:
            text = text[:max_len].rstrip()
        return f"{text}{suffix}"
    if len(text) > MAX_TWEET_LENGTH:
        return text[:MAX_TWEET_LENGTH].rstrip()
    return text


def _is_duplicate_error(message: str) -> bool:
    msg = message.lower()
    return "duplicate" in msg or "same text" in msg


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

    normalized = _normalize_text(text)
    if not normalized:
        return {"status": "error", "message": "X投稿文が空です"}

    normalized = _truncate_text(normalized)

    client = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
    )

    try:
        response = client.create_tweet(text=normalized)
        tweet_id = response.data["id"]
        logger.info(f"X投稿成功: tweet_id={tweet_id}")
        return {"status": "ok", "tweet_id": tweet_id}

    except tweepy.TweepyException as e:
        message = str(e)
        logger.warning(f"X投稿失敗: {message}")
        if _is_duplicate_error(message):
            suffix = f"\n（更新 {datetime.now().strftime('%H:%M')}）"
            retry_text = _truncate_text(normalized, suffix=suffix)
            if retry_text != normalized:
                try:
                    response = client.create_tweet(text=retry_text)
                    tweet_id = response.data["id"]
                    logger.info(f"X再投稿成功: tweet_id={tweet_id}")
                    return {"status": "ok", "tweet_id": tweet_id}
                except tweepy.TweepyException as retry_error:
                    logger.error(f"X再投稿失敗: {retry_error}")
                    return {"status": "error", "message": str(retry_error)}
        return {"status": "error", "message": message}
