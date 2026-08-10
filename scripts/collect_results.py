"""분석 스크립트들이 남긴 결과 조각을 모아 results.csv 와 RESULTS.md 를 만든다.

왜 필요한가
-----------
1차 보고서는 수치를 사람이 Word 로 옮겨 적어서, 라벨을 고친 뒤 어느 문장이
틀렸는지 알 수 없었다(실제로 세 문장이 어긋나 있었다). 이제 각 분석 스크립트가
주장할 만한 값을 data/output/results/*.json 에 적고, 이 스크립트가 모은다.
발표·논문 문장은 여기 있는 값과 대조하면 된다.

**'상태' 열이 값보다 중요하다.** 그 수치를 어디까지 말해도 되는지를 정한다.
  확정  세기만 하면 되는 값. 코더가 1명이어도 다시 세면 같다
  잠정  판정이 들어간 값. κ 가 없어 신뢰도가 검증되지 않았다
  탐색  검정력이 부족하다. 방향만 말하고 '없다'고 말하면 안 된다
  관찰  사례 수준. 통계로 주장하지 않는다

출력
----
data/output/results.csv    1행 = 1주장 (기계용)
RESULTS.md                 같은 내용을 부·상태별로 펼친 것 (사람용)

사용:
    python scripts/analyze_survey.py
    python scripts/analyze_speechact.py
    python scripts/surface_va_probe.py
    python scripts/collect_results.py
"""

import csv
import json
import sys
from datetime import date

from speechact_data import FIELDS, RESULTS_DIR, ROOT, STATUS

CSV_OUT = ROOT / "data" / "output" / "results.csv"
MD_OUT = ROOT / "RESULTS.md"

# 조각 파일이 나오는 순서. 없으면 건너뛴다.
ORDER = ["S", "A", "V"]
PART_ORDER = ["공통", "제1부", "제2부", "제3부", "제4부"]
# 발표·논문에서 단정해도 되는 순서. RESULTS.md 를 이 순으로 묶는다.
STATUS_ORDER = ["확정", "잠정", "탐색", "관찰"]


def load():
    rows = []
    for pfx in ORDER:
        p = RESULTS_DIR / f"{pfx}.json"
        if p.exists():
            rows += json.load(open(p, encoding="utf-8"))
    extra = sorted(x for x in RESULTS_DIR.glob("*.json")
                   if x.stem not in ORDER) if RESULTS_DIR.exists() else []
    for p in extra:
        rows += json.load(open(p, encoding="utf-8"))
    return rows


def fmt(r):
    v = f"**{r['값']}**{r['단위']}" if r["단위"] else f"**{r['값']}**"
    n = f"n={r['n']}" if r["n"] != "" else "—"
    return v, n


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    rows = load()
    if not rows:
        sys.exit("결과 조각이 없다. 분석 스크립트를 먼저 돌린다 "
                 "(analyze_survey.py · analyze_speechact.py · surface_va_probe.py)")

    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(CSV_OUT, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    by_status = {s: [r for r in rows if r["상태"] == s] for s in STATUS_ORDER}
    L = [
        "# 분석 결과 모음",
        "",
        f"`{date.today()}` 자동 생성 · 총 **{len(rows)}건**",
        "",
        "> 이 파일은 손으로 고치지 않는다. 값을 바꾸려면 분석 스크립트를 고치고",
        "> `python scripts/collect_results.py` 를 다시 돌린다.",
        "> 기계용 표는 [`data/output/results.csv`](data/output/results.csv).",
        "",
        "## 이 표를 어떻게 읽나",
        "",
        "**`상태` 가 값보다 중요하다.** 그 수치를 발표·논문에서 어디까지 말해도 되는지를 정한다.",
        "",
        "| 상태 | 건수 | 뜻 |",
        "|---|---|---|",
    ]
    for s in STATUS_ORDER:
        L.append(f"| **{s}** | {len(by_status[s])} | {STATUS[s]} |")
    L += ["",
          "지금은 코더가 1명이라 판정이 들어간 값은 전부 `잠정` 이다. "
          "두 번째 코더가 독립 코딩해 Cohen's κ 가 나오면 `확정` 으로 올라간다.",
          ""]

    for s in STATUS_ORDER:
        sel = by_status[s]
        if not sel:
            continue
        L += [f"## {s}", "", f"*{STATUS[s]}*", ""]
        for part in PART_ORDER + sorted({r["부"] for r in sel} - set(PART_ORDER)):
            grp = [r for r in sel if r["부"] == part]
            if not grp:
                continue
            L += [f"### {part}", "",
                  "| | 항목 | 값 | n | 그림 | 산출 |",
                  "|---|---|---|---|---|---|"]
            for r in grp:
                v, n = fmt(r)
                L.append(f"| `{r['result_id']}` | {r['항목']} | {v} | {n} | "
                         f"{r['그림'] or '—'} | `{r['산출']}` |")
            L.append("")
            for r in grp:
                if r["비고"]:
                    L.append(f"- `{r['result_id']}` {r['비고']}")
            L.append("")

    L += ["## 산출 스크립트", "",
          "| 스크립트 | 결과 | 다시 돌리는 법 |", "|---|---|---|"]
    for src in dict.fromkeys(r["산출"] for r in rows):
        n = sum(1 for r in rows if r["산출"] == src)
        L.append(f"| [`{src}`](scripts/{src}) | {n}건 | `python scripts/{src}` |")
    L += ["",
          "네 개를 순서대로 돌리면 이 파일이 새로 만들어진다.",
          "",
          "```bash",
          "python scripts/analyze_survey.py",
          "python scripts/analyze_speechact.py",
          "python scripts/surface_va_probe.py",
          "python scripts/collect_results.py",
          "```",
          ""]

    MD_OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"결과 {len(rows)}건  ·  "
          + " · ".join(f"{s} {len(by_status[s])}" for s in STATUS_ORDER))
    print(f"저장: {CSV_OUT.relative_to(ROOT)}\n      {MD_OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
