#!/usr/bin/env python3
"""현대해상 굿앤굿어린이종합보험Q(Hi2607) 약관 조회 도구.

사용법 (스킬 폴더에서):  python3 scripts/kb.py <명령> [인자]
  ask "<질문>[ || 질문2 ..]" [id,id..]   ★ 기본(|| 로 여러 질문 한 번에). 질문 1개 → 관련 특약 사실(facts) + 근거 원문 항(출처 포함) 상위 목록을 한 번에
  item <설계항목명>          설계 화면 항목명 → 특약 id·하위 구분 (ask가 자동 적용)
  faq [FAQ-id]             자주 묻는 주제별 근거 묶음(ask가 자동으로 붙여 줌)
  rows <별표id> [단어..]     별표 표에서 단어가 든 행만 (머리글 포함) — 예: rows 별표-26 2종
  facts <id>               특약 핵심 사실(한도·갱신·가입종·관련별표·조목록·같은계열) — 짧음
  para <pid> [pid..]       항 단위 원문 전문 + 표준 출처 (ask 결과의 P번호)
  article <id> <조> [조..]  특약 원문 해당 조 전체(여러 조 한 번에) (공통조항이면 원문 자동 펼침)
  find <검색어>            특약·보통약관·별표·주제 후보 찾기
  card <id>                특약 요약 카드(긴 조는 잘림 — 인용 금지, 개요용)
  arts <id>                특약의 조 목록
  show <id> [최대줄|refs]   아무 문서 출력 (보통-08, 별표-32, C-08, 계열-…, 개요-…, 주제-…)
  code <코드|질병명>        질병코드/질병명 → 별표 → 보장 특약 (범위코드 J12~J18 도 판정)
  grep <문구> [id|최대건수] 원문 문구 검색 (id를 주면 그 문서 안에서만)
"""
import os, re, sys, csv, json, math

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'references')
IDX = os.path.join(BASE, 'index.tsv')
csv.field_size_limit(10 ** 8)


def norm(s):
    s = re.sub(r'[^가-힣a-z0-9ⅰ-ⅿⅠ-Ⅿ]', '', s.lower())
    return s.replace('특별약관', '').replace('보장', '').replace('약관', '')


_cache = {}
def load_index():
    if 'idx' not in _cache:
        rows = list(csv.DictReader(open(IDX, encoding='utf-8'), delimiter='\t'))
        _cache['idx'] = (rows, {r['id']: r for r in rows})
    return _cache['idx']


def load_facts():
    if 'facts' not in _cache:
        _cache['facts'] = json.load(open(os.path.join(BASE, 'facts.json'), encoding='utf-8'))
    return _cache['facts']


def load_paras():
    if 'para' not in _cache:
        _cache['para'] = list(csv.DictReader(open(os.path.join(BASE, 'para.tsv'), encoding='utf-8'), delimiter='\t'))
    return _cache['para']


def body(path):
    t = open(os.path.join(BASE, path), encoding='utf-8').read()
    if t.startswith('---'):
        t = t.split('\n---\n', 1)[-1]
    return t.strip()


def resolve(i):
    rows, by = load_index()
    if i in by:
        return by[i]
    m = re.fullmatch(r'별표\s*-?(\d+(?:-\d+)?)', i)
    if m and f'별표-{m.group(1)}' in by:
        return by[f'별표-{m.group(1)}']
    m = re.fullmatch(r'(?:보통|보통약관)?\s*-?(\d{1,2})조?', i)
    if m and f'보통-{int(m.group(1)):02d}' in by:
        return by[f'보통-{int(m.group(1)):02d}']
    sys.exit(f'id를 찾을 수 없음: {i}  (find 로 먼저 검색)')


def score_docs(q):
    rows, _ = load_index()
    qn = norm(q)
    toks = [norm(t) for t in q_tokens(q) if len(norm(t)) >= 2]
    scored = []
    for r in rows:
        tn = norm(r['title'])
        hay = tn + norm(r.get('aliases', '')) + norm(r.get('tags', '')) + norm(r.get('oneliner', ''))
        s = 0
        if qn and qn == tn:
            s += 100
        if qn and qn in tn:
            s += 50
        if qn and qn in hay:
            s += 20
        s += sum(8 for t in toks if t in tn) + sum(3 for t in toks if t in hay)
        if s:
            if r['kind'] in ('특약', '하위보장'):
                s += 2
            scored.append((s, r))
    scored.sort(key=lambda x: -x[0])
    return scored


def cmd_find(q):
    sc = score_docs(q)
    if not sc:
        print('결과 없음 → 다른 표현(띄어쓰기 없이 핵심 명사) 또는 grep 사용')
    for s, r in sc[:8]:
        print(f"{r['id']}\t{r['kind']}\t{r['title']}\tp.{r['pages']}\t{r.get('oneliner', '')[:70]}")


# ---------- ask : 질문 1개 → 특약 사실 + 근거 항
SUFFIX = ['이라면', '라면', '인가요', '되나요', '하나요', '나요', '할까요', '을까요', '까요', '으로', '에서', '까지', '부터', '에게',
          '에도', '에는', '이나', '이며', '하고', '와', '과', '은', '는', '이', '가', '을', '를', '에', '의', '도', '로', '만']
STOP = set('보장 보험금 담보 특약 경우 확인 궁금 궁금합니다 가능 있을까요 부탁 부탁드립니다 정확한 구체적인 관련 해당 어떻게 무엇 '
           '건 수 있나요 대한 그리고 또는 혹은 현재 고민 중 조언 함께 가입 가입할지 할지 동일 같은 다른 지급 지급되나요'.split())

SYN = [('해지환급금', '해약환급금'), ('해지', '해약'), ('실비', '실손'), ('입원비', '입원일당'), ('수술비', '수술'),
       ('깁스', '깁스'), ('태아보험', '태아'), ('어린이보험', '어린이')]
JONG = re.compile(r'미지급형|해약환급금|해지환급금|표준형|보험기간\s*연장형|순수보장형|보험종목')

def load_syn():
    p = os.path.join(BASE, 'synonyms.tsv')
    if os.path.exists(p):
        rows = [l.rstrip('\n').split('\t') for l in open(p, encoding='utf-8')][1:]
        return sorted([(a, b) for a, b in rows if a and b and a != b], key=lambda x: -len(x[0]))
    return SYN


def q_tokens(q):
    for a, b in load_syn():
        q = q.replace(a, b)
    q = q.replace('~', '-')
    out = []
    for t in re.findall(r'[가-힣A-Za-z0-9.\-]+', q):
        if t[:1].isdigit():
            t = re.match(r'\d[\d\-.]*(?:일|세|회|종|년|개월|주|%)?', t).group(0)
        for s in ([] if t[:1].isdigit() else SUFFIX):
            if t.endswith(s) and len(t) - len(s) >= 2:
                t = t[:-len(s)]
                break
        if len(t) >= 2 and t not in STOP:
            out.append(t)
    return list(dict.fromkeys(out))


def load_items():
    p = os.path.join(BASE, 'item_map.tsv')
    if not os.path.exists(p):
        return []
    return list(csv.DictReader(open(p, encoding='utf-8'), delimiter='\t'))


def match_items(q):
    """질문 속 설계 화면 항목명(가장 긴 것부터) → [(항목, 특약id, 하위구분, 비고)]"""
    qn = norm(q)
    hits, used = [], ''
    for it in sorted(load_items(), key=lambda x: -len(norm(x['설계항목명']))):
        n = norm(it['설계항목명'])
        if len(n) >= 3 and n in qn and n not in used:
            hits.append(it)
            used += '|' + n
    return hits


def cmd_ask(q, ids=None, n=10):
    facts = load_facts()
    rows, by = load_index()
    items = match_items(q)
    for it in items:
        if it['특약id'] == '약관밖':
            print(f"■ 설계 항목 '{it['설계항목명']}' → 이 약관에 없음: {it['비고']} (이 스킬로 답할 수 없다고 안내)")
        else:
            print(f"■ 설계 항목 '{it['설계항목명']}' → {it['특약id']}" + (f" (하위 보험금 구분: {it['하위구분']})" if it['하위구분'] else '') + (f" · {it['비고']}" if it['비고'] and it['비고'] != '하위 보험금 구분' else ''))
    if items and not ids and all(it['특약id'] == '약관밖' for it in items):
        print('■ 이 질문의 항목은 이 약관(굿앤굿어린이종합보험Q) 범위 밖 → 근거 원문 없음. 실손의료비보장보험 약관·상품설명서 확인 안내')
        return
    subs = [x.strip() for it in items for x in it['하위구분'].split('/') if x.strip()]
    if not ids:
        mapped = [it['특약id'] for it in items if it['특약id'] not in ('약관밖', '미확인')]
        if mapped:
            ids = ','.join(dict.fromkeys(mapped))
    jong_q = bool(JONG.search(q))
    if ids:
        docs = [i.strip() for i in ids.split(',') if i.strip()]
    elif jong_q:
        docs = []
        print('■ 1·2·3종(해약환급금 미지급형 등) 질문 → 보통약관·종비교 문서 우선. 특정 특약의 가입종은 facts <id>, 종별 차이 요약은 show 개요-종비교 60')
    else:
        sc = [x for x in score_docs(q) if x[1]['kind'] in ('특약', '하위보장')]
        top = sc[0][0] if sc else 0
        qt = [norm(t) for t in q_tokens(q) if len(re.sub(r'[^가-힣]', '', t)) >= 2]
        docs, bodies = [], set()
        for s_, r in sc:
            if s_ < max(10, top * 0.75) or not any(t and t in norm(r['title']) for t in qt):
                continue
            f = facts.get(r['id'], {})
            key = tuple(sorted(f.get('동일본문') or [r['id']]))
            if key in bodies:
                continue
            bodies.add(key)
            docs.append(r['id'])
            if len(docs) == 3:
                break
    toks = q_tokens(q)
    print(f'■ 질문 키워드: {", ".join(toks) or "(없음)"}')
    fq = [f for f in load_faq() if any(t in q for t in f['triggers'])]
    if fq:
        pmap = {p['pid']: p for p in load_paras()}
        for f in fq[:2]:
            print(f"■ FAQ 근거 묶음 [{f['id']}] {f['title']}\n   요령: {f['note']}")
            for pid in dict.fromkeys(f['pids']):
                p = pmap.get(pid)
                if p:
                    tx = p['text'].replace(' ⏎ ', '\n    ')
                    print(f"  [{pid}] 〔{p['cite']}〕\n    {tx[:500]}{' …(para ' + pid + ')' if len(tx) > 500 else ''}")
    print('■ 매칭 특약(facts)')
    if not docs:
        print('  (특약 매칭 없음 — 전체 원문에서 근거 항만 제시. 필요시 find 로 특약 지정 후 ask "<질문>" <id>)')
    for d in docs:
        f = facts.get(d)
        if not f:
            print(f'  {d}: (facts 없음 — show {d})')
            continue
        print(f"  [{f['id']}] {f['title']} p.{f['pages']} | {f['oneliner']}")
        print(f"     한도:{f['limit'] or '-'} | 갱신형:{'예' if f['갱신형'] else '아니오'} | 가입종:{f['가입종']} | "
              f"자체 보장개시조항:{'있음' if f['자체_보장개시조항'] else '없음→보통약관 제33조'} | "
              f"자체 청구조항:{'있음' if f['자체_청구조항'] else '없음→보통약관 제10조'} | 관련별표:{', '.join(f['관련별표']) or '-'}")
        if f['같은계열']:
            print(f"     같은 계열: {', '.join(f['같은계열'][:10])}")
    paras = load_paras()
    N = len(paras)
    df = {t: sum(1 for p in paras if t in p['text']) for t in toks}
    avg = sum(len(p['text']) for p in paras) / N
    body_ids = set()
    for d in docs:
        f = facts.get(d)
        body_ids.add(d)
        if f:
            body_ids.update(f['동일본문'])
    def sc(p):
        tx = p['text']
        s = sum(math.log(N / (1 + df[t])) for t in toks if t in tx)
        s /= (0.5 + 0.5 * len(tx) / avg)                      # 긴 문단 감점
        if re.search(r'(이라 함은|라 함은|말합니다|한도로 합니다|한하여)', tx):
            s *= 1.3
        return s
    tgt, glob_ = {}, []
    # 대상 특약이 참조하는 별표·보통약관 조 → 특약 밖 근거는 여기서만
    allowed = set()
    for d in docs:
        allowed.update((facts.get(d) or {}).get('관련별표', []))
    for p in paras:
        if p['doc'] in body_ids:
            for m in re.finditer(r'보통약관\s*제(\d+)조', p['text']):
                allowed.add(f'보통-{int(m.group(1)):02d}')
    ESS = r'지급사유|보상하는|보험기간|보장개시|정의|지급하지 않는|보상하지 않는|세부규정'
    for p in paras:
        if p['doc'] in body_ids:
            base = 3.0 if re.search(r'지급사유|보상하는', p['art']) else (1.2 if re.search(ESS, p['art']) else 0)
            v = sc(p) + base
            if subs and any(x in p['text'] for x in subs):
                v *= 3
            tgt.setdefault(p['doc'], []).append((v, p))
        elif not docs or p['doc'] in allowed:
            v = sc(p)
            if jong_q:
                v *= 2.5 if (p['doc'] == '개요-종비교' or re.search(r'[123]종', p['text'])) else 0.6
            if subs and any(x in p['text'] for x in subs):
                v = v * 3 + 2
            if v > 1.5:
                glob_.append((v, p))
    picked = []
    order = []
    for d in docs:
        f = facts.get(d, {})
        for bdy in [d] + list(f.get('동일본문', [])):
            if bdy in tgt and bdy not in order:
                order.append(bdy)
    per = 10 if len(order) <= 1 else 6
    for d in order + [k for k in tgt if k not in order]:
        lst = tgt[d]
        lst.sort(key=lambda x: -x[0])
        # 조별로 최소 1개(핵심 조) 보장 후 점수순
        seen_art, sel = set(), []
        for v, p in lst:
            if re.search(ESS, p['art']) and p['art'] not in seen_art:
                sel.append(p); seen_art.add(p['art'])
        for v, p in lst:
            if p not in sel and v > 0:
                sel.append(p)
        picked += sel[:per]
    glob_.sort(key=lambda x: -x[0])
    picked += [p for v, p in glob_[:(4 if docs else max(3, int(n) - len(picked)))]]
    if docs and allowed:
        print('■ 이 특약이 참조하는 문서: ' + ', '.join(sorted(allowed)) + '  (별표 행 필터: rows 별표-N <단어>)')
    print(f'■ 근거 원문 {len(picked)}개 — 대상 특약 항 먼저, 이어서 보통약관·별표·개요 (인용은 텍스트 그대로, 출처는 〔…〕 그대로)')
    for p in picked:
        tx = p['text'].replace(' ⏎ ', '\n    ')
        print(f"\n[{p['pid']}] 〔{p['cite']}〕\n    {tx[:700]}{' …(para ' + p['pid'] + ' 로 전문)' if len(tx) > 700 else ''}")
    if not picked:
        print('  (일치하는 항 없음 — grep 으로 다른 표현 검색)')


def load_faq():
    p = os.path.join(BASE, 'faq.json')
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else []


def cmd_faq(i=None):
    for f in load_faq():
        if i and f['id'] != i:
            continue
        print(f"{f['id']}\t{f['title']}\t트리거: {', '.join(f['triggers'])}")
        if i:
            print('요령:', f['note'])
            cmd_para(*f['pids'])


def cmd_rows(i, *flt):
    r = resolve(i)
    rows_ = [p for p in load_paras() if p['doc'] == r['id'] and p['lab'] == '표']
    if not rows_:
        sys.exit(f'{i}: 표 행 없음 → show {i}')
    print(f"[{r['id']} {r['title']} | p.{r['pages']} · {r['file']}]  필터: {' '.join(flt) or '(없음)'}")
    k = 0
    for p in rows_:
        tx = p['text']
        if flt and not all(f in tx for f in flt):
            continue
        print(f"[{p['pid']}] {tx.replace(' ⏎ ', chr(10) + '   ')}")
        k += 1
        if k >= 60:
            print('… (60행 초과 — 필터를 더 좁히세요)'); break
    if not k:
        print('일치 행 없음')


def cmd_facts(i):
    f = load_facts().get(i)
    if not f:
        sys.exit(f'facts 없음: {i}')
    print(json.dumps(f, ensure_ascii=False, indent=1))


def cmd_para(*pids):
    want = set(pids)
    for p in load_paras():
        if p['pid'] in want:
            print(f"[{p['pid']}] 〔{p['cite']}〕\n{p['text'].replace(' ⏎ ', chr(10))}\n")


# ---------- 기존 명령
def cmd_card(i):
    r = resolve(i)
    t = body(r['file'])
    print(t.split('\n## 원문', 1)[0].strip())
    print(f"\n[파일: {r['file']} | 원문 p.{r['pages']}]  ※ 카드는 인용 금지(잘림). 인용은 ask/para/article")


def article_text(r, no):
    t = body(r['file']).split('\n## 원문', 1)[-1]
    m = re.search(rf'### 제{no}조 \(.*?\)\n.*?(?=\n### 제\d+조 \(|\Z)', t, re.S)
    if not m:
        return None
    s = m.group(0).strip()
    c = re.search(r'→ 공통조항 (C-\d+)', s)
    if c:
        _, by = load_index()
        ct = body(by[c.group(1)]['file']).split('## 사용 특약')[0]
        ct = re.sub(r'^# .*\n', '', ct).strip()
        s += f'\n\n[공통조항 {c.group(1)} 원문 — 문구 속 특약/보장 표기만 다를 수 있음]\n' + ct
    return s


def cmd_article(i, no):
    r = resolve(i)
    s = article_text(r, int(no))
    if not s:
        sys.exit(f'{i} 에 제{no}조 없음 → arts {i} 로 조 목록 확인')
    f = load_facts().get(r['id'], {})
    pg = next((x.rsplit(' p.', 1)[1] for x in f.get('조목록', []) if x.startswith(f'제{no}조(')), r['pages'])
    print(f"[{r['id']} {r['title']} | 제{no}조 p.{pg} · {r['file']} §제{no}조]\n")
    print(s)


def cmd_arts(i):
    f = load_facts().get(i)
    if f:
        print(f"[{f['id']} {f['title']} | p.{f['pages']}]")
        for a in f['조목록']:
            print(' ', a)
        return
    r = resolve(i)
    t = body(r['file']).split('\n## 원문', 1)[-1]
    print(f"[{r['id']} {r['title']} | p.{r['pages']}]")
    for m in re.finditer(r'^### (제\d+조 \(.*?\))', t, re.M):
        print(' ', m.group(1))


def cmd_show(i, n=None):
    r = resolve(i)
    t = body(r['file'])
    refs = n == 'refs'
    if refs:
        n = None
    if not refs and '\n## 이 문서를 참조하는 특약' in t:
        t, tail = t.split('\n## 이 문서를 참조하는 특약', 1)
        k = len([x for x in tail.split('\n') if x.startswith('- ')])
        t += f'\n\n(이 문서를 참조하는 특약 {k}개 — 목록은 show {i} refs)'
    lines = t.split('\n')
    print(f"[{r['id']} {r['title']} | p.{r['pages']} · {r['file']}]\n")
    print('\n'.join(lines[:int(n)] if n else lines))


def code_hit(q, codes):
    q = q.upper().replace(' ', '')
    qm = re.fullmatch(r'([A-Z])(\d{2})(?:\.(\d+))?', q)
    if not qm:
        return False
    for part in codes.upper().replace(' ', '').split(','):
        m = re.fullmatch(r'([A-Z])(\d{2})(?:\.(\d+))?(?:[~∼\-]([A-Z])?(\d{2})(?:\.(\d+))?)?', part)
        if not m:
            continue
        L, a, _, L2, b, _ = m.groups()
        if b is None:
            if part.startswith(q) or q.startswith(part):
                return True
        elif (L, int(a)) <= (qm.group(1), int(qm.group(2))) <= ((L2 or L), int(b)):
            return True
    return False


def cmd_code(q):
    rows = list(csv.reader(open(os.path.join(BASE, 'diseases.tsv'), encoding='utf-8'), delimiter='\t'))[1:]
    is_code = re.fullmatch(r'[A-Za-z]\d{2}(\.\d+)?', q.strip())
    out = [r for r in rows if (code_hit(q, r[1]) if is_code else norm(q) in norm(r[0]))]
    print('질병명\t코드\t별표(쪽)\t보장특약')
    for r in out[:40]:
        print(f'{r[0]}\t{r[1]}\t{r[2]} p.{r[3]}\t{r[4]}')
    if len(out) > 40:
        print(f'… 외 {len(out) - 40}건')
    if not out:
        print('결과 없음')


def cmd_grep(q, n=15):
    rows, _ = load_index()
    only = None
    if isinstance(n, str) and not n.isdigit():
        only, n = resolve(n)['file'], 50
    hits = 0
    pat = re.compile(re.escape(q).replace(r'\ ', r'\s*'))
    seen = set()
    for r in rows:
        if r['kind'] in ('계열', '주제') or r['file'] in seen or (only and r['file'] != only):
            continue
        seen.add(r['file'])
        t = body(r['file'])
        if r['kind'] in ('특약', '하위보장'):
            t = t.split('\n## 원문', 1)[-1]
        art = ''
        for line in t.split('\n'):
            m = re.match(r'### (제\d+조 \(.*?\))', line)
            if m:
                art = m.group(1)
            if pat.search(line):
                print(f"{r['id']}\t{art}\tp.{r['pages']}\t{line.strip()[:160]}")
                hits += 1
                if hits >= int(n):
                    print('… (최대건수 도달 — 더 구체적인 문구나 id 범위 지정)')
                    return
    if not hits:
        print('결과 없음')


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        sys.exit()
    c, args = a[0], a[1:]
    {'ask': lambda: [cmd_ask(q.strip(), *(args[1:2])) or print('\n' + '=' * 60) for q in args[0].split('||')],
     'item': lambda: [print(f"{it['설계항목명']}\t{it['섹션']}\t{it['특약id']}\t{it['하위구분']}\t{it['비고']}") for it in (match_items(' '.join(args)) or [])] or None,
     'rows': lambda: cmd_rows(*args), 'facts': lambda: cmd_facts(args[0]), 'faq': lambda: cmd_faq(*args[:1]), 'para': lambda: cmd_para(*args),
     'find': lambda: cmd_find(' '.join(args)), 'card': lambda: cmd_card(args[0]),
     'article': lambda: [cmd_article(args[0], x) for x in args[1:]], 'arts': lambda: cmd_arts(args[0]),
     'show': lambda: cmd_show(*args[:2]), 'code': lambda: cmd_code(' '.join(args)),
     'grep': lambda: cmd_grep(args[0], *(args[1:2]))}.get(c, lambda: print(__doc__))()
