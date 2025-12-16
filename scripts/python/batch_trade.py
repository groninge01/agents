import json
import os
import re
from datetime import datetime, timedelta
from typing import Any, Optional

from agents.polymarket.gamma import GammaMarketClient
from scripts.python.market_scorer import calculate_market_score


def _parse_outcome_prices(market: dict) -> tuple[float, float]:
    prices = market.get("outcomePrices", [])
    if isinstance(prices, str):
        try:
            prices = json.loads(prices)
        except Exception:
            prices = []

    yes_price = float(prices[0]) if prices and prices[0] is not None else 0.5
    no_price = float(prices[1]) if prices and len(prices) > 1 and prices[1] is not None else (1 - yes_price)
    return yes_price, no_price


def _parse_clob_token_ids(market: dict) -> list[str]:
    token_ids = market.get("clobTokenIds", [])
    if isinstance(token_ids, str):
        try:
            token_ids = json.loads(token_ids)
        except Exception:
            token_ids = []
    if not isinstance(token_ids, list):
        return []
    return [str(t) for t in token_ids]


def find_short_term_markets(
    gamma: GammaMarketClient,
    *,
    hours: int = 48,
    min_liquidity: float = 1000,
    count: int = 30,
    min_score: Optional[int] = 7,
    executor: Any = None,
) -> list[dict]:
    markets = gamma.get_all_current_markets(limit=500)
    now = datetime.utcnow()
    deadline = now + timedelta(hours=hours)

    candidates: list[dict] = []
    for m in markets:
        try:
            end_date = m.get("endDate")
            if not end_date:
                continue

            end = datetime.fromisoformat(str(end_date).replace("Z", "+00:00")).replace(tzinfo=None)
            if not (now < end <= deadline):
                continue

            liquidity = float(m.get("liquidity", 0) or m.get("liquidityClob", 0) or 0)
            if liquidity < min_liquidity:
                continue

            if m.get("enableOrderBook") is False:
                continue

            yes_price, _ = _parse_outcome_prices(m)
            if not (0.1 <= yes_price <= 0.9):
                continue

            score_data = calculate_market_score(m, executor=executor)
            total_score = int(score_data.get("total_score", 0) or 0)
            if min_score is not None and total_score < min_score:
                continue

            candidates.append(
                {
                    "market": m,
                    "question": m.get("question", ""),
                    "end": end_date,
                    "hours_left": max(0.0, (end - now).total_seconds() / 3600),
                    "liquidity": liquidity,
                    "yes_price": yes_price,
                    "score": score_data,
                }
            )
        except Exception:
            continue

    candidates.sort(
        key=lambda x: (
            float(x.get("score", {}).get("total_score", 0) or 0),
            float(x.get("liquidity", 0) or 0),
        ),
        reverse=True,
    )
    return candidates[:count]


def ai_select_markets(executor: Any, candidates: list[dict], *, count: int) -> list[dict]:
    if not candidates:
        return []

    if executor is None:
        return candidates[:count]

    market_list = []
    for i, m in enumerate(candidates, 1):
        question = (m.get("question") or "").strip()
        yes_price = float(m.get("yes_price", 0.5) or 0.5)
        hours_left = float(m.get("hours_left", 0.0) or 0.0)
        market_list.append(f"{i}. {question} (Yes:{yes_price:.0%}, ends in {hours_left:.0f}h)")

    prompt = (
        "You are a professional forecasting expert. Below are prediction markets that end soon.\n\n"
        + "\n".join(market_list)
        + f"\n\nSelect {count} markets you feel most confident forecasting. "
        "Return only the market numbers, comma-separated. Example: 1,5,12"
    )

    try:
        from langchain_core.messages import HumanMessage

        result = executor.llm.invoke([HumanMessage(content=prompt)])
        selection = result.content
    except Exception:
        return candidates[:count]

    indices = re.findall(r"\d+", str(selection))
    picked: list[dict] = []
    seen: set[int] = set()
    for raw in indices:
        idx = int(raw) - 1
        if idx < 0 or idx >= len(candidates) or idx in seen:
            continue
        seen.add(idx)
        picked.append(candidates[idx])
        if len(picked) >= count:
            break

    if len(picked) < count:
        for c in candidates:
            if c in picked:
                continue
            picked.append(c)
            if len(picked) >= count:
                break

    return picked


def _extract_probability(text: str) -> Optional[float]:
    match = re.search(r"(0?\.\d+)", text)
    if not match:
        return None
    try:
        val = float(match.group(1))
    except Exception:
        return None
    if not (0.0 <= val <= 1.0):
        return None
    return val


def analyze_and_decide(executor: Any, market_info: dict, *, min_edge: float = 0.03) -> dict:
    question = market_info.get("question", "")
    yes_price = float(market_info.get("yes_price", 0.5) or 0.5)
    no_price = 1 - yes_price

    ai_prob: Optional[float] = None
    if executor is not None:
        try:
            prediction = executor.get_superforecast(
                event_title=question,
                market_question=question,
                outcome="Yes",
            )
            ai_prob = _extract_probability(prediction)
        except Exception:
            ai_prob = None

    if ai_prob is None:
        ai_prob = yes_price

    yes_edge = ai_prob - yes_price
    no_edge = (1 - ai_prob) - no_price

    if yes_edge >= no_edge:
        side = "Yes" if yes_edge >= min_edge else ("Yes" if ai_prob >= 0.5 else "No")
        edge = yes_edge
    else:
        side = "No" if no_edge >= min_edge else ("Yes" if ai_prob >= 0.5 else "No")
        edge = no_edge

    return {"side": side, "ai_prob": ai_prob, "edge": edge}


def execute_batch_trades(
    *,
    dry_run: bool = True,
    amount_per_trade: float = 1.0,
    num_trades: int = 3,
    hours: int = 48,
    min_liquidity: float = 1000,
    min_score: Optional[int] = 7,
) -> list[dict]:
    gamma = GammaMarketClient()

    executor = None
    try:
        from agents.application.executor import Executor

        if os.getenv("OPENAI_API_KEY"):
            executor = Executor()
    except Exception:
        executor = None

    candidates = find_short_term_markets(
        gamma,
        hours=hours,
        min_liquidity=min_liquidity,
        count=max(30, num_trades * 10),
        min_score=min_score,
        executor=executor,
    )

    selected = ai_select_markets(executor, candidates, count=num_trades)

    results: list[dict] = []
    if dry_run:
        for m in selected:
            decision = analyze_and_decide(executor, m)
            results.append(
                {
                    "question": m.get("question", ""),
                    "side": decision.get("side"),
                    "ai_prob": decision.get("ai_prob"),
                    "edge": decision.get("edge"),
                    "status": "simulated",
                }
            )
        return results

    from agents.polymarket.polymarket import Polymarket
    from scripts.python.position_monitor import PositionManager

    polymarket = Polymarket()
    pm = PositionManager()

    for m in selected:
        market = m.get("market") or {}
        token_ids = _parse_clob_token_ids(market)
        if len(token_ids) < 2:
            continue

        decision = analyze_and_decide(executor, m)
        side = decision.get("side", "Yes")
        token_id = token_ids[0] if side == "Yes" else token_ids[1]

        try:
            orderbook = polymarket.client.get_order_book(token_id)
            if not orderbook or not orderbook.asks:
                continue

            best_ask = min(orderbook.asks, key=lambda x: float(x.price))
            buy_price = float(best_ask.price)
            min_amount = max(float(amount_per_trade), 1.05)
            quantity = round(min_amount / buy_price, 2)

            result = polymarket.execute_order(
                price=buy_price,
                size=quantity,
                side="BUY",
                token_id=token_id,
            )

            order_id = result.get("orderID", result.get("id", "")) if isinstance(result, dict) else str(result)

            pm.add_position(
                token_id=token_id,
                market_question=m.get("question", ""),
                side=side,
                buy_price=buy_price,
                quantity=quantity,
                cost=round(buy_price * quantity, 6),
                order_id=order_id,
            )

            results.append(
                {
                    "question": m.get("question", ""),
                    "side": side,
                    "ai_prob": decision.get("ai_prob"),
                    "edge": decision.get("edge"),
                    "token_id": token_id,
                    "price": buy_price,
                    "quantity": quantity,
                    "order_id": order_id,
                    "status": "success",
                }
            )
        except Exception as e:
            results.append(
                {
                    "question": m.get("question", ""),
                    "side": side,
                    "ai_prob": decision.get("ai_prob"),
                    "edge": decision.get("edge"),
                    "status": "failed",
                    "error": str(e),
                }
            )

    return results
