"""Customer-only mobile presentation for the existing comparison calculator.

All monetary inputs and underlying formulas are supplied by app.py. No quote is
stored here and the salesperson's editing/share workflow is left in app.py.
"""

import html
import streamlit as st


def _safe(value):
    return html.escape(str(value or ""))


def _won(value):
    return f"{int(value):,}원"


def _row(name, installment, finance, emphasis=False):
    cls = " cv2-row cv2-emphasis" if emphasis else " cv2-row"
    return (f'<div class="{cls}"><span>{_safe(name)}</span>'
            f'<b>{_safe(installment)}</b><b>{_safe(finance)}</b></div>')


def _result(title, installment, finance, detail, finance_name, rows):
    diff = abs(installment - finance)
    winner = "할부" if installment < finance else finance_name
    verdict = "두 방식의 총비용이 같아요." if not diff else f"{winner}가 {_won(diff)} 적게 들어요."
    return f'''<section class="cv2-card cv2-cost">
      <h2>{title}</h2><p class="cv2-sub">{detail}</p>
      <div class="cv2-grid"><div class="cv2-row cv2-head"><span>항목</span><b>할부</b><b>{finance_name}</b></div>
      {''.join(rows)}{_row('총 투입 비용', _won(installment), _won(finance), True)}</div>
      <div class="cv2-verdict"><small>이 조건의 총 투입 비용</small>
        <div><span>일반 할부</span><strong>{_won(installment)}</strong></div>
        <div><span>{finance_name}</span><strong>{_won(finance)}</strong></div>
        <p>{verdict}</p></div></section>'''


def render_customer_v2(*, logo_data_uri, customer_name, car_name, car_option, car_price,
                       installment_car_price, finance_car_price, months,
                       mileage, rent_monthly_pay, rent_deposit, finance_mode,
                       lease_tax_included, installment_prepaid, inst_monthly_pay,
                       installment_interest, reg_tax, total_tax, total_ins,
                       car_sell_value, rent_takeover_price, rent_takeover_tax,
                       installment_rate, installment_resale_pct, rent_resale_pct,
                       visible_sections):
    """Render the customer share using the same quote and calculations as app.py."""
    lease = finance_mode == "lease"
    finance_name = "리스" if lease else "장기렌트"
    finance_tax = 0 if lease_tax_included else total_tax
    inst_return = installment_prepaid + inst_monthly_pay * months + installment_interest + reg_tax + total_tax + total_ins - car_sell_value
    fin_return = rent_monthly_pay * months + rent_deposit + (total_ins + finance_tax if lease else 0)
    inst_takeover = installment_prepaid + inst_monthly_pay * months + installment_interest + reg_tax + total_tax + total_ins
    fin_takeover = rent_monthly_pay * months + rent_deposit + rent_takeover_price + rent_takeover_tax + (total_ins + finance_tax if lease else 0)
    tax_value = (_won(finance_tax) if lease and not lease_tax_included else "월 이용료 포함")
    insurance_value = _won(total_ins) if lease else "월 이용료 포함"
    base_rows = [
        _row("선납금", _won(installment_prepaid), _won(rent_deposit)),
        _row("월 납입금", _won(inst_monthly_pay), _won(rent_monthly_pay)),
        _row("할부이자", _won(installment_interest), "—"),
        _row("취등록세", _won(reg_tax), "월 이용료 포함"),
        _row("자동차세", _won(total_tax), tax_value),
        _row("보험료", _won(total_ins), insurance_value),
    ]
    options = _safe(car_option).replace("\n", "<br>")
    customer = _safe(customer_name).rstrip("님") + "님" if customer_name else "고객님"
    sections = []
    if visible_sections.get("intro", True):
        sections.append(f'<div class="cv2-brand"><img src="{_safe(logo_data_uri)}" alt="카프리오"></div>'
                        f'<header class="cv2-hero"><span>CARFREEOH COMPARISON</span><h1>{customer},<br>어떤 방식이 더 잘 맞을까요?</h1></header>')
    if visible_sections.get("common", True):
        price = _won(finance_car_price)
        if installment_car_price != finance_car_price:
            price = f'할부 {_won(installment_car_price)} · {finance_name} {price}'
        sections.append(f'''<section class="cv2-card"><h2>비교하는 차량</h2>
          <div class="cv2-car"><strong>{_safe(car_name)}</strong><span>{options}</span><b>{price}</b></div>
          <div class="cv2-facts"><div><small>이용 기간</small><b>{months}개월</b></div>
          <div><small>약정 거리</small><b>{_safe(mileage)}</b></div></div></section>''')
    if visible_sections.get("installment_condition", True):
        sections.append(f'''<section class="cv2-card"><h2>계산에 사용한 조건</h2>
          <div class="cv2-facts"><div><small>할부 금리</small><b>{installment_rate:g}%</b></div>
          <div><small>보험료</small><b>연 {_won(total_ins * 12 / months)}</b></div>
          <div><small>차량 매각 예상</small><b>{installment_resale_pct}%</b></div>
          <div><small>만기 인수 가격</small><b>{_won(rent_takeover_price)}</b></div></div></section>''')
    if visible_sections.get("summary", True) and visible_sections.get("summary_return", True):
        rows = base_rows + [_row("만기 차량 매각", f"−{_won(car_sell_value)}", "—"),
                            _row("월 평균 환산", _won(inst_return / months), _won(fin_return / months))]
        sections.append(_result("만기 때 반납한다면", inst_return, fin_return,
                                "차량을 반납하거나 할부 차량을 매각했을 때예요.", finance_name, rows))
    if visible_sections.get("summary", True) and visible_sections.get("summary_takeover", True):
        rows = base_rows + [_row("만기 인수금", "—", _won(rent_takeover_price)),
                            _row("인수 시 취등록세", "—", _won(rent_takeover_tax)),
                            _row("월 평균 환산", _won(inst_takeover / months), _won(fin_takeover / months))]
        sections.append(_result("만기 때 인수한다면", inst_takeover, fin_takeover,
                                "차량을 계속 소유할 때 드는 비용이에요.", finance_name, rows))
    if visible_sections.get("rate_table", True):
        sections.append(f'''<section class="cv2-card"><h2>계산에 사용한 기준</h2>
          <details><summary>잔존가치 예상</summary><p>할부 차량 매각 예상 {installment_resale_pct}% · {finance_name} 만기 인수 가격 {rent_resale_pct:g}%</p></details>
          <details><summary>할부이자</summary><p>적용 금리 {installment_rate:g}% · 총 할부이자 {_won(installment_interest)}</p></details>
          <details><summary>세금·보험료</summary><p>취등록세 {_won(reg_tax)} · 자동차세 {_won(total_tax)} · 보험료 {_won(total_ins)}</p></details></section>''')
    if visible_sections.get("compare", True):
        methods = [m for m in ("installment", "rent", "lease") if visible_sections.get("compare_" + m, False)]
        if len(methods) >= 2:
            headings = {"installment": "할부", "rent": "장기렌트", "lease": "리스"}
            facts = {
                "번호판": {"installment": "일반", "rent": "하·허·호", "lease": "일반"},
                "차량 명의": {"installment": "내 명의", "rent": "렌트사 명의", "lease": "리스사 명의"},
                "자동차세·보험": {"installment": "별도 납부", "rent": "월 이용료 포함", "lease": "조건에 따라 별도"},
                "만기 선택": {"installment": "차량 매각 가능", "rent": "반납·인수 선택", "lease": "반납·인수 선택"},
            }
            columns = f'34% repeat({len(methods)}, minmax(0, 1fr))'
            cells = [f'<div class="cv2-method-row" style="grid-template-columns:{columns}"><strong>항목</strong>{"".join(f"<b>{headings[m]}</b>" for m in methods)}</div>']
            for title, values in facts.items():
                cells.append(f'<div class="cv2-method-row" style="grid-template-columns:{columns}"><strong>{title}</strong>{"".join(f"<span>{values[m]}</span>" for m in methods)}</div>')
            sections.append(f'<section class="cv2-card"><h2>이용 방식은 무엇이 달라요?</h2><div class="cv2-methods">{"".join(cells)}</div></section>')
    if visible_sections.get("guide", True):
        guides = {
            "installment": ("할부가 잘 맞아요", "내 명의로 오래 타고 싶을 때", "초기비용과 보험·세금을 직접 관리할 수 있다면 살펴보세요."),
            "rent": ("장기렌트가 잘 맞아요", "차를 편하게 이용하고 싶을 때", "보험·세금·사고 처리 부담을 줄이고, 만기에 반납 또는 인수하고 싶다면 살펴보세요."),
            "lease": ("리스가 잘 맞아요", "일반 번호판으로 이용하고 싶을 때", "보험 경력을 유지하고, 초기 부담과 만기 선택을 함께 고려한다면 살펴보세요."),
        }
        cards = []
        for method, (title, lead, detail) in guides.items():
            if visible_sections.get("guide_" + method, False):
                cards.append(f'<article class="cv2-guide"><h3>{title}</h3><b>{lead}</b><p>{detail}</p></article>')
        if cards:
            sections.append('<section class="cv2-card"><h2>어떤 방식이 어울릴까요?</h2>' + ''.join(cards) + '</section>')
    if visible_sections.get("outro", True):
        sections.append('<section class="cv2-card cv2-outro"><h2>궁금한 점이 있어?</h2><p>견적 조건과 진행 순서를 담당자에게 물어보세요.</p></section>')

    st.markdown('''<style>
    .block-container{max-width:650px!important;padding:0 14px 55px!important}
    .cv2-brand{margin:0 -14px;background:white;padding:13px 21px;border-bottom:1px solid #dce7ed}.cv2-brand img{display:block;width:160px;max-width:55%;height:auto}
    .cv2-hero{margin:0 -14px 18px;padding:28px 25px 34px;background:linear-gradient(130deg,#143b58,#216d92);color:white;border-radius:0 0 25px 25px}
    .cv2-hero span{font-size:12px;letter-spacing:.16em;color:#a6d8ed;font-weight:800}.cv2-hero h1{font-size:27px;line-height:1.36;margin:15px 0 0;color:white}
    .cv2-card{margin:16px 0;padding:21px 17px;background:#fff;border:1px solid #dbe7ed;border-radius:19px;color:#17384e}
    .cv2-card h2{font-size:20px;font-weight:800;letter-spacing:-.04em;margin:0 0 17px}.cv2-sub{color:#5c7686;font-size:14px;line-height:1.6;margin:-8px 0 16px}
    .cv2-car{display:grid;gap:8px;background:#f0f7fa;padding:16px;border-radius:13px}.cv2-car strong{font-size:19px}.cv2-car span{font-size:14px;line-height:1.6;color:#58778b}.cv2-car b{font-size:18px;color:#14597e}
    .cv2-facts{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-top:13px}.cv2-facts>div{display:grid;gap:5px;background:#f4f8fa;padding:13px;border-radius:10px;min-width:0}.cv2-facts small{color:#6c8492;font-size:12px}.cv2-facts b{font-size:15px;overflow-wrap:anywhere}
    .cv2-grid{border:1px solid #dce8ee;border-radius:12px;overflow:hidden}.cv2-row{display:grid;grid-template-columns:34% 33% 33%;border-bottom:1px solid #e8eef1;align-items:stretch;min-height:46px}.cv2-row:last-child{border:0}.cv2-row>*{display:grid;place-items:center;text-align:center;padding:9px 3px;font-size:13px;overflow-wrap:anywhere}.cv2-row>*+*{border-left:1px solid #e5edf1}.cv2-row span{background:#f1f7fa;color:#315a71;font-weight:750}.cv2-row b{font-weight:650}.cv2-head span,.cv2-head b{background:#dcebf3;font-weight:850}.cv2-emphasis span,.cv2-emphasis b{background:#143b58;color:white;font-size:14px;font-weight:850}
    .cv2-verdict{background:#143b58;color:white;border-radius:14px;padding:20px 17px;margin-top:18px}.cv2-verdict small{color:#b8d8e6;font-size:12px}.cv2-verdict div{display:flex;justify-content:space-between;gap:9px;margin-top:12px;align-items:baseline}.cv2-verdict div span{font-size:13px;color:#d3e6ed}.cv2-verdict strong{font-size:20px;white-space:nowrap}.cv2-verdict p{font-weight:750;color:#aee1fa;background:#ffffff17;border-radius:8px;padding:10px;margin:17px 0 0;font-size:15px}
    .cv2-card details{border-top:1px solid #e5edf1;padding:13px 0;font-size:14px}.cv2-card details summary{cursor:pointer;font-weight:650}.cv2-card details p{line-height:1.6;color:#597487;margin:10px 0 0}
    .cv2-method-row{display:grid;grid-template-columns:34% repeat(2,33%);border-bottom:1px solid #e1ebef;min-height:48px}.cv2-method-row>*{font-size:12px;padding:11px 4px;display:grid;place-items:center;text-align:center}.cv2-method-row strong{background:#eaf3f8}.cv2-method-row>*+*{border-left:1px solid #e2ebef}.cv2-guide{border:1px solid #dce8ee;border-radius:12px;padding:17px;margin:12px 0}.cv2-guide h3{font-size:18px;margin:0 0 8px}.cv2-guide b{font-size:14px}.cv2-guide p,.cv2-outro p{font-size:14px;color:#5c7686;line-height:1.65;margin:7px 0 0}
    @supports(animation-timeline:view()){.cv2-cost,.cv2-guide{animation:cv2-reveal both;animation-timeline:view();animation-range:entry 0% entry 28%}@keyframes cv2-reveal{from{opacity:.35;transform:translateY(18px)}to{opacity:1;transform:translateY(0)}}}
    @media(prefers-reduced-motion:reduce){.cv2-cost,.cv2-guide{animation:none!important}}
    </style>''', unsafe_allow_html=True)
    for section in sections:
        st.markdown(section, unsafe_allow_html=True)
