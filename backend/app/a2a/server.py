
import os

import uvicorn
from starlette.applications import Starlette

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    create_agent_card_routes,
    create_jsonrpc_routes,
)
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
)

from backend.app.a2a.review_agent import ForensicReviewExecutor


HOST = "127.0.0.1"
PORT = int(os.getenv("CYBERGUARD_A2A_PORT", "8000"))
# Must match the address this process actually listens on, because the
# A2A client sends review requests to the URL published in this card.
BASE_URL = os.getenv("CYBERGUARD_A2A_URL", "http://127.0.0.1:8000/")

skill = AgentSkill(
    id="forensic_quality_review",
    name="Forensic Quality Review",
    description=(
        "Checks evidence references, hypothesis support and timeline "
        "consistency in a CyberGuard investigation."
    ),
    tags=["digital-forensics", "evidence-review", "timeline"],
    examples=[
        "Review this investigation for missing evidence references.",
        "Check whether verified hypotheses have linked evidence.",
    ],
)

agent_card = AgentCard(
    name="CyberGuard Forensic Review Agent",
    description=(
        "An independent agent that reviews the structural consistency "
        "of a CyberGuard forensic investigation."
    ),
    version="1.0.0",
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
    capabilities=AgentCapabilities(streaming=True),
    supported_interfaces=[
        AgentInterface(
            protocol_binding="JSONRPC",
            url=BASE_URL,
            protocol_version="1.0",
        )
    ],
    skills=[skill],
)

request_handler = DefaultRequestHandler(
    agent_executor=ForensicReviewExecutor(),
    task_store=InMemoryTaskStore(),
    agent_card=agent_card,
)

app = Starlette(
    routes=[
        *create_agent_card_routes(agent_card),
        *create_jsonrpc_routes(request_handler, "/"),
    ]
)


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
