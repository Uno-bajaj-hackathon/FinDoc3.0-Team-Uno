"""
Policy comparison and gap analysis functionality
"""

from typing import Dict, List, Any, Tuple
from .ingestion import Clause
from .risk_engine import RiskAssessmentEngine
from .vector_store import get_vector_store

class PolicyAnalyzer:
    def __init__(self, risk_engine: RiskAssessmentEngine):
        self.risk_engine = risk_engine
    
    def compare_policies(self, question: str, all_clauses: List[Clause]) -> Dict[str, Any]:
        """Compare how different policies handle the same question"""
        # Group clauses by policy (doc_id)
        policies = {}
        for clause in all_clauses:
            policy_id = clause.id.split('_')[0]  # Extract policy ID from clause ID
            if policy_id not in policies:
                policies[policy_id] = []
            policies[policy_id].append(clause)
        
        if len(policies) < 2:
            return {"error": "Need at least 2 policies for comparison", "policies_found": len(policies)}
        
        # Analyze each policy for the question
        comparison_results = {}
        vector_store = get_vector_store()
        
        for policy_id, policy_clauses in policies.items():
            # Add clauses to search
            vector_store.add_clauses(policy_clauses)
            
            # Search within this policy context
            relevant_clauses = vector_store.search(question, k=3)
            clause_objects = [clause for clause, _, _ in relevant_clauses]
            
            # Risk assessment for this policy
            risk_analysis = self.risk_engine.assess_claim_risk(clause_objects, question)
            
            comparison_results[policy_id] = {
                "claim_probability": risk_analysis["claim_probability"],
                "estimated_payout": risk_analysis["estimated_payout"],
                "waiting_period": risk_analysis.get("waiting_period_status", "Unknown"),
                "risk_factors": risk_analysis["risk_factors"],
                "relevant_clauses": len(clause_objects),
                "top_clause": clause_objects[0].text[:200] + "..." if clause_objects else "No relevant clauses found"
            }
        
        # Generate comparison summary
        best_policy = max(comparison_results.keys(), 
                         key=lambda k: comparison_results[k]["claim_probability"])
        
        return {
            "question": question,
            "policies_compared": len(policies),
            "detailed_comparison": comparison_results,
            "recommendation": {
                "best_policy": best_policy,
                "reason": f"Highest claim probability ({comparison_results[best_policy]['claim_probability']:.0%})",
                "coverage_advantage": comparison_results[best_policy]["estimated_payout"]
            }
        }
    
    def find_coverage_gaps(self, all_clauses: List[Clause]) -> Dict[str, Any]:
        """Identify coverage gaps and advantages between policies"""
        # Group by policy
        policies = {}
        for clause in all_clauses:
            policy_id = clause.id.split('_')[0]
            if policy_id not in policies:
                policies[policy_id] = []
            policies[policy_id].append(clause)
        
        if len(policies) < 2:
            return {"error": "Need at least 2 policies for gap analysis", "policies_found": len(policies)}
        
        # Common coverage areas to analyze
        coverage_areas = [
            "maternity", "dental", "eye care", "mental health", 
            "pre-existing", "surgery", "emergency", "ambulance",
            "room rent", "ICU", "daycare", "AYUSH"
        ]
        
        gap_analysis = {}
        vector_store = get_vector_store()
        
        for area in coverage_areas:
            area_coverage = {}
            
            for policy_id, policy_clauses in policies.items():
                # Add clauses to search
                vector_store.add_clauses(policy_clauses)
                relevant = vector_store.search(area, k=2)
                
                if relevant and len(relevant) > 0 and relevant[0][1] > 0.3:  # Relevance threshold
                    area_coverage[policy_id] = {
                        "covered": True,
                        "details": relevant[0][0].text[:150] + "...",
                        "confidence": relevant[0][1]
                    }
                else:
                    area_coverage[policy_id] = {
                        "covered": False,
                        "details": "No specific coverage found",
                        "confidence": 0.0
                    }
            
            gap_analysis[area] = area_coverage
        
        # Identify clear gaps
        coverage_gaps = {}
        
        for area, coverage in gap_analysis.items():
            covered_policies = [pid for pid, info in coverage.items() if info["covered"]]
            uncovered_policies = [pid for pid, info in coverage.items() if not info["covered"]]
            
            if len(covered_policies) > 0 and len(uncovered_policies) > 0:
                coverage_gaps[area] = {
                    "covered_by": covered_policies,
                    "missing_in": uncovered_policies,
                    "impact": "high" if area in ["surgery", "emergency", "ICU"] else "medium"
                }
        
        return {
            "total_policies_analyzed": len(policies),
            "coverage_areas_checked": len(coverage_areas),
            "identified_gaps": coverage_gaps,
            "summary": {
                "major_gaps": len([g for g in coverage_gaps.values() if g["impact"] == "high"]),
                "minor_gaps": len([g for g in coverage_gaps.values() if g["impact"] == "medium"]),
                "total_gaps": len(coverage_gaps)
            }
        }
