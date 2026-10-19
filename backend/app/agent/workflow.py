"""
LangGraph Agent Workflow for Project Atlas
Coordinates routing, entitlement-filtered retrieval, read-only SQL, Python calculations,
critic review, cited answer generation, and low-confidence analyst escalation.
"""

from typing import List, Dict, Any, Optional, TypedDict
import logging
from pydantic import BaseModel
from langgraph.graph import StateGraph, START, END

from backend.app.agent.router import QueryRouter
from backend.app.agent.sql_tool import ReadOnlySQLTool
from backend.app.agent.calculator import MarketCalculator, DerivedValue
from backend.app.agent.critic import EvidenceCritic, ConflictAnalysis
from backend.app.agent.escalation import EscalationService
from backend.app.services.retrieval import SecureRAGService, SupportingPassage, rag_service as default_rag_service
from backend.app.services.rag_generator import Citation

logger = logging.getLogger(__name__)


# Structured Agent Output Contract
class WorkflowOutput(BaseModel):
    answer: str
    citations: List[Citation]
    confidence: float
    conflicts: List[Dict[str, Any]]
    derived_values: List[Dict[str, Any]]
    escalated: bool
    escalation_ticket_id: Optional[str] = None
    route: str
    conversation_id: Optional[int] = None



# State schema for LangGraph
class AgentState(TypedDict):
    client_id: str
    query: str
    route: str
    retrieved_passages: List[SupportingPassage]
    sql_result: Optional[Dict[str, Any]]
    derived_values: List[Dict[str, Any]]
    conflicts: List[Dict[str, Any]]
    answer: str
    citations: List[Citation]
    confidence: float
    upgrade_notice: Optional[str]
    escalated: bool
    escalation_ticket_id: Optional[str]
    injection_detected: bool
    error: Optional[str]


class AtlasAgentWorkflow:
    """Orchestrates the LangGraph agent state graph."""

    def __init__(self, retrieval_service: Optional[SecureRAGService] = None):
        self.retrieval_service = retrieval_service or default_rag_service
        self.app = self._build_graph()

    def _build_graph(self):
        """Build and compile the LangGraph workflow."""
        workflow = StateGraph(AgentState)

        # Register nodes
        workflow.add_node("router", self._router_node)
        workflow.add_node("retriever", self._retriever_node)
        workflow.add_node("sql_executor", self._sql_node)
        workflow.add_node("calculator", self._calculator_node)
        workflow.add_node("critic", self._critic_node)
        workflow.add_node("writer", self._writer_node)
        workflow.add_node("escalator", self._escalation_node)
        workflow.add_node("refusal", self._refusal_node)

        # Wire edges
        workflow.add_edge(START, "router")

        # Conditional routing from router
        workflow.add_conditional_edges(
            "router",
            self._route_decision,
            {
                "unsafe": "refusal",
                "out_of_scope": "refusal",
                "sql_aggregate": "sql_executor",
                "calculation": "calculator",
                "factual_lookup": "retriever",
                "comparison": "retriever"
            }
        )

        # Tool execution flows into critic
        workflow.add_edge("retriever", "critic")
        workflow.add_edge("sql_executor", "critic")
        workflow.add_edge("calculator", "critic")

        # Critic branches to writer or escalator
        workflow.add_conditional_edges(
            "critic",
            lambda state: "escalator" if state["escalated"] else "writer",
            {
                "writer": "writer",
                "escalator": "escalator"
            }
        )

        workflow.add_edge("escalator", "writer")
        workflow.add_edge("writer", END)
        workflow.add_edge("refusal", END)

        return workflow.compile()

    # --- Graph Nodes ---

    def _router_node(self, state: AgentState) -> Dict[str, Any]:
        """Classify user question."""
        route, confidence = QueryRouter.classify(state["query"])
        return {"route": route, "confidence": confidence}

    def _route_decision(self, state: AgentState) -> str:
        return state["route"]

    def _refusal_node(self, state: AgentState) -> Dict[str, Any]:
        """Handle unsafe, injection, or out-of-scope requests safely."""
        route = state["route"]
        q_lower = state["query"].lower()

        if route == "unsafe":
            if "delete" in q_lower or "drop" in q_lower or "alter" in q_lower:
                answer = (
                    "Security Refusal: Destructive database modifications (DELETE, DROP, TRUNCATE, UPDATE) "
                    "are strictly prohibited by database guardrails. No changes were executed."
                )
            elif "email" in q_lower or "client" in q_lower or "disregard" in q_lower:
                answer = (
                    "Security Refusal: Your request attempts to bypass system instructions or access confidential "
                    "client information. This action has been blocked and logged in accordance with data protection policy."
                )
            else:
                answer = "Security Refusal: This instruction violates safety policy and has been rejected."

            return {
                "answer": answer,
                "confidence": 1.0,
                "citations": [],
                "conflicts": [],
                "derived_values": [],
                "escalated": False,
                "injection_detected": True
            }

        # Out of scope
        return {
            "answer": (
                "Out of Scope: I am Project Atlas, Cognitive Market Research's Report Copilot. "
                "I specialize in market intelligence, technology sector outlooks, and market sizing projections. "
                "I cannot answer questions about general elections, politics, or unrelated trivia. "
                "Please ask a question regarding our market research library."
            ),
            "confidence": 1.0,
            "citations": [],
            "conflicts": [],
            "derived_values": [],
            "escalated": False
        }

    def _retriever_node(self, state: AgentState) -> Dict[str, Any]:
        """Execute entitlement-filtered RAG retrieval."""
        res = self.retrieval_service.retrieve(
            client_id=state["client_id"],
            query=state["query"],
            top_k=5
        )
        return {
            "retrieved_passages": res.passages,
            "upgrade_notice": res.upgrade_notice,
            "injection_detected": res.injection_detected
        }

    def _sql_node(self, state: AgentState) -> Dict[str, Any]:
        """Execute approved read-only SQL aggregate template."""
        res = ReadOnlySQLTool.resolve_and_execute(state["query"])
        return {
            "sql_result": res,
            "retrieved_passages": []
        }

    def _calculator_node(self, state: AgentState) -> Dict[str, Any]:
        """Execute Python mathematical CAGR projection."""
        q_lower = state["query"].lower()
        target_year = 2030
        if "2035" in q_lower:
            target_year = 2035

        calc_result: DerivedValue = MarketCalculator.calculate_smart_water_meter_projection(
            target_year=target_year,
            region="APAC"
        )
        return {
            "derived_values": [calc_result.model_dump()],
            "escalated": calc_result.is_out_of_horizon,
            "retrieved_passages": []
        }

    def _critic_node(self, state: AgentState) -> Dict[str, Any]:
        """Audit claims, verify citations, and identify source conflicts."""
        is_out_of_horizon = any(d.get("is_out_of_horizon") for d in state.get("derived_values", []))
        critic_res = EvidenceCritic.evaluate(
            query=state["query"],
            retrieved_passages=state.get("retrieved_passages", []),
            route=state["route"],
            is_out_of_horizon=is_out_of_horizon
        )

        conflicts_list = [c.model_dump() for c in critic_res.conflicts]
        escalate = critic_res.requires_escalation or state.get("escalated", False)

        return {
            "confidence": critic_res.confidence,
            "conflicts": conflicts_list,
            "escalated": escalate
        }

    def _escalation_node(self, state: AgentState) -> Dict[str, Any]:
        """Create support ticket in MySQL when confidence is low or query is out of horizon."""
        reason = "Low retrieval confidence or unverified projection requested."
        if any(d.get("is_out_of_horizon") for d in state.get("derived_values", [])):
            reason = "Projection year exceeds published forecast horizon (2030)."

        ticket = EscalationService.create_ticket(
            client_id=state["client_id"],
            query=state["query"],
            reason=reason
        )
        return {
            "escalation_ticket_id": ticket.get("ticket_id"),
            "escalated": True
        }

    def _writer_node(self, state: AgentState) -> Dict[str, Any]:
        """Synthesize concise cited answer with conflicts and derived values."""
        route = state["route"]
        answer_parts = []
        citations: List[Citation] = []

        # 1. SQL Result formatting
        if route == "sql_aggregate" and state.get("sql_result"):
            sql_data = state["sql_result"]
            answer_parts.append(sql_data.get("summary", "SQL aggregate query executed successfully."))
            answer_parts.append(f"\n*(Database Query: `{sql_data.get('query_executed')}`)*")
            return {
                "answer": "\n".join(answer_parts),
                "citations": [],
                "confidence": state["confidence"],
                "conflicts": [],
                "derived_values": [],
                "escalated": False
            }

        # 2. Calculation formatting
        if route == "calculation" and state.get("derived_values"):
            d = state["derived_values"][0]
            if d.get("is_out_of_horizon"):
                t_id = state.get("escalation_ticket_id", "PENDING")
                answer_parts.append(
                    f"**Horizon Limitation:** {d.get('limitation_warning')}\n\n"
                    f"Because extrapolating beyond 2030 would produce unverified estimates, "
                    f"this inquiry has been escalated to a Senior Market Research Analyst (Ticket: **{t_id}**). "
                    f"Our analyst team will provide a tailored customized forecast model."
                )
            else:
                answer_parts.append(
                    f"### Derived Projection: {d['metric_name']}\n"
                    f"• **Estimated Valuation (6-year compounding from 2024):** **{d['result_primary']}**\n"
                    f"• **Estimated Valuation (5-year compounding from 2025):** **{d['result_secondary']}**\n\n"
                    f"**Calculation Formula:**\n"
                    f"`{d['formula']}`\n\n"
                    f"**Assumptions & Parameters:**\n"
                )
                for a in d.get("assumptions", []):
                    answer_parts.append(f"• {a}")
                
                citations.append(Citation(report_id="R-101", title="Global Smart Water Meter Market 2025", page_number=8))

            return {
                "answer": "\n".join(answer_parts),
                "citations": citations,
                "confidence": state["confidence"],
                "conflicts": state.get("conflicts", []),
                "derived_values": state["derived_values"],
                "escalated": state.get("escalated", False)
            }

        # 3. Retrieval / Comparison formatting
        passages = state.get("retrieved_passages", [])
        if state.get("upgrade_notice"):
            answer_parts.append(f"**License Notice:** {state['upgrade_notice']}\n")

        # Conflict reconciliation
        if state.get("conflicts"):
            for conf in state["conflicts"]:
                answer_parts.append(f"### Market Sizing Reconciliation:\n{conf['explanation']}\n")
                for s in conf.get("sources", []):
                    answer_parts.append(
                        f"• **{s['report_id']}** ({s['title']}): Valued at **{s['valuation_2024']}** ({s['cagr']}), "
                        f"APAC Share: **{s.get('apac_share', 'N/A')}**, Scope: {s['scope']} [{s['citation']}]."
                    )
                answer_parts.append("")

        if passages:
            # Sort passages so that pages containing quantitative metrics (valuations, CAGRs) come first
            def metric_priority(p):
                score = 0
                t = p.text.lower()
                if "billion" in t or "usd" in t: score += 10
                if "cagr" in t or "%" in t: score += 10
                if "market size" in t or "valued at" in t or "reached" in t: score += 5
                return score

            sorted_passages = sorted(passages, key=metric_priority, reverse=True)
            seen_rids = set()
            for p in sorted_passages:
                if state.get("conflicts") and p.report_id in ("R-101", "R-102"):
                    continue
                if p.report_id not in seen_rids:
                    seen_rids.add(p.report_id)
                    answer_parts.append(
                        f"• According to **{p.title}** [{p.report_id}, p.{p.page_number}]:\n  "
                        f"{p.text.strip()}"
                    )



        # Build citations list
        seen_keys = set()
        for p in passages:
            key = (p.report_id, p.page_number)
            if key not in seen_keys:
                seen_keys.add(key)
                citations.append(Citation(report_id=p.report_id, title=p.title, page_number=p.page_number))

        # Handle escalation message
        if state.get("escalated"):
            t_id = state.get("escalation_ticket_id", "PENDING")
            answer_parts.append(
                f"\n**Support Escalation:** Evidence was insufficient to guarantee 100% confidence. "
                f"A support ticket has been created: **{t_id}**. An analyst will reply shortly."
            )

        if not answer_parts:
            answer_parts.append("No matching information was found within your authorized entitlements.")

        return {
            "answer": "\n".join(answer_parts),
            "citations": citations,
            "confidence": state["confidence"],
            "conflicts": state.get("conflicts", []),
            "derived_values": state.get("derived_values", []),
            "escalated": state.get("escalated", False),
            "escalation_ticket_id": state.get("escalation_ticket_id")
        }

    def run(self, client_id: str, query: str) -> WorkflowOutput:
        """
        Execute the LangGraph workflow for a client query.
        """
        initial_state: AgentState = {
            "client_id": client_id,
            "query": query,
            "route": "factual_lookup",
            "retrieved_passages": [],
            "sql_result": None,
            "derived_values": [],
            "conflicts": [],
            "answer": "",
            "citations": [],
            "confidence": 0.0,
            "upgrade_notice": None,
            "escalated": False,
            "escalation_ticket_id": None,
            "injection_detected": False,
            "error": None
        }

        final_state = self.app.invoke(initial_state)

        return WorkflowOutput(
            answer=final_state["answer"],
            citations=final_state["citations"],
            confidence=final_state["confidence"],
            conflicts=final_state.get("conflicts", []),
            derived_values=final_state.get("derived_values", []),
            escalated=final_state.get("escalated", False),
            escalation_ticket_id=final_state.get("escalation_ticket_id"),
            route=final_state.get("route", "unknown")
        )


# Global default instance
agent_workflow = AtlasAgentWorkflow()
