"""
Market scoring system
Scores a market across 5 dimensions (0-10 total)
"""

import json
import re
from datetime import datetime, timedelta
from typing import Dict, Optional


def score_liquidity(liquidity: float) -> int:
    """
    ① Liquidity score (0-3)

    Args:
        liquidity: Market liquidity (USD)

    Returns:
        0-3
    """
    if liquidity < 100000:  # < $100k
        return 0
    elif liquidity < 300000:  # $100k - $300k
        return 1
    elif liquidity < 1000000:  # $300k - $1M
        return 2
    else:  # ≥ $1M
        return 3


def score_activity(market: dict, volume_24hr: Optional[float] = None) -> int:
    """
    ② Activity score (0-2)
    Uses recent trading activity (roughly the last 5 minutes)

    Args:
        market: Market data
        volume_24hr: 24h volume (if available)

    Returns:
        0-2
    """
    # Try to derive an activity signal from the market data
    # If 24h volume is available, estimate activity
    if volume_24hr is not None:
        # Rough estimate: 24h volume / 288 (number of 5-minute buckets)
        volume_per_5min = volume_24hr / 288

        if volume_per_5min > 100:  # High activity (assume average trade size ~$100+)
            return 2
        elif volume_per_5min > 10:  # Some activity
            return 1
        else:
            return 0

    # If we cannot get the above, use volume as a coarse signal
    volume = market.get('volume', 0) or market.get('volume24hr', 0) or 0
    volume_num = market.get('volumeNum', 0) or 0
    volume_clob = market.get('volumeClob', 0) or market.get('volume24hrClob', 0) or 0

    # Use the largest volume metric
    max_volume = max(float(volume or 0), float(volume_num or 0), float(volume_clob or 0))

    if max_volume > 50000:  # High activity
        return 2
    elif max_volume > 5000:  # Medium activity
        return 1
    else:  # Low activity
        return 0


def score_volatility(market: dict, price_history: Optional[list] = None) -> int:
    """
    ③ Volatility score (0-2)
    Historical / intraday price movement

    Args:
        market: Market data
        price_history: Price history (if available)

    Returns:
        0-2
    """
    # If no price history is provided, estimate from current market prices
    prices = market.get('outcomePrices', [])
    if isinstance(prices, str):
        prices = json.loads(prices)

    if prices and len(prices) >= 2:
        yes_price = float(prices[0]) if prices[0] else 0.5
        no_price = float(prices[1]) if prices[1] else (1 - yes_price)

        # Compute price range (in cents)
        price_range = abs(yes_price - no_price) * 100  # Convert to cents

        if price_range >= 15:  # ≥ 15c
            return 2
        elif price_range >= 8:  # 8-15c
            return 1
        else:  # < 8c
            return 0

    # If there is no price data, use spread as a fallback signal
    spread = market.get('spread', 0) or 0
    spread_cents = float(spread) * 100

    if spread_cents >= 15:
        return 2
    elif spread_cents >= 8:
        return 1
    else:
        return 0


def score_event_structure(market: dict, question: str, end_date: Optional[str] = None) -> int:
    """
    ④ Event time-structure score (0-2)

    Args:
        market: Market data
        question: Market question
        end_date: End date

    Returns:
        0-2
    """
    question_lower = question.lower()
    description = market.get('description', '').lower()

    # Check for explicit "scheduled event" keywords
    explicit_keywords = [
        'cpi', 'consumer price index', 'inflation',
        'election',
        'fomc', 'fed meeting', 'interest rate',
        'earnings', 'financial report',
        'jobs report',
        'debate',
        'launch', 'release'
    ]

    # Check whether there is a clear time node
    has_explicit_node = any(keyword in question_lower or keyword in description
                           for keyword in explicit_keywords)

    if has_explicit_node:
        return 2  # Explicit scheduled event

    # Check for ongoing event keywords
    continuous_keywords = [
        'war', 'conflict',
        'crisis',
        'trend',
        'ongoing'
    ]

    has_continuous = any(keyword in question_lower or keyword in description
                        for keyword in continuous_keywords)

    if has_continuous:
        return 1  # Ongoing event

    # If end time is near, it may indicate a structured schedule
    if end_date:
        try:
            end = datetime.fromisoformat(end_date.replace('Z', '+00:00')).replace(tzinfo=None)
            hours_left = (end - datetime.utcnow()).total_seconds() / 3600

            # If ending within 24 hours, likely an explicit schedule
            if hours_left <= 24:
                return 2
            elif hours_left <= 48:
                return 1
        except:
            pass

    return 0  # Unstructured


def score_sentiment_engagement(market: dict, question: str, executor=None) -> int:
    """
    ⑤ Sentiment/engagement score (0-1)

    Args:
        market: Market data
        question: Market question
        executor: Optional Executor instance (for AI analysis)

    Returns:
        0-1
    """
    question_lower = question.lower()
    description = market.get('description', '').lower()

    # Comment count (if available)
    comment_count = market.get('commentCount', 0) or 0
    if comment_count and comment_count > 50:
        return 1  # Many discussions

    # Check hot keywords (common in social media)
    hot_keywords = [
        'trump', 'biden', 'president',
        'crypto', 'bitcoin', 'ethereum',
        'war', 'election',
        'trending', 'viral',
        'breaking'
    ]

    # Check whether it is a hot topic
    has_hot_topic = any(keyword in question_lower or keyword in description
                       for keyword in hot_keywords)

    if has_hot_topic:
        return 1

    # Optional AI analysis
    if executor:
        try:
            # Placeholder for future: AI analysis of social/media attention
            pass
        except:
            pass

    return 0  # Low attention


def calculate_market_score(market: dict, executor=None) -> Dict:
    """
    Compute total market score (0-10).

    Args:
        market: Market data dict
        executor: Optional Executor instance (for AI analysis)

    Returns:
        Dict containing sub-scores and total score
    """
    question = market.get('question', '')

    # Liquidity
    liquidity = float(market.get('liquidity', 0) or market.get('liquidityClob', 0) or 0)

    # ① Liquidity
    liquidity_score = score_liquidity(liquidity)

    # ② Activity
    volume_24hr = market.get('volume24hr', None) or market.get('volume24hrClob', None)
    activity_score = score_activity(market, volume_24hr)

    # ③ Volatility
    volatility_score = score_volatility(market)

    # ④ Event structure
    end_date = market.get('endDate', None)
    structure_score = score_event_structure(market, question, end_date)

    # ⑤ Sentiment/engagement
    sentiment_score = score_sentiment_engagement(market, question, executor)

    # Total
    total_score = liquidity_score + activity_score + volatility_score + structure_score + sentiment_score

    return {
        'total_score': total_score,
        'liquidity_score': liquidity_score,
        'activity_score': activity_score,
        'volatility_score': volatility_score,
        'structure_score': structure_score,
        'sentiment_score': sentiment_score,
        'liquidity': liquidity,
        'tradable': total_score >= 7,
        'observable': 5 <= total_score < 7,
        'skip': total_score < 5
    }


def interpret_score(score: int) -> str:
    """
    Interpret the total score.

    Args:
        score: Total score (0-10)

    Returns:
        Human-readable label
    """
    if score >= 7:
        return "Tradable ✅"
    elif score >= 5:
        return "Small / Observe ⚠️"
    else:
        return "Skip ❌"


def filter_markets_by_score(markets: list, min_score: int = 7, executor=None) -> list:
    """
    Filter markets by score.

    Args:
        markets: Market list
        min_score: Minimum score requirement (default 7)
        executor: Optional Executor instance

    Returns:
        Filtered markets (sorted by score)
    """
    scored_markets = []

    for market in markets:
        score_data = calculate_market_score(market, executor)
        market['score_data'] = score_data
        market['score'] = score_data['total_score']

        if score_data['total_score'] >= min_score:
            scored_markets.append(market)

    # Sort by score (high to low)
    scored_markets.sort(key=lambda x: x.get('score', 0), reverse=True)

    return scored_markets
