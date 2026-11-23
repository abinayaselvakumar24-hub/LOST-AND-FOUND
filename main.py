#!/usr/bin/env python3
"""
Railway Station Lost & Found Matcher
====================================
Domain: Railway Transit Safety & Passenger Assistance Desk

A beginner-friendly, clean Python application that:
1. Reads lost.csv (passenger reports) and found.csv (station custody articles)
2. Extracts entity facts (item, colour, brand, place, summary) using an LLM prompt
   (with Google Gemini API, or an automatic zero-dependency offline NLP fallback)
3. Compares reports using plain Python rule-based scoring:
   - +2 points for matching colour
   - +2 points for matching brand
   - +1 point for matching station location
   - Enforces hard mismatches (different colours or brands = 0 score)
   - Enforces 30-day temporal window and chronological sequence
4. Detects double claims (items claimed by multiple passengers)
5. Generates 4 clean output files:
   - matches.csv   : Matched pairs with scores and reasons
   - no_match.csv  : Lost reports that could not be matched
   - unclaimed.csv : Found articles still waiting for their owner
   - summary.txt   : Clean executive handover & audit summary
"""

import os
import re
import csv
import json
import time
from pathlib import Path
from datetime import datetime

# ==============================================================================
# SECTION 1: CONFIGURATION & ENVIRONMENT
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent
LOST_CSV_PATH = BASE_DIR / "lost.csv"
FOUND_CSV_PATH = BASE_DIR / "found.csv"
SYSTEM_PROMPT_PATH = BASE_DIR / "system_prompt.txt"

MATCHES_CSV_PATH = BASE_DIR / "matches.csv"
NO_MATCH_CSV_PATH = BASE_DIR / "no_match.csv"
UNCLAIMED_CSV_PATH = BASE_DIR / "unclaimed.csv"
SUMMARY_TXT_PATH = BASE_DIR / "summary.txt"

# Allowed vocabularies per Assessment Specification
ALLOWED_ITEMS = {
    "phone", "wallet", "id_card", "bottle", "bag", "earphones",
    "keys", "umbrella", "calculator", "watch", "spectacles", "other"
}

ALLOWED_COLOURS = {
    "black", "blue", "red", "brown", "white",
    "green", "grey", "yellow", "silver", "gold"
}

KNOWN_PLACES = {
    "platform_1", "platform_2", "platform_3", "waiting_hall",
    "ticket_counter", "station_canteen", "cloak_room", "parking_lot",
    "foot_overbridge", "station_master_office", "station_entrance",
    "station_fountain"
}

KNOWN_BRANDS = [
    "samsung", "apple", "iphone", "wildhorn", "titan", "milton",
    "dell", "sony", "casio", "fastrack", "american tourister"
]

def load_env():
    """Reads .env file to load GEMINI_API_KEY if present."""
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                k = key.strip()
                v = val.strip().strip('"').strip("'")
                if k and v:
                    os.environ.setdefault(k, v)

load_env()

# ==============================================================================
# SECTION 2: LLM ENTITY EXTRACTOR (WITH OFFLINE FALLBACK)
# ==============================================================================
def fallback_extract(text: str) -> dict:
    """
    Deterministic rule-based NLP extractor.
    Runs when GEMINI_API_KEY is blank or offline.
    Follows system_prompt.txt rules exactly with 0% hallucination.
    """
    lower = text.lower()

    # 1. Extract Item
    item = "other"
    item_keywords = {
        "phone": ["phone", "smartphone", "mobile", "iphone", "galaxy"],
        "wallet": ["wallet", "purse", "billfold"],
        "id_card": ["id_card", "id card", "identity card", "passenger id", "student id"],
        "bottle": ["bottle", "flask", "water bottle"],
        "bag": ["bag", "backpack", "suitcase", "laptop bag"],
        "earphones": ["earphones", "headphones", "airpods", "earbuds"],
        "keys": ["keys", "keychain", "house keys"],
        "umbrella": ["umbrella", "parasol"],
        "calculator": ["calculator"],
        "watch": ["watch", "wristwatch", "fastrack", "titan"],
        "spectacles": ["spectacles", "glasses", "eyeglass", "specs"]
    }
    for itype, kws in item_keywords.items():
        if any(re.search(rf"\b{re.escape(kw)}\b", lower) for kw in kws):
            item = itype
            break

    # 2. Extract Colour
    colour = None
    if "gray" in lower:
        lower = lower.replace("gray", "grey")
    for c in ["black", "blue", "red", "brown", "white", "green", "grey", "yellow", "silver", "gold", "golden"]:
        if re.search(rf"\b{c}\b", lower):
            colour = "gold" if c == "golden" else c
            break

    # 3. Extract Brand (Anti-hallucination: ignore similes like 'looks like an iPhone')
    brand = None
    for b in KNOWN_BRANDS:
        simile_pattern = rf"(?:similar\s+to|looks?\s+like|like\s+an?|resembling)\s+{re.escape(b)}\b"
        if re.search(simile_pattern, lower):
            continue
        if re.search(rf"\b{re.escape(b)}\b", lower):
            if b == "american tourister":
                brand = "American Tourister"
            elif b in ["iphone", "apple"]:
                brand = "Apple"
            else:
                brand = b.capitalize()
            break

    # 4. Extract Station Place
    place = None
    for p in KNOWN_PLACES:
        clean_p = p.replace("_", " ")
        if p in lower or clean_p in lower:
            place = p
            break

    # 5. Build Short Summary (8 words or fewer)
    tokens = []
    if colour:
        tokens.append(colour.capitalize())
    if brand:
        tokens.append(brand)
    tokens.append(item.replace("_", " ").title())
    if place:
        tokens.append(f"at {place.replace('_', ' ').title()}")
    summary = " ".join(tokens)
    summary_words = summary.split()[:8]
    summary = " ".join(summary_words) if summary_words else item.title()

    return {
        "item": item,
        "colour": colour,
        "brand": brand,
        "place": place,
        "summary": summary
    }

def call_gemini(text: str, api_key: str) -> dict:
    """Calls Google Gemini API using system_prompt.txt."""
    from google import genai

    client = genai.Client(api_key=api_key)
    sys_prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8") if SYSTEM_PROMPT_PATH.exists() else ""
    prompt = f"{sys_prompt}\n\nIncident Report to Extract:\n\"{text}\""
    model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
    last_error = None
    for attempt in range(1, 4):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
            )
            break
        except Exception as exc:
            last_error = exc
            message = str(exc)
            is_transient = "503" in message or "UNAVAILABLE" in message or "429" in message
            if not is_transient or attempt == 3:
                raise
            delay = 2 ** attempt
            print(f"  [Retry] Gemini is busy ({exc.__class__.__name__}); retrying in {delay} seconds ({attempt}/3)...")
            time.sleep(delay)
    else:
        raise last_error
    raw_text = (response.text or "").strip()
    raw_text = re.sub(r"^```(?:json)?", "", raw_text)
    raw_text = re.sub(r"```$", "", raw_text).strip()
    return json.loads(raw_text)

def check_facts(raw_text: str, extracted: dict) -> dict:
    """
    Anti-Hallucination verification: ensures extracted colour and brand
    actually appear in the source text.
    """
    raw_lower = raw_text.lower()
    clean = dict(extracted)

    # Fact check colour
    colour = clean.get("colour")
    if colour:
        c_lower = colour.lower()
        if c_lower not in raw_lower and not (c_lower == "gold" and "golden" in raw_lower):
            clean["colour"] = None

    # Fact check brand
    brand = clean.get("brand")
    if brand:
        b_lower = brand.lower()
        if b_lower not in raw_lower and not (b_lower == "apple" and "iphone" in raw_lower):
            clean["brand"] = None

    # Enforce item vocabulary
    if clean.get("item") not in ALLOWED_ITEMS:
        clean["item"] = "other"

    # Enforce summary limit (<= 8 words)
    summary = clean.get("summary", "")
    if summary and len(summary.split()) > 8:
        clean["summary"] = " ".join(summary.split()[:8])

    return clean

def extract_entities(text: str) -> dict:
    """Extracts entity attributes from report text."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if api_key:
        try:
            extracted = call_gemini(text, api_key)
        except Exception as exc:
            message = str(exc)
            if "503" in message or "UNAVAILABLE" in message or "429" in message or "KeyboardInterrupt" in message:
                print(f"  [Fallback] Gemini unavailable; using the fact-grounded offline extractor ({exc.__class__.__name__}).")
                extracted = fallback_extract(text)
            else:
                raise
    else:
        extracted = fallback_extract(text)
    return check_facts(text, extracted)

# ==============================================================================
# SECTION 3: CSV READING & VALIDATION
# ==============================================================================
def read_csv_reports(filepath: Path) -> list:
    """Reads an input CSV (id, date, report)."""
    if not filepath.exists():
        raise FileNotFoundError(f"Missing input file: {filepath.name}")

    records = []
    with open(filepath, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cleaned = {k.strip(): v.strip() for k, v in row.items() if k}
            # Validation check
            if cleaned.get("id") and cleaned.get("date") and cleaned.get("report"):
                try:
                    datetime.strptime(cleaned["date"], "%Y-%m-%d")
                    records.append(cleaned)
                except ValueError:
                    print(f"  [Warning] Skipping row with invalid date: {cleaned}")
    return records

# ==============================================================================
# SECTION 4: SCORING ALGORITHM
# ==============================================================================
def score_pair(lost: dict, found: dict) -> tuple:
    """
    Computes compatibility score (0 to 5) between lost and found items.
    Scoring:
      - Item mismatch: score = 0
      - Colour hard clash: score = 0
      - Brand hard clash: score = 0
      - Date order violation (found before lost) or > 30 days gap: score = 0
      - Colour match: +2
      - Brand match: +2
      - Place match: +1
    Returns: (score, match_level, reasons, days_diff)
    """
    l_ent = lost["entities"]
    f_ent = found["entities"]

    # 1. Item compatibility check
    if l_ent["item"] != f_ent["item"]:
        return 0, "None", f"Different items: {l_ent['item']} vs {f_ent['item']}", 0

    if l_ent["item"] == "other" and f_ent["item"] == "other":
        if not l_ent.get("brand") and not l_ent.get("place"):
            return 0, "None", "Vague 'other' item with insufficient attributes", 0

    # 2. Date checks
    l_date = datetime.strptime(lost["date"], "%Y-%m-%d").date()
    f_date = datetime.strptime(found["date"], "%Y-%m-%d").date()
    days_diff = (f_date - l_date).days

    if days_diff < 0:
        return 0, "None", f"Chronological mismatch: found {abs(days_diff)} days before lost", days_diff

    if days_diff > 30:
        return 0, "None", f"Temporal window exceeded: {days_diff} days gap (>30 days limit)", days_diff

    # 3. Hard clash checks
    l_col = l_ent.get("colour")
    f_col = f_ent.get("colour")
    if l_col and f_col and l_col.lower() != f_col.lower():
        return 0, "None", f"Hard colour mismatch: {l_col} vs {f_col}", days_diff

    l_brand = l_ent.get("brand")
    f_brand = f_ent.get("brand")
    if l_brand and f_brand and l_brand.lower() != f_brand.lower():
        return 0, "None", f"Hard brand mismatch: {l_brand} vs {f_brand}", days_diff

    # 4. Calculate points
    score = 0
    reasons = []

    if l_col and f_col and l_col.lower() == f_col.lower():
        score += 2
        reasons.append(f"Same colour '{l_col}' (+2)")

    if l_brand and f_brand and l_brand.lower() == f_brand.lower():
        score += 2
        reasons.append(f"Same brand '{l_brand}' (+2)")

    l_place = l_ent.get("place")
    f_place = f_ent.get("place")
    if l_place and f_place and l_place.lower() == f_place.lower():
        score += 1
        reasons.append(f"Same place '{l_place}' (+1)")

    if score >= 3:
        level = "Likely"
    elif score in [1, 2]:
        level = "Possible"
    else:
        level = "None"
        reasons.append("No common attributes")

    reason_str = "; ".join(reasons)
    return score, level, reason_str, days_diff

# ==============================================================================
# SECTION 5: MATCHING PIPELINE
# ==============================================================================
def run_matcher():
    print("===========================================================================")
    print("  RAILWAY STATION LOST & FOUND MATCHER")
    print("  Domain: Railway Transit Safety & Passenger Assistance Desk")
    print("===========================================================================")

    # 1. Read input CSV files
    lost_list = read_csv_reports(LOST_CSV_PATH)
    found_list = read_csv_reports(FOUND_CSV_PATH)
    print(f"\n[1/3] Loaded {len(lost_list)} reports from lost.csv and {len(found_list)} items from found.csv")

    # 2. Extract entity facts
    print("[2/3] Extracting entity attributes via LLM system prompt...")
    for item in lost_list:
        item["entities"] = extract_entities(item["report"])
    for item in found_list:
        item["entities"] = extract_entities(item["report"])

    # 3. Compare all pairs
    print("[3/3] Scoring pairs and identifying match candidates...")
    candidates = []
    found_claim_count = {}

    for l in lost_list:
        for f in found_list:
            score, level, reasons, days_diff = score_pair(l, f)
            if score > 0:
                candidates.append({
                    "lost_id": l["id"],
                    "found_id": f["id"],
                    "score": score,
                    "match_level": level,
                    "reasons": reasons,
                    "lost_date": l["date"],
                    "found_date": f["date"],
                    "days_difference": days_diff,
                    "lost_summary": l["entities"]["summary"],
                    "found_summary": f["entities"]["summary"],
                    "lost_report": l["report"],
                    "found_report": f["report"],
                })
                found_claim_count[f["id"]] = found_claim_count.get(f["id"], 0) + 1

    # Mark double claims
    for c in candidates:
        if found_claim_count.get(c["found_id"], 0) > 1:
            c["double_claim_flag"] = "YES (Multiple Claimants)"
        else:
            c["double_claim_flag"] = "NO"

    # Sort matches: highest score first, then smallest date difference
    candidates.sort(key=lambda x: (-x["score"], x["days_difference"], x["lost_id"]))

    # Identify unmatched and unclaimed
    matched_lost_ids = {c["lost_id"] for c in candidates}
    matched_found_ids = {c["found_id"] for c in candidates}

    no_matches = [
        {"lost_id": l["id"], "date": l["date"], "report": l["report"], "reason": "No compatible found item in custody"}
        for l in lost_list if l["id"] not in matched_lost_ids
    ]

    unclaimed = [
        {"found_id": f["id"], "date": f["date"], "report": f["report"], "reason": "No passenger claim submitted"}
        for f in found_list if f["id"] not in matched_found_ids
    ]

    # Write output files
    write_output_files(candidates, no_matches, unclaimed, lost_list, found_list, found_claim_count)

def write_output_files(matches, no_matches, unclaimed, lost_list, found_list, found_claim_count):
    """Writes the 4 required output files."""
    # 1. matches.csv
    with open(MATCHES_CSV_PATH, mode="w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "lost_id", "found_id", "score", "match_level", "reasons",
            "double_claim_flag", "lost_date", "found_date", "days_difference",
            "lost_summary", "found_summary", "lost_report", "found_report"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in matches:
            writer.writerow(row)

    # 2. no_match.csv
    with open(NO_MATCH_CSV_PATH, mode="w", newline="", encoding="utf-8") as f:
        fieldnames = ["lost_id", "date", "report", "reason"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in no_matches:
            writer.writerow(row)

    # 3. unclaimed.csv
    with open(UNCLAIMED_CSV_PATH, mode="w", newline="", encoding="utf-8") as f:
        fieldnames = ["found_id", "date", "report", "reason"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in unclaimed:
            writer.writerow(row)

    # 4. summary.txt
    likely_count = sum(1 for m in matches if m["match_level"] == "Likely")
    possible_count = sum(1 for m in matches if m["match_level"] == "Possible")
    double_claim_items = [fid for fid, count in found_claim_count.items() if count > 1]

    with open(SUMMARY_TXT_PATH, mode="w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("RAILWAY STATION PASSENGER ASSISTANCE: LOST AND FOUND MATCHER SUMMARY\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")

        f.write("1. EXECUTIVE METRICS\n")
        f.write("-" * 80 + "\n")
        f.write(f"Total Lost Passenger Reports : {len(lost_list)}\n")
        f.write(f"Total Found Articles Logged  : {len(found_list)}\n")
        f.write(f"Total Suggested Match Pairs  : {len(matches)}\n")
        f.write(f"  - Likely Matches  (Score >= 3): {likely_count}\n")
        f.write(f"  - Possible Matches (Score 1-2): {possible_count}\n")
        f.write(f"Unmatched Lost Reports       : {len(no_matches)}\n")
        f.write(f"Unclaimed Custody Articles   : {len(unclaimed)}\n\n")

        f.write("2. DOUBLE CLAIM ALERTS (CONFLICTING PASSENGER CLAIMS)\n")
        f.write("-" * 80 + "\n")
        f.write(f"Found Articles Claimed by Multiple Passengers: {len(double_claim_items)}\n")
        for fid in double_claim_items:
            f.write(f"[!] ALERT: Found Item '{fid}' has multiple competing claims:\n")
            competing = [m for m in matches if m["found_id"] == fid]
            for c in competing:
                f.write(f"    -> Lost ID: {c['lost_id']} | Score: {c['score']} ({c['match_level']}) | "
                        f"Reasons: {c['reasons']} | Summary: {c['lost_summary']}\n")
        f.write("\n")

        f.write("3. TOP SUGGESTED MATCHES (SORTED BY HIGHEST CONFIDENCE)\n")
        f.write("-" * 80 + "\n")
        for idx, m in enumerate(matches[:10], start=1):
            flag_note = " [DOUBLE CLAIM]" if "YES" in m["double_claim_flag"] else ""
            f.write(f"#{idx:02d} Lost {m['lost_id']} <--> Found {m['found_id']}{flag_note}\n")
            f.write(f"     Score: {m['score']} ({m['match_level']}) | Date Delta: {m['days_difference']} days\n")
            f.write(f"     Reasons: {m['reasons']}\n")
            f.write(f"     Lost Summary : {m['lost_summary']}\n")
            f.write(f"     Found Summary: {m['found_summary']}\n\n")

        f.write("4. HUMAN-IN-THE-LOOP VERIFICATION CHECKPOINT\n")
        f.write("-" * 80 + "\n")
        f.write("NOTICE: AI match scores are decision-support aids only and NEVER decide final\n")
        f.write("ownership. To release custody, authorized Station Personnel / RPF Duty Officers\n")
        f.write("MUST verify private hidden proof (e.g., serial number, photo ID, lockscreen code).\n")
        f.write("=" * 80 + "\n")

    # Console output
    print("\n" + "=" * 75)
    print("  MATCHING PIPELINE COMPLETED SUCCESSFULLY!")
    print("=" * 75)
    print(f"  1. Matches Output     : {MATCHES_CSV_PATH.name} ({len(matches)} pairs)")
    print(f"  2. No-Match Lost List : {NO_MATCH_CSV_PATH.name} ({len(no_matches)} reports)")
    print(f"  3. Unclaimed Articles : {UNCLAIMED_CSV_PATH.name} ({len(unclaimed)} articles)")
    print(f"  4. Executive Summary  : {SUMMARY_TXT_PATH.name}")
    print("=" * 75)
    print(f"\nExecutive Summary Preview:\n- Total Matches: {len(matches)} ({likely_count} Likely, {possible_count} Possible)")
    print(f"- Double Claims Flagged: {len(double_claim_items)}")
    print(f"- Unmatched Lost: {len(no_matches)} | Unclaimed Found: {len(unclaimed)}\n")

if __name__ == "__main__":
    run_matcher()
