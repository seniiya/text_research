"""제4부 정서 표면성 ↔ 설문 자기보고 VA 의 관계를 잰다.

무엇을 왜 재는가
----------------
다음 실험의 종속변수는 `오차 = |LLM 추정 VA - 자기보고 VA|` 다. 아직 LLM 추정치가
없으므로 그 자리에, 텍스트만 보는 관찰자가 쓸 수 있는 가장 단순한 신호를 넣는다.

    표면 정서 비율 = (EXP + IMP) / 라벨된 문장 수

이 신호가 자기보고를 얼마나 설명하는지가 곧 텍스트 기반 추정의 하한 근거다.
설명력이 낮으면 "텍스트에 안 남는 정서가 있다"는 주장에 자리가 생긴다.

V 만이 아니라 A 도 같이 본다
---------------------------
Valence(유쾌-불쾌)와 Arousal(각성-이완)은 독립 축이다. 표면 정서 비율은 '정서가
드러났는가'라서 방향(V)보다 강도(A)와 논리적으로 더 가깝다. 어느 축이 걸리는지
자체가 자료이므로 축을 합치지 않고 따로 본 뒤, 거리도 참고로 병기한다.

    거리 = sqrt( (V-5)^2 + (A-5)^2 )     중립점(5,5)에서 얼마나 벗어났나

통계량 읽는 법
-------------
r    Pearson 상관계수. -1~+1. 두 값이 같이 움직이는 방향과 세기.
         r = Σ(x-x̄)(y-ȳ) / sqrt( Σ(x-x̄)^2 · Σ(y-ȳ)^2 )
R²   r 을 제곱한 것. y 의 분산 중 x 로 설명되는 비율.
p    귀무가설(모상관 = 0)이 참일 때 이만한 r 이 나올 확률.
         t = r · sqrt( (n-2) / (1-r^2) ),  자유도 n-2 인 t 분포에서 양측 검정
95% CI  Fisher z 변환으로 구한다. r 은 표본분포가 비대칭이라 그대로는 못 쓴다.
         z = artanh(r),  SE = 1/sqrt(n-3),  CI = tanh( z ± 1.96·SE )
        구간이 0 을 가로지르면 부호가 뒤집힐 가능성을 배제할 수 없다는 뜻이다.
        이때 "관계가 없다"고 말하면 안 된다. 검정력이 없어서 못 잡은 것과
        실제로 없는 것은 다르다.

입력
----
data/coding/coder1/P##_speechact.xlsx    speech_act_coder1 · emotion_surface_coder1
                                          (규칙 6 '붙여넣은 문서'는 빈칸이라 자동 제외)
data/deid/survey_analysis.csv             전_V/A · 후_V/A · 주제1_V/A · 주제2_V/A
                                          모두 9점 척도 직접 응답이다. 차이값이 아니다.

출력
----
data/output/pilot_speechact/surface_va_probe.csv     참가자별 표
표준출력                                              상관표 · 괴리 사례

사용: python scripts/surface_va_probe.py
"""

import csv
import math
import sys

import numpy as np
from scipy import stats

from speechact_data import (OUT_DIR, ROOT, SURFACE, Results, load_labels,
                            load_survey, num)

OUT = OUT_DIR / "surface_va_probe.csv"

# 설문 문항 그대로. 파생값이 아니다.
#   전_V/A   "지금 이 순간(대화 시작 직전)의 감정 상태"
#   후_V/A   "지금 이 순간(대화 종료 직후)의 감정 상태"
#   주제n_V/A "그 주제를 이야기할 때의 감정은 어땠나요?"
AXES = ("V", "A")


def build():
    lab = load_labels()
    sv = load_survey()
    recs = []
    for pid, all_rows in sorted(lab.items()):
        rows = [d["emotion_surface_coder1"] for d in all_rows
                if d.get("emotion_surface_coder1")]
        n = len(rows)
        if not n:
            continue
        c = {k: rows.count(k) for k in SURFACE}
        s = sv.get(pid, {})
        rec = dict(pid=pid, n=n, **c, surf=(c["EXP"] + c["IMP"]) / n * 100)
        for ax in AXES:
            rec[f"pre_{ax}"] = num(s.get(f"전_{ax}"))
            rec[f"post_{ax}"] = num(s.get(f"후_{ax}"))
            t = [num(s.get(f"주제{i}_{ax}")) for i in (1, 2)]
            t = [v for v in t if v is not None]
            # 주제가 둘인 참가자가 6명뿐이라 대표값이 필요하다. V 는 가장 부정적인
            # 쪽(최솟값), A 는 가장 각성된 쪽(최댓값)을 쓴다. 어느 쪽이든 '가장
            # 중립에서 먼 에피소드'를 고르는 것이라 기준이 일관된다.
            rec[f"topic_{ax}"] = (min(t) if ax == "V" else max(t)) if t else None
        v, a = rec["topic_V"], rec["topic_A"]
        rec["topic_dist"] = (math.hypot(v - 5, a - 5) if v is not None and a is not None
                             else None)
        recs.append(rec)
    return recs


def corr(recs, key):
    pair = [(r["surf"], r[key]) for r in recs if r.get(key) is not None]
    if len(pair) < 4:
        return None
    x = np.array([p[0] for p in pair], float)
    y = np.array([p[1] for p in pair], float)
    r, p = stats.pearsonr(x, y)
    rho, sp = stats.spearmanr(x, y)
    n = len(pair)
    z, se = math.atanh(r), 1 / math.sqrt(n - 3)          # Fisher z
    lo, hi = math.tanh(z - 1.96 * se), math.tanh(z + 1.96 * se)
    return dict(key=key, n=n, r=r, r2=r * r, p=p, rho=rho, sp=sp, lo=lo, hi=hi)


def n_needed(r, alpha=0.05, cap=2000):
    """이 효과크기가 유의해지려면 표본이 얼마나 필요한가 (사후 참고용)."""
    r = abs(r)
    for n in range(6, cap):
        t = r * math.sqrt((n - 2) / (1 - r ** 2))
        if 2 * (1 - stats.t.cdf(t, n - 2)) < alpha:
            return n
    return None


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    recs = build()
    print(f"라벨 완료 {len(recs)}명 · {sum(r['n'] for r in recs)}문장"
          f"  (빈칸·붙여넣은 문서 제외)\n")

    hdr = f"{'pid':<5}{'n':>4}{'EXP':>5}{'IMP':>5}{'NONE':>6}{'표면%':>8}"
    hdr += "".join(f"{k:>9}" for k in ("주제V", "주제A", "전V", "전A", "후V", "후A", "거리"))
    print(hdr)
    print("-" * len(hdr))
    f = lambda v: "  -" if v is None else f"{v:.1f}"
    for r in sorted(recs, key=lambda r: -r["surf"]):
        print(f"{r['pid']:<5}{r['n']:>4}{r['EXP']:>5}{r['IMP']:>5}{r['NONE']:>6}"
              f"{r['surf']:>7.1f}%"
              + "".join(f"{f(r[k]):>9}" for k in
                        ("topic_V", "topic_A", "pre_V", "pre_A", "post_V", "post_A",
                         "topic_dist")))

    print("\n\n[상관]  x = 표면 정서 비율 (EXP+IMP %)")
    print(f"{'y':<26}{'n':>4}{'r':>9}{'R2':>7}{'p':>8}"
          f"{'95% CI':>20}{'rho':>8}{'p':>8}{'필요n':>7}")
    print("-" * 97)
    NAMES = [("topic_V", "주제 Valence (최솟값)"), ("topic_A", "주제 Arousal (최댓값)"),
             ("topic_dist", "주제 중립점 거리"),
             ("pre_V", "전 Valence"), ("pre_A", "전 Arousal"),
             ("post_V", "후 Valence"), ("post_A", "후 Arousal")]
    rows = []
    for key, name in NAMES:
        c = corr(recs, key)
        if not c:
            continue
        nn = n_needed(c["r"])
        star = " *" if c["p"] < .05 else ""
        print(f"{name:<26}{c['n']:>4}{c['r']:>+9.3f}{c['r2']:>7.3f}{c['p']:>8.3f}"
              f"{f'[{c[chr(108)+chr(111)]:+.2f}, {c[chr(104)+chr(105)]:+.2f}]':>20}"
              f"{c['rho']:>+8.3f}{c['sp']:>8.3f}{(nn or '>2000'):>7}{star}")
        rows.append((name, c))
    print("\n  * p < .05  ·  95% CI 가 0 을 가로지르면 부호를 확정할 수 없다."
          "\n  '관계 없음'이 아니라 '검정력 부족'으로 읽어야 한다.")

    R = Results("V", "surface_va_probe.py")
    for name, c in rows:
        R.add(f"정서 표면 비율 ↔ {name}", c["r"], "r", n=c["n"],
              status="확정" if c["p"] < .05 else "탐색",
              note=f"R²={c['r2']:.3f} · p={c['p']:.3f} · 95% CI "
                   f"[{c['lo']:+.2f}, {c['hi']:+.2f}] · 유의해지려면 n≥{n_needed(c['r'])}")
    worst = max(rows, key=lambda kv: kv[1]["r2"])[1]
    R.add("자기보고 VA 중 정서 표면 비율로 설명되는 분산의 최댓값",
          worst["r2"] * 100, "%", n=worst["n"], status="탐색", fig="그림 6",
          note="네 시점(전·주제·후) × 두 축(V·A) + 중립점 거리 중 가장 큰 값")

    print("\n[교란 확인] 표면 비율 ↔ 대화 길이")
    x = np.array([r["surf"] for r in recs]); y = np.array([r["n"] for r in recs])
    rr, pp = stats.pearsonr(x, y)
    print(f"  r = {rr:+.3f}  p = {pp:.3f}")

    print("\n[괴리 사례] 자기보고 부정(V<=4) 인데 발화에 정서가 안 드러난 순")
    for r in sorted((r for r in recs if (r["topic_V"] or 9) <= 4),
                    key=lambda r: r["surf"]):
        print(f"  {r['pid']}  V{r['topic_V']:.0f} A{r['topic_A']:.0f}"
              f"  표면 {r['surf']:>4.0f}%   NONE {r['NONE']}/{r['n']}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(recs[0].keys()))
        w.writeheader()
        w.writerows(recs)
    print(f"\n저장: {OUT.relative_to(ROOT)}")
    R.save()


if __name__ == "__main__":
    main()
