"""Bind the original comparison workbench UI to the existing calculator outputs.

customer_ui contains the unchanged reference HTML, CSS, JS and logo. All numeric
values are supplied by app.py; this adapter never saves quotes or sends messages.
"""
from pathlib import Path
import base64
from copy import deepcopy
from bs4 import BeautifulSoup
import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).parent / 'customer_ui'

def _won(value):
    return f'{int(value):,}원'

def build_customer_html(*, preview=False, **v):
    soup = BeautifulSoup((ROOT / 'compare-v2.html').read_text(), 'html.parser')
    def put(selector, value, scope=None):
        node = (scope or soup).select_one(selector)
        if node is not None:
            node.string = str(value)
    def fragment(node, markup):
        node.clear()
        node.append(BeautifulSoup(markup, 'html.parser'))
    logo = 'data:image/png;base64,' + base64.b64encode((ROOT / 'carfreeoh-logo-transparent.png').read_bytes()).decode()
    for img in soup.select('img'):
        img['src'] = logo
    soup.select_one('link[rel="stylesheet"]').decompose()
    style = soup.new_tag('style')
    style.string = (ROOT / 'compare-v2.css').read_text()
    soup.head.append(style)
    soup.select_one('script[src]').decompose()
    script = soup.new_tag('script')
    script.string = (ROOT / 'compare-v2.js').read_text()
    soup.body.append(script)
    name = str(v['customer_name'] or '고객')
    if not name.endswith('님'):
        name += '님'
    put('.eyebrow', f'FOR {name}')
    title = soup.select_one('.intro h1')
    title.contents[0].replace_with(f'{name}, 차를 고르는 데')
    put('.car-summary b', v['car_name'])
    put('.car-summary span', v['car_option'] or '옵션 없음')
    price = _won(v['finance_car_price'])
    if v['installment_car_price'] != v['finance_car_price']:
        price = f"할부 {_won(v['installment_car_price'])} · {'리스' if v['finance_mode']=='lease' else '렌트'} {price}"
    put('.car-summary strong', price)
    for node, value in zip(soup.select('#common .facts b'), [v['car_option'] or '없음', f"{v['months']}개월", v['mileage'], f"{v.get('fuel_text','')} · {v.get('cc_raw_text','')}"]):
        node.string = str(value)
    for node, value in zip(soup.select('#installment .facts b'), ['예' if v.get('is_corporate') else '아니요', _won(v['installment_prepaid']), f"{v['installment_rate']:g}%", _won(v.get('insurance_annual', v['total_ins']*12/v['months'])), f"{v['installment_resale_pct']:g}%", f"{v['rent_resale_pct']:g}%"]):
        node.string = str(value)
    lease = v['finance_mode'] == 'lease'
    finance_name = '리스' if lease else '장기렌트'
    months = v['months']
    # These totals match the original calculator, including its integer rounding.
    inst_take = v['installment_prepaid'] + v['inst_monthly_pay']*months + v['installment_interest'] + v['reg_tax'] + v['total_tax'] + v['total_ins']
    fin_ret = v['rent_monthly_pay']*months + v['rent_deposit'] + (v['total_ins'] + (0 if v['lease_tax_included'] else v['total_tax']) if lease else 0)
    inst_ret = inst_take - v['car_sell_value']
    fin_take = fin_ret + v['rent_takeover_price'] + v['rent_takeover_tax']
    for section_id, inst, fin in [('return',inst_ret,fin_ret),('takeover',inst_take,fin_take)]:
        section = soup.select_one('#'+section_id)
        values = {
            '선납금': (_won(v['installment_prepaid']),_won(v['rent_deposit'])),
            '월 납입금선납금 제외': (_won(v['inst_monthly_pay']),_won(v['rent_monthly_pay'])),
            '할부이자': (_won(v['installment_interest']),'—'),
            '만기 차량 매각': ('−'+_won(v['car_sell_value']),'—'),
            '만기 인수금': ('—',_won(v['rent_takeover_price'])),
            '인수 시 취등록세': ('—',_won(v['rent_takeover_tax'])),
            '월 평균 환산': (_won(inst/months),_won(fin/months)),
            '총 투입 비용': (_won(inst),_won(fin)),
        }
        for row in section.select('.compare-rows > .row:not(.headings)'):
            key = row.select_one('span').get_text()
            for node, value in zip(row.select('b'), values[key]):
                node.string = value
        for node, value in zip(section.select('.bundle-values b'), [v['reg_tax'],v['total_tax'],v['total_ins']]):
            node.string = _won(value)
        if lease:
            put('.headings span:last-child','리스',section)
            bundle = section.select_one('.bundle-included')
            bundle['class'] = ['bundle-values']
            bundle.clear()
            for value in ['월 리스료 포함','월 리스료 포함' if v['lease_tax_included'] else _won(v['total_tax']),_won(v['total_ins'])]:
                b = soup.new_tag('b'); b.string = value; bundle.append(b)
            put('.calc-explain', '할부는 월 납입금에 이자·세금·보험료를 더했어요.' + (' 만기 차량 매각 예상액을 뺐어요.' if section_id=='return' else '') + ' 리스는 월 납입금과 별도 보험료·자동차세를 반영했어요.' + (' 만기 인수금과 인수 시 취등록세를 합쳤어요.' if section_id=='takeover' else ''),section)
            if section_id=='takeover':
                put('.head p','리스 인수금과 인수 시 세금까지 반영했어요.',section)
        for node,value in zip(section.select('.amounts b'),[inst,fin]):
            node.string = _won(value)
        put('.amounts div:last-child span',finance_name,section)
        diff = section.select_one('.difference'); diff.clear()
        if inst == fin:
            diff.string = '두 방식의 총 투입 비용이 같아요.'
        else:
            diff.append(('할부' if inst<fin else finance_name)+'가 ')
            strong=soup.new_tag('strong'); strong.string=_won(abs(inst-fin)); diff.append(strong); diff.append(' 적게 들어요.')
    if lease:
        put('#installment .facts div:last-child small','리스 잔존가치')
    # Keep the reference cards verbatim; the existing lease option uses its own
    # checklist in the same reference card markup, never the rent checklist.
    guide=soup.select_one('#guide')
    cards=guide.select('article')
    lease_card=deepcopy(cards[1])
    put('.tag','일반 번호판으로 이용하기',lease_card)
    put('h3','리스가 잘 맞는 경우',lease_card)
    put('p','일반 번호판과 개인 보험요율을 유지하고 싶을 때.',lease_card)
    for node,text in zip(lease_card.select('ul:not(.cautions) li'),['취등록세 초기 목돈 지출이 부담스러움','하·허·호 대신 일반 번호판을 원함','렌트보다 자차와 유사한 만족감을 원함']): node.string=text
    for node,text in zip(lease_card.select('.cautions li'),['개인 보험요율을 유지해요.','보험은 직접 가입하고 사고도 직접 처리해요.','자동차세 포함 여부는 견적 조건을 확인해요.','리스도 대출한도에 영향을 줄 수 있어요.']): node.string=text
    put('.match','일반 번호판을 원하고 개인 보험요율을 유지하고 싶다면 리스가 맞을 수 있어요.',lease_card)
    guide.append(lease_card)
    visible=v['visible_sections']
    for method,card in zip(['installment','rent','lease'],[cards[0],cards[1],lease_card]):
        if not visible.get('guide_'+method,True): card.decompose()
    methods=[m for m in ['installment','rent','lease'] if visible.get('compare_'+m,True)]
    table=soup.select_one('#methods .methods')
    lease_values=['일반','대출한도 영향','리스사 명의','보험 별도','조건 선택','직접 가입·처리','수리비·감가','O','O','O','납입기간 내','인수·반납 선택']
    for index,row in enumerate(table.select('.row')):
        cells=row.find_all(recursive=False)
        extra=soup.new_tag('span' if index==0 else 'b'); extra.string='리스' if index==0 else lease_values[index-1]
        all_cells={'installment':deepcopy(cells[1]),'rent':deepcopy(cells[2]),'lease':extra}
        cells[1].decompose();cells[2].decompose()
        for method in methods: row.append(all_cells[method])
        row['style']=f'grid-template-columns:34% repeat({max(1,len(methods))},minmax(0,1fr))'
    labels={'installment':'할부','rent':'렌트','lease':'리스'}
    put('#methods h2', '와 '.join(labels[m] for m in methods)+', 무엇이 달라요?')
    mapping={'intro':'intro','common':'common','installment':'installment_condition','rates':'rate_table','methods':'compare','guide':'guide'}
    for section_id,key in mapping.items():
        if not visible.get(key,True): soup.select_one('#'+section_id).decompose()
    for section_id in ['return','takeover']:
        if not visible.get('summary',True) or not visible.get('summary_'+section_id,True): soup.select_one('#'+section_id).decompose()
    if not visible.get('outro',True): soup.select_one('.outro').decompose()
    if preview:
        soup.select_one('#comparisonOpening').decompose()
    if not preview:
        resize = soup.new_tag('script')
        resize.string = '''(() => { const resize = () => { try {
          const frame = window.frameElement;
          const height = Math.ceil(document.querySelector('.app').getBoundingClientRect().height + 48);
          if (frame && frame.style.height !== height + 'px') frame.style.height = height + 'px';
        } catch (_) {} }; new ResizeObserver(resize).observe(document.querySelector('.app')); resize(); })();'''
        soup.body.append(resize)
    return str(soup)

def render_customer_v2(*, preview=False, **values):
    if not preview:
        st.markdown('<style>#caprio-brand-header{display:none!important}.block-container{max-width:470px!important;padding:0!important}iframe{border:0}</style>', unsafe_allow_html=True)
    components.html(build_customer_html(preview=preview, **values), height=850 if preview else 1100, scrolling=True)
