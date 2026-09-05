import json
import logging
import os
from datetime import datetime
from typing import Optional


class TradeJournal:
    """Persists trade records to a JSON file for review and backtesting.

    Each entry: entry, exit, direction, qty, pnl, reason, timestamps.
    Enhanced with behavioral journaling: thesis, outcome, lesson per trade.
    """

    def __init__(self, path: str = "journal.jsonl"):
        self.path = path
        self._ensure_file()

    def _ensure_file(self) -> None:
        """Create the journal file if it doesn't exist."""
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, "w") as f:
                pass

    def log(self, msg: str) -> None:
        """Log an informational message."""
        logging.info(msg)

    def log_trade(self, trade: dict) -> None:
        """Append a completed trade to the journal.

        Behavioral fields (optional, for trade journal analysis):
        - thesis: What was the setup thesis entering this trade?
        - outcome: What actually happened vs expected?
        - lesson: What to do differently next time?
        Each field max 200 characters. Cannot close a position without
        completing the journal if behavioral_journaling is enabled.
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "symbol": trade.get("symbol", "unknown"),
            "direction": trade.get("direction"),
            "qty": trade.get("qty", 1),
            "entry_price": trade.get("entry"),
            "exit_price": trade.get("exit_price"),
            "target": trade.get("target"),
            "stop": trade.get("stop"),
            "pnl": trade.get("pnl", 0),
            "rr": trade.get("rr"),
            "reason": trade.get("reason"),
            "entry_time": trade.get("entry_time"),
            "exit_time": str(trade.get("exit_time", "")),
            # Behavioral journal fields (prompts.chat: Trading Simulation Platform)
            "thesis": trade.get("thesis", ""),  # max 200 chars
            "outcome": trade.get("outcome", ""),  # max 200 chars
            "lesson": trade.get("lesson", ""),  # max 200 chars
        }
        with open(self.path, "a") as f:
            f.write(json.dumps(entry) + "\n")
        logging.info(f"Logged trade: {entry['direction']} {entry['qty']} {entry['symbol']} "
                      f"P&L=${entry['pnl']:.2f}")

    def get_summary(self) -> dict:
        """Return summary stats from the journal."""
        if not os.path.exists(self.path):
            return {"total_trades": 0, "total_pnl": 0, "win_rate": 0}

        trades = []
        with open(self.path) as f:
            for line in f:
                line = line.strip()
                if line:
                    trades.append(json.loads(line))

        if not trades:
            return {"total_trades": 0, "total_pnl": 0, "win_rate": 0}

        total = len(trades)
        wins = [t for t in trades if t["pnl"] > 0]
        total_pnl = sum(t["pnl"] for t in trades)

        return {
            "total_trades": total,
            "total_pnl": total_pnl,
            "win_rate": len(wins) / total if total > 0 else 0,
            "avg_pnl": total_pnl / total if total > 0 else 0,
        }

    def behavioral_analysis(self, lookback: int = 20) -> dict:
        """Analyze recent trade journal entries for recurring behavioral patterns.

        Inspired by the Trading & Investing Simulation Platform's behavioral
        analysis concept: identify thesis quality, emotional patterns, and
        decision-making trends from the last N trades.

        Returns a dict with:
        - total_analyzed: number of trades reviewed
        - thesis_keywords: most common words in trade theses
        - win_rate_trend: win rate split into first/second half of lookback
        - avg_pnl_by_direction: long vs short performance
        - recurring_exit_reasons: frequency of exit reasons
        - behavioral_flags: list of detected patterns (overtrading, revenge trading, etc.)
        """
        if not os.path.exists(self.path):
            return {"total_analyzed": 0, "error": "no journal file"}

        trades = []
        with open(self.path) as f:
            for line in f:
                line = line.strip()
                if line:
                    trades.append(json.loads(line))

        if not trades:
            return {"total_analyzed": 0, "error": "no trades recorded"}

        recent = trades[-lookback:]
        total = len(recent)

        # Thesis keyword extraction (simple frequency from 'reason' field)
        from collections import Counter
        import re

        all_reasons = " ".join(t.get("reason", "") or "" for t in recent).lower()
        words = re.findall(r'[a-z]+', all_reasons)
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "is", "it", "this", "that", "was", "are", "be", "with", "as", "by", "from", "no", "not", "if", "then", "else", "when", "where", "what", "which", "who", "how"}
        meaningful = [w for w in words if w not in stop_words and len(w) > 2]
        thesis_keywords = Counter(meaningful).most_common(10)

        # Win rate trend: first half vs second half
        mid = total // 2
        first_half = recent[:mid]
        second_half = recent[mid:]
        first_wr = sum(1 for t in first_half if t["pnl"] > 0) / len(first_half) if first_half else 0
        second_wr = sum(1 for t in second_half if t["pnl"] > 0) / len(second_half) if second_half else 0

        # Avg P&L by direction
        longs = [t for t in recent if t.get("direction") == "long"]
        shorts = [t for t in recent if t.get("direction") == "short"]
        avg_long = sum(t["pnl"] for t in longs) / len(longs) if longs else 0
        avg_short = sum(t["pnl"] for t in shorts) / len(shorts) if shorts else 0

        # Exit reason frequency
        exit_reasons = Counter(t.get("reason", "unknown") for t in recent)

        # Behavioral flags
        flags = []

        # Overtrading: more than 5 trades in a single day
        daily_counts = Counter()
        for t in recent:
            try:
                ts = t.get("timestamp", "") or t.get("entry_time", "")
                if ts:
                    day = ts[:10]  # YYYY-MM-DD
                    daily_counts[day] += 1
            except Exception:
                pass
        if any(c > 5 for c in daily_counts.values()):
            flags.append("overtrading: more than 5 trades in a single day detected")

        # Revenge trading: loss followed by immediate larger position
        for i in range(1, len(recent)):
            prev = recent[i - 1]
            curr = recent[i]
            if prev["pnl"] < 0 and curr.get("qty", 1) > prev.get("qty", 1):
                flags.append(f"revenge trading: larger position after loss at index {i}")
                break

        # Declining win rate
        if second_wr < first_wr - 0.15:
            flags.append(f"declining performance: win rate dropped from {first_wr:.0%} to {second_wr:.0%}")

        # Directional bias
        if longs and not shorts:
            flags.append("directional bias: only long trades in sample")
        elif shorts and not longs:
            flags.append("directional bias: only short trades in sample")

        return {
            "total_analyzed": total,
            "thesis_keywords": thesis_keywords,
            "win_rate_trend": {
                "first_half": round(first_wr, 3),
                "second_half": round(second_wr, 3),
                "direction": "improving" if second_wr > first_wr else "declining"
            },
            "avg_pnl_by_direction": {
                "long": round(avg_long, 2),
                "short": round(avg_short, 2)
            },
            "recurring_exit_reasons": exit_reasons.most_common(5),
            "behavioral_flags": flags
        }

    def get_behavioral_summary(self) -> dict:
        """Quick summary of behavioral journal coverage and patterns."""
        if not os.path.exists(self.path):
            return {"total_trades": 0, "journaled": 0, "coverage": 0}

        trades = []
        with open(self.path) as f:
            for line in f:
                line = line.strip()
                if line:
                    trades.append(json.loads(line))

        if not trades:
            return {"total_trades": 0, "journaled": 0, "coverage": 0}

        journaled = [t for t in trades if t.get("thesis") or t.get("lesson")]
        return {
            "total_trades": len(trades),
            "journaled": len(journaled),
            "coverage": len(journaled) / len(trades) if trades else 0,
        }
