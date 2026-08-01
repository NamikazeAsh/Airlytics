import asyncio
import datetime
import json
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.ai_coach.coach_service import send_message
from app.ai_coach.context_builder import build_system_prompt
from app.storage.models import Base
from app.storage.repositories.conversation_repository import ConversationRepository
from evals.cases import get_eval_cases
from evals.scorer import check_grounding, score_tool_calls
from evals.seed_data import seed_synthetic_data

RESULTS_DIR = Path(__file__).parent / "results"


async def run_eval() -> dict:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    case_results = []
    async with session_factory() as session:
        await seed_synthetic_data(session)
        system_prompt = await build_system_prompt(session)

        cases = get_eval_cases()
        print(f"Running {len(cases)} eval cases against the configured Groq model...\n")

        for case in cases:
            result = await send_message(session, None, case.question)
            messages = await ConversationRepository(session).get_messages(result["conversation_id"])
            tool_evidence = "\n".join(m.content for m in messages if m.role == "tool" and m.content)
            evidence = f"{system_prompt}\n{tool_evidence}\n{case.question}"

            tool_ok = score_tool_calls(case.expected_tools, result["tool_calls_used"])
            grounding = check_grounding(result["reply"] or "", evidence)

            print(f'[{case.id}] "{case.question}"')
            print(
                f"  tool calls: {'OK' if tool_ok else 'MISMATCH'} (expected {case.expected_tools}, "
                f"got {result['tool_calls_used']})"
            )
            print(f"  grounding:  {'OK' if grounding.is_grounded else f'FLAGGED {grounding.ungrounded_numbers}'}\n")

            case_results.append(
                {
                    "id": case.id,
                    "question": case.question,
                    "expected_tools": case.expected_tools,
                    "actual_tools": result["tool_calls_used"],
                    "tool_call_correct": tool_ok,
                    "reply": result["reply"],
                    "is_grounded": grounding.is_grounded,
                    "ungrounded_numbers": grounding.ungrounded_numbers,
                }
            )

    await engine.dispose()

    n = len(case_results)
    tool_call_accuracy = round(sum(r["tool_call_correct"] for r in case_results) / n, 3)
    grounding_accuracy = round(sum(r["is_grounded"] for r in case_results) / n, 3)

    report = {
        "run_at": datetime.datetime.now().isoformat(),
        "n_cases": n,
        "tool_call_accuracy": tool_call_accuracy,
        "grounding_accuracy": grounding_accuracy,
        "cases": case_results,
    }

    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = RESULTS_DIR / f"{report['run_at'].replace(':', '-')}.json"
    out_path.write_text(json.dumps(report, indent=2))

    print("=== Summary ===")
    print(f"Tool-call accuracy: {sum(r['tool_call_correct'] for r in case_results)}/{n} ({tool_call_accuracy:.0%})")
    print(f"Grounding accuracy: {sum(r['is_grounded'] for r in case_results)}/{n} ({grounding_accuracy:.0%})")
    print(f"Report saved to {out_path}")

    return report


if __name__ == "__main__":
    asyncio.run(run_eval())
