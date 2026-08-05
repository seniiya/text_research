"""제4부 1차 분석. 보고서(화행코딩_1차보고).docx 의 모든 수치를 여기서 만든다.

이 파일이 있는 이유
------------------
1차 보고서는 수치를 임시 스크립트로 뽑아 Word 에 옮겨 적어 재현이 안 됐다.
라벨이 하나 바뀌면 보고서의 어느 문장이 틀리는지 알 수 없다는 뜻이다.
그래서 보고서에 등장하는 값은 전부 이 스크립트가 출력한다.

출력
----
표준출력                                            절별 수치 (보고서 문장과 1:1)
data/output/pilot_speechact/report_stats.json      make_report_charts.py 입력
data/output/pilot_speechact/participants.csv       참가자별 표

사용: python scripts/analyze_speechact.py
"""

import json
import sys
from collections import Counter, defaultdict

import numpy as np
from scipy import stats

from speechact_data import (CODES_3I4K, CORPUS_3I4K, CORPUS_3I4K_N, OUT_DIR,
                            ROOT, SPEECH_ACT, SURFACE, load_labels, load_survey,
                            load_v1, num)

# 발견 1. '직전 AI 응답이 길다' 의 기준. 임계값은 아직 정하지 않았으므로
# 자동 판정에 쓰지 않고 C 코드 발화의 직전 응답 길이를 전부 나열만 한다.
PUSHBACK_KEYWORDS = ("길게", "길지", "말이 너무 많")
# 그림 1은 문장 수가 적은 참가자를 빼야 비율이 읽힌다. 보고서 캡션의 'n>=10문장'.
C1_MIN_SENTENCES = 10


def section(t):
    print(f"\n{'=' * 72}\n{t}\n{'=' * 72}")


def pct(a, b):
    return a / b * 100 if b else 0.0


def cramers_v(table):
    chi2, p, dof, _ = stats.chi2_contingency(table)
    n = table.sum()
    v = np.sqrt(chi2 / (n * (min(table.shape) - 1)))
    return chi2, p, dof, v


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    lab = load_labels()
    allrows = load_labels(include_unlabeled=True)
    sv = load_survey()
    rows = [d for v in lab.values() for d in v]
    both = [d for d in rows if d.get("emotion_surface_coder1")]
    st = {}

    # ── 진행률 ────────────────────────────────────────────────────────
    section("0. 코딩 진행률")
    total_sent = sum(len(v) for v in allrows.values())
    done = sorted(lab)
    todo = sorted(set(allrows) - set(lab))
    print(f"참가자        {len(done)} / {len(allrows)} 명   미코딩: {', '.join(todo) or '없음'}")
    print(f"화행 라벨     {len(rows)} / {total_sent} 문장  ({pct(len(rows), total_sent):.0f}%)")
    print(f"두 축 모두    {len(both)} 문장")
    if len(rows) != len(both):
        miss = [f"{d['p_id']}·{d['utterance_id']}" for d in rows
                if not d.get("emotion_surface_coder1")]
        print(f"  ! 정서 표면성이 빈 행 {len(rows) - len(both)}건 — {', '.join(miss)}")
        print("    보고서의 '319문장'(화행)과 '318문장'(교차표) 차이가 여기서 난다.")
    print(f"미코딩 문장   {total_sent - len(rows)} ({pct(total_sent - len(rows), total_sent):.0f}%)"
          f"  — {', '.join(f'{p}({len(allrows[p])})' for p in todo)}")
    st["n_participants"] = len(done)
    st["n_act"], st["n_both"], st["n_total"] = len(rows), len(both), total_sent

    # ── 축 A 분포 (그림 4) ────────────────────────────────────────────
    section("1. 축 A 화행 분포  [그림 4]")
    ca = Counter(d["speech_act_coder1"] for d in rows)
    st["dist_a"] = [(c, ca.get(c, 0)) for c in SPEECH_ACT]
    for c, n in st["dist_a"]:
        bar = "관찰되지 않음" if not n else f"{n:>4}  {pct(n, len(rows)):>5.1f}%"
        print(f"  {c:<8}{bar}")
    print(f"\n  UNC {ca.get('UNC', 0)}건 · RC {ca.get('RC', 0)}건 · "
          f"RQ {pct(ca.get('RQ', 0), len(rows)):.1f}%")

    # ── 축 A × 축 B (그림 2) ─────────────────────────────────────────
    section("2. 화행 × 정서 표면성  [그림 2]")
    cross = defaultdict(Counter)
    for d in both:
        cross[d["speech_act_coder1"]][d["emotion_surface_coder1"]] += 1
    used = [c for c in SPEECH_ACT if sum(cross[c].values())]
    print(f"  {'':<8}{'EXP':>5}{'IMP':>5}{'NONE':>6}{'계':>5}{'정서%':>8}")
    st["cross"] = []
    for c in used:
        r = [cross[c][k] for k in SURFACE]
        t = sum(r)
        st["cross"].append((c, *r))
        print(f"  {c:<8}{r[0]:>5}{r[1]:>5}{r[2]:>6}{t:>5}{pct(r[0] + r[1], t):>7.0f}%")
    marg = Counter(d["emotion_surface_coder1"] for d in both)
    print(f"  {'계':<8}{marg['EXP']:>5}{marg['IMP']:>5}{marg['NONE']:>6}{len(both):>5}")

    # 화행을 알면 정서를 맞힐 수 있나 — 보고서 '발견 4' 의 근거
    base = pct(marg.most_common(1)[0][1], len(both))
    hit = sum(max(cross[c].values()) for c in used)
    tbl = np.array([[cross[c][k] for k in SURFACE] for c in used])
    chi2, p, dof, v = cramers_v(tbl)
    print(f"\n  [화행으로 정서를 맞힐 수 있나]")
    print(f"    무조건 최빈값(NONE)      {base:.1f}%")
    print(f"    화행별 최빈 정서         {pct(hit, len(both)):.1f}%"
          f"   (+{pct(hit, len(both)) - base:.1f}%p)")
    print(f"    chi2 = {chi2:.1f}  df = {dof}  p = {p:.2e}  Cramer's V = {v:.3f}")
    print("    → 두 축은 연관되지만 서로를 대체하지 못한다.")
    s = cross["S"]
    print(f"    S {sum(s.values())}건: EXP {s['EXP']} · IMP {s['IMP']} · NONE {s['NONE']}"
          f"  (정서 {pct(s['EXP'] + s['IMP'], sum(s.values())):.0f}%)")
    st.update(baseline=base, act_acc=pct(hit, len(both)), chi2=chi2, cramers_v=v)

    # ── 발견 1. 응답 길이 pushback ───────────────────────────────────
    section("3. 발견 1 — AI 응답이 길면 사용자가 제지한다")
    push = [d for d in rows
            if any(k in str(d.get("text", "")) for k in PUSHBACK_KEYWORDS)]
    for d in sorted(push, key=lambda d: d["utterance_id"]):
        ctx = len(str(d.get("prev_assistant_turn") or ""))
        print(f"  {d['p_id']} {d['utterance_id']:<14} [{d['speech_act_coder1']:<6}] "
              f"직전 AI {ctx:>5}자  \"{str(d['text'])[:42]}\"")
    ctxlen = [len(str(d.get("prev_assistant_turn") or "")) for d in rows
              if d.get("prev_assistant_turn")]
    print(f"\n  참고 · 직전 AI 응답 길이 전체 중앙값 {int(np.median(ctxlen))}자 "
          f"(n={len(ctxlen)})")
    print(f"  C 코드 {ca.get('C', 0)}건 중 위 유형 {len(push)}건. 임계값은 미정이다.")
    st["pushback"] = [(d["p_id"], d["utterance_id"], d["speech_act_coder1"],
                       len(str(d.get("prev_assistant_turn") or "")),
                       str(d["text"])[:60]) for d in push]

    # ── 발견 2. 물음표 ───────────────────────────────────────────────
    section("4. 발견 2 — 물음표가 붙었다고 질문이 아니다")
    qm = [d for d in rows if str(d.get("text", "")).rstrip().endswith("?")]
    notq = [d for d in qm if d["speech_act_coder1"] != "Q"]
    print(f"  물음표로 끝나는 문장 {len(qm)}건 중 Q 가 아닌 것 {len(notq)}건 "
          f"({pct(len(notq), len(qm)):.0f}%)")
    for c, n in Counter(d["speech_act_coder1"] for d in notq).most_common():
        print(f"    {c:<8}{n:>3}")
    print("\n  예시")
    for d in notq[:6]:
        print(f"    {d['p_id']} {d['utterance_id']:<14} → {d['speech_act_coder1']:<6}"
              f" \"{str(d['text'])[:46]}\"")
    st["qmark"] = dict(total=len(qm), not_q=len(notq))

    # ── 발견 3. 참가자별 (그림 1) ────────────────────────────────────
    section("5. 발견 3 — 참가자별 정서 비율 vs 설문 자기보고  [그림 1]")
    parts = []
    for pid in done:
        r = [d for d in lab[pid] if d.get("emotion_surface_coder1")]
        if not r:
            continue
        c = Counter(d["emotion_surface_coder1"] for d in r)
        s = sv.get(pid, {})
        parts.append(dict(
            pid=pid, n=len(r), **{k: c[k] for k in SURFACE},
            surf=pct(c["EXP"] + c["IMP"], len(r)),
            topic=s.get("주제1", ""), v=num(s.get("주제1_V")), a=num(s.get("주제1_A")),
            word=s.get("주제1_감정단어", ""),
            pre_v=num(s.get("전_V")), post_v=num(s.get("후_V"))))
    parts.sort(key=lambda r: -r["surf"])
    print(f"  {'pid':<5}{'n':>4}{'정서%':>7}{'V':>4}{'A':>4}  {'감정단어':<12}주제")
    for r in parts:
        mark = "*" if (r["v"] or 9) <= 3 else " "
        print(f" {mark}{r['pid']:<5}{r['n']:>4}{r['surf']:>6.0f}%"
              f"{('-' if r['v'] is None else int(r['v'])):>4}"
              f"{('-' if r['a'] is None else int(r['a'])):>4}  "
              f"{str(r['word'])[:11]:<12}{str(r['topic'])[:26]}")
    print("\n  * = 자기보고 부정 (주제1 V<=3)")
    neg = [r for r in parts if (r["v"] or 9) <= 3]
    print(f"  자기보고 부정 {len(neg)}명의 정서 비율: "
          + " · ".join(f"{r['pid']} {r['surf']:.0f}%" for r in sorted(neg, key=lambda r: r["surf"])))
    st["participants"] = parts
    st["c1"] = [r for r in parts if r["n"] >= C1_MIN_SENTENCES]

    # 전→후 는 코딩 여부와 무관한 설문 값이므로 전원(22명) 기준이 기본이다.
    # 코딩된 18명만으로도 같이 내서, 보고서에 어느 쪽을 썼는지 헷갈리지 않게 한다.
    def prepost(ids, label):
        a = [num(sv[p].get("전_V")) for p in ids if num(sv[p].get("전_V")) is not None]
        b = [num(sv[p].get("후_V")) for p in ids if num(sv[p].get("후_V")) is not None]
        print(f"  {label:<16} 전_V {np.mean(a):.2f} (n={len(a)}) → "
              f"후_V {np.mean(b):.2f} (n={len(b)})   {np.mean(b) - np.mean(a):+.2f}")
        return np.mean(a), np.mean(b)

    print()
    st["prepost_all"] = prepost(sorted(sv), "설문 전원")
    st["prepost_coded"] = prepost([r["pid"] for r in parts], "코딩된 참가자")

    # ── v1 → v2 (그림 3) ────────────────────────────────────────────
    section("6. 원 체계(v1) → 보완 체계(v2)  [그림 3]")
    v1 = load_v1("P04")
    if v1:
        key = {(d["utterance_id"], d["text"]): d["speech_act_coder1"] for d in v1}
        pair = [(key.get((d["utterance_id"], d["text"])), d["speech_act_coder1"])
                for d in lab.get("P04", [])]
        pair = [(a, b) for a, b in pair if a]
        c1c = Counter(a for a, _ in pair)
        c2c = Counter(b for _, b in pair)
        codes = [c for c in SPEECH_ACT if c1c[c] or c2c[c]] + ["UNC"]
        codes = list(dict.fromkeys(codes))
        print(f"  P04 동일한 {len(pair)}문장")
        print(f"  {'':<8}{'v1':>4}{'v2':>4}")
        st["v1v2"] = []
        for c in codes:
            if c1c[c] or c2c[c]:
                print(f"  {c:<8}{c1c[c]:>4}{c2c[c]:>4}")
                st["v1v2"].append((c, c1c[c], c2c[c]))
        print("\n  전이")
        for (a, b), n in Counter(pair).most_common():
            if a != b:
                print(f"    {a:<6} → {b:<6} {n:>3}")
        keep = [(a, b) for a, b in pair if a == b]
        print(f"    (변화 없음 {len(keep)}건)")
        moved_q = [1 for a, b in pair if a in ("Q", "RQ") and a != b]
        print(f"\n  Q·RQ 가 움직인 건수: {len(moved_q)}  "
              f"→ 의도 층위는 유효하고 대화행위 층위만 비어 있었다는 근거")
    else:
        print("  P04_speechact_v1.xlsx 없음")

    # ── 3i4K 원 코퍼스 대조 (그림 5) ────────────────────────────────
    section("7. 3i4K 원 코퍼스 대조  [그림 5]")
    only6 = [d for d in rows if d["speech_act_coder1"] in CODES_3I4K]
    c6 = Counter(d["speech_act_coder1"] for d in only6)
    print(f"  본 연구 n={len(only6)} (전체 {len(rows)} - 추가 3코드 "
          f"{len(rows) - len(only6)})   ·   원 코퍼스 n={CORPUS_3I4K_N}")
    print(f"  {'':<8}{'원 코퍼스':>10}{'본 연구':>10}{'차이':>9}")
    st["c5"] = []
    for c in CODES_3I4K:
        mine = pct(c6[c], len(only6))
        d = mine - CORPUS_3I4K[c]
        print(f"  {c:<8}{CORPUS_3I4K[c]:>9.1f}%{mine:>9.1f}%{d:>+8.1f}p")
        st["c5"].append((c, CORPUS_3I4K[c], mine))
    st["n_3i4k"] = len(only6)

    # ── 저장 ─────────────────────────────────────────────────────────
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "report_stats.json", "w", encoding="utf-8") as fh:
        json.dump(st, fh, ensure_ascii=False, indent=1)
    import csv as _csv
    with open(OUT_DIR / "participants.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = _csv.DictWriter(fh, fieldnames=list(parts[0].keys()))
        w.writeheader()
        w.writerows(parts)
    print(f"\n저장: {(OUT_DIR / 'report_stats.json').relative_to(ROOT)}"
          f"\n      {(OUT_DIR / 'participants.csv').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
