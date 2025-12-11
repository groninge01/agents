"""
市场评分系统
根据 5 个维度给市场打分（0-10 分）
"""

import json
import re
from datetime import datetime, timedelta
from typing import Dict, Optional


def score_liquidity(liquidity: float) -> int:
    """
    ① 流动性评分（0-3 分）
    
    Args:
        liquidity: 市场流动性（美元）
    
    Returns:
        0-3 分
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
    ② 活跃度评分（0-2 分）
    看最近 5 分钟的成交情况
    
    Args:
        market: 市场数据
        volume_24hr: 24小时成交量（如果可用）
    
    Returns:
        0-2 分
    """
    # 尝试从市场数据中获取活跃度指标
    # 如果有 24小时成交量，可以粗略估算活跃度
    if volume_24hr is not None:
        # 粗略估算：24小时成交量 / 288 (5分钟次数)
        volume_per_5min = volume_24hr / 288
        
        if volume_per_5min > 100:  # 几十笔成交（假设平均每笔$100+）
            return 2
        elif volume_per_5min > 10:  # 偶尔成交
            return 1
        else:
            return 0
    
    # 如果无法获取数据，使用成交量作为粗略指标
    volume = market.get('volume', 0) or market.get('volume24hr', 0) or 0
    volume_num = market.get('volumeNum', 0) or 0
    volume_clob = market.get('volumeClob', 0) or market.get('volume24hrClob', 0) or 0
    
    # 使用最大的成交量指标
    max_volume = max(float(volume or 0), float(volume_num or 0), float(volume_clob or 0))
    
    if max_volume > 50000:  # 高活跃度
        return 2
    elif max_volume > 5000:  # 中等活跃度
        return 1
    else:  # 低活跃度
        return 0


def score_volatility(market: dict, price_history: Optional[list] = None) -> int:
    """
    ③ 波动空间评分（0-2 分）
    历史 / 日内的价格波动
    
    Args:
        market: 市场数据
        price_history: 价格历史数据（如果可用）
    
    Returns:
        0-2 分
    """
    # 如果没有价格历史，尝试从市场价格范围估算
    prices = market.get('outcomePrices', [])
    if isinstance(prices, str):
        prices = json.loads(prices)
    
    if prices and len(prices) >= 2:
        yes_price = float(prices[0]) if prices[0] else 0.5
        no_price = float(prices[1]) if prices[1] else (1 - yes_price)
        
        # 计算价格范围（以美分计）
        price_range = abs(yes_price - no_price) * 100  # 转换为美分
        
        if price_range >= 15:  # ≥ 15c
            return 2
        elif price_range >= 8:  # 8-15c
            return 1
        else:  # < 8c
            return 0
    
    # 如果没有价格数据，使用 spread 作为替代指标
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
    ④ 事件时间结构评分（0-2 分）
    
    Args:
        market: 市场数据
        question: 市场问题
        end_date: 结束日期
    
    Returns:
        0-2 分
    """
    question_lower = question.lower()
    description = market.get('description', '').lower()
    
    # 检查是否有明确节点事件关键词
    explicit_keywords = [
        'cpi', 'consumer price index', 'inflation',
        'election', '投票', '选举',
        'fomc', 'fed meeting', 'interest rate',
        'earnings', '财报', 'financial report',
        'jobs report', '非农',
        'debate', '辩论',
        'launch', '发射', 'release', '发布'
    ]
    
    # 检查是否有明确的时间节点
    has_explicit_node = any(keyword in question_lower or keyword in description 
                           for keyword in explicit_keywords)
    
    if has_explicit_node:
        return 2  # 明确节点
    
    # 检查是否有持续事件关键词
    continuous_keywords = [
        'war', '战争', 'conflict',
        'crisis', '危机',
        'trend', '趋势',
        'ongoing', '持续'
    ]
    
    has_continuous = any(keyword in question_lower or keyword in description 
                        for keyword in continuous_keywords)
    
    if has_continuous:
        return 1  # 持续发酵
    
    # 检查结束时间，如果很快结束可能有节奏
    if end_date:
        try:
            end = datetime.fromisoformat(end_date.replace('Z', '+00:00')).replace(tzinfo=None)
            hours_left = (end - datetime.utcnow()).total_seconds() / 3600
            
            # 如果24小时内结束，可能是明确节点
            if hours_left <= 24:
                return 2
            elif hours_left <= 48:
                return 1
        except:
            pass
    
    return 0  # 没节奏


def score_sentiment_engagement(market: dict, question: str, executor=None) -> int:
    """
    ⑤ 情绪参与度评分（0-1 分）
    
    Args:
        market: 市场数据
        question: 市场问题
        executor: Executor 实例（用于 AI 分析，可选）
    
    Returns:
        0-1 分
    """
    question_lower = question.lower()
    description = market.get('description', '').lower()
    
    # 检查评论数（如果有）
    comment_count = market.get('commentCount', 0) or 0
    if comment_count and comment_count > 50:
        return 1  # 有较多讨论
    
    # 检查热门关键词（社交媒体常见）
    hot_keywords = [
        'trump', 'biden', 'president',
        'crypto', 'bitcoin', 'ethereum',
        'war', 'election',
        'trending', 'viral',
        'breaking', '重大'
    ]
    
    # 检查是否是热门话题
    has_hot_topic = any(keyword in question_lower or keyword in description 
                       for keyword in hot_keywords)
    
    if has_hot_topic:
        return 1
    
    # 如果使用 AI 分析（可选）
    if executor:
        try:
            # 简单判断：如果市场问题包含明显的热点话题词汇
            # 这里可以扩展为使用 AI 分析社交媒体热度
            pass
        except:
            pass
    
    return 0  # 冷清


def calculate_market_score(market: dict, executor=None) -> Dict:
    """
    计算市场总分（0-10 分）
    
    Args:
        market: 市场数据字典
        executor: Executor 实例（可选，用于 AI 分析）
    
    Returns:
        包含各项评分和总分的字典
    """
    question = market.get('question', '')
    
    # 获取流动性
    liquidity = float(market.get('liquidity', 0) or market.get('liquidityClob', 0) or 0)
    
    # ① 流动性评分
    liquidity_score = score_liquidity(liquidity)
    
    # ② 活跃度评分
    volume_24hr = market.get('volume24hr', None) or market.get('volume24hrClob', None)
    activity_score = score_activity(market, volume_24hr)
    
    # ③ 波动空间评分
    volatility_score = score_volatility(market)
    
    # ④ 事件时间结构评分
    end_date = market.get('endDate', None)
    structure_score = score_event_structure(market, question, end_date)
    
    # ⑤ 情绪参与度评分
    sentiment_score = score_sentiment_engagement(market, question, executor)
    
    # 总分
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
    解读总分
    
    Args:
        score: 总分（0-10）
    
    Returns:
        解读文本
    """
    if score >= 7:
        return "可交易 ✅"
    elif score >= 5:
        return "小仓 / 观察 ⚠️"
    else:
        return "跳过 ❌"


def filter_markets_by_score(markets: list, min_score: int = 7, executor=None) -> list:
    """
    根据评分筛选市场
    
    Args:
        markets: 市场列表
        min_score: 最低分数要求（默认 7 分）
        executor: Executor 实例（可选）
    
    Returns:
        筛选后的市场列表（按分数排序）
    """
    scored_markets = []
    
    for market in markets:
        score_data = calculate_market_score(market, executor)
        market['score_data'] = score_data
        market['score'] = score_data['total_score']
        
        if score_data['total_score'] >= min_score:
            scored_markets.append(market)
    
    # 按分数从高到低排序
    scored_markets.sort(key=lambda x: x.get('score', 0), reverse=True)
    
    return scored_markets






