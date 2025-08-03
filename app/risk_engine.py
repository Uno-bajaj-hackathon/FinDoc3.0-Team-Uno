"""
Financial risk assessment and business intelligence.
✓ Calculate claim probability and payout estimates
✓ Identify risk factors and waiting periods
✓ Generate actionable insights
"""

import re
from typing import Dict, List, Any
from .ingestion import Clause

class RiskAssessmentEngine:
    
    def assess_claim_risk(self, relevant_clauses: List[Clause], question: str) -> Dict[str, Any]:
        """Calculate comprehensive risk assessment"""
        
        # Extract key information from clauses
        combined_text = " ".join([clause.text for clause in relevant_clauses])
        
        # Parse financial amounts
        amounts = self._extract_amounts(combined_text)
        
        # Check waiting periods
        waiting_info = self._check_waiting_periods(combined_text, question)
        
        # Identify risk factors
        risk_factors = self._identify_risk_factors(combined_text, question)
        
        # Calculate probability
        probability = self._calculate_probability(waiting_info, risk_factors, combined_text)
        
        return {
            "claim_probability": probability,
            "estimated_payout": amounts.get("max_payout", "Coverage limit dependent"),
            "waiting_period_status": waiting_info,
            "risk_factors": risk_factors,
            "coverage_limits": amounts,
            "confidence_score": min(0.95, probability + 0.1)
        }
    
    def _extract_amounts(self, text: str) -> Dict[str, str]:
        """Extract monetary amounts and limits"""
        amounts = {}
        
        # Look for sum insured, limits, etc.
        sum_patterns = [
            r"sum insured[:\s]+(?:rs\.?\s*|₹\s*)?(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:lakh|crore|thousand)?",
            r"coverage[:\s]+(?:rs\.?\s*|₹\s*)?(\d+(?:,\d+)*(?:\.\d+)?)",
            r"limit[:\s]+(?:rs\.?\s*|₹\s*)?(\d+(?:,\d+)*(?:\.\d+)?)"
        ]
        
        for pattern in sum_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                amounts["max_payout"] = f"₹{matches[0]} (subject to policy terms)"
                break
        
        return amounts
    
    def _check_waiting_periods(self, text: str, question: str) -> Dict[str, Any]:
        """Check if waiting periods apply"""
        waiting_patterns = [
            r"waiting period[:\s]+(\d+)\s*(months?|years?)",
            r"(\d+)\s*(months?|years?)\s+waiting period",
            r"after completion of\s+(\d+)\s*(months?|years?)"
        ]
        
        for pattern in waiting_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                period, unit = matches[0]
                months = int(period) * (12 if 'year' in unit else 1)
                return {
                    "required_months": months,
                    "status": "Check policy start date",
                    "description": f"{period} {unit} waiting period applies"
                }
        
        return {"status": "No waiting period found", "required_months": 0}
    
    def _identify_risk_factors(self, text: str, question: str) -> List[str]:
        """Identify potential claim risk factors"""
        factors = []
        
        # Check for common exclusions/conditions
        risk_keywords = {
            "pre-existing": "Pre-existing condition clause",
            "exclusion": "Policy exclusions may apply", 
            "maternity": "Maternity-specific conditions",
            "surgery": "Surgical procedure requirements",
            "emergency": "Emergency treatment protocols"
        }
        
        for keyword, description in risk_keywords.items():
            if keyword in text.lower() or keyword in question.lower():
                factors.append(description)
        
        return factors[:3]  # Limit to top 3 factors
    
    def _calculate_probability(self, waiting_info: Dict, risk_factors: List, text: str) -> float:
        """Calculate claim approval probability"""
        base_probability = 0.75
        
        # Adjust for waiting periods
        if waiting_info.get("required_months", 0) > 0:
            base_probability -= 0.15
        
        # Adjust for risk factors
        base_probability -= len(risk_factors) * 0.05
        
        # Boost if coverage seems clear
        if "covered" in text.lower() and "not covered" not in text.lower():
            base_probability += 0.10
        
        return max(0.1, min(0.95, base_probability))
