# Railway Station Lost and Found Matcher

**Domain:** Railway Transit Safety & Passenger Assistance Desk  
**Course:** CIT AI-Native Engineering Programme (Assessment 5 Capstone)

---

## 📌 Project Overview
This project is an automated AI-assisted matching system designed for **Central Railway Junction**. When passengers lose personal belongings (phones, wallets, bags, watches, umbrellas, water bottles) at railway platforms, waiting halls, or ticket counters, station staff record found items into custody. 

This program:
1. Reads passenger reports from `lost.csv` and custody records from `found.csv`.
2. Extracts entity attributes (**Item, Colour, Brand, Station Place, Summary**) using an LLM prompt (`system_prompt.txt`).
3. Compares reports using plain Python rules to determine matches.
4. Identifies **double claims** (when multiple passengers claim the same item).
5. Generates 4 clean output files: `matches.csv`, `no_match.csv`, `unclaimed.csv`, and `summary.txt`.

---

## 📂 File Structure (13 Files)
```text
lost and found/
├── .env                 # Optional: Stores GEMINI_API_KEY (runs offline if empty)
├── .env.example         # Safe template for configuring the Gemini API key
├── .gitignore           # Git ignore configuration
├── found.csv            # Input: 20 custody found items logged by station staff
├── lost.csv             # Input: 20 passenger lost property reports
├── main.py              # Main Python matching script (run this file)
├── requirements.txt     # Gemini SDK dependency
├── matches.csv          # Output: Suggested match pairs with scores and reasons
├── no_match.csv         # Output: Lost reports with no matching found item
├── README.md            # Project documentation and instructions
├── summary.txt          # Output: Executive summary and handover audit report
├── system_prompt.txt    # 5-Role prompt template for entity extraction
└── unclaimed.csv        # Output: Found items remaining in station custody
```

---

## 🚀 How to Run the Program

### 1. Configure your Gemini API key

Create a key in Google AI Studio, then open or create `.env` in this folder and add:

```text
GEMINI_API_KEY=your_google_ai_studio_api_key
```

Gemini may also use a model override in `.env`:

```text
GEMINI_MODEL=gemini-3.5-flash-lite
```

Replace the example value with your key. Do not put the key in `main.py`, commit `.env`, or share it in screenshots or messages. The `.gitignore` file excludes `.env` from Git.

### 2. Install the Gemini SDK

```bash
python -m pip install -r requirements.txt
```

### 3. Run the program

Open your terminal in this folder and run:

```bash
python main.py
```

### What happens when you run it:
1. Reads all 20 reports from `lost.csv` and 20 items from `found.csv`.
2. With `GEMINI_API_KEY` set, sends each report to Gemini using `GEMINI_MODEL` or the default `gemini-3.5-flash-lite`. Without a key, or after persistent temporary Gemini `503`/`429` failures, it uses the built-in offline NLP fallback so the project can still finish.
3. Evaluates all pairs using the scoring system:
   - **+2 Points:** Same Colour
   - **+2 Points:** Same Brand
   - **+1 Point:** Same Station Location
   - **Hard Mismatches (0 Points):** Conflicting colours, conflicting brands, or >30-day time gaps.
4. Generates the 4 output files:
   - `matches.csv`: Sorted list of matches (Likely or Possible), with reasons and double-claim flags.
   - `no_match.csv`: Unmatched lost passenger reports.
   - `unclaimed.csv`: Found items still waiting for a claimant.
   - `summary.txt`: Executive metrics and handover verification instructions.

---

## 🛡️ Human-in-the-Loop Handover Rule
The AI match scores are algorithmic decision-support aids only and **never** automatically release an item. Station staff and Railway Protection Force (RPF) officers must physically verify at least one undisclosed private detail (such as a lock screen passcode, serial number, or government ID) before handing over any property.
