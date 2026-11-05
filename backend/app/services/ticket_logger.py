"""Ticket Logging Service for ClothesSpot Support Desk.

Handles persistent audit logging to CSV in compliance with Section 7 of the specification.
Generates sequential ticket IDs (e.g. TKT-0001), formats dates, and computes
real-time metrics for the analytics dashboard using standard library csv,
without optional dataframe dependencies.
"""

import csv
import json
import os
from pathlib import Path
import tempfile
import threading
from typing import Any, Dict, List, Optional

CSV_COLUMNS = [
    "ticket_id",
    "timestamp",
    "customer_name",
    "order_id",
    "complaint",
    "category",
    "urgency",
    "sentiment",
    "kb_sources",
    "response",
    "status",
    "escalation_reason",
    "confidence",
    "agent_steps",
]


class TicketLogger:
    """Thread-safe ticket logging service that writes directly to logs/tickets.csv."""

    def __init__(self, log_path: Optional[str] = None) -> None:
        if log_path:
            self.log_path = Path(log_path)
        else:
            self.log_path = Path(__file__).resolve().parent.parent.parent.parent / "logs" / "tickets.csv"

        self.lock = threading.Lock()
        self._ensure_log_file()

    def _ensure_log_file(self) -> None:
        """Create logs directory and tickets.csv with header if not present."""
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.log_path.exists() or self.log_path.stat().st_size == 0:
            with open(self.log_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(CSV_COLUMNS)
            return

        with open(self.log_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            if fieldnames == CSV_COLUMNS:
                return
            if fieldnames is None or not set(CSV_COLUMNS[:-2]).issubset(fieldnames):
                raise ValueError(f"Ticket log has an invalid CSV header: {self.log_path}")
            records = list(reader)

        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                newline="",
                encoding="utf-8",
                dir=self.log_path.parent,
                delete=False,
            ) as f:
                temporary_path = Path(f.name)
                writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
                writer.writeheader()
                for record in records:
                    writer.writerow({column: record.get(column, "") for column in CSV_COLUMNS})
            os.replace(temporary_path, self.log_path)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()

    def get_next_ticket_id(self) -> str:
        """Calculate the next sequential ticket ID (e.g., TKT-0001)."""
        with self.lock:
            count = 0
            if self.log_path.exists():
                with open(self.log_path, "r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    next(reader, None)
                    count = sum(1 for row in reader if row)
            next_num = count + 1
            return f"TKT-{next_num:04d}"

    def log_ticket(
        self,
        ticket_id: str,
        timestamp: str,
        customer_name: str,
        order_id: str,
        complaint: str,
        category: str,
        urgency: str,
        sentiment: str,
        kb_sources: str,
        response: str,
        status: str,
        escalation_reason: str,
        confidence: float = 0.0,
        agent_steps: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Append a ticket row to tickets.csv."""
        with self.lock:
            self._ensure_log_file()

            clean_customer = customer_name.strip() if customer_name else "Guest"
            clean_order = order_id.strip() if order_id else "N/A"
            clean_sources = kb_sources if kb_sources else "None"
            clean_reason = escalation_reason if (status == "Escalated" and escalation_reason) else "None"

            row = [
                ticket_id,
                timestamp,
                clean_customer,
                clean_order,
                complaint.replace("\n", " ").strip(),
                category,
                urgency,
                sentiment,
                clean_sources,
                response.replace("\n", " ").strip(),
                status,
                clean_reason,
                confidence,
                json.dumps(agent_steps or [], ensure_ascii=True),
            ]

            with open(self.log_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(row)

            return {
                "ticket_id": ticket_id,
                "timestamp": timestamp,
                "customer_name": clean_customer,
                "order_id": clean_order,
                "complaint": complaint,
                "category": category,
                "urgency": urgency,
                "sentiment": sentiment,
                "kb_sources": clean_sources,
                "response": response,
                "status": status,
                "escalation_reason": clean_reason,
                "confidence": confidence,
                "agent_steps": agent_steps or [],
            }

    def get_all_tickets(self) -> List[Dict[str, Any]]:
        """Return all logged tickets as a list of dicts."""
        with self.lock:
            if not self.log_path.exists():
                return []
            with open(self.log_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                records = [dict(row) for row in reader]
            for record in records:
                try:
                    record["agent_steps"] = json.loads(record.get("agent_steps") or "[]")
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"Invalid agent_steps JSON in ticket {record.get('ticket_id', 'unknown')}"
                    ) from exc
            return records

    def get_analytics(self) -> Dict[str, Any]:
        """Compute operational metrics: total tickets, resolved vs escalated, categories."""
        records = self.get_all_tickets()
        if not records:
            return {
                "total_tickets": 0,
                "resolved_count": 0,
                "escalated_count": 0,
                "escalation_rate": 0.0,
                "categories": {},
                "urgencies": {},
                "sentiments": {},
                "avg_confidence": 0.0,
            }

        total = len(records)
        resolved = sum(1 for r in records if r.get("status") == "Resolved")
        escalated = sum(1 for r in records if r.get("status") == "Escalated")
        esc_rate = round((escalated / total) * 100, 1) if total > 0 else 0.0

        categories: Dict[str, int] = {}
        urgencies: Dict[str, int] = {}
        sentiments: Dict[str, int] = {}

        for r in records:
            cat = r.get("category", "General")
            categories[cat] = categories.get(cat, 0) + 1
            urg = r.get("urgency", "Low")
            urgencies[urg] = urgencies.get(urg, 0) + 1
            snt = r.get("sentiment", "Neutral")
            sentiments[snt] = sentiments.get(snt, 0) + 1

        confidence_values = [
            float(record["confidence"])
            for record in records
            if record.get("confidence") not in (None, "")
        ]
        return {
            "total_tickets": total,
            "resolved_count": resolved,
            "escalated_count": escalated,
            "escalation_rate": esc_rate,
            "categories": categories,
            "urgencies": urgencies,
            "sentiments": sentiments,
            "avg_confidence": (
                round(sum(confidence_values) / len(confidence_values), 2)
                if confidence_values
                else 0.0
            ),
        }


# Global singleton logger
_ticket_logger_instance: Optional[TicketLogger] = None


def get_ticket_logger() -> TicketLogger:
    """Retrieve global singleton TicketLogger instance."""
    global _ticket_logger_instance
    if _ticket_logger_instance is None:
        _ticket_logger_instance = TicketLogger()
    return _ticket_logger_instance


def log_ticket(
    ticket_id: str,
    timestamp: str,
    customer_name: str,
    order_id: str,
    complaint: str,
    category: str,
    urgency: str,
    sentiment: str,
    kb_sources: str,
    response: str,
    status: str,
    escalation_reason: str,
    confidence: float = 0.0,
    agent_steps: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Tool callable by LogAgent to record ticket and return status confirmation."""
    logger = get_ticket_logger()
    logger.log_ticket(
        ticket_id=ticket_id,
        timestamp=timestamp,
        customer_name=customer_name,
        order_id=order_id,
        complaint=complaint,
        category=category,
        urgency=urgency,
        sentiment=sentiment,
        kb_sources=kb_sources,
        response=response,
        status=status,
        escalation_reason=escalation_reason,
        confidence=confidence,
        agent_steps=agent_steps,
    )
    return f"LOGGED: Ticket {ticket_id} successfully saved with status '{status}'."
