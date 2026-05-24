"""Read sql/business_questions.sql and business_questions.csv; execute queries and render outputs/business_answers.md."""

import csv
import logging
import re
import sqlite3
from datetime import date
from pathlib import Path

DB_PATH = Path("outputs/curated.sqlite")
INPUT_DIR = Path("input_data")
SQL_DIR = Path("sql")
OUTPUT_DIR = Path("outputs")

BQ_CSV_PATH = INPUT_DIR / "business_questions.csv"
BQ_SQL_PATH = SQL_DIR / "business_questions.sql"
ANSWERS_PATH = OUTPUT_DIR / "business_answers.md"

logger = logging.getLogger(__name__)


def _load_questions(path: Path) -> list[str]:
    """
    Parse business_questions.csv and return questions in CSV row order.

    The CSV header is 'Questions'; each non-empty data row is one question.
    Preserving order is critical so each question pairs correctly with its
    SQL block by index.
    """
    questions: list[str] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            q = row.get("Questions", "").strip()
            if q:
                questions.append(q)
    logger.info("Loaded %d questions from %s", len(questions), path)
    return questions


def _parse_sql_blocks(path: Path) -> list[str]:
    """
    Parse sql/business_questions.sql and return one SQL string per numbered block.

    Blocks are delimited by label lines matching '-- Q{n}' (e.g. '-- Q1:', '-- Q2:').
    Everything after a label line up to the next label (or EOF) is the SQL for that
    block.  Any preamble text before the first label is discarded, so the file can
    carry a file-level comment without affecting parsing.
    """
    text = path.read_text(encoding="utf-8")
    label_pattern = re.compile(r"^-- Q\d+.*$", re.MULTILINE)
    matches = list(label_pattern.finditer(text))

    blocks: list[str] = []
    for i, m in enumerate(matches):
        # Slice from end of this label line to start of next label (or EOF)
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sql = text[m.end():end].strip()
        if sql:
            blocks.append(sql)

    logger.info("Parsed %d SQL blocks from %s", len(blocks), path)
    return blocks


def _rows_to_md_table(headers: list[str], rows: list[tuple]) -> list[str]:
    """
    Render query results as a GitHub-Flavored Markdown table.

    NULL database values are shown as 'NULL'. Returns a single '_No results._'
    line when the query returns no rows, so the section is never blank.
    Column widths are padded to the longest value in each column for readability
    in the raw Markdown source.
    """
    if not rows:
        return ["_No results._"]

    str_rows = [[str(c) if c is not None else "NULL" for c in r] for r in rows]
    col_widths = [
        max(len(h), max(len(r[i]) for r in str_rows))
        for i, h in enumerate(headers)
    ]

    def _fmt(cells: list[str]) -> str:
        return "| " + " | ".join(c.ljust(col_widths[i]) for i, c in enumerate(cells)) + " |"

    sep = "| " + " | ".join("-" * w for w in col_widths) + " |"
    return [_fmt(headers), sep] + [_fmt(r) for r in str_rows]


def run(conn: sqlite3.Connection) -> None:
    """
    Execute the five business-question queries and render outputs/business_answers.md.

    Questions come from input_data/business_questions.csv; SQL blocks come from
    sql/business_questions.sql.  They are paired by position: first question ↔
    first SQL block, etc.  All output values are query-derived; nothing is
    hard-coded here.
    """
    logger.info("Starting reporting stage")

    questions = _load_questions(BQ_CSV_PATH)
    sql_blocks = _parse_sql_blocks(BQ_SQL_PATH)

    if len(questions) != len(sql_blocks):
        logger.warning(
            "Mismatch: %d questions vs %d SQL blocks — pairing up to the shorter list",
            len(questions),
            len(sql_blocks),
        )

    lines: list[str] = [
        "# Business Answers",
        "",
        f"**Generated:** {date.today().isoformat()}  ",
        "**Source database:** `outputs/curated.sqlite`",
        "",
        "---",
        "",
    ]

    for i, (question, sql) in enumerate(zip(questions, sql_blocks), start=1):
        logger.info("Executing Q%d: %s", i, question)
        lines.append(f"## Q{i}: {question}")
        lines.append("")
        try:
            cur = conn.execute(sql)
            headers = [d[0] for d in cur.description]
            rows = cur.fetchall()
            logger.info("Q%d returned %d row(s)", i, len(rows))
            lines.extend(_rows_to_md_table(headers, rows))
        except sqlite3.Error as exc:
            logger.error("Q%d query failed: %s", i, exc)
            lines.append(f"> **Error executing query:** `{exc}`")
        lines += ["", "---", ""]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ANSWERS_PATH.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Business answers written to %s", ANSWERS_PATH)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DB_PATH}. Run the full pipeline first."
        )
    with sqlite3.connect(DB_PATH) as conn:
        run(conn)
