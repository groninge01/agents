"""
市场数据工具函数
用于正确解析和映射市场的 outcomes、prices 和 token IDs
"""

import json
from typing import Dict, List, Optional, Tuple


def parse_market_outcomes(market: Dict) -> Tuple[List[str], List[float], List[str]]:
    """
    解析市场的结果、价格和 token IDs
    
    Args:
        market: 市场数据字典
        
    Returns:
        (outcomes, prices, token_ids) 元组
    """
    # 解析 outcomes
    outcomes = market.get('outcome', []) or market.get('outcomes', [])
    if isinstance(outcomes, str):
        try:
            outcomes = json.loads(outcomes)
        except:
            outcomes = outcomes.split(',') if outcomes else []
    
    # 解析 prices
    prices = market.get('outcomePrices', [])
    if isinstance(prices, str):
        try:
            prices = json.loads(prices)
        except:
            prices = []
    
    # 解析 token IDs
    token_ids = market.get('clobTokenIds', [])
    if isinstance(token_ids, str):
        try:
            token_ids = json.loads(token_ids)
        except:
            token_ids = []
    
    # 确保都是列表
    if not isinstance(outcomes, list):
        outcomes = []
    if not isinstance(prices, list):
        prices = []
    if not isinstance(token_ids, list):
        token_ids = []
    
    return outcomes, prices, token_ids


def get_yes_no_mapping(market: Dict) -> Dict[str, int]:
    """
    获取 Yes/No 到索引的映射
    
    对于普通 Yes/No 市场：
    - Yes 通常对应第一个 outcome
    - No 通常对应第二个 outcome
    
    对于体育比赛等市场，需要根据问题判断：
    - 如果问题是 "Will X win?"，那么 X = Yes，对手 = No
    - 需要根据问题文本和 outcomes 名称来判断
    
    Returns:
        {'Yes': index, 'No': index} 字典
    """
    question = market.get('question', '').lower()
    outcomes, _, _ = parse_market_outcomes(market)
    
    if not outcomes or len(outcomes) < 2:
        # 默认映射（如果无法解析）
        return {'Yes': 0, 'No': 1}
    
    # 标准化 outcomes 名称（转小写）
    outcomes_lower = [str(o).lower().strip() for o in outcomes]
    
    # 检查是否是标准的 Yes/No 市场
    if 'yes' in outcomes_lower or 'no' in outcomes_lower:
        yes_idx = outcomes_lower.index('yes') if 'yes' in outcomes_lower else 0
        no_idx = outcomes_lower.index('no') if 'no' in outcomes_lower else 1
        return {'Yes': yes_idx, 'No': no_idx}
    
    # 对于体育比赛等市场，需要根据问题判断
    # 常见模式：
    # - "Will [Team] win?" -> Team = Yes
    # - "Will [Team] beat [Opponent]?" -> Team = Yes
    # - "[Team] vs [Opponent]" -> 需要看具体问题
    
    # 提取问题中的队名
    question_lower = question.lower()
    
    # 方法1: 查找 "will [team] win" 模式
    import re
    will_win_match = re.search(r'will\s+([^?\s]+(?:\s+[^?\s]+)*?)\s+win', question_lower)
    if will_win_match:
        team_name = will_win_match.group(1).strip()
        # 在 outcomes 中查找这个队
        for idx, outcome in enumerate(outcomes_lower):
            # 检查队名是否在 outcome 中（部分匹配）
            if team_name in outcome or outcome in team_name:
                return {'Yes': idx, 'No': 1 - idx}
    
    # 方法2: 查找 "will [team] beat" 模式
    will_beat_match = re.search(r'will\s+([^?\s]+(?:\s+[^?\s]+)*?)\s+beat', question_lower)
    if will_beat_match:
        team_name = will_beat_match.group(1).strip()
        for idx, outcome in enumerate(outcomes_lower):
            if team_name in outcome or outcome in team_name:
                return {'Yes': idx, 'No': 1 - idx}
    
    # 方法3: 查找问题中第一个出现的队名
    # 提取所有可能的队名（大写的单词，通常是队名）
    for outcome in outcomes_lower:
        # 检查 outcome 是否在问题中
        if outcome in question_lower:
            idx = outcomes_lower.index(outcome)
            return {'Yes': idx, 'No': 1 - idx}
    
    # 方法4: 对于 "vs" 或 "vs." 模式，检查哪个队在问题中先出现
    vs_match = re.search(r'([^vs]+?)\s+vs\.?\s+([^?]+)', question_lower)
    if vs_match:
        team1 = vs_match.group(1).strip()
        team2 = vs_match.group(2).strip()
        # 在 outcomes 中查找
        for idx, outcome in enumerate(outcomes_lower):
            if team1 in outcome or outcome in team1:
                return {'Yes': idx, 'No': 1 - idx}
    
    # 如果无法判断，使用默认映射（假设第一个是 Yes）
    # 但这种情况需要警告
    print(f"⚠️ 警告: 无法确定 Yes/No 映射，使用默认映射。")
    print(f"   问题: {market.get('question', '')[:60]}...")
    print(f"   Outcomes: {outcomes}")
    print(f"   注意：可能映射错误！请手动检查。")
    
    return {'Yes': 0, 'No': 1}


def get_price_for_side(market: Dict, side: str) -> Optional[float]:
    """
    获取指定方向（Yes/No）的价格
    
    Args:
        market: 市场数据字典
        side: 'Yes' 或 'No'
        
    Returns:
        价格（0-1之间），如果无法获取则返回 None
    """
    _, prices, _ = parse_market_outcomes(market)
    mapping = get_yes_no_mapping(market)
    
    if side not in mapping:
        return None
    
    idx = mapping[side]
    if idx < len(prices):
        try:
            return float(prices[idx])
        except:
            return None
    
    return None


def get_token_id_for_side(market: Dict, side: str) -> Optional[str]:
    """
    获取指定方向（Yes/No）的 token ID
    
    Args:
        market: 市场数据字典
        side: 'Yes' 或 'No'
        
    Returns:
        token ID 字符串，如果无法获取则返回 None
    """
    _, _, token_ids = parse_market_outcomes(market)
    mapping = get_yes_no_mapping(market)
    
    if side not in mapping:
        return None
    
    idx = mapping[side]
    if idx < len(token_ids):
        return str(token_ids[idx])
    
    return None


def normalize_side_for_market(market: Dict, side: str) -> Tuple[str, Optional[str]]:
    """
    标准化市场方向
    
    对于体育比赛，如果用户选择的是具体的队名，转换为 Yes/No
    
    Args:
        market: 市场数据字典
        side: 用户输入的方向（'Yes', 'No', 或队名）
        
    Returns:
        (normalized_side, outcome_name) 元组
        normalized_side: 'Yes' 或 'No'
        outcome_name: 对应的 outcome 名称（如果有）
    """
    outcomes, _, _ = parse_market_outcomes(market)
    
    # 如果 side 已经是 Yes/No，直接返回
    if side.lower() in ['yes', 'no']:
        mapping = get_yes_no_mapping(market)
        outcome_name = outcomes[mapping[side.capitalize()]] if outcomes else None
        return side.capitalize(), outcome_name
    
    # 如果 side 是队名，需要找到对应的索引
    side_lower = side.lower()
    outcomes_lower = [str(o).lower().strip() for o in outcomes] if outcomes else []
    
    for idx, outcome in enumerate(outcomes_lower):
        if side_lower in outcome or outcome in side_lower:
            # 找到匹配的 outcome
            mapping = get_yes_no_mapping(market)
            # 检查这个索引对应 Yes 还是 No
            if idx == mapping.get('Yes', 0):
                return 'Yes', outcomes[idx] if idx < len(outcomes) else None
            elif idx == mapping.get('No', 1):
                return 'No', outcomes[idx] if idx < len(outcomes) else None
            else:
                # 如果不是标准的 Yes/No 映射，假设第一个是 Yes
                return 'Yes' if idx == 0 else 'No', outcomes[idx] if idx < len(outcomes) else None
    
    # 如果找不到匹配，返回原始值（可能是错误的）
    print(f"⚠️ 警告: 无法将 '{side}' 映射到 Yes/No。Outcomes: {outcomes}")
    return side.capitalize(), None


def get_market_info(market: Dict) -> Dict:
    """
    获取标准化的市场信息
    
    Returns:
        包含标准化信息的字典
    """
    outcomes, prices, token_ids = parse_market_outcomes(market)
    mapping = get_yes_no_mapping(market)
    
    yes_idx = mapping.get('Yes', 0)
    no_idx = mapping.get('No', 1)
    
    yes_price = float(prices[yes_idx]) if yes_idx < len(prices) else 0.5
    no_price = float(prices[no_idx]) if no_idx < len(prices) else (1 - yes_price)
    
    yes_token = token_ids[yes_idx] if yes_idx < len(token_ids) else None
    no_token = token_ids[no_idx] if no_idx < len(token_ids) else None
    
    yes_outcome = outcomes[yes_idx] if yes_idx < len(outcomes) else 'Yes'
    no_outcome = outcomes[no_idx] if no_idx < len(outcomes) else 'No'
    
    return {
        'question': market.get('question', ''),
        'yes_price': yes_price,
        'no_price': no_price,
        'yes_token_id': yes_token,
        'no_token_id': no_token,
        'yes_outcome': yes_outcome,
        'no_outcome': no_outcome,
        'outcomes': outcomes,
        'prices': prices,
        'token_ids': token_ids,
        'mapping': mapping
    }

