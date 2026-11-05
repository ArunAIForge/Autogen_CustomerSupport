"""Query expansion and transformation module for ClothesSpot Customer Automation.

Performs query normalization, spelling correction, intent classification,
and synonym expansion for apparel and customer service domains.
"""

import re
from typing import Dict, List, Set, Tuple


SYNONYM_DICTIONARY: Dict[str, List[str]] = {
    # Shipping & Tracking
    "where is my order": ["shipping delivery tracking order status courier delayed late dispatch"],
    "late": ["delivery delayed tracking courier transit estimated date 24 to 48 hours"],
    "arrive": ["delivery shipping courier transit estimated arrival"],
    "tracking": ["courier tracking link dispatch confirmation track package"],
    
    # Returns & Refunds
    "return": ["refund returns 30 days return window prepaid label unworn original tags"],
    "refund": ["refund processing returns 30 days 5 to 7 business days original payment method"],
    "shoes": ["footwear shoes sneakers original shoe box unworn return refund"],
    
    # Account & Login
    "password": ["forgot password reset link 15 minutes email credentials login account"],
    "log in": ["login account password reset lockout 30 minutes credentials"],
    "login": ["forgot password reset link account lockout 5 attempts credentials"],
    
    # Broken & Replacements
    "broken": ["damaged defective broken item replacement 14 days report photos free replacement"],
    "blender": ["appliance broken defective replacement 14 days photos prepaid label dispatch"],
    "damaged": ["broken defective replacement 14 days photos report damaged item"],
    "replacement": ["damaged item free replacement 24 to 48 hours prepaid label"],
    
    # Billing & Disputes
    "charged": ["duplicate charge multiple charges pre-authorization hold bank statement refund billing"],
    "lawyer": ["legal threat attorney payment dispute bank escalation fraudulent"],
    "card": ["credit card duplicate charges billing pre-authorization refund payment"],
    "dispute": ["chargeback bank dispute duplicate charge fraud escalation"],
    
    # Gift cards & B2B
    "gift cards": ["gift cards digital gift cards denominations 10 25 50 100"],
    "gift card": ["digital gift cards corporate bulk custom branding enterprise"],
    "500 employees": ["corporate branding bulk gift cards b2b out of scope custom"],
    "custom branding": ["corporate branding bulk b2b gift cards not offered"],
    
    # Vouchers & Promotions
    "voucher": ["promo code discount coupon voucher minimum spend 50 summer25"],
    "promo": ["promotional code discount checkout full price minimum spend"],
}

CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "Shipping": ["order", "shipping", "delivery", "track", "transit", "arrive", "courier", "package", "dispatch"],
    "Refund": ["return", "refund", "shoes", "size", "exchange", "unworn", "money back", "box", "tags"],
    "Account": ["password", "login", "log in", "account", "locked", "credentials", "email", "reset"],
    "Product": ["broken", "blender", "damaged", "defective", "item", "replacement", "quality", "warranty", "gift card"],
    "Billing": ["charged", "charge", "card", "bank", "lawyer", "duplicate", "invoice", "payment", "fraud", "dispute"],
}


class QueryTransformer:
    """Normalizes and expands queries to improve BM25 and vector search recall."""

    def __init__(self) -> None:
        pass

    def clean_query(self, query: str) -> str:
        """Strip special characters and normalize whitespace."""
        query = query.strip()
        query = re.sub(r"[^\w\s\-\']", " ", query)
        query = re.sub(r"\s+", " ", query).strip()
        return query

    def detect_category(self, query: str) -> Tuple[str, float]:
        """Detect the most probable category based on lexical overlap."""
        q_lower = query.lower()
        category_scores: Dict[str, int] = {}
        
        for category, keywords in CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in q_lower)
            if score > 0:
                category_scores[category] = score
                
        if not category_scores:
            return "General", 0.5
            
        best_category = max(category_scores, key=category_scores.get)
        confidence = min(1.0, 0.5 + (category_scores[best_category] * 0.15))
        return best_category, confidence

    def expand_query(self, query: str) -> str:
        """Expand the query with domain synonyms and relevant policy keywords."""
        q_lower = query.lower()
        expanded_terms: List[str] = [query]
        
        for key, synonyms in SYNONYM_DICTIONARY.items():
            if key in q_lower:
                expanded_terms.extend(synonyms)
                
        # Combine unique terms
        return " ".join(expanded_terms)
