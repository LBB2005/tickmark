"""Segment facts from SEC's Financial Statement AND NOTES data sets.

companyfacts returns non-dimensional facts only, so segment revenue has to
come from somewhere else. The spec budgeted a day for parsing raw XBRL
instance documents; the notes data sets make it a table join instead:

    num.tsv  (adsh, tag, ddate, qtrs, uom, dimh, value, dimn, coreg)
      -> dim.tsv (dimhash -> segments string)
      -> sub.tsv (adsh -> cik, form, period, filed)
      -> tag.tsv (tag -> tlabel, for human-readable member names)

Two filters decide what is usable as a question:

  * SINGLE-AXIS ONLY. A row dimensioned on BusinessSegments *and*
    ProductOrService is a product line inside a segment, not the segment. Both
    answer "what was the X segment's revenue" differently, which is exactly
    the genuine-ambiguity failure mode the adversarial review is meant to
    catch (spec section 6.5). Measured on 2026_07: 2,349 segment-revenue rows
    collapse to 108 unambiguous ones.
  * NO COREG. A co-registrant row reports a subsidiary's books, not the
    parent's.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import pathlib
import re
import zipfile
from dataclasses import asdict, dataclass

from . import config
from .http import SecClient

NOTES_URL = ("https://www.sec.gov/files/dera/data/"
             "financial-statement-notes-data-sets/{month}_notes.zip")
SEGMENT_AXIS = "BusinessSegments"
GEOGRAPHIC_AXIS = "Geographical"
SCORED_FORMS = ("10-K", "10-Q")

REVENUE_TAGS = frozenset({
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
})
SEGMENT_TAGS = REVENUE_TAGS | frozenset({"OperatingIncomeLoss"})

CACHE_DIR = config.DATA_DIR / "cache" / "segments"


@dataclass(frozen=True)
class SegmentFact:
    cik: int
    concept: str          # raw XBRL tag
    axis: str             # BusinessSegments | Geographical
    member: str           # raw member element, e.g. InnovativeMedicine
    member_label: str     # human-readable, for the question prompt
    unit: str
    start: str | None
    end: str
    qtrs: int             # 0=instant, 1=quarter, 4=annual
    val: float
    accn: str
    form: str
    filed: str

    @property
    def period_label(self) -> str:
        end = dt.date.fromisoformat(self.end).strftime("%B %-d, %Y")
        if self.qtrs == 0:
            return f"as of {end}"
        if self.qtrs == 4:
            return f"the fiscal year ended {end}"
        months = self.qtrs * 3
        word = {3: "three", 6: "six", 9: "nine"}.get(months, str(months))
        return f"the {word} months ended {end}"


def parse_segments(segments: str) -> dict[str, str]:
    """"A=B;C=D;" -> {"A": "B", "C": "D"}."""
    out: dict[str, str] = {}
    for part in segments.strip(";").split(";"):
        if "=" in part:
            axis, member = part.split("=", 1)
            out[axis] = member
    return out


def humanise_member(label: str | None, member: str) -> str:
    """Prefer SEC's own label; fall back to splitting the element name.

    Spec section 6.2 requires naming the concept as an analyst would. tag.tsv
    carries 'Aviation Segment [Member]'; the fallback turns
    'InnovativeMedicine' into 'Innovative Medicine'.
    """
    if label:
        cleaned = re.sub(r"\s*\[.*?\]\s*$", "", label).strip()
        if cleaned:
            return cleaned
    name = re.sub(r"Member$", "", member)
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name).strip()


def _start_for(end: str, qtrs: int) -> str | None:
    if qtrs == 0:
        return None
    end_date = dt.date.fromisoformat(end)
    month = end_date.month - qtrs * 3
    year = end_date.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    try:
        return dt.date(year, month, end_date.day).isoformat()
    except ValueError:  # e.g. Feb 30
        return dt.date(year, month, 28).isoformat()


def _ddate_to_iso(ddate: str) -> str:
    return f"{ddate[0:4]}-{ddate[4:6]}-{ddate[6:8]}"


def extract(
    zip_path: pathlib.Path,
    ciks: set[int],
    *,
    tags: frozenset[str] = SEGMENT_TAGS,
    axes: tuple[str, ...] = (SEGMENT_AXIS, GEOGRAPHIC_AXIS),
) -> list[SegmentFact]:
    """Pull unambiguous single-axis dimensional facts for the given CIKs."""
    archive = zipfile.ZipFile(zip_path)

    def rows(name: str):
        with archive.open(name) as fh:
            yield from csv.DictReader(
                io.TextIOWrapper(fh, "utf-8", errors="replace"), delimiter="\t")

    subs = {r["adsh"]: r for r in rows("sub.tsv")
            if r["cik"].isdigit() and int(r["cik"]) in ciks
            and r["form"] in SCORED_FORMS}
    if not subs:
        return []

    # Single-axis only: dimh -> (axis, member).
    dims: dict[str, tuple[str, str]] = {}
    for row in rows("dim.tsv"):
        parsed = parse_segments(row["segments"])
        if len(parsed) != 1:
            continue
        axis, member = next(iter(parsed.items()))
        if axis in axes:
            dims[row["dimhash"]] = (axis, member)

    labels: dict[str, str] = {}
    wanted_members = {m for _, m in dims.values()}
    for row in rows("tag.tsv"):
        if row["tag"] in wanted_members and row["tlabel"]:
            labels.setdefault(row["tag"], row["tlabel"])

    facts: list[SegmentFact] = []
    for row in rows("num.tsv"):
        if row["coreg"] or row["tag"] not in tags:
            continue
        sub = subs.get(row["adsh"])
        if sub is None or row["dimh"] not in dims:
            continue
        try:
            value = float(row["value"])
        except (ValueError, KeyError):
            continue
        axis, member = dims[row["dimh"]]
        end = _ddate_to_iso(row["ddate"])
        qtrs = int(row["qtrs"] or 0)
        facts.append(SegmentFact(
            cik=int(sub["cik"]), concept=row["tag"], axis=axis, member=member,
            member_label=humanise_member(labels.get(member), member),
            unit=row["uom"], start=_start_for(end, qtrs), end=end, qtrs=qtrs,
            val=value, accn=sub["adsh"], form=sub["form"],
            filed=_ddate_to_iso(sub["filed"]),
        ))
    return facts


def recent_months(count: int, today: dt.date | None = None) -> list[str]:
    """Month keys (YYYY_MM) for the notes data sets, newest first.

    SEC publishes the current month only after it closes, so start one back.
    """
    today = today or dt.date.today()
    year, month = today.year, today.month - 1
    out = []
    for _ in range(count):
        if month == 0:
            year, month = year - 1, 12
        out.append(f"{year}_{month:02d}")
        month -= 1
    return out


def build_cache(months: list[str], ciks: set[int]) -> int:
    """Download each month, keep only our companies' rows, drop the 108MB zip."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    total = 0
    with SecClient() as client:
        for month in months:
            out = CACHE_DIR / f"{month}.jsonl"
            if out.exists():
                total += sum(1 for _ in out.open())
                print(f"  {month}  cached")
                continue
            url = NOTES_URL.format(month=month)
            tmp = CACHE_DIR / f"{month}.zip.part"
            try:
                tmp.write_bytes(client.get_bytes(url))
            except Exception as exc:  # noqa: BLE001
                print(f"  {month}  SKIP ({type(exc).__name__})")
                tmp.unlink(missing_ok=True)
                continue
            try:
                facts = extract(tmp, ciks)
            finally:
                tmp.unlink(missing_ok=True)
            with out.open("w", encoding="utf-8") as fh:
                for fact in facts:
                    fh.write(json.dumps(asdict(fact)) + "\n")
            total += len(facts)
            print(f"  {month}  {len(facts):>5} facts")
    return total


def load_cached() -> list[SegmentFact]:
    facts: list[SegmentFact] = []
    if not CACHE_DIR.exists():
        return facts
    for path in sorted(CACHE_DIR.glob("*.jsonl")):
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    facts.append(SegmentFact(**json.loads(line)))
    return facts


def segment_facts(cik: int, facts: list[SegmentFact] | None = None) -> list[SegmentFact]:
    facts = load_cached() if facts is None else facts
    return [f for f in facts if f.cik == cik]
