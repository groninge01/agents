"""
Market data utility functions
Used to correctly parse and map a market's outcomes, prices, and token IDs
"""

import json
from typing import Dict, List, Optional, Tuple


def parse_market_outcomes(market: Dict) -> Tuple[List[str], List[float], List[str]]:
    """
    Parse market outcomes, prices, and token IDs.

    Args:
        market: Market data dict

    Returns:
        (outcomes, prices, token_ids) tuple
    """
    # Parse outcomes
    outcomes = market.get('outcome', []) or market.get('outcomes', [])
    if isinstance(outcomes, str):
        try:
            outcomes = json.loads(outcomes)
        except:
            outcomes = outcomes.split(',') if outcomes else []

    # Parse prices
    prices = market.get('outcomePrices', [])
    if isinstance(prices, str):
        try:
            prices = json.loads(prices)
        except:
            prices = []

    # Parse token IDs
    token_ids = market.get('clobTokenIds', [])
    if isinstance(token_ids, str):
        try:
            token_ids = json.loads(token_ids)
        except:
            token_ids = []

    # Ensure they are lists
    if not isinstance(outcomes, list):
        outcomes = []
    if not isinstance(prices, list):
        prices = []
    if not isinstance(token_ids, list):
        token_ids = []

    return outcomes, prices, token_ids


def get_yes_no_mapping(market: Dict) -> Dict[str, int]:
    """
    Get a mapping from Yes/No to indices.

    For standard Yes/No markets:
    - Yes typically maps to the first outcome
    - No typically maps to the second outcome

    For sports matches and similar markets, mapping may depend on the question:
    - If the question is "Will X win?", then X = Yes and opponent = No
    - Use the question text and outcome names to decide

    Returns:
        {'Yes': index, 'No': index} dict
    """
    question = market.get('question', '').lower()
    outcomes, _, _ = parse_market_outcomes(market)

    if not outcomes or len(outcomes) < 2:
        # Default mapping (if we cannot parse)
        return {'Yes': 0, 'No': 1}

    # Normalize outcome names (lowercase)
    outcomes_lower = [str(o).lower().strip() for o in outcomes]

    # Check whether it's a standard Yes/No market
    if 'yes' in outcomes_lower or 'no' in outcomes_lower:
        yes_idx = outcomes_lower.index('yes') if 'yes' in outcomes_lower else 0
        no_idx = outcomes_lower.index('no') if 'no' in outcomes_lower else 1
        return {'Yes': yes_idx, 'No': no_idx}

    # For sports matches etc, decide based on the question
    # Common patterns:
    # - "Will [Team] win?" -> Team = Yes
    # - "Will [Team] beat [Opponent]?" -> Team = Yes
    # - "[Team] vs [Opponent]" -> depends on the exact question

    # Extract team name from the question
    question_lower = question.lower()

    # Method 1: match "will [team] win"
    import re
    will_win_match = re.search(r'will\s+([^?\s]+(?:\s+[^?\s]+)*?)\s+win', question_lower)
    if will_win_match:
        team_name = will_win_match.group(1).strip()
        # Find this team in outcomes
        for idx, outcome in enumerate(outcomes_lower):
            # Partial matching
            if team_name in outcome or outcome in team_name:
                return {'Yes': idx, 'No': 1 - idx}

    # Method 2: match "will [team] beat"
    will_beat_match = re.search(r'will\s+([^?\s]+(?:\s+[^?\s]+)*?)\s+beat', question_lower)
    if will_beat_match:
        team_name = will_beat_match.group(1).strip()
        for idx, outcome in enumerate(outcomes_lower):
            if team_name in outcome or outcome in team_name:
                return {'Yes': idx, 'No': 1 - idx}

    # Method 3: find the first outcome name that appears in the question
    for outcome in outcomes_lower:
        # Check whether outcome appears in question
        if outcome in question_lower:
            idx = outcomes_lower.index(outcome)
            return {'Yes': idx, 'No': 1 - idx}

    # Method 4: for "vs" or "vs." patterns
    vs_match = re.search(r'([^vs]+?)\s+vs\.?\s+([^?]+)', question_lower)
    if vs_match:
        team1 = vs_match.group(1).strip()
        team2 = vs_match.group(2).strip()
        # Find in outcomes
        for idx, outcome in enumerate(outcomes_lower):
            if team1 in outcome or outcome in team1:
                return {'Yes': idx, 'No': 1 - idx}

    # If we cannot determine, use default mapping (assume first is Yes)
    # This case should warn because the mapping might be wrong
    print(f"⚠️ Warning: unable to determine Yes/No mapping; using default mapping.")
    print(f"   Question: {market.get('question', '')[:60]}...")
    print(f"   Outcomes: {outcomes}")
    print(f"   Note: mapping may be incorrect! Please verify manually.")

    return {'Yes': 0, 'No': 1}


def get_price_for_side(market: Dict, side: str) -> Optional[float]:
    """
    Get the price for a given side (Yes/No).

    Args:
        market: Market data dict
        side: 'Yes' or 'No'

    Returns:
        Price (0-1); returns None if unavailable
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
    Get token ID for a given side (Yes/No).

    Args:
        market: Market data dict
        side: 'Yes' or 'No'

    Returns:
        Token ID string; returns None if unavailable
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
    Normalize side for a market.

    For sports matches, if the user selects a specific team name, convert to Yes/No.

    Args:
        market: Market data dict
        side: User input side ('Yes', 'No', or a team name)

    Returns:
        (normalized_side, outcome_name) tuple
        normalized_side: 'Yes' or 'No'
        outcome_name: The corresponding outcome name (if any)
    """
    outcomes, _, _ = parse_market_outcomes(market)

    # If side is already Yes/No, return directly
    if side.lower() in ['yes', 'no']:
        mapping = get_yes_no_mapping(market)
        outcome_name = outcomes[mapping[side.capitalize()]] if outcomes else None
        return side.capitalize(), outcome_name

    # If side is a team name, find the corresponding index
    side_lower = side.lower()
    outcomes_lower = [str(o).lower().strip() for o in outcomes] if outcomes else []

    for idx, outcome in enumerate(outcomes_lower):
        if side_lower in outcome or outcome in side_lower:
            # Found a matching outcome
            mapping = get_yes_no_mapping(market)
            # Determine whether this index corresponds to Yes or No
            if idx == mapping.get('Yes', 0):
                return 'Yes', outcomes[idx] if idx < len(outcomes) else None
            elif idx == mapping.get('No', 1):
                return 'No', outcomes[idx] if idx < len(outcomes) else None
            else:
                # If not a standard Yes/No mapping, assume the first is Yes
                return 'Yes' if idx == 0 else 'No', outcomes[idx] if idx < len(outcomes) else None

    # If no match found, return the original value (may be wrong)
    print(f"⚠️ Warning: unable to map '{side}' to Yes/No. Outcomes: {outcomes}")
    return side.capitalize(), None


def get_market_info(market: Dict) -> Dict:
    """
    Get normalized market info.

    Returns:
        Dict containing normalized fields
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
