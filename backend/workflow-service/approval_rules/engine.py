"""
Approval Rules Engine
=====================
Configurable rules for invoice approval routing.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import json
import structlog

logger = structlog.get_logger(__name__)


class RuleOperator(str, Enum):
    """Comparison operators for rule conditions."""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_OR_EQUAL = "greater_or_equal"
    LESS_OR_EQUAL = "less_or_equal"
    CONTAINS = "contains"
    IN_LIST = "in_list"
    MATCHES_REGEX = "matches_regex"


class RuleAction(str, Enum):
    """Actions that rules can trigger."""
    REQUIRE_APPROVAL = "require_approval"
    ASSIGN_TO = "assign_to"
    AUTO_APPROVE = "auto_approve"
    AUTO_REJECT = "auto_reject"
    ESCALATE = "escalate"
    ADD_TAG = "add_tag"
    SET_PRIORITY = "set_priority"
    SEND_NOTIFICATION = "send_notification"


@dataclass
class RuleCondition:
    """A single condition in a rule."""
    field: str  # e.g., "amount", "vendor.risk_level"
    operator: RuleOperator
    value: Any
    
    def evaluate(self, data: Dict[str, Any]) -> bool:
        """Evaluate condition against invoice data."""
        # Get field value (supports nested fields like "vendor.name")
        field_value = data
        for part in self.field.split("."):
            if isinstance(field_value, dict):
                field_value = field_value.get(part)
            else:
                field_value = None
                break
        
        if field_value is None:
            return False
        
        # Evaluate based on operator
        if self.operator == RuleOperator.EQUALS:
            return field_value == self.value
        elif self.operator == RuleOperator.NOT_EQUALS:
            return field_value != self.value
        elif self.operator == RuleOperator.GREATER_THAN:
            return float(field_value) > float(self.value)
        elif self.operator == RuleOperator.LESS_THAN:
            return float(field_value) < float(self.value)
        elif self.operator == RuleOperator.GREATER_OR_EQUAL:
            return float(field_value) >= float(self.value)
        elif self.operator == RuleOperator.LESS_OR_EQUAL:
            return float(field_value) <= float(self.value)
        elif self.operator == RuleOperator.CONTAINS:
            return str(self.value).lower() in str(field_value).lower()
        elif self.operator == RuleOperator.IN_LIST:
            return field_value in self.value
        
        return False


@dataclass
class ApprovalRule:
    """A complete approval rule with conditions and actions."""
    id: str
    name: str
    description: str
    conditions: List[RuleCondition]
    condition_logic: str = "AND"  # AND or OR
    actions: List[Dict[str, Any]]  # Action type + parameters
    priority: int = 0  # Higher = evaluated first
    active: bool = True
    
    def matches(self, data: Dict[str, Any]) -> bool:
        """Check if invoice matches rule conditions."""
        if not self.conditions:
            return True
        
        results = [c.evaluate(data) for c in self.conditions]
        
        if self.condition_logic == "AND":
            return all(results)
        else:  # OR
            return any(results)


class ApprovalRulesEngine:
    """
    Engine for evaluating and applying approval rules.
    
    Features:
    - Configurable rule definitions
    - Amount-based routing
    - Vendor risk-based escalation
    - Department-based assignment
    - Auto-approval for low-risk invoices
    """
    
    def __init__(self):
        self._rules: Dict[str, ApprovalRule] = {}
        self._load_default_rules()
    
    def _load_default_rules(self):
        """Load default approval rules."""
        default_rules = [
            ApprovalRule(
                id="auto_approve_low",
                name="Auto-approve small amounts",
                description="Auto-approve invoices under $500 from verified vendors",
                conditions=[
                    RuleCondition("total_amount", RuleOperator.LESS_THAN, 500),
                    RuleCondition("vendor.is_verified", RuleOperator.EQUALS, True),
                ],
                actions=[
                    {"type": RuleAction.AUTO_APPROVE}
                ],
                priority=100,
            ),
            ApprovalRule(
                id="manager_approval",
                name="Manager approval required",
                description="Require manager approval for amounts $500-$5000",
                conditions=[
                    RuleCondition("total_amount", RuleOperator.GREATER_OR_EQUAL, 500),
                    RuleCondition("total_amount", RuleOperator.LESS_THAN, 5000),
                ],
                actions=[
                    {"type": RuleAction.REQUIRE_APPROVAL, "level": "manager"}
                ],
                priority=90,
            ),
            ApprovalRule(
                id="director_approval",
                name="Director approval required",
                description="Require director approval for amounts $5000-$25000",
                conditions=[
                    RuleCondition("total_amount", RuleOperator.GREATER_OR_EQUAL, 5000),
                    RuleCondition("total_amount", RuleOperator.LESS_THAN, 25000),
                ],
                actions=[
                    {"type": RuleAction.REQUIRE_APPROVAL, "level": "director"}
                ],
                priority=80,
            ),
            ApprovalRule(
                id="executive_approval",
                name="Executive approval required",
                description="Require VP/CFO approval for amounts over $25000",
                conditions=[
                    RuleCondition("total_amount", RuleOperator.GREATER_OR_EQUAL, 25000),
                ],
                actions=[
                    {"type": RuleAction.REQUIRE_APPROVAL, "level": "executive"},
                    {"type": RuleAction.SET_PRIORITY, "priority": "high"},
                ],
                priority=70,
            ),
            ApprovalRule(
                id="high_risk_vendor",
                name="High risk vendor escalation",
                description="Escalate invoices from high-risk vendors",
                conditions=[
                    RuleCondition("vendor.risk_level", RuleOperator.EQUALS, "high"),
                ],
                actions=[
                    {"type": RuleAction.ESCALATE, "to": "finance_manager"},
                    {"type": RuleAction.ADD_TAG, "tag": "high_risk_vendor"},
                ],
                priority=150,
            ),
        ]
        
        for rule in default_rules:
            self._rules[rule.id] = rule
    
    def add_rule(self, rule: ApprovalRule) -> None:
        """Add or update a rule."""
        self._rules[rule.id] = rule
        logger.info("Rule added", rule_id=rule.id, name=rule.name)
    
    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule."""
        if rule_id in self._rules:
            del self._rules[rule_id]
            return True
        return False
    
    def evaluate(
        self,
        invoice_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Evaluate all rules against invoice data.
        
        Returns:
            List of actions to take
        """
        actions = []
        
        # Sort rules by priority (descending)
        sorted_rules = sorted(
            [r for r in self._rules.values() if r.active],
            key=lambda r: r.priority,
            reverse=True
        )
        
        for rule in sorted_rules:
            if rule.matches(invoice_data):
                logger.info(
                    "Rule matched",
                    rule_id=rule.id,
                    rule_name=rule.name,
                )
                
                for action in rule.actions:
                    actions.append({
                        "rule_id": rule.id,
                        "rule_name": rule.name,
                        **action
                    })
                
                # Check for terminal actions
                if any(a.get("type") in [RuleAction.AUTO_APPROVE, RuleAction.AUTO_REJECT] 
                       for a in rule.actions):
                    break
        
        return actions
    
    def get_required_approvers(
        self,
        invoice_data: Dict[str, Any],
    ) -> List[str]:
        """Get list of required approver levels."""
        actions = self.evaluate(invoice_data)
        approvers = []
        
        for action in actions:
            if action.get("type") == RuleAction.REQUIRE_APPROVAL:
                level = action.get("level", "default")
                if level not in approvers:
                    approvers.append(level)
        
        return approvers
    
    def load_rules_from_json(self, json_path: str) -> int:
        """Load rules from a JSON file."""
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
            
            count = 0
            for rule_data in data.get("rules", []):
                conditions = [
                    RuleCondition(
                        field=c["field"],
                        operator=RuleOperator(c["operator"]),
                        value=c["value"]
                    )
                    for c in rule_data.get("conditions", [])
                ]
                
                rule = ApprovalRule(
                    id=rule_data["id"],
                    name=rule_data["name"],
                    description=rule_data.get("description", ""),
                    conditions=conditions,
                    condition_logic=rule_data.get("condition_logic", "AND"),
                    actions=rule_data.get("actions", []),
                    priority=rule_data.get("priority", 0),
                    active=rule_data.get("active", True),
                )
                self._rules[rule.id] = rule
                count += 1
            
            logger.info("Rules loaded from JSON", count=count, path=json_path)
            return count
            
        except Exception as e:
            logger.error("Failed to load rules", error=str(e), path=json_path)
            return 0


# Default engine instance
approval_rules_engine = ApprovalRulesEngine()
