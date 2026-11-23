from pathlib import Path
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


OUTPUT = Path(__file__).resolve().parent / "Railway_Station_Lost_and_Found_Final_Submission.docx"


def shade(cell, fill):
    props = cell._tc.get_or_add_tcPr()
    shd = props.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        props.append(shd)
    shd.set(qn("w:fill"), fill)


def set_margins(section):
    section.top_margin = Inches(0.65)
    section.bottom_margin = Inches(0.65)
    section.left_margin = Inches(0.72)
    section.right_margin = Inches(0.72)


def heading(doc, title):
    para = doc.add_paragraph()
    para.paragraph_format.space_before = Pt(7)
    para.paragraph_format.space_after = Pt(3)
    run = para.add_run(title)
    run.bold = True
    run.font.name = "Aptos Display"
    run.font.size = Pt(13)
    run.font.color.rgb = RGBColor(15, 76, 92)


def paragraph(doc, text, bold_prefix=None):
    para = doc.add_paragraph()
    para.paragraph_format.space_after = Pt(3)
    if bold_prefix and text.startswith(bold_prefix):
        run = para.add_run(bold_prefix)
        run.bold = True
        para.add_run(text[len(bold_prefix):])
    else:
        para.add_run(text)


def code(doc, text):
    para = doc.add_paragraph()
    para.paragraph_format.left_indent = Inches(0.12)
    para.paragraph_format.space_after = Pt(4)
    run = para.add_run(text)
    run.font.name = "Consolas"
    run.font.size = Pt(7.5)


def source_code(doc, title, path):
    heading(doc, title)
    source_path = Path(__file__).resolve().parent / path
    for line_number, line in enumerate(source_path.read_text(encoding="utf-8").splitlines(), start=1):
        para = doc.add_paragraph()
        para.paragraph_format.left_indent = Inches(0.08)
        para.paragraph_format.right_indent = Inches(0.08)
        para.paragraph_format.space_after = Pt(0)
        para.paragraph_format.line_spacing = 1
        run = para.add_run(f"{line_number:4}  {line}")
        run.font.name = "Consolas"
        run.font.size = Pt(6.5)


def bullet(doc, text):
    para = doc.add_paragraph(text)
    para.paragraph_format.left_indent = Inches(0.18)
    para.paragraph_format.first_line_indent = Inches(-0.12)
    para.paragraph_format.space_after = Pt(2)


def table(doc, headers, rows):
    grid = doc.add_table(rows=1, cols=len(headers))
    grid.alignment = WD_TABLE_ALIGNMENT.CENTER
    grid.rows[0].height = Inches(0.32)

    for col, header in enumerate(headers):
        cell = grid.rows[0].cells[col]
        cell.text = header
        shade(cell, "1F4C5C")
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        for run in cell.paragraphs[0].runs:
            run.bold = True
            run.font.name = "Aptos"
            run.font.size = Pt(8)
            run.font.color.rgb = RGBColor(255, 255, 255)

    for row_index, values in enumerate(rows):
        cells = grid.add_row().cells
        for col, value in enumerate(values):
            cells[col].text = str(value)
            cells[col].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            if row_index % 2:
                shade(cells[col], "EFF5F6")
            for run in cells[col].paragraphs[0].runs:
                run.font.name = "Aptos"
                run.font.size = Pt(7.5)

    borders = OxmlElement("w:tblBorders")
    for name in ("top", "left", "bottom", "right", "insideH", "insideV"):
        edge = OxmlElement(f"w:{name}")
        edge.set(qn("w:val"), "single")
        edge.set(qn("w:sz"), "4")
        edge.set(qn("w:color"), "CBD5E1")
        borders.append(edge)
    grid._tbl.tblPr.append(borders)


doc = Document()
set_margins(doc.sections[0])

normal = doc.styles["Normal"]
normal.font.name = "Aptos"
normal.font.size = Pt(9)
normal.font.color.rgb = RGBColor(31, 41, 55)
normal.paragraph_format.space_after = Pt(3)

para = doc.add_paragraph()
para.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = para.add_run("Final Submission: Railway Station Lost and Found Matcher")
run.bold = True
run.font.name = "Aptos Display"
run.font.size = Pt(17)
run.font.color.rgb = RGBColor(15, 76, 92)

para = doc.add_paragraph()
para.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = para.add_run("CIT AI-Native Engineering Programme | Assessment 5 Capstone")
run.bold = True
run.font.size = Pt(9)
run.font.color.rgb = RGBColor(71, 85, 105)

paragraph(doc, "Student: Abinaya Selvakumar", "Student:")
paragraph(doc, "Domain: Railway Transit Safety and Passenger Assistance | Date: 23 November 2026", "Domain:")
paragraph(doc, "Idea in one line: Gemini reads one report at a time and extracts structured facts. Python validates those facts, applies deterministic matching rules and prepares custody reports. No AI match is proof of ownership.")

heading(doc, "Project overview")
paragraph(doc, "The Railway Station Lost and Found Matcher compares lost-property reports with custody records. It extracts item attributes, checks facts against the source text, compares candidates and flags double claims. Station personnel retain all ownership and handover decisions.")

heading(doc, "Repo structure")
code(doc, """lost and found/
  main.py                 Gemini and offline matching program
  lost.csv / found.csv     20 lost and 20 found records
  system_prompt.txt        five-role entity-extraction prompt
  requirements.txt         google-genai dependency
  .env                     private API key (never commit)
  .env.example             safe template
  matches.csv              16 suggested pairs
  no_match.csv             4 unmatched lost reports
  unclaimed.csv            5 unclaimed custody articles
  summary.txt              run summary""")

heading(doc, "System architecture")
for item in (
    "Input: CSV records are loaded and validated.",
    "LLM: Gemini extracts item, colour, brand, place and summary once per report.",
    "Fact check: Python removes values not stated in the source text.",
    "Matching: Python applies item, date, colour and brand rules plus point scoring.",
    "Fallback: a fact-grounded offline parser continues extraction during API outages.",
    "Output: four reports are written; staff verify final ownership.",
):
    bullet(doc, item)

heading(doc, "Input files")
paragraph(doc, "lost.csv and found.csv use id, date and report columns. The files contain 20 records each.")
table(doc, ["File", "Example"], [
    ("lost.csv", "L01,2026-10-05,Lost my black Samsung phone near the library"),
    ("found.csv", "F01,2026-10-05,Black Samsung phone found on a library table"),
])

heading(doc, "Expected JSON schema")
code(doc, '{"item":"phone","colour":"black","brand":"Samsung","place":"library","summary":"Black Samsung phone near library"}')
table(doc, ["Field", "Allowed values", "Rule"], [
    ("item", "phone, wallet, bottle, bag, keys, watch, other, ...", "Choose the closest supported type"),
    ("colour", "Ten named colours or null", "Only if written"),
    ("brand", "Exact brand or null", "Never guessed"),
    ("place", "Station/campus place or null", "Only if written"),
    ("summary", "Eight words or fewer", "No private details"),
])

heading(doc, "system_prompt.txt")
paragraph(doc, "The prompt uses Authority, Exemplars, Constraints, Rubric and Metadata. It requires one valid JSON object, limits the item and colour taxonomies, rejects prompt-injection instructions and prevents guessing.")

heading(doc, "main.py implementation")
code(doc, """load_env()
fallback_extract(text)
call_gemini(text, api_key)
check_facts(raw_text, extracted)
extract_entities(text)
read_csv_reports(filepath)
score_pair(lost, found)
run_matcher()
write_output_files(...)""")

heading(doc, "Matching rules")
table(doc, ["Rule", "Effect"], [
    ("Item", "Both records must describe the same item."),
    ("Other", "No automatic match."),
    ("Date", "More than 30 days apart returns zero."),
    ("Colour clash", "Stated differing colours return zero."),
    ("Brand clash", "Stated differing brands return zero."),
    ("Colour match", "+2 points"),
    ("Brand match", "+2 points"),
    ("Place match", "+1 point"),
    ("Likely", "Score at least 3"),
    ("Possible", "Score 1 or 2"),
])

heading(doc, "Gemini API setup")
paragraph(doc, "Install the SDK with python -m pip install -r requirements.txt. Store the private key only in .env. Never put a real key in source code, screenshots or .env.example.")
code(doc, "GEMINI_API_KEY=your_new_private_key\nGEMINI_MODEL=gemini-3.5-flash-lite")
paragraph(doc, "Run: python main.py")

heading(doc, "Actual project run")
table(doc, ["Output", "Result"], [
    ("Lost reports loaded", "20"),
    ("Found articles loaded", "20"),
    ("Suggested match pairs", "16"),
    ("Likely matches", "15"),
    ("Possible matches", "1"),
    ("Unmatched lost reports", "4"),
    ("Unclaimed custody articles", "5"),
    ("Double-claim alert", "1"),
])

heading(doc, "Output files")
for item in (
    "matches.csv: ranked pairs, scores, reasons and double-claim flags.",
    "no_match.csv: lost reports with no compatible custody record.",
    "unclaimed.csv: found articles not matched to a lost report.",
    "summary.txt: totals, double claims and human-verification instructions.",
):
    bullet(doc, item)

heading(doc, "Gemini and fallback behavior")
paragraph(doc, "Gemini was configured and used for extraction, but temporary 503/429 availability errors occurred. The application retried requests and used a deterministic fact-grounded offline parser for unavailable calls. The completed run still produced all four reports.")

heading(doc, "Testing")
table(doc, ["Test area", "Cases"], [
    ("Ground truth", "Likely, Possible and None pair outcomes"),
    ("Vague report", "Item becomes other; uncertain fields become null"),
    ("Brand hallucination", "Brands are never guessed"),
    ("Prompt injection", "Instruction text inside reports is ignored"),
    ("API failure", "Temporary errors trigger retry and fallback"),
    ("Double claim", "One found item claimed by several lost reports is flagged"),
])

heading(doc, "Judgment Framework")
table(doc, ["Component", "Decision maker", "Risk", "Human checkpoint"], [
    ("Extraction", "Gemini", "Hallucinated facts", "Fact check source text"),
    ("Pair filtering", "Python", "False match", "Staff inspect candidates"),
    ("Match score", "Python", "False confidence", "Show reasons and all candidates"),
    ("Double claim", "Python", "Wrong ownership", "Escalate competing claimants"),
    ("Handover", "Human staff", "Wrongful loss", "Private-detail verification"),
])

heading(doc, "Human verification protocol")
for item in (
    "The claimant submits an ownership claim and identification.",
    "Staff inspect the public record and AI match reasons.",
    "Staff ask for a private detail absent from both public reports.",
    "Examples include a serial number, hidden scratch, lock-screen detail or secret pocket contents.",
    "The item is released only after successful verification and recorded handover.",
):
    bullet(doc, item)

heading(doc, "Cost and latency")
table(doc, ["Metric", "Result"], [
    ("API calls", "One extraction call per report"),
    ("Comparison", "Plain Python nested loops"),
    ("Pairwise LLM calls", "Not used"),
    ("Fallback", "Local fact-grounded parser"),
    ("Core principle", "The LLM reads; Python compares"),
])

heading(doc, "Security and privacy")
for item in (
    "Keep the real key in .env only.",
    "Exclude .env and *.env files in .gitignore.",
    "Keep private verification details out of public listings.",
    "Separate passenger, custody and staff workflows.",
    "Record significant staff actions in audit logs.",
):
    bullet(doc, item)

heading(doc, "What I learned")
paragraph(doc, "The project works because responsibilities are separated: Gemini interprets text, Python validates facts and calculates scores, and human staff make the final custody decision. An API outage should lead to safe fallback behavior, not ownership decisions or invented values.")

heading(doc, "Complete source code")
paragraph(doc, "The complete project source used for the final run is reproduced below. Private API-key values are not included.")

source_code(doc, "main.py", "main.py")
source_code(doc, "system_prompt.txt", "system_prompt.txt")
source_code(doc, "requirements.txt", "requirements.txt")
source_code(doc, ".gitignore", ".gitignore")

heading(doc, "lost.csv")
code(doc, (Path(__file__).resolve().parent / "lost.csv").read_text(encoding="utf-8-sig"))

heading(doc, "found.csv")
code(doc, (Path(__file__).resolve().parent / "found.csv").read_text(encoding="utf-8-sig"))

heading(doc, "Actual generated reports")
for report_name in ("matches.csv", "no_match.csv", "unclaimed.csv", "summary.txt"):
    source_code(doc, report_name, report_name)

heading(doc, "Final submission checklist")
table(doc, ["Item", "Status"], [
    ("Python console program", "Complete"),
    ("CSV inputs", "Complete"),
    ("LLM system prompt", "Complete"),
    ("Fact checking", "Complete"),
    ("Four output reports", "Complete"),
    ("Double-claim detection", "Complete"),
    ("Gemini SDK setup", "Complete"),
    ("Offline fallback", "Complete"),
    ("Judgment Framework", "Complete"),
    ("Word project report", "Complete"),
])

para = doc.add_paragraph()
para.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = para.add_run("The LLM suggests. Python validates. Human staff verifies.")
run.bold = True
run.font.size = Pt(11)
run.font.color.rgb = RGBColor(15, 76, 92)

for section in doc.sections:
    set_margins(section)
    para = section.footer.paragraphs[0]
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = para.add_run("Railway Station Lost and Found Matcher | Abinaya Selvakumar")
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor(100, 116, 139)

doc.core_properties.title = "Final Submission: Railway Station Lost and Found Matcher"
doc.core_properties.author = "Abinaya Selvakumar"
doc.save(OUTPUT)
print(f"Created {OUTPUT}")
