"""제4부 코딩 시트와 설문을 읽는 공용 로더.

분석 스크립트가 세 개(analyze_speechact · make_report_charts · surface_va_probe)라
로딩을 각자 구현하면 제외 규칙이 어긋난다. 실제로 '규칙 6 붙여넣은 문서는 빈칸'
같은 규칙은 한 군데서만 틀려도 문장 수가 달라져 보고서 수치가 갈린다.
그래서 읽기는 전부 이 파일을 거친다.

정본은 XLSX 다. CSV 는 sync_labels.py 가 XLSX 에서 뽑아 Git 에 보이게 한 사본이라
여기서는 XLSX 만 읽는다.
"""

import csv
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent.parent
CODER1 = ROOT / "data" / "coding" / "coder1"
SURVEY_CSV = ROOT / "data" / "deid" / "survey_analysis.csv"
OUT_DIR = ROOT / "data" / "output" / "pilot_speechact"
REPORT_DIR = ROOT / "data" / "output" / "report"

# 축 A. 목록 순서가 곧 판정 우선순위이자 표·차트의 정렬 순서다.
SPEECH_ACT = ["FRAG", "RESP", "PHATIC", "EXPR", "Q", "C", "RQ", "RC", "S", "UNC"]
# 3i4K 원 체계에 있는 6코드. 원 코퍼스와 대조할 때 이것만 쓴다.
CODES_3I4K = ["FRAG", "S", "Q", "C", "RQ", "RC"]
# 대화행위 표준에서 가져와 채운 3코드 (ISO 24617-2 · DAMSL · Searle 1976).
CODES_ADDED = ["RESP", "PHATIC", "EXPR"]
SURFACE = ["EXP", "IMP", "NONE"]

# 3i4K 원 코퍼스 분포 (Cho et al. 2018, IU 제외 후 재정규화). 논문 수치이므로 상수다.
CORPUS_3I4K = {"FRAG": 2.2, "S": 45.3, "Q": 20.1, "C": 25.8, "RQ": 3.5, "RC": 3.2}
CORPUS_3I4K_N = 17735


def _cell(v):
    return v.strip() if isinstance(v, str) else v


def sheet_rows(path):
    """코딩 시트 한 장을 dict 목록으로. 빈 라벨은 None 이 아니라 '' 로 통일한다.

    prev_assistant_turn 은 시트에서 **턴의 첫 문장에만** 적혀 있다(같은 값을 문장마다
    반복하면 읽을 수 없기 때문). 분석에서 't08-s02 의 직전 AI 응답 길이'를 물으면
    0 이 나와 버리므로, 여기서 턴 안으로 채워 넣는다.
    """
    ws = load_workbook(path, data_only=True)["coding"]
    head = [c.value for c in ws[1]]
    out = []
    ctx, turn = "", None
    for r in ws.iter_rows(min_row=2, values_only=True):
        d = {h: _cell(v) for h, v in zip(head, r)}
        if not d.get("text"):
            continue
        if d.get("turn_index") != turn:
            turn, ctx = d.get("turn_index"), d.get("prev_assistant_turn") or ""
        d["prev_assistant_turn"] = d.get("prev_assistant_turn") or ctx
        out.append(d)
    return out


def load_labels(include_unlabeled=False):
    """{p_id: [행, ...]}.

    기본값은 **화행이 채워진 행만** 준다. 규칙 6(붙여넣은 문서)에 걸린 행은
    두 축이 모두 빈칸이라 여기서 자동으로 빠진다.
    include_unlabeled=True 면 미코딩 참가자를 포함한 전체를 준다 (진행률 계산용).
    """
    out = {}
    for x in sorted(CODER1.glob("P*_speechact.xlsx")):
        if "_v1" in x.name:                       # 원 체계 대조본은 별도 함수로
            continue
        pid = x.name.split("_")[0]
        rows = sheet_rows(x)
        for d in rows:
            d["p_id"] = pid
        out[pid] = rows if include_unlabeled else [
            d for d in rows if d.get("speech_act_coder1")]
    return {k: v for k, v in out.items() if v or include_unlabeled}


def load_v1(pid="P04"):
    """원 체계(v1) 코딩본. P04 한 명뿐이다."""
    p = CODER1 / f"{pid}_speechact_v1.xlsx"
    return sheet_rows(p) if p.exists() else []


def load_survey():
    with open(SURVEY_CSV, encoding="utf-8-sig") as fh:
        return {r["p_id"]: r for r in csv.DictReader(fh)}


def num(s):
    try:
        return float(str(s).strip())
    except (ValueError, AttributeError, TypeError):
        return None
