"""Tests for multi-agent orchestrator."""
from dhybrid.agent.orchestrator import Orchestrator, TaskPlan


def test_task_plan_creation():
    """Test TaskPlan dataclass creation."""
    plan = TaskPlan(
        tasks=[
            {"role": "planner", "goal": "Analyze requirements"},
            {"role": "executor", "goal": "Implement solution"},
            {"role": "reviewer", "goal": "Review and verify"},
        ]
    )
    assert len(plan.tasks) == 3
    roles = [t["role"] for t in plan.tasks]
    assert "planner" in roles
    assert "executor" in roles
    assert "reviewer" in roles


def test_task_plan_serialization():
    """Test TaskPlan can be serialized to dict."""
    plan = TaskPlan(
        tasks=[
            {"role": "planner", "goal": "Analyze requirements", "priority": 1},
            {"role": "executor", "goal": "Implement solution", "priority": 2},
            {"role": "reviewer", "goal": "Review and verify", "priority": 3},
        ]
    )
    data = plan.to_dict()
    assert "tasks" in data
    assert len(data["tasks"]) == 3


def test_orchestrator_initialization():
    """Test Orchestrator can be initialized with client factory and tools."""
    from dhybrid.tools.registry import ToolRegistry
    
    def dummy_factory(preset):
        return None
    
    tools = ToolRegistry()
    orch = Orchestrator(client_factory=dummy_factory, tools=tools)
    assert orch.client_factory is dummy_factory
    assert orch.tools is tools