# 간접화법 연구 — AI 응답 전략 분석

사용자가 ChatGPT와 나눈 실제 대화에서, AI 응답이 8가지 지원 전략(ESConv) 중
어디에 분량을 배분했는지 측정한다. 참여자의 사전·사후 감정 상태(SAM valence/arousal)와
함께 분석한다.

- 참여자 11명, ChatGPT 대화 11건 — 총 280 메시지 (Prompt 140 / Response 140)
- 코딩 기준: [codebook_part1.md](codebook_part1.md)
- 전략 분류 출처: Liu et al. (2021), *Towards Emotional Support Dialog Systems*, ACL 2021

## 데이터 접근 정책

**이 저장소에는 개인 식별정보가 포함되지 않는다.** 참여자는 `P01`~`P11` 가명으로만
표기된다.

원자료(`data/raw/`, `data/survey/`)에는 참여자 실명과 ChatGPT 공개 share URL이
들어 있어 `.gitignore`로 제외되어 있으며, Git 히스토리에 한 번도 올라간 적이 없다.
share URL은 링크만 알면 누구나 열람할 수 있으므로 특히 주의한다.

가명–실명 연결키는 `data/private/mapping.csv`에 생성되며, 이 역시 저장소 밖에서만
보관한다.

**공동연구자 여러분께** — 분석에 필요한 데이터는 전부 `data/deid/`에 있다.
원자료가 필요한 경우 저장소가 아니라 연구책임자에게 별도로 요청한다.

## 디렉터리 구조

```
data/
  deid/                    ← 공유 대상. 가명화 완료.
    chats/P01.json … P11.json    대화 로그 (user.name = P##, share URL 제거)
    survey_analysis.csv          설문 분석표 (p_id 기준)
    index.csv                    P## → 대화 제목, 메시지 수
  coding/                  ← 코딩 결과 (p_id 기준)
  output/                  ← 분석 산출물

  raw/                     ← Git 제외. 원본 대화 JSON (파일명에 실명)
  survey/                  ← Git 제외. 설문 원본 (실명·share URL)
  private/                 ← Git 제외. 가명–실명 연결키

scripts/
  deidentify.py            원자료 → data/deid/ 가명화
codebook_part1.md          제1부 코딩북 (AI 응답 전략)
```

## 가명 데이터 재생성

원자료를 가진 사람만 실행할 수 있다. 공동연구자는 실행할 필요가 없다.

```bash
python scripts/deidentify.py
```

스크립트는 마지막에 검증 단계를 돌려 `data/deid/` 전체를 훑고, 실명·URL·이메일·
전화번호가 하나라도 남아 있으면 비정상 종료한다.

### 설문 CSV 구조 주의

설문 원본 한 파일에 표가 두 개 세로로 쌓여 있다. 스크립트가 이를 분리한다.

| 표 | 위치 | 내용 |
|---|---|---|
| A | 0행 헤더, 1~11행 | 접수 응답. 실명·share URL 포함 → 연결키 생성에만 사용 |
| B | `p_id` 헤더 행 이후 | 분석표. 이미 `P01`~`P11` 기준 → 그대로 공유 |

## 데이터 형식

`data/deid/chats/P##.json`:

```json
{
  "metadata": {
    "title": "대화 제목",
    "user": { "name": "P04" },
    "dates": { "created": "...", "updated": "...", "exported": "..." }
  },
  "messages": [
    { "role": "Prompt",   "say": "사용자 발화", "time": "..." },
    { "role": "Response", "say": "AI 응답",    "time": "..." }
  ]
}
```

`role`이 `Prompt`면 사용자, `Response`면 AI다. 코딩 대상은 `Response`뿐이다
(코딩북 §2 참조).
