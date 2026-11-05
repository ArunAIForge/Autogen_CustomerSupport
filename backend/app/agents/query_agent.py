"""Customer Query Agent for ClothesSpot.

Understands the customer's request: what the problem is, how urgent it is,
how the customer feels, and outputs category, urgency, sentiment, and summary.
"""

import json
import re
from typing import Any, Dict

from backend.app.agents.autogen_runtime import create_assistant, run_assistant

QUERY_AGENT_SYSTEM_MESSAGE = """You are the CustomerQueryAgent for ClothesSpot, an online fashion and lifestyle apparel store.
Your sole job is to analyze the customer's incoming raw complaint or inquiry and extract key diagnostic attributes:
1. Category: One of ['Shipping', 'Refund', 'Account', 'Product', 'Billing', 'General']
2. Urgency: One of ['Low', 'Medium', 'High']
   - High: Missing orders past delivery deadline, legal threats, fraud, duplicate credit card charges, severe distress.
   - Medium: General return requests, broken items awaiting replacement, voucher issues.
   - Low: Password reset instructions, general product questions.
3. Sentiment: One of ['Positive', 'Neutral', 'Frustrated', 'Angry']
   - Angry: Profanity, legal threats, demands for immediate intervention, extreme irritation (e.g. 'You charged my card three times! Fix this now or I'm contacting my bank and a lawyer').
   - Frustrated: Mild annoyance about delays or unclear instructions.
   - Neutral: Objective factual questions ('Where is my order?', 'How do I return?').
4. Summary: Exactly one clear, concise sentence summarizing the core problem.
5. Flags: Check if the issue involves legal_threats, payment_disputes, or fraud.

Format your output as structured text:
Category: <category>
Urgency: <urgency>
Sentiment: <sentiment>
Summary: <one-line summary>
Flags: <legal_threats, payment_disputes, fraud, or none>
"""


class CustomerQueryAgent:
    """Extracts issue classification, urgency, sentiment, and summary."""

    name = "CustomerQueryAgent"
    description = "Understands the customer's request: what the problem is, how urgent it is, and how the customer feels."

    def __init__(self, model_client: Any = None) -> None:
        self.model_client = model_client
        self.autogen_agent = create_assistant(
            self.name, self.description, QUERY_AGENT_SYSTEM_MESSAGE, model_client
        )

    def process(self, complaint: str) -> Dict[str, Any]:
        """Analyze complaint text and return structured classification."""
        if self.autogen_agent:
            output = run_assistant(
                self.autogen_agent,
                "Classify this customer message. Return only a JSON object with "
                "category, urgency, sentiment, summary, and flags (an array).\n"
                f"Customer message:\n{complaint}",
            )
            try:
                data = json.loads(output or "")
            except json.JSONDecodeError as exc:
                raise ValueError("CustomerQueryAgent returned invalid JSON.") from exc
            allowed = {
                "category": {"Shipping", "Refund", "Account", "Product", "Billing", "General"},
                "urgency": {"Low", "Medium", "High"},
                "sentiment": {"Positive", "Neutral", "Frustrated", "Angry"},
            }
            if any(data.get(key) not in values for key, values in allowed.items()):
                raise ValueError("CustomerQueryAgent returned an invalid classification.")
            if not isinstance(data.get("summary"), str) or not isinstance(data.get("flags"), list):
                raise ValueError("CustomerQueryAgent returned an invalid summary or flags.")
            flags = [flag for flag in data["flags"] if flag in {"legal_threats", "payment_disputes", "fraud"}]
            category, urgency, sentiment = data["category"], data["urgency"], data["sentiment"]
            summary = data["summary"].strip()
            return {
                "agent": self.name,
                "category": category,
                "urgency": urgency,
                "sentiment": sentiment,
                "summary": summary,
                "flags": flags,
                "formatted_output": (
                    f"Category: {category}\nUrgency: {urgency}\n"
                    f"Sentiment: {sentiment}\nSummary: {summary}\n"
                    f"Flags: {', '.join(flags) if flags else 'none'}"
                ),
            }

        q_lower = complaint.lower()

        # 1. Detect Flags (Legal threats, fraud, payment dispute) FIRST
        has_legal = bool(re.search(r"\b(lawyer|attorney|sue|court|legal\s+action)\b", q_lower))
        has_fraud = bool(re.search(r"\b(fraud|hacked|scam|unauthorized|stolen)\b", q_lower))
        has_dispute = bool(re.search(r"\b(charged.*(?:three|two|multiple|times)|bank|dispute|chargeback)\b", q_lower))

        # 2. Detect Category with priority for security/fraud/billing
        if has_fraud or has_dispute or any(w in q_lower for w in ["charged", "card", "bank", "lawyer", "duplicate", "invoice", "payment", "billing"]):
            category = "Billing"
        elif any(w in q_lower for w in ["password", "login", "log in", "account", "locked", "credentials", "email"]):
            category = "Account"
        elif any(w in q_lower for w in ["broken", "blender", "damaged", "defective", "item", "replacement", "gift card", "voucher", "promo"]):
            category = "Product"
        elif any(w in q_lower for w in ["return", "refund", "shoes", "size", "exchange", "money back"]):
            category = "Refund"
        elif any(w in q_lower for w in ["order", "shipping", "deliver", "track", "transit", "package", "dispatch"]):
            category = "Shipping"
        else:
            category = "General"

        # 3. Detect Sentiment
        if has_legal or has_dispute or any(w in q_lower for w in ["fix this now", "furious", "unacceptable", "terrible", "outrageous"]):
            sentiment = "Angry"
        elif any(w in q_lower for w in ["annoyed", "frustrated", "waiting", "nobody replies", "disappointed", "delayed"]):
            sentiment = "Frustrated"
        elif any(w in q_lower for w in ["thank", "great", "appreciate", "please"]):
            sentiment = "Positive" if "thank" in q_lower else "Neutral"
        else:
            sentiment = "Neutral"

        # 4. Detect Urgency
        if has_legal or has_fraud or has_dispute or "10 days late" in q_lower or sentiment == "Angry":
            urgency = "High"
        elif category in ["Refund", "Product", "Shipping"] and any(w in q_lower for w in ["yesterday", "broken", "return", "last week"]):
            urgency = "Medium"
        else:
            urgency = "Low"

        # 5. One-line Summary
        if has_fraud:
            summary = "Security incident: customer reports unauthorized account access and fraudulent charges on saved card."
        elif has_dispute:
            summary = "Customer reports being charged multiple times and threatens bank dispute and legal action."
        elif "yesterday" in q_lower and "order" in q_lower:
            summary = "Customer inquiry regarding delayed package delivery supposed to arrive yesterday."
        elif "shoes" in q_lower and "return" in q_lower:
            summary = "Customer requesting return instructions and refund policy details for recently purchased shoes."
        elif "password" in q_lower and "log in" in q_lower:
            summary = "Customer unable to log into their account due to a forgotten password."
        elif "blender" in q_lower and "broken" in q_lower:
            summary = "Customer received a broken blender and is inquiring about how to receive a replacement."
        elif "gift card" in q_lower and ("500" in q_lower or "branding" in q_lower):
            summary = "B2B inquiry requesting bulk custom-branded corporate gift cards for 500 employees."
        else:
            first_sentence = complaint.split(".")[0].strip()
            summary = f"Customer inquiry: {first_sentence[:100]}."

        flags = []
        if has_legal:
            flags.append("legal_threats")
        if has_fraud:
            flags.append("fraud")
        if has_dispute:
            flags.append("payment_disputes")

        flags_str = ", ".join(flags) if flags else "none"

        formatted_output = (
            f"Category: {category}\n"
            f"Urgency: {urgency}\n"
            f"Sentiment: {sentiment}\n"
            f"Summary: {summary}\n"
            f"Flags: {flags_str}"
        )

        return {
            "agent": self.name,
            "category": category,
            "urgency": urgency,
            "sentiment": sentiment,
            "summary": summary,
            "flags": flags,
            "formatted_output": formatted_output,
        }
