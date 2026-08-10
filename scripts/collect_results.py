"""분석 스크립트들이 남긴 조각을 모아 RESULTS.md 를 만든다.

왜 필요한가
-----------
1차 보고서는 수치를 사람이 Word 로 옮겨 적어서, 라벨을 고친 뒤 어느 문장이
틀렸는지 알 수 없었다(실제로 네 문장이 어긋나 있었다). 이제 분석 스크립트가
표와 수치를 data/output/_build/results/*.json 에 적고, 이 스크립트가 한 문서로 모은다.
표마다 어느 스크립트에서 나왔는지 적히므로 다시 뽑을 때 어디를 돌릴지 바로 안다.

출력
----
RESULTS.md   절별로 표와 수치를 펼친 것. 결과를 볼 곳은 여기 하나다.

사용:
    python scripts/analyze_survey.py
    python scripts/analyze_speechact.py
    python scripts/surface_va_probe.py
    python scripts/collect_results.py
"""

import json
import sys
from datetime import date

from speechact_data import RESULTS_DIR, ROOT, SECTIONS

MD_OUT = ROOT / "RESULTS.md"

# 절마다 맨 앞에 붙일 한 줄. 그 절이 무엇에 대한 것인지 먼저 말한다.
LEAD = {
    "참가자": "누가 참여했나.",
    "평소 AI와 무슨 대화를 하는가":
        "실험과 무관하게 평소 용도를 물은 것. 복수응답이라 합이 인원을 넘는다.",
    "이번에 실제로 한 대화": "주제명은 참가자가 직접 적은 것이다.",
    "감정 자기보고 VA":
        "**전 / 주제1 / 주제2 / 후 는 서로 다른 설문 문항**이다. '후−전'만 계산값.",
    "사용자 발화 화행":
        "사용자 발화를 문장으로 쪼개 화행(축 A)과 정서 표면성(축 B)을 붙였다.",
    "정서 표면성과 자기보고": "축 B 와 설문 VA 를 잇는다. 다음 실험의 사전 탐색.",
}
CAVEAT = "제4부 코딩은 **coder1 1인 판정**이라 신뢰도(Cohen's κ)가 아직 없다."
CAVEAT_SECTIONS = {"사용자 발화 화행", "정서 표면성과 자기보고"}


def load():
    items = []
    if RESULTS_DIR.exists():
        for p in sorted(RESULTS_DIR.glob("*.json")):
            items += json.load(open(p, encoding="utf-8"))
    return items


def md_table(headers, rows):
    out = ["| " + " | ".join(str(h) for h in headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) if str(c).strip() else "—"
                                     for c in r) + " |")
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    items = load()
    if not items:
        sys.exit("결과 조각이 없다. 분석 스크립트를 먼저 돌린다.")

    nums = [i for i in items if i["kind"] == "num"]
    tables = [i for i in items if i["kind"] == "table"]

    L = [f"# 분석 결과",
         "",
         f"`{date.today()}` 자동 생성 · 표 {len(tables)}개 · 수치 {len(nums)}개",
         "",
         "> 손으로 고치지 않는다. 값을 바꾸려면 분석 스크립트를 고치고 "
         "`python scripts/collect_results.py` 를 다시 돌린다.",
         "",
         f"> {CAVEAT}",
         "",
         "## 목차", ""]
    present = [s for s in SECTIONS if any(i["section"] == s for i in items)]
    for k, s in enumerate(present, 1):
        L.append(f"{k}. [{s}](#{k}-{s.replace(' ', '-')})")
    L.append("")

    for k, sec in enumerate(present, 1):
        L += [f"## {k}. {sec}", ""]
        if LEAD.get(sec):
            L += [LEAD[sec], ""]
        if sec in CAVEAT_SECTIONS:
            L += [f"> {CAVEAT}", ""]

        for t in [i for i in tables if i["section"] == sec]:
            L += [f"### {t['title']}", ""]
            L += md_table(t["headers"], t["rows"])
            L.append("")
            src = f"`{t['source']}`" + (f" · {t['fig']}" if t["fig"] else "")
            if t["note"]:
                L += [f"> {t['note']}", ">", f"> <sub>{src}</sub>", ""]
            else:
                L += [f"<sub>{src}</sub>", ""]

        sn = [i for i in nums if i["section"] == sec]
        if sn:
            L += ["### 주요 수치", "",
                  "| 항목 | 값 | n | 산출 |", "|---|---|---|---|"]
            for i in sn:
                v = f"**{i['value']}**" + (f" {i['unit']}" if i["unit"] else "")
                src = f"`{i['source']}`" + (f" · {i['fig']}" if i["fig"] else "")
                L.append(f"| {i['item']} | {v} | "
                         f"{i['n'] if i['n'] != '' else '—'} | {src} |")
            L.append("")
            for i in sn:
                if i["note"]:
                    L.append(f"- **{i['item']}** — {i['note']}")
            L.append("")

    L += ["---", "", "## 다시 만드는 법", "",
          "```bash",
          "python scripts/analyze_survey.py      # 설문",
          "python scripts/analyze_speechact.py   # 제4부 화행 코딩",
          "python scripts/surface_va_probe.py    # 표면성 ↔ 자기보고",
          "python scripts/collect_results.py     # 이 파일",
          "python scripts/make_report_charts.py  # 그림 1~6",
          "```", ""]

    MD_OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"절 {len(present)} · 표 {len(tables)} · 수치 {len(nums)}")
    print(f"저장: {MD_OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
