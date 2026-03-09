import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"

MAX_ARGS_PER_DIM = 5


def call_ollama(messages: list, temperature: float = 0.3) -> str:
    prompt = "\n\n".join([
        f"{m['role'].upper()}: {m['content']}"
        for m in messages
    ])
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model":  OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": temperature}
            },
            timeout=120
        )
        data = response.json()
        if "response" not in data:
            print(f"  ⚠️  Ollama unexpected response: {data}")
            return "ERROR"
        return data["response"].strip()
    except requests.exceptions.ConnectionError:
        print(f"  ⚠️  Ollama not running — start with: ollama serve")
        return "ERROR"
    except Exception as e:
        print(f"  ⚠️  Ollama error: {e}")
        return f"ERROR: {e}"


def format_arguments_for_prompt(
    argument_bank: dict,
    dimensions:    list,
    max_per_dim:   int = MAX_ARGS_PER_DIM
) -> str:
    lines = []
    for dim in dimensions:
        args = argument_bank.get(dim, [])[:max_per_dim]
        if not args:
            continue
        lines.append(f"\n[{dim.upper()}]")
        for i, arg in enumerate(args, 1):
            lines.append(
                f"  {i}. [{arg['source_type']}] "
                f"(weight:{arg['weight']}) {arg['claim'][:300]}"
            )
    return "\n".join(lines)


def opening_statement(
    company:       str,
    argument_bank: dict,
    plaintiff:     dict,
    dimensions:    list
) -> dict:

    evidence = format_arguments_for_prompt(argument_bank, dimensions)
    use_case = plaintiff.get("use_case", "general database workload")
    budget   = plaintiff.get("budget", "unspecified")
    scale    = plaintiff.get("scale", "unspecified")
    priority = plaintiff.get("priority", "performance")

    system_prompt = f"""You are the advocate for {company} in a competitive database evaluation.
Your job is to make the strongest possible case for {company}.

RULES:
- You may ONLY use the evidence provided below
- Every claim must reference its source type in brackets
- Do not hallucinate features or pricing not in the evidence
- Be direct and persuasive — you are arguing for a win
- Structure arguments around the plaintiff's specific needs"""

    user_prompt = f"""PLAINTIFF PROFILE:
- Use case: {use_case}
- Budget: {budget}/month
- Scale: {scale}
- Top priority: {priority}

YOUR EVIDENCE FOR {company.upper()}:
{evidence}

Deliver a compelling opening statement for {company}.
Address the plaintiff's specific needs directly.
Make your 3 strongest arguments using only the evidence above.
Format:
OPENING STATEMENT — {company.upper()}
[argument 1]
[argument 2]
[argument 3]
CLOSING LINE: One sentence on why {company} wins for this buyer."""

    content = call_ollama([
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_prompt}
    ])

    return {
        "company": company,
        "round":   1,
        "type":    "opening_statement",
        "content": content
    }


def cross_examination(
    attacking_company:  str,
    defending_company:  str,
    attacker_bank:      dict,
    defender_statement: str,
    dimensions:         list
) -> dict:

    evidence = format_arguments_for_prompt(attacker_bank, dimensions)

    system_prompt = f"""You are the advocate for {attacking_company}.
Your job is to challenge {defending_company}'s opening statement.

RULES:
- Use ONLY the evidence provided to attack
- Find the weakest claim in their statement and destroy it
- Cite your source type for every counter-argument
- Be sharp and specific — vague attacks are worthless
- Maximum 3 attack points"""

    user_prompt = f"""{defending_company.upper()} CLAIMED:
{defender_statement[:800]}

YOUR EVIDENCE TO ATTACK WITH:
{evidence}

Cross-examine {defending_company}.
Attack their weakest 3 claims with your evidence.
Format:
CROSS EXAMINATION — {attacking_company.upper()} vs {defending_company.upper()}
ATTACK 1: [their claim] → [your counter + source]
ATTACK 2: [their claim] → [your counter + source]
ATTACK 3: [their claim] → [your counter + source]"""

    content = call_ollama([
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_prompt}
    ])

    return {
        "company": attacking_company,
        "target":  defending_company,
        "round":   2,
        "type":    "cross_examination",
        "content": content
    }


def plaintiff_challenge(
    company:       str,
    argument_bank: dict,
    plaintiff:     dict,
    challenge:     str,
    dimensions:    list
) -> dict:

    evidence = format_arguments_for_prompt(argument_bank, dimensions)

    system_prompt = f"""You are the advocate for {company}.
The judge has posed a specific constraint from the plaintiff.
Respond directly and honestly using only your evidence.

RULES:
- If your evidence supports the constraint — argue it strongly
- If your evidence does NOT support the constraint — concede honestly
- A concession that is honest is better than a weak argument
- Cite source types for every claim"""

    user_prompt = f"""PLAINTIFF CONSTRAINT:
{challenge}

PLAINTIFF PROFILE:
- Budget: {plaintiff.get('budget', 'unspecified')}
- Scale: {plaintiff.get('scale', 'unspecified')}
- Priority: {plaintiff.get('priority', 'unspecified')}
- Use case: {plaintiff.get('use_case', 'unspecified')}

YOUR EVIDENCE:
{evidence}

Respond to the constraint for {company}.
Format:
PLAINTIFF CHALLENGE RESPONSE — {company.upper()}
POSITION: [STRONG / MODERATE / CONCEDE]
ARGUMENT: [your response with source citations]
CAVEAT: [honest limitation if any]"""

    content = call_ollama([
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_prompt}
    ])

    return {
        "company":   company,
        "round":     3,
        "type":      "plaintiff_challenge",
        "challenge": challenge,
        "content":   content
    }


def run_advocates(
    companies:      list,
    argument_banks: dict,
    plaintiff:      dict,
    dimensions:     list,
    challenge:      str
) -> dict:

    print("\n🎙️  ADVOCATES — Building arguments")
    print("=" * 40)
    print(f"  ℹ️  Using Ollama ({OLLAMA_MODEL}) locally")

    results = {
        "round_1": {},
        "round_2": {},
        "round_3": {}
    }

    print("\n  ROUND 1 — Opening Statements")
    print("  " + "─" * 36)
    for company in companies:
        print(f"  🎙️  {company} opening...")
        statement = opening_statement(
            company, argument_banks[company],
            plaintiff, dimensions
        )
        results["round_1"][company] = statement
        print(f"     ✅ Done")

    print("\n  ROUND 2 — Cross Examination")
    print("  " + "─" * 36)
    primary = companies[0]
    for competitor in companies[1:]:
        print(f"  ⚔️  {primary} attacks {competitor}...")
        attack = cross_examination(
            attacking_company=primary,
            defending_company=competitor,
            attacker_bank=argument_banks[primary],
            defender_statement=results["round_1"][competitor]["content"],
            dimensions=dimensions
        )
        results["round_2"][f"{primary}_vs_{competitor}"] = attack
        print(f"     ✅ Done")

    print("\n  ROUND 3 — Plaintiff Challenge")
    print("  " + "─" * 36)
    for company in companies:
        print(f"  📋 {company} responding to challenge...")
        response = plaintiff_challenge(
            company, argument_banks[company],
            plaintiff, challenge, dimensions
        )
        results["round_3"][company] = response
        print(f"     ✅ Done")

    return results