from dataclasses import dataclass, field


@dataclass
class AgentReport:
    agent_name: str
    report_text: str
    metadata: dict = field(default_factory=dict)
