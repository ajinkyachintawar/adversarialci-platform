from state import WarRoomState
from db.atlas import get_research


def aggregator(state: WarRoomState) -> WarRoomState:
    print("\n📦 AGGREGATOR — Building research summary")
    print("=" * 40)

    all_companies = [state["primary"]] + state["competitors"]
    research      = {}

    for company in all_companies:
        docs = get_research(company)

        if not docs:
            print(f"  ⚠️  No verified data found for {company}")
            continue

        summary = {
            "tech":     [],
            "pricing":  [],
            "sentiment": [],
            "github":   []
        }

        for doc in docs:
            data_type = doc.get("data_type", "tech")
            bullets   = doc.get("content_bullets", [])
            score     = doc.get("confidence_score", 0)

            # Only include bullets with confidence above threshold
            if score and score >= 0.3:
                key = data_type if data_type in summary else "tech"
                summary[key].extend(bullets[:5])

        total = sum(len(v) for v in summary.values())
        print(f"  ✅ {company}: {total} verified bullets aggregated")
        research[company] = summary

    return {
        **state,
        "research": research,
        "stage":    "complete"
    }