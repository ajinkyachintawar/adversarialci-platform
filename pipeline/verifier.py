from state import WarRoomState
from db.atlas import get_collection, mark_verified, flag_contradiction


def verifier(state: WarRoomState) -> WarRoomState:
    print("\n🔎 VERIFIER — Checking research quality")
    print("=" * 40)

    col = get_collection("research_data")

    all_companies = [state["primary"]] + state["competitors"]

    for company in all_companies:
        print(f"\n  Verifying: {company}")

        docs = list(col.find({
            "company":  company,
            "verified": False
        }))

        if not docs:
            print(f"    ⏭️  No unverified docs found")
            continue

        # Collect pricing bullets for contradiction check
        pricing_bullets = []
        for doc in docs:
            if doc.get("data_type") == "pricing":
                pricing_bullets.extend(doc.get("content_bullets", []))

        prices_found = [b for b in pricing_bullets
                       if "$" in b or "free" in b.lower()]

        for doc in docs:
            bullets  = doc.get("content_bullets", [])
            has_data = len(bullets) > 0

            confidence = 0.0
            if has_data:
                confidence += 0.4

            if doc.get("source_type") in ["github", "pricing_scrape"]:
                confidence += 0.4
            elif doc.get("source_type") in ["hn"]:
                confidence += 0.3
            elif doc.get("source_type") == "tavily":
                confidence += 0.2

            # Flag marketing language
            marketing_terms = [
                "best in class", "industry leading",
                "revolutionary", "cutting edge",
                "world class", "unmatched"
            ]
            combined_text = " ".join(bullets).lower()
            has_marketing = any(t in combined_text
                               for t in marketing_terms)

            if has_marketing:
                confidence -= 0.1
                print(f"    ⚠️  Marketing language detected in "
                      f"{doc.get('source_type')} doc")

            if (doc.get("data_type") == "pricing"
                    and len(prices_found) > 3):
                flag_contradiction(
                    doc["_id"],
                    "Multiple conflicting price points found"
                )
                print(f"    ⚠️  Pricing contradiction flagged")

            confidence = round(max(0.0, min(1.0, confidence)), 2)
            mark_verified(doc["_id"], confidence)

        print(f"    ✅ {len(docs)} docs verified for {company}")

    return {
        **state,
        "stage": "complete"
    }