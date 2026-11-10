Y��x-���jם��i��+��j[h��ܢ���8�N��m�o+^����םimport streamlit as st
import streamlit.components.v1 as components
import re
import json
import base64
import secrets
import string
import urllib.request
import urllib.parse
import urllib.error
import html
import textwrap

st.set_page_config(page_title="카프리오 비교 계산기", layout="wide")

APP_PASSWORD = st.secrets.get("APP_PASSWORD", "")
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")
APP_BASE_URL = "https://test-carfreeoh.streamlit.app"

# ==========================================
# [고객 공유 항목 선택 기본값/유틸]
# ==========================================
DEFAULT_VISIBLE_SECTIONS = {
    "intro": True,
    "conditions": True,
    "common": True,
    "installment_condition": True,
    "summary": True,
    "summary_return": True,
    "summary_takeover": True,
    "rate_table": True,
    "compare": True,
    "compare_installment": True,
    "compare_rent": True,
    "compare_lease": False,
    "guide": True,
    "guide_installment": True,
    "guide_rent": True,
    "guide_lease": False,
    "outro": True,
}

SHARE_SECTION_GROUPS = {
    "conditions": ["common", "installment_condition"],
    "summary": ["summary_return", "summary_takeover"],
    "compare": ["compare_installment", "compare_rent", "compare_lease"],
    "guide": ["guide_installment", "guide_rent", "guide_lease"],
}


def normalize_visible_sections(data=None):
    sections = DEFAULT_VISIBLE_SECTIONS.copy()
    if isinstance(data, dict):
        for key in sections:
            if key in data:
                sections[key] = bool(data.get(key))

    if not sections.get("conditions", True):
        sections["common"] = False
        sections["installment_condition"] = False

    if not sections.get("summary", True):
        sections["summary_return"] = False
        sections["summary_takeover"] = False

    if not sections.get("compare", True):
        sections["compare_installment"] = False
        sections["compare_rent"] = False
        sections["compare_lease"] = False
    else:
        selected_compare = [
            key for key in ["compare_installment", "compare_rent", "compare_lease"]
            if sections.get(key, False)
        ]
        if len(selected_compare) < 2:
            sections["compare_installment"] = True
            sections["compare_rent"] = True
            sections["compare_lease"] = False

    if not sections.get("guide", True):
        sections["guide_installment"] = False
        sections["guide_rent"] = False
        sections["guide_lease"] = False

    # 인삿말/마무리말은 체크 UI에는 노출하지 않지만 내부 섹션값은 항상 노출(True)로 유지
    sections["intro"] = True
    sections["outro"] = True

    return sections


def apply_visible_sections_to_state(sections):
    sections = normalize_visible_sections(sections)
    for key, value in sections.items():
        st.session_state[f"share_{key}"] = value


def collect_visible_sections_from_state():
    sections = {}
    for key, default_value in DEFAULT_VISIBLE_SECTIONS.items():
        sections[key] = bool(st.session_state.get(f"share_{key}", default_value))

    for parent_key, child_keys in SHARE_SECTION_GROUPS.items():
        if not sections.get(parent_key, True):
            for child_key in child_keys:
                sections[child_key] = False
        else:
            if any(sections.get(child_key, False) for child_key in child_keys):
                sections[parent_key] = True

    return normalize_visible_sections(sections)


def format_option_html(option_text):
    option_text = str(option_text or "").strip()
    if not option_text or option_text == "-":
        return "-"

    parts = []
    current = []
    depth = 0
    for char in option_text:
        if char == "(":
            depth += 1
        elif char == ")" and depth > 0:
            depth -= 1

        if char == "," and depth == 0:
            item = "".join(current).strip()
            if item:
                parts.append(item)
            current = []
        else:
            current.append(char)

    item = "".join(current).strip()
    if item:
        parts.append(item)

    formatted_parts = []
    for item in parts:
        match = re.match(r"^(.*?)(\([^)]*\))$", item)
        if match:
            name = html.escape(match.group(1).strip())
            price = html.escape(match.group(2).strip())
            formatted_parts.append(f'<div class="option-line"><span class="option-name">{name}</span> <span class="option-price">{price}</span></div>')
        else:
            formatted_parts.append(f'<div class="option-line"><span class="option-name">{html.escape(item)}</span></div>')

    return '<div class="option-stack">' + ''.join(formatted_parts) + '</div>'


def render_output_section_gap():
    """모바일 출력 섹션 간격 통일용. PC에는 영향을 주지 않음."""
    st.markdown('<div class="output-section-gap"></div>', unsafe_allow_html=True)

def build_share_copy_message(share_url, finance_mode=None):
    """카톡/문자 붙여넣기용 공유 안내문. URL만 복사하지 않고 문구+링크를 함께 복사한다."""
    raw_customer_name = str(st.session_state.get("customer_name", "") or "").strip()
    if raw_customer_name:
        display_name = raw_customer_name if raw_customer_name.endswith("님") else f"{raw_customer_name}님"
    else:
        display_name = "고객님"

    mode = str(finance_mode or st.session_state.get("finance_mode", "rent") or "rent").strip().lower()
    compare_text = "할부·리스" if mode == "lease" else "할부·렌트"

    return f"""🚗{display_name},
요청하신 [{compare_text}] 비교 계산이 완료되었습니다. ✨

어떤 방식이 더 유리한지
지금 바로 확인해 보세요. 👇

국내최다 33개 금융사 비교!
카 라이프에 자유를 더하다, 카프리오!

{share_url}"""


def render_share_section_selector(current_sections):
    current_sections = normalize_visible_sections(current_sections)

    for key, value in current_sections.items():
        st.session_state.setdefault(f"share_{key}", value)

    def set_all_sections(value):
        for section_key in DEFAULT_VISIBLE_SECTIONS:
            st.session_state[f"share_{section_key}"] = value

    def sync_parent_to_children(parent_key):
        parent_value = bool(st.session_state.get(f"share_{parent_key}", True))
        for child_key in SHARE_SECTION_GROUPS.get(parent_key, []):
            st.session_state[f"share_{child_key}"] = parent_value

    def sync_children_to_parent(parent_key):
        child_keys = SHARE_SECTION_GROUPS.get(parent_key, [])
        if child_keys:
            st.session_state[f"share_{parent_key}"] = any(
                bool(st.session_state.get(f"share_{child_key}", False))
                for child_key in child_keys
            )

    st.markdown("""
    <style>
    /* ===== 고객 공유 항목 선택: PC/MO 분리형 최종 정리 ===== */
    .share-selector-anchor + div[data-testid="stHorizontalBlock"] {
        align-items: flex-start !important;
        gap: 0 !important;
        margin: 0 0 10px 0 !important;
        padding: 0 !important;
    }

    .share-selector-anchor + div[data-testid="stHorizontalBlock"] > div {
        padding: 0 10px !important;
        box-sizing: border-box !important;
    }

    .share-selector-anchor + div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button {
        min-height: 42px !important;
        height: 42px !important;
        border-radius: 7px !important;
        background: #f8fafc !important;
        border: 1px solid #d6e0eb !important;
        color: #0f172a !important;
        font-weight: 800 !important;
        box-shadow: none !important;
    }

    html.caprio-dark .share-selector-anchor + div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button {
        background: #131a24 !important;
        border-color: #46566d !important;
        color: #f3f6fb !important;
    }

    .share-selector-anchor + div[data-testid="stHorizontalBlock"] div[data-testid="stCheckbox"] {
        margin: 0 0 10px 0 !important;
        padding: 0 !important;
    }

    .share-selector-anchor + div[data-testid="stHorizontalBlock"] div[data-testid="stCheckbox"] label {
        min-height: 25px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 7px !important;
        width: 100% !important;
        padding: 0 !important;
    }

    .share-selector-anchor + div[data-testid="stHorizontalBlock"] div[data-testid="stCheckbox"] [data-testid="stMarkdownContainer"] p {
        font-weight: 850 !important;
        font-size: 14px !important;
        line-height: 1.15 !important;
        margin: 0 !important;
        white-space: nowrap !important;
        text-align: center !important;
        color: #111827 !important;
        -webkit-text-fill-color: #111827 !important;
    }

    html.caprio-dark .share-selector-anchor + div[data-testid="stHorizontalBlock"] div[data-testid="stCheckbox"] [data-testid="stMarkdownContainer"] p {
        color: #f3f6fb !important;
        -webkit-text-fill-color: #f3f6fb !important;
    }

    .share-group-divider {
        width: 86%;
        height: 1px;
        background: #d6e0eb;
        margin: 9px auto 18px auto;
    }

    html.caprio-dark .share-group-divider {
        background: #46566d !important;
    }

    .share-mini-note {
        width: 100%;
        text-align: center;
        font-size: 10px;
        line-height: 1.2;
        color: #8a95a8;
        margin: 5px 0 0 0;
        padding: 0;
    }

    /* 화이트 모드 체크 해제: 검정 방지, 회색 계열 */
    html.caprio-light div[data-testid="stCheckbox"] div[role="checkbox"][aria-checked="false"],
    html:not(.caprio-dark) div[data-testid="stCheckbox"] div[role="checkbox"][aria-checked="false"],
    html.caprio-light div[data-testid="stCheckbox"] div[data-baseweb="checkbox"][aria-checked="false"],
    html:not(.caprio-dark) div[data-testid="stCheckbox"] div[data-baseweb="checkbox"][aria-checked="false"],
    html.caprio-light div[data-testid="stCheckbox"] label:has(input:not(:checked)) > div:first-child,
    html:not(.caprio-dark) div[data-testid="stCheckbox"] label:has(input:not(:checked)) > div:first-child,
    html.caprio-light div[data-testid="stCheckbox"] label:has(input:not(:checked)) span:first-child,
    html:not(.caprio-dark) div[data-testid="stCheckbox"] label:has(input:not(:checked)) span:first-child {
        background-color: #cbd5e1 !important;
        border-color: #cbd5e1 !important;
        color: #64748b !important;
        fill: #64748b !important;
        box-shadow: none !important;
    }

    html.caprio-light div[data-testid="stCheckbox"] label:has(input:not(:checked)) svg,
    html:not(.caprio-dark) div[data-testid="stCheckbox"] label:has(input:not(:checked)) svg,
    html.caprio-light div[data-testid="stCheckbox"] div[role="checkbox"][aria-checked="false"] svg,
    html:not(.caprio-dark) div[data-testid="stCheckbox"] div[role="checkbox"][aria-checked="false"] svg {
        color: #64748b !important;
        fill: #64748b !important;
    }

    @media (max-width: 768px) {
        .share-selector-anchor + div[data-testid="stHorizontalBlock"] {
            display: block !important;
            margin-bottom: 8px !important;
        }

        .share-selector-anchor + div[data-testid="stHorizontalBlock"] > div {
            width: 100% !important;
            padding: 0 !important;
            margin: 0 0 4px 0 !important;
        }

        .share-selector-anchor + div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button {
            min-height: 40px !important;
            height: 40px !important;
            margin-bottom: 10px !important;
        }

        .share-selector-anchor + div[data-testid="stHorizontalBlock"] div[data-testid="stCheckbox"] {
            margin: 0 0 9px 0 !important;
        }

        .share-selector-anchor + div[data-testid="stHorizontalBlock"] div[data-testid="stCheckbox"] label {
            justify-content: flex-start !important;
            min-height: 25px !important;
        }

        .share-selector-anchor + div[data-testid="stHorizontalBlock"] div[data-testid="stCheckbox"] [data-testid="stMarkdownContainer"] p {
            text-align: left !important;
            font-size: 14px !important;
        }

        .share-group-divider {
            width: 100% !important;
            margin: 10px auto 16px auto !important;
        }

        .share-mini-note {
            text-align: left !important;
            padding-left: 26px !important;
            margin-top: 2px !important;
        }
    }
    
    .quick-rent-condition {
        margin-top: 4px !important;
    }
</style>
    """, unsafe_allow_html=True)

    all_selected_now = all(
        bool(st.session_state.get(f"share_{key}", default_value))
        for key, default_value in DEFAULT_VISIBLE_SECTIONS.items()
    )

    st.markdown('<div class="share-selector-anchor"></div>', unsafe_allow_html=True)

    group_cols = list(st.columns(3, gap="small")) + list(st.columns(3, gap="small"))

    with group_cols[0]:
        if st.button("전체 선택 / 해제", use_container_width=True):
            set_all_sections(not all_selected_now)
            st.rerun()

    with group_cols[1]:
        st.checkbox("조건설정", key="share_conditions", on_change=sync_parent_to_children, args=("conditions",))
        st.markdown('<div class="share-group-divider"></div>', unsafe_allow_html=True)
        st.checkbox("공통조건", key="share_common", disabled=not st.session_state.get("share_conditions", True), on_change=sync_children_to_parent, args=("conditions",))
        st.checkbox("할부조건", key="share_installment_condition", disabled=not st.session_state.get("share_conditions", True), on_change=sync_children_to_parent, args=("conditions",))

    with group_cols[2]:
        st.checkbox("비교 계산기", key="share_summary", on_change=sync_parent_to_children, args=("summary",))
        st.markdown('<div class="share-group-divider"></div>', unsafe_allow_html=True)
        st.checkbox("반납형", key="share_summary_return", disabled=not st.session_state.get("share_summary", True), on_change=sync_children_to_parent, args=("summary",))
        st.checkbox("인수형", key="share_summary_takeover", disabled=not st.session_state.get("share_summary", True), on_change=sync_children_to_parent, args=("summary",))

    with group_cols[3]:
        st.checkbox("검증 요율표", key="share_rate_table")
        st.markdown('<div class="share-group-divider"></div>', unsafe_allow_html=True)

    with group_cols[4]:
        st.checkbox("비교표", key="share_compare", on_change=sync_parent_to_children, args=("compare",))
        st.markdown('<div class="share-group-divider"></div>', unsafe_allow_html=True)
        st.checkbox("할부", key="share_compare_installment", disabled=not st.session_state.get("share_compare", True), on_change=sync_children_to_parent, args=("compare",))
        st.checkbox("렌트", key="share_compare_rent", disabled=not st.session_state.get("share_compare", True), on_change=sync_children_to_parent, args=("compare",))
        st.checkbox("리스", key="share_compare_lease", disabled=not st.session_state.get("share_compare", True), on_change=sync_children_to_parent, args=("compare",))
        st.markdown('<div class="share-mini-note">최소 2개 선택</div>', unsafe_allow_html=True)

    with group_cols[5]:
        st.checkbox("선택 가이드", key="share_guide", on_change=sync_parent_to_children, args=("guide",))
        st.markdown('<div class="share-group-divider"></div>', unsafe_allow_html=True)
        st.checkbox("할부", key="share_guide_installment", disabled=not st.session_state.get("share_guide", True), on_change=sync_children_to_parent, args=("guide",))
        st.checkbox("렌트", key="share_guide_rent", disabled=not st.session_state.get("share_guide", True), on_change=sync_children_to_parent, args=("guide",))
        st.checkbox("리스", key="share_guide_lease", disabled=not st.session_state.get("share_guide", True), on_change=sync_children_to_parent, args=("guide",))

    selected_compare_count = sum(
        bool(st.session_state.get(f"share_{key}", False))
        for key in ["compare_installment", "compare_rent", "compare_lease"]
    )
    if st.session_state.get("share_compare", True) and selected_compare_count < 2:
        st.warning("비교표는 최소 2개 선택이 필요합니다. 저장/공유 시 할부·렌트 기준으로 자동 보정됩니다.")

    return collect_visible_sections_from_state()

def render_quote_history_area(raw_data, car_name, rent_monthly_pay, months, mileage, rent_resale_pct, rent_deposit, make_share_url_func, visible_sections, has_active_quote=True):
    st.markdown("""
    <style>
    .customer-name-inline-anchor + div[data-testid="stHorizontalBlock"] {
        align-items: center !important;
        gap: 0 !important;
        margin: 0 0 10px 0 !important;
    }
    .customer-name-inline-label {
        font-size: 14px;
        font-weight: 900;
        color: #111827;
        white-space: nowrap;
        line-height: 1;
        padding-top: 2px;
    }
    html.caprio-dark .customer-name-inline-label {
        color: #f3f6fb !important;
    }
    .customer-name-inline-anchor + div[data-testid="stHorizontalBlock"] div[data-testid="stTextInput"] {
        margin: 0 !important;
    }
    .customer-name-inline-anchor + div[data-testid="stHorizontalBlock"] div[data-testid="stTextInput"] input {
        height: 38px !important;
        min-height: 38px !important;
    }
    @media (max-width: 768px) {
        .customer-name-inline-anchor + div[data-testid="stHorizontalBlock"] {
            display: block !important;
        }
        .customer-name-inline-label {
            margin-bottom: 6px !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)
    st.markdown('<div class="customer-name-inline-anchor"></div>', unsafe_allow_html=True)
    customer_label_col, customer_input_col = st.columns([0.16, 0.84], gap="small")
    with customer_label_col:
        st.markdown('<div class="customer-name-inline-label">고객명</div>', unsafe_allow_html=True)
    with customer_input_col:
        st.text_input("고객명", key="customer_name", placeholder="고객명 입력", label_visibility="collapsed")
    st.markdown('<div class="quote-history-panel">', unsafe_allow_html=True)
    st.markdown('<div class="quote-history-title">🕘 견적 저장 / 이력</div>', unsafe_allow_html=True)

    save_col1, save_col2 = st.columns([1, 1], gap="small")
    with save_col1:
        save_clicked = st.button("➕ 현재 견적 저장", use_container_width=True)
    with save_col2:
        clear_clicked = st.button("🗑️ 이력 전체 삭제", use_container_width=True)

    if clear_clicked:
        st.session_state.quote_history = []
        st.session_state.raw_quote_input = ""
        st.rerun()

    if save_clicked:
        if raw_data.strip() or has_active_quote:
            short_car_name = car_name[:15] + "..." if len(car_name) > 15 else car_name
            history_title = (
                f"{short_car_name}\n"
                f"월 {rent_monthly_pay:,}원｜{months}개월｜{mileage}"
            )
            current_share_url = make_share_url_func()
            current_finance_mode = st.session_state.get("finance_mode", "rent")
            st.session_state.quote_history.append(
                {
                    "title": history_title,
                    "raw": raw_data,
                    "share_url": current_share_url,
                    "share_message": build_share_copy_message(current_share_url, current_finance_mode),
                    "quick_edit": {
                        "rent_monthly_pay": rent_monthly_pay,
                        "rent_resale_pct": rent_resale_pct,
                        "installment_car_price": installment_car_price,
                        "finance_car_price": finance_car_price,
                        "months": months,
                        "mileage": mileage,
                        "rent_deposit": rent_deposit,
                        "prepayment_mode": st.session_state.get("quick_prepayment_mode", "원" if rent_deposit else "%"),
                        "prepayment_value": st.session_state.get("quick_prepayment_value", f"{rent_deposit:,}" if rent_deposit else ""),
                        "finance_mode": st.session_state.get("finance_mode", "rent"),
                        "lease_tax_included": bool(st.session_state.get("lease_tax_included", False)),
                    },
                    "visible_sections": normalize_visible_sections(visible_sections),
                    "presentation": presentation_settings(st.session_state),
                }
            )
            st.session_state.quote_history = st.session_state.quote_history[:5]
            st.rerun()
        else:
            st.warning("저장할 견적 데이터가 없습니다.")

    if st.session_state.quote_history:
        for idx, item in enumerate(st.session_state.quote_history):
            history_col1, history_col2 = st.columns([0.78, 0.22], gap="small")
            with history_col1:
                if st.button(
                    f"📄 견적 {idx+1}",
                    key=f"history_{idx}",
                    help=item["title"],
                    use_container_width=True,
                ):
                    st.session_state.pending_quote_input = item["raw"]
                    st.session_state.pending_quick_edit = item.get("quick_edit")
                    st.session_state.pending_visible_sections = item.get("visible_sections")
                    st.session_state.pending_presentation = item.get("presentation", {})
                    history_quick_edit = item.get("quick_edit") or {}
                    if history_quick_edit.get("finance_mode") in ["rent", "lease"]:
                        st.session_state.pending_finance_mode = history_quick_edit.get("finance_mode")
                    if "lease_tax_included" in history_quick_edit:
                        st.session_state.pending_lease_tax_included = bool(history_quick_edit.get("lease_tax_included", False))
                    st.rerun()
            with history_col2:
                components.html(
                    f"""
                    <html>
                    <head>
                    <style>
                        html, body {{ margin:0; padding:0; width:100%; height:38px; overflow:hidden; }}
                        button {{
                            width:100%;
                            height:38px;
                            min-height:38px;
                            padding:0;
                            border-radius:8px;
                            border:1px solid #e3c86a;
                            background:#fff4c2;
                            color:#7a5b00;
                            cursor:pointer;
                            font-size:15px;
                            line-height:38px;
                            display:flex;
                            align-items:center;
                            justify-content:center;
                            box-sizing:border-box;
                            overflow:hidden;
                        }}
                    </style>
                    </head>
                    <body>
                    <button
                        onclick="
                            navigator.clipboard.writeText({item.get('share_message') or build_share_copy_message(item.get('share_url', ''), (item.get('quick_edit') or {}).get('finance_mode'))!r});
                            this.innerText='✅';
                            this.style.background='#dff3df';
                            this.style.border='1px solid #86c986';
                        "
                    >🔗</button>
                    </body>
                    </html>
                    """,
                    height=38,
                )
    else:
        st.caption("저장된 견적이 없습니다.")


def render_compare_summary_table(selected_methods):
    method_labels = {
        "installment": "할부",
        "rent": "렌트",
        "lease": "리스",
    }
    selected_methods = [method for method in selected_methods if method in method_labels]
    if len(selected_methods) < 2:
        selected_methods = ["installment", "rent"]

    method_width = int(70 / len(selected_methods))
    compare_class = f"compare-cols-{len(selected_methods)}"

    rows = [
        ("번호판", 1, "compare-cat", "일반번호판", {"installment": "O", "rent": "X", "lease": "O"}),
        ("재무/신용", 2, "compare-cat", "금융·부채 영향", {"installment": "O<br><span style=\"color:red; font-size:10px; display:block; margin-top:-2px; line-height:1;\">(대출한도 영향)</span>", "rent": "X", "lease": "△<br><span style=\"color:red; font-size:10px; display:block; margin-top:-2px; line-height:1;\">(대출한도 영향)</span>"}),
        (None, None, None, "차량 자산 인식", {"installment": "O<br><span style=\"color:red; font-size:10px; display:block; margin-top:-2px; line-height:1;\">(재산세 등 인상)</span>", "rent": "X", "lease": "X"}),
        ("비용", 2, "compare-cat", "세금·보험 납부", {"installment": "별도 납부", "rent": "월납입 포함", "lease": "보험 별도"}),
        (None, None, None, "초기비용", {"installment": "차량가·취등록세 부담", "rent": "선택 가능", "lease": "선택 가능"}),
        ("보험·사고", 3, "compare-cat", "보험 포함", {"installment": "X", "rent": "O", "lease": "X"}),
        (None, None, None, "보험·사고 처리", {"installment": "직접 가입·처리", "rent": "보험 포함·지원", "lease": "직접 가입·처리"}),
        (None, None, None, "사고 비용·리스크", {"installment": "수리비·감가 부담", "rent": "면책금 처리", "lease": "수리비·감가 부담"}),
        ("이력 관리", 2, "compare-cat", "보험경력 인정", {"installment": "O", "rent": "O", "lease": "O"}),
        (None, None, None, "사고이력·보험할증", {"installment": "O", "rent": "X", "lease": "O"}),
        ("관리", 1, "compare-cat", "정비 선택 가능", {"installment": "O", "rent": "O", "lease": "O"}),
        ("법인", 2, "compare-legal", "비용처리", {"installment": "O (최장 8년)", "rent": "O (납입기간 내)", "lease": "O (납입기간 내)"}),
        (None, None, None, "판매 시", {"installment": "부가세 10% 발생<br><span style=\"color:red; font-size:10px; display:block; margin-top:-2px; line-height:1;\">(경차, 승합차 제외)</span>", "rent": "인수·반납 자유", "lease": "인수·반납 자유"}),
    ]

    header_cells = "".join(
        f'<th style="width:{method_width}%">{method_labels[method]}</th>'
        for method in selected_methods
    )
    body_rows = []
    for category, rowspan, category_class, item_name, values in rows:
        cells = []
        if category is not None:
            cells.append(f'<td rowspan="{rowspan}" class="{category_class}">{category}</td>')
        cells.append(f'<td class="compare-item">{item_name}</td>')
        for method in selected_methods:
            cells.append(f'<td>{values[method]}</td>')
        body_rows.append("<tr>" + "".join(cells) + "</tr>")

    return f"""
    <table class="matrix-table compare-summary-table {compare_class}" style="width:55%; font-size:13px;">
        <tr>
            <th style="width:12%;">분류</th>
            <th style="width:18%;">항목</th>
            {header_cells}
        </tr>
        {''.join(body_rows)}
    </table>
    """

from pathlib import Path
CAPRIO_LOGO_BLUE_DATA_URI = 'data:image/png;base64,' + base64.b64encode((Path(__file__).parent / 'customer_ui' / 'carfreeoh-logo-transparent.png').read_bytes()).decode()
CAPRIO_LOGO_WHITE_DATA_URI = 'data:image/png;base64,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'
IS_CLIENT_VIEW = st.query_params.get("view") == "client" and bool(st.query_params.get("q"))

CHO = ["ㄱ","ㄲ","ㄴ","ㄷ","ㄸ","ㄹ","ㅁ","ㅂ","ㅃ","ㅅ","ㅆ","ㅇ","ㅈ","ㅉ","ㅊ","ㅋ","ㅌ","ㅍ","ㅎ"]
JUNG = ["ㅏ","ㅐ","ㅑ","ㅒ","ㅓ","ㅔ","ㅕ","ㅖ","ㅗ","ㅘ","ㅙ","ㅚ","ㅛ","ㅜ","ㅝ","ㅞ","ㅟ","ㅠ","ㅡ","ㅢ","ㅣ"]
JONG = ["","ㄱ","ㄲ","ㄳ","ㄴ","ㄵ","ㄶ","ㄷ","ㄹ","ㄺ","ㄻ","ㄼ","ㄽ","ㄾ","ㄿ","ㅀ","ㅁ","ㅂ","ㅄ","ㅅ","ㅆ","ㅇ","ㅈ","ㅊ","ㅋ","ㅌ","ㅍ","ㅎ"]

KEY = {
    "ㄱ":"r","ㄲ":"R","ㄴ":"s","ㄷ":"e","ㄸ":"E","ㄹ":"f","ㅁ":"a","ㅂ":"q","ㅃ":"Q","ㅅ":"t","ㅆ":"T","ㅇ":"d","ㅈ":"w","ㅉ":"W","ㅊ":"c","ㅋ":"z","ㅌ":"x","ㅍ":"v","ㅎ":"g",
    "ㅏ":"k","ㅐ":"o","ㅑ":"i","ㅒ":"O","ㅓ":"j","ㅔ":"p","ㅕ":"u","ㅖ":"P","ㅗ":"h","ㅛ":"y","ㅜ":"n","ㅠ":"b","ㅡ":"m","ㅣ":"l",
    "ㅘ":"hk","ㅙ":"ho","ㅚ":"hl","ㅝ":"nj","ㅞ":"np","ㅟ":"nl","ㅢ":"ml",
    "ㄳ":"rt","ㄵ":"sw","ㄶ":"sg","ㄺ":"fr","ㄻ":"fa","ㄼ":"fq","ㄽ":"ft","ㄾ":"fx","ㄿ":"fv","ㅀ":"fg","ㅄ":"qt"
}

def hangul_to_eng(text):
    result = ""
    for ch in text:
        code = ord(ch)
        if 0xAC00 <= code <= 0xD7A3:
            base = code - 0xAC00
            cho = base // 588
            jung = (base % 588) // 28
            jong = base % 28
            result += KEY.get(CHO[cho], "")
            result += KEY.get(JUNG[jung], "")
            result += KEY.get(JONG[jong], "")
        else:
            result += ch
    return result.lower()


def is_short_code(value):
    value = str(value or "").strip()
    return bool(re.fullmatch(r"[A-Z0-9]{6,10}", value))


    st.markdown('</div>', unsafe_allow_html=True)

def generate_share_code(length=6):
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def supabase_request(method, path, payload=None):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None

    url = f"{SUPABASE_URL}{path}"
    data = None
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Prefer"] = "return=minimal"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else True
    except Exception:
        return None


def save_share_data(data):
    for _ in range(5):
        code = generate_share_code()
        result = supabase_request(
            "POST",
            "/rest/v1/share_links",
            [{"code": code, "payload": data}]
        )
        if result is not None:
            return code
    return ""


def load_share_data(code):
    code = str(code or "").strip().upper()
    if not is_short_code(code):
        return {}

    result = supabase_request(
        "GET",
        f"/rest/v1/share_links?code=eq.{urllib.parse.quote(code)}&select=payload"
    )

    if isinstance(result, list) and result:
        return result[0].get("payload", {}) or {}
    return {}

def encode_share_data(data):
    json_text = json.dumps(data, ensure_ascii=False)
    return base64.urlsafe_b64encode(json_text.encode("utf-8")).decode("utf-8")

def decode_share_data(encoded_text):
    encoded_text = str(encoded_text or "").strip()

    if is_short_code(encoded_text):
        loaded_data = load_share_data(encoded_text)
        if loaded_data:
            return loaded_data

    try:
        padding = "=" * (-len(encoded_text) % 4)
        decoded = base64.urlsafe_b64decode((encoded_text + padding).encode("utf-8"))
        return json.loads(decoded.decode("utf-8"))
    except Exception:
        return {}


def extract_share_query_value(value):
    value = str(value or "").strip()
    if not value:
        return ""

    parsed_url = urllib.parse.urlparse(value)
    query_value = urllib.parse.parse_qs(parsed_url.query).get("q", [""])[0]
    if query_value:
        return query_value.strip()

    query_match = re.search(r"[?&]q=([^&\s]+)", value)
    if query_match:
        return urllib.parse.unquote(query_match.group(1)).strip()

    return value.strip()


# ==========================================
# [EARLY UI SECURITY PATCH] 로그인 전 상단/하단 Streamlit 기본 UI 숨김
# ==========================================
st.markdown("""
<style>
    header[data-testid="stHeader"],
    div[data-testid="stToolbar"],
    div[data-testid="stDecoration"],
    div[data-testid="stStatusWidget"],
    #MainMenu,
    footer,
    button[title*="Fork"],
    button[title*="GitHub"],
    button[title*="Share"],
    button[title*="Edit"],
    button[title*="Rerun"],
    button[aria-label*="Fork"],
    button[aria-label*="GitHub"],
    button[aria-label*="Share"],
    button[aria-label*="Edit"],
    button[aria-label*="Rerun"],
    a[href*="github.com"],
    a[href*="streamlit.io"] {
        display: none !important;
        visibility: hidden !important;
        pointer-events: none !important;
        width: 0 !important;
        height: 0 !important;
        overflow: hidden !important;
    }
</style>
""", unsafe_allow_html=True)

components.html("""
<script>
(function(){
    const doc = window.parent.document;

    function hideStreamlitChromeEarly(){
        const selectors = [
            'header[data-testid="stHeader"]',
            'div[data-testid="stToolbar"]',
            'div[data-testid="stDecoration"]',
            'div[data-testid="stStatusWidget"]',
            '#MainMenu',
            'footer',
            'button[title*="Fork"]',
            'button[title*="GitHub"]',
            'button[title*="Share"]',
            'button[title*="Edit"]',
            'button[title*="Rerun"]',
            'button[aria-label*="Fork"]',
            'button[aria-label*="GitHub"]',
            'button[aria-label*="Share"]',
            'button[aria-label*="Edit"]',
            'button[aria-label*="Rerun"]',
            'a[href*="github.com"]',
            'a[href*="streamlit.io"]'
        ];

        selectors.forEach(function(sel){
            doc.querySelectorAll(sel).forEach(function(el){
                if(el.closest && el.closest('#caprio-brand-header')) return;
                el.style.setProperty('display','none','important');
                el.style.setProperty('visibility','hidden','important');
                el.style.setProperty('pointer-events','none','important');
                el.style.setProperty('width','0','important');
                el.style.setProperty('height','0','important');
                el.style.setProperty('overflow','hidden','important');
            });
        });

    }

    hideStreamlitChromeEarly();
    setInterval(hideStreamlitChromeEarly, 350);
})();
</script>
""", height=0, width=0)

if not IS_CLIENT_VIEW:
    if not APP_PASSWORD:
        st.warning("APP_PASSWORD가 설정되지 않았습니다.")
        st.stop()

    if "auth_ok" not in st.session_state:
        st.session_state.auth_ok = False

    if not st.session_state.auth_ok:
        input_password = st.text_input(
            "",
            type="password",
            placeholder="비밀번호 입력"
        )

        if input_password:
            pw_input = input_password.strip().lower()
            pw_secret = APP_PASSWORD.strip().lower()
            pw_secret_eng = hangul_to_eng(pw_secret)

            if pw_input == pw_secret or pw_input == pw_secret_eng:
                st.session_state.auth_ok = True
                st.rerun()
            else:
                st.error("비밀번호가 올바르지 않습니다.")
                st.stop()
        else:
            st.stop()



# ==========================================
# [고객용 전용 스크롤/계산 애니메이션]
# - 영업자용에는 적용하지 않음
# - 기존 계산 로직/값/색상은 건드리지 않고 화면 표시 효과만 적용
# - PC/MO 공통 적용
# - 비교 계산기 영역은 자동차 진행바 → 숫자 카운트업 순서로 연출
# ==========================================
if IS_CLIENT_VIEW:
    st.markdown("""
    <style>
    html.caprio-client-view .caprio-reveal-target {
        opacity: 0;
        transform: translateY(24px);
        transition: opacity 0.92s cubic-bezier(.22,.75,.2,1), transform 0.92s cubic-bezier(.22,.75,.2,1);
        will-change: opacity, transform;
    }

    html.caprio-client-view .caprio-reveal-target.caprio-show {
        opacity: 1;
        transform: translateY(0);
    }

    html.caprio-client-view .pure-table.caprio-calc-ready {
        opacity: 0;
        transform: translateY(14px);
        transition: opacity 0.55s ease, transform 0.55s ease;
    }

    html.caprio-client-view .pure-table.caprio-calc-ready.caprio-show {
        opacity: 1;
        transform: translateY(0);
    }

    html.caprio-client-view .pure-table.caprio-calc-ready tr:not(:first-child) {
        opacity: 0;
        transform: translateY(9px);
        transition: opacity 0.42s ease, transform 0.42s ease;
    }

    html.caprio-client-view .pure-table.caprio-calc-ready tr.caprio-row-show {
        opacity: 1;
        transform: translateY(0);
    }

    html.caprio-client-view .pure-table + .excel-green,
    html.caprio-client-view .pure-table + .excel-red {
        margin-top: 30px !important;
    }

    /* 비교 계산기 표와 최종 결과 카드 사이 실제 간격: st.markdown 래퍼 때문에 + 선택자가 먹지 않아 전용 spacer를 출력부에 직접 삽입 */
    html.caprio-client-view .caprio-result-spacer {
        height: 22px;
        line-height: 22px;
        display: block;
        width: 100%;
        clear: both;
    }

    html.caprio-client-view .caprio-result-spacer + div,
    html.caprio-client-view .caprio-result-spacer + .excel-green,
    html.caprio-client-view .caprio-result-spacer + .excel-red {
        margin-top: 0 !important;
    }

    html.caprio-client-view .excel-green.caprio-reveal-target,
    html.caprio-client-view .excel-red.caprio-reveal-target {
        opacity: 0;
        transform: translateY(-22px) scale(0.985);
        transition-delay: 0s;
        transition-duration: 0.96s;
        transition-timing-function: cubic-bezier(.22,.75,.2,1);
    }

    html.caprio-client-view .excel-green.caprio-reveal-target.caprio-show,
    html.caprio-client-view .excel-red.caprio-reveal-target.caprio-show {
        opacity: 1;
        transform: translateY(0) scale(1);
    }

    html.caprio-client-view .caprio-down-cue {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 100%;
        margin: 12px 0 42px 0;
        color: #1d4ed8;
        font-size: 18px;
        font-weight: 900;
        opacity: 0;
        transform: translateY(-6px);
        transition: opacity 0.58s ease, transform 0.58s ease;
        pointer-events: none;
    }

    html.caprio-client-view .caprio-down-cue.caprio-cue-show {
        opacity: 0.82;
        transform: translateY(0);
        animation: caprioCueBounce 1.35s ease-in-out infinite;
    }

    html.caprio-dark.caprio-client-view .caprio-down-cue {
        color: #8ab9ff;
    }

    /* 화살표 제거: 절감 카드 전후 간격만 사용 */
    html.caprio-client-view .caprio-down-cue {
        display: none !important;
    }

    @keyframes caprioCueBounce {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(5px); }
    }

    html.caprio-client-view .caprio-calc-loader {
        display: none;
        width: min(680px, 100%);
        margin: 10px auto 14px auto;
        padding: 14px 16px 13px 16px;
        border-radius: 14px;
        background: rgba(248, 250, 252, 0.96);
        border: 1px solid rgba(214, 224, 235, 0.95);
        box-shadow: 0 10px 26px rgba(15, 23, 42, 0.08);
        box-sizing: border-box;
        opacity: 0;
        transform: translateY(10px);
        transition: opacity 0.35s ease, transform 0.35s ease;
    }

    html.caprio-dark.caprio-client-view .caprio-calc-loader {
        background: rgba(19, 26, 36, 0.96);
        border-color: rgba(70, 86, 109, 0.95);
        box-shadow: 0 10px 26px rgba(0, 0, 0, 0.24);
    }

    html.caprio-client-view .caprio-calc-loader.caprio-loader-active {
        display: block;
        opacity: 1;
        transform: translateY(0);
    }

    html.caprio-client-view .caprio-calc-loader.caprio-loader-done {
        opacity: 0;
        transform: translateY(-6px);
        pointer-events: none;
    }

    html.caprio-client-view .caprio-loader-title {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 10px;
        margin-bottom: 10px;
        font-size: 13px;
        font-weight: 900;
        color: #0f172a;
        line-height: 1.25;
    }

    html.caprio-dark.caprio-client-view .caprio-loader-title {
        color: #f3f6fb;
    }

    html.caprio-client-view .caprio-loader-percent {
        font-size: 13px;
        font-weight: 950;
        color: #1d4ed8;
        white-space: nowrap;
    }

    html.caprio-client-view .caprio-loader-track {
        position: relative;
        height: 30px;
        border-radius: 999px;
        background: #e8eef6;
        overflow: visible;
    }

    html.caprio-dark.caprio-client-view .caprio-loader-track {
        background: #273244;
    }

    html.caprio-client-view .caprio-loader-fill {
        position: absolute;
        left: 0;
        top: 0;
        height: 100%;
        width: 0%;
        border-radius: 999px;
        background: linear-gradient(90deg, #1d4ed8 0%, #38bdf8 100%);
        transition: width 0.38s ease;
    }

    html.caprio-client-view .caprio-loader-car {
        position: absolute;
        left: 0%;
        top: 50%;
        width: 42px;
        height: 24px;
        transform: translate(-5px, -62%);
        transition: left 0.38s ease;
        z-index: 2;
    }

    html.caprio-client-view .caprio-loader-car svg {
        width: 42px;
        height: 24px;
        display: block;
        filter: drop-shadow(0 4px 5px rgba(15, 23, 42, 0.18));
    }

    html.caprio-client-view .caprio-loader-car .wheel {
        transform-box: fill-box;
        transform-origin: center;
        animation: caprioWheelSpin 0.48s linear infinite;
    }

    @keyframes caprioWheelSpin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }

    html.caprio-client-view .caprio-loader-sub {
        margin-top: 9px;
        font-size: 11px;
        line-height: 1.35;
        color: #64748b;
        text-align: center;
        font-weight: 800;
    }

    html.caprio-dark.caprio-client-view .caprio-loader-sub {
        color: #b7c3d4;
    }



    html.caprio-client-view .compare-summary-table.caprio-compare-ready tr:not(:first-child) {
        opacity: 0;
        transform: translateY(8px);
        transition: opacity 0.38s ease, transform 0.38s ease;
    }

    html.caprio-client-view .compare-summary-table.caprio-compare-ready tr.caprio-compare-row-show {
        opacity: 1;
        transform: translateY(0);
    }

    html.caprio-client-view .guide-wrap.caprio-guide-ready .guide-card {
        opacity: 0;
        transform: translateY(16px) scale(0.985);
        transition: opacity 0.55s cubic-bezier(.22,.75,.2,1), transform 0.55s cubic-bezier(.22,.75,.2,1);
    }

    html.caprio-client-view .guide-wrap.caprio-guide-ready .guide-card.caprio-guide-card-show {
        opacity: 1;
        transform: translateY(0) scale(1);
    }

    html.caprio-client-view .excel-green.caprio-final-pulse.caprio-show,
    html.caprio-client-view .excel-red.caprio-final-pulse.caprio-show {
        animation: caprioFinalPulse 0.72s ease 1;
    }

    @keyframes caprioFinalPulse {
        0% { transform: translateY(0) scale(1); }
        45% { transform: translateY(-1px) scale(1.018); }
        100% { transform: translateY(0) scale(1); }
    }

    @media (max-width: 768px) {
        html.caprio-client-view .caprio-reveal-target {
            transform: translateY(18px);
            transition-duration: 0.78s;
        }

        html.caprio-client-view .caprio-calc-loader {
            width: 100%;
            margin: 8px auto 12px auto;
            padding: 13px 13px 12px 13px;
            border-radius: 12px;
        }

        html.caprio-client-view .caprio-loader-title {
            font-size: 12px;
        }

        html.caprio-client-view .pure-table + .excel-green,
        html.caprio-client-view .pure-table + .excel-red {
            margin-top: 36px !important;
        }

        html.caprio-client-view .caprio-down-cue {
            display: none !important;
        }

        html.caprio-client-view .caprio-result-spacer {
            height: 24px;
            line-height: 24px;
        }
    }
    </style>
    """, unsafe_allow_html=True)

    components.html("""
    <script>
    (function(){
        const doc = window.parent.document;
        const root = doc.documentElement;
        root.classList.add('caprio-client-view');

        const loaderMessages = [
            { pct: 12, text: '고객님 조건 반영 중...' },
            { pct: 35, text: '월 납입금 계산 중...' },
            { pct: 58, text: '잔존가치 계산 중...' },
            { pct: 80, text: '보험·세금 계산 중...' },
            { pct: 100, text: '계산 완료 ✓' }
        ];

        function formatWon(value) {
            const sign = value < 0 ? '-' : '';
            const absValue = Math.abs(Math.round(value));
            return sign + absValue.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',') + ' 원';
        }

        function carSvg() {
            return `
                <svg viewBox="0 0 84 48" aria-hidden="true">
                    <path d="M18 28 L25 15 C27 11 31 9 36 9 H50 C55 9 59 12 62 16 L70 28 Z" fill="#1d4ed8"/>
                    <path d="M28 17 C30 14 33 13 37 13 H42 V27 H22 L28 17Z" fill="#dff6ff"/>
                    <path d="M45 13 H50 C54 13 56 15 59 18 L65 27 H45 Z" fill="#bdefff"/>
                    <path d="M9 27 C10 22 15 20 21 20 H62 C70 20 77 26 78 34 L78 36 H8 L8 32 C8 30 8 29 9 27Z" fill="#2563eb"/>
                    <path d="M8 32 H78 V37 H8 Z" fill="#1e40af"/>
                    <path d="M74 29 H80 C81 29 82 30 82 31 V34 H76 Z" fill="#facc15"/>
                    <path d="M8 29 H15 L12 34 H5 V32 C5 30 6 29 8 29Z" fill="#93c5fd"/>
                    <circle class="wheel" cx="24" cy="37" r="8" fill="#111827"/>
                    <circle class="wheel" cx="61" cy="37" r="8" fill="#111827"/>
                    <circle cx="24" cy="37" r="3" fill="#cbd5e1"/>
                    <circle cx="61" cy="37" r="3" fill="#cbd5e1"/>
                </svg>
            `;
        }

        function makeLoader() {
            const loader = doc.createElement('div');
            loader.className = 'caprio-calc-loader';
            loader.innerHTML = `
                <div class="caprio-loader-title">
                    <span class="caprio-loader-text">고객님 조건 반영 중...</span>
                    <span class="caprio-loader-percent">0%</span>
                </div>
                <div class="caprio-loader-track">
                    <div class="caprio-loader-fill"></div>
                    <div class="caprio-loader-car">${carSvg()}</div>
                </div>
                <div class="caprio-loader-sub">카프리오가 조건별 비용을 계산하고 있습니다</div>
            `;
            return loader;
        }

        function runLoader(loader, done) {
            if (!loader || loader.dataset.caprioLoaderDone === '1') {
                done();
                return;
            }
            loader.dataset.caprioLoaderDone = '1';
            loader.classList.add('caprio-loader-active');

            const textEl = loader.querySelector('.caprio-loader-text');
            const percentEl = loader.querySelector('.caprio-loader-percent');
            const fillEl = loader.querySelector('.caprio-loader-fill');
            const carEl = loader.querySelector('.caprio-loader-car');

            loaderMessages.forEach(function(item, index){
                setTimeout(function(){
                    if (textEl) textEl.textContent = item.text;
                    if (percentEl) percentEl.textContent = item.pct + '%';
                    if (fillEl) fillEl.style.width = item.pct + '%';
                    if (carEl) carEl.style.left = item.pct + '%';
                }, 260 + index * 360);
            });

            setTimeout(function(){
                loader.classList.add('caprio-loader-done');
                setTimeout(function(){
                    loader.style.display = 'none';
                    done();
                }, 360);
            }, 2260);
        }

        function animateMoneyCell(cell, delay) {
            if (!cell || cell.dataset.caprioMoneyDone === '1') return;

            const original = (cell.textContent || '').trim();
            const match = original.match(/^(-?)([0-9,]+)\s*원$/);
            if (!match) return;

            const target = parseInt(match[2].replace(/,/g, ''), 10) * (match[1] === '-' ? -1 : 1);
            if (!Number.isFinite(target)) return;

            cell.dataset.caprioMoneyDone = '1';
            cell.dataset.caprioOriginalText = original;
            cell.textContent = '0 원';

            const duration = 980;
            const startDelay = Math.max(0, delay || 0);
            const startAt = performance.now() + startDelay;

            function step(now) {
                if (now < startAt) {
                    requestAnimationFrame(step);
                    return;
                }
                const progress = Math.min((now - startAt) / duration, 1);
                const eased = 1 - Math.pow(1 - progress, 3);
                const current = target * eased;
                cell.textContent = formatWon(current);
                if (progress < 1) {
                    requestAnimationFrame(step);
                } else {
                    cell.textContent = original;
                }
            }
            requestAnimationFrame(step);
        }

        function animateCalcTable(table, extraDelay) {
            if (!table || table.dataset.caprioCalcDone === '1') return;
            table.dataset.caprioCalcDone = '1';

            const startRows = function(){
                table.classList.add('caprio-show');
                const rows = Array.from(table.querySelectorAll('tr'));
                let lastRowDelay = 0;

                rows.forEach(function(row, index){
                    if (index === 0) return;
                    const rowDelay = Math.min(index * 145, 1450);
                    lastRowDelay = Math.max(lastRowDelay, rowDelay);
                    setTimeout(function(){
                        row.classList.add('caprio-row-show');
                        row.querySelectorAll('td').forEach(function(cell){
                            animateMoneyCell(cell, 80);
                        });
                    }, rowDelay);
                });

                // 절감/유리 카드 숫자는 반드시 바로 위 계산표의 행/숫자 애니메이션이 끝난 뒤 시작한다.
                // 기존에는 카드가 동시에 viewport에 들어오면 final card 타이머가 먼저 돌아서 엇박자가 생길 수 있었다.
                setTimeout(function(){
                    table.dataset.caprioCalcVisualDone = '1';
                    table.dispatchEvent(new CustomEvent('caprioCalcVisualDone', { bubbles: true }));
                }, lastRowDelay + 700);
            };

            const loader = table.previousElementSibling && table.previousElementSibling.classList.contains('caprio-calc-loader')
                ? table.previousElementSibling
                : null;
            setTimeout(function(){
                runLoader(loader, startRows);
            }, Math.max(0, extraDelay || 0));
        }



        function animateInlineMoney(el, delay) {
            if (!el || el.dataset.caprioInlineMoneyDone === '1') return;
            const original = (el.textContent || '').trim();
            const match = original.match(/(-?)([0-9,]+)원/);
            if (!match) return;
            const target = parseInt(match[2].replace(/,/g, ''), 10) * (match[1] === '-' ? -1 : 1);
            if (!Number.isFinite(target)) return;

            el.dataset.caprioInlineMoneyDone = '1';
            const prefix = original.slice(0, match.index);
            const suffix = original.slice(match.index + match[0].length);
            const startDelay = Math.max(0, delay || 0);
            const duration = 1050;
            const startAt = performance.now() + startDelay;

            function step(now) {
                if (now < startAt) {
                    requestAnimationFrame(step);
                    return;
                }
                const progress = Math.min((now - startAt) / duration, 1);
                const eased = 1 - Math.pow(1 - progress, 3);
                const current = target * eased;
                el.textContent = prefix + Math.abs(Math.round(current)).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',') + '원' + suffix;
                if (progress < 1) {
                    requestAnimationFrame(step);
                } else {
                    el.textContent = original;
                    el.classList.add('caprio-final-pulse');
                }
            }
            requestAnimationFrame(step);
        }

        function findPreviousCalcTable(el) {
            const tables = Array.from(doc.querySelectorAll('.pure-table'));
            let previous = null;
            tables.forEach(function(table){
                if (table === el) return;
                if (table.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING) {
                    previous = table;
                }
            });
            return previous;
        }

        function revealFinalCardAfterPreviousTable(el, fallbackDelay) {
            if (!el || el.dataset.caprioFinalRevealStarted === '1') return;

            const previousTable = findPreviousCalcTable(el);
            const reveal = function(delay){
                if (el.dataset.caprioFinalRevealStarted === '1') return;
                el.dataset.caprioFinalRevealStarted = '1';
                setTimeout(function(){
                    el.classList.add('caprio-show');
                    animateInlineMoney(el, 320);
                }, Math.max(0, delay || 0));
            };

            if (previousTable && previousTable.dataset.caprioCalcVisualDone !== '1') {
                const onDone = function(){ reveal(50); };
                previousTable.addEventListener('caprioCalcVisualDone', onDone, { once: true });

                // 혹시 브라우저/Streamlit 재렌더 타이밍으로 이벤트를 놓쳐도 멈추지 않게 안전장치
                setTimeout(function(){
                    if (previousTable.dataset.caprioCalcVisualDone === '1') {
                        reveal(50);
                    } else {
                        reveal(900);
                    }
                }, 5200);
            } else {
                reveal(fallbackDelay);
            }
        }

        function animateCompareSummaryTable(table) {
            if (!table || table.dataset.caprioCompareDone === '1') return;
            table.dataset.caprioCompareDone = '1';
            table.classList.add('caprio-show');
            const rows = Array.from(table.querySelectorAll('tr'));
            rows.forEach(function(row, index){
                if (index === 0) return;
                setTimeout(function(){
                    row.classList.add('caprio-compare-row-show');
                }, Math.min(index * 95, 1200));
            });
        }

        function animateGuideWrap(wrap) {
            if (!wrap || wrap.dataset.caprioGuideDone === '1') return;
            wrap.dataset.caprioGuideDone = '1';
            wrap.classList.add('caprio-show');
            const cards = Array.from(wrap.querySelectorAll('.guide-card'));
            cards.forEach(function(card, index){
                setTimeout(function(){
                    card.classList.add('caprio-guide-card-show');
                }, index * 220);
            });
        }

        const revealObserver = new IntersectionObserver(function(entries){
            entries.forEach(function(entry){
                if (!entry.isIntersecting) return;

                const el = entry.target;

                if (el.classList.contains('pure-table')) {
                    const tableIndex = parseInt(el.dataset.caprioCalcIndex || '0', 10);
                    const tableDelay = Math.min(tableIndex * 780, 1600);
                    animateCalcTable(el, tableDelay);
                } else if (el.classList.contains('compare-summary-table')) {
                    animateCompareSummaryTable(el);
                } else if (el.classList.contains('guide-wrap')) {
                    animateGuideWrap(el);
                } else {
                    const isFinalCard = el.classList.contains('excel-green') || el.classList.contains('excel-red');
                    const isBlueHeader = el.classList.contains('excel-header-blue');
                    const finalIndex = parseInt(el.dataset.caprioFinalIndex || '0', 10);
                    const headerIndex = parseInt(el.dataset.caprioHeaderIndex || '0', 10);

                    let showDelay = 180;
                    if (isFinalCard) {
                        showDelay = 700 + Math.min(finalIndex * 500, 1200);
                    } else if (isBlueHeader) {
                        // 모바일에서 반납형 결과 카드가 보이자마자 인수형 바가 바로 튀어나오지 않도록
                        // 파란 제목 바는 순서별로 조금 더 늦게 등장시킨다.
                        showDelay = 180 + Math.min(headerIndex * 900, 1800);
                    }

                    if (isFinalCard) {
                        revealFinalCardAfterPreviousTable(el, showDelay);
                    } else {
                        setTimeout(function(){
                            el.classList.add('caprio-show');
                        }, showDelay);
                    }
                }

                revealObserver.unobserve(el);
            });
        }, { threshold: 0.18, rootMargin: '0px 0px -10% 0px' });

        function ensureFinalCues() {
            const finalCards = Array.from(doc.querySelectorAll('.excel-green, .excel-red'));
            finalCards.forEach(function(card, index){
                if (!card.dataset.caprioFinalIndex) card.dataset.caprioFinalIndex = String(index);
            });
        }

        function assignCalcTableOrder() {
            const tables = Array.from(doc.querySelectorAll('.pure-table'));
            tables.forEach(function(table, index){
                if (!table.dataset.caprioCalcIndex) table.dataset.caprioCalcIndex = String(index);
            });
        }

        function assignHeaderOrder() {
            const headers = Array.from(doc.querySelectorAll('.excel-header-blue'));
            headers.forEach(function(header, index){
                if (!header.dataset.caprioHeaderIndex) header.dataset.caprioHeaderIndex = String(index);
            });
        }

        function setupCaprioAnimations() {
            ensureFinalCues();
            assignCalcTableOrder();
            assignHeaderOrder();
            const targets = doc.querySelectorAll([
                '.common-info-box',
                '.excel-header-blue',
                '.pure-table',
                '.excel-green',
                '.excel-red',
                '.excel-header-gray',
                '.matrix-table',
                '.compare-summary-table',
                '.guide-wrap'
            ].join(','));

            targets.forEach(function(el){
                if (el.dataset.caprioRevealReady === '1') return;
                el.dataset.caprioRevealReady = '1';
                el.classList.add('caprio-reveal-target');

                if (el.classList.contains('pure-table')) {
                    el.classList.add('caprio-calc-ready');
                    if (!el.previousElementSibling || !el.previousElementSibling.classList.contains('caprio-calc-loader')) {
                        el.parentNode.insertBefore(makeLoader(), el);
                    }
                }

                if (el.classList.contains('compare-summary-table')) {
                    el.classList.add('caprio-compare-ready');
                }

                if (el.classList.contains('guide-wrap')) {
                    el.classList.add('caprio-guide-ready');
                }

                revealObserver.observe(el);
            });
        }

        setupCaprioAnimations();
        setTimeout(setupCaprioAnimations, 450);
        setTimeout(setupCaprioAnimations, 1200);
        setInterval(setupCaprioAnimations, 1500);
    })();
    </script>
    """, height=0, width=0)


# 레이아웃 완벽 정렬 및 불필요한 공백 제거용 CSS
st.markdown("""
    <style>
    div.block-container { padding-top: 1rem !important; padding-bottom: 1rem !important; }
    
    /* 상단 공통 조건 박스 및 테이블 */
    .common-info-box { background-color: #f8f9fa; border: 1px solid #dee2e6; padding: 15px; border-radius: 6px; margin-bottom: 20px; }
    html.caprio-dark .customer-message-box div { color: #f3f6fb !important; }

    /* ===== 고객 인삿말 / 마무리말: 프리미엄 3회 폴리싱 효과 ===== */
    html.caprio-client-view .customer-message-box.caprio-polish-message {
        position: relative !important;
        overflow: hidden !important;
        isolation: isolate !important;
        border-radius: 6px !important;
        animation: caprioMessageSoftIn 0.25s ease-out both;
        will-change: opacity, transform;
        box-shadow: 0 10px 24px rgba(11, 56, 115, 0.06) !important;
    }

    html.caprio-client-view .customer-message-box.caprio-polish-message::before {
        content: "";
        position: absolute;
        inset: -1px;
        z-index: 1;
        pointer-events: none;
        border-radius: inherit;
        opacity: 0;
        background:
            radial-gradient(circle at 16% 0%, rgba(37, 99, 235, 0.13), transparent 36%),
            radial-gradient(circle at 100% 100%, rgba(14, 165, 233, 0.10), transparent 38%);
    }

    html.caprio-client-view .customer-message-box.caprio-polish-message::after {
        content: "";
        position: absolute;
        top: -60%;
        left: -105%;
        width: 72%;
        height: 230%;
        z-index: 2;
        pointer-events: none;
        opacity: 0;
        transform: rotate(10deg);
        background: linear-gradient(
            115deg,
            transparent 0%,
            rgba(255, 255, 255, 0.00) 18%,
            rgba(219, 234, 254, 0.20) 34%,
            rgba(255, 255, 255, 0.62) 50%,
            rgba(59, 130, 246, 0.14) 64%,
            rgba(255, 255, 255, 0.00) 82%,
            transparent 100%
        );
    }

    html.caprio-client-view .customer-message-box.caprio-polish-message.caprio-show::before {
        animation: caprioMessageGlowTriple 7.8s ease-out 0.25s 1 both;
    }

    html.caprio-client-view .customer-message-box.caprio-polish-message.caprio-show::after {
        animation: caprioMessagePolishSweepTriple 2.6s cubic-bezier(.22,.75,.2,1) 0.45s 3 both;
    }

    html.caprio-dark.caprio-client-view .customer-message-box.caprio-polish-message {
        box-shadow: 0 12px 28px rgba(0, 102, 255, 0.14) !important;
    }

    html.caprio-dark.caprio-client-view .customer-message-box.caprio-polish-message::before {
        background:
            radial-gradient(circle at 16% 0%, rgba(80, 150, 255, 0.18), transparent 38%),
            radial-gradient(circle at 100% 100%, rgba(56, 189, 248, 0.12), transparent 40%);
    }

    html.caprio-dark.caprio-client-view .customer-message-box.caprio-polish-message::after {
        background: linear-gradient(
            115deg,
            transparent 0%,
            rgba(125, 180, 255, 0.00) 18%,
            rgba(96, 165, 250, 0.16) 34%,
            rgba(147, 197, 253, 0.46) 50%,
            rgba(255, 255, 255, 0.16) 64%,
            rgba(125, 180, 255, 0.00) 82%,
            transparent 100%
        );
    }

    @keyframes caprioMessageSoftIn {
        0% { opacity: 0; transform: translateY(8px) scale(0.995); }
        100% { opacity: 1; transform: translateY(0) scale(1); }
    }

    @keyframes caprioMessagePolishSweepTriple {
        0% { left: -105%; opacity: 0; }
        7% { opacity: 1; }
        65% { left: 135%; opacity: 0; }
        100% { left: 135%; opacity: 0; }
    }

    @keyframes caprioMessageGlowTriple {
        0% { opacity: 0; }
        8% { opacity: 0.9; }
        32% { opacity: 0.55; }
        40% { opacity: 0.85; }
        64% { opacity: 0.55; }
        72% { opacity: 0.82; }
        100% { opacity: 0.48; }
    }

    @media (max-width: 768px) {
        html.caprio-client-view .customer-message-box.caprio-polish-message::after {
            width: 86%;
            top: -65%;
            height: 240%;
        }
    }

    .common-table { width: 100%; border-collapse: collapse; background-color: #ffffff; text-align: center; font-size: 13px; }
    .common-table th { background-color: #f1f3f5; color: #0b3873; font-weight: bold; padding: 8px; border: 1px solid #dee2e6; }
    .common-table td { padding: 8px; border: 1px solid #dee2e6; color: #333333; }
    .option-stack { display: inline-flex; flex-direction: column; gap: 1px; line-height: 1.12; align-items: center; justify-content: center; }
    .option-line { margin: 0; padding: 0; line-height: 1.12; white-space: normal; }
    .option-name { font-weight: 800; color: inherit; }
    .option-price { font-size: 0.86em; color: #666666; font-weight: 600; }
    html.caprio-dark .option-price { color: #b7c0cf !important; }

    /* 메인 비교 테이블 */
    .excel-header-blue { background-color: #0b3873; color: white; padding: 8px; text-align: center; font-weight: bold; font-size: 15px; border-radius: 4px; margin-bottom: 12px; }
    .excel-header-gray { background-color: #5a5a5a; color: white; padding: 6px; text-align: center; font-weight: bold; font-size: 14px; border-radius: 4px; margin-bottom: 10px; }
    .capture-box { border: 2px solid #0b3873; padding: 15px; border-radius: 6px; background-color: #ffffff; }
    .excel-green { background-color: #e2efda; color: #375623; font-weight: bold; font-size: 14px; border: 1px solid #a9d08e; border-radius: 4px; padding: 8px; text-align: center; margin-top: -7px; }
    .excel-red { background-color: #fce4d6; color: #c65911; font-weight: bold; font-size: 14px; border: 1px solid #f4b084; border-radius: 4px; padding: 8px; text-align: center; margin-top: -7px; }
    html.caprio-client-view .caprio-result-spacer + div .excel-green,
    html.caprio-client-view .caprio-result-spacer + div .excel-red,
    html.caprio-client-view .caprio-result-spacer ~ .excel-green,
    html.caprio-client-view .caprio-result-spacer ~ .excel-red {
        margin-top: 0 !important;
    }

    html.caprio-client-view .pure-table + .excel-green,
    html.caprio-client-view .pure-table + .excel-red {
        margin-top: 30px !important;
    }

    @media (max-width: 768px) {
        html.caprio-client-view .pure-table + .excel-green,
        html.caprio-client-view .pure-table + .excel-red {
            margin-top: 36px !important;
        }
    }
    
    .pure-table { width: 100%; border-collapse: collapse; font-size: 13px; text-align: center; }
    .pure-table th { background-color: #0b3873; color: white; font-weight: bold; padding: 8px; border: 1px solid #dee2e6; }
    .pure-table td { padding: 8px; border: 1px solid #dee2e6; height: 40px; }
    
    /* 하단 검증 요율표 */
    .matrix-table { width: 100%; border-collapse: collapse; font-size: 12px; text-align: center; margin-bottom: 10px; }
    .matrix-table th { background-color: #0b3873; color: white; font-weight: bold; padding: 5px; border: 1px solid #dee2e6; }
    .matrix-table td { padding: 5px; border: 1px solid #dee2e6; }
    
    .td-highlight { background-color: #e2efda; color: #375623; font-weight: bold; }
    .bg-light { background-color: #f8f9fa; }
    .text-blue { color: #0b3873; font-weight: bold; }
    .font-bold { font-weight: bold; }

    /* 할부·렌트·리스 비교표 셀 색상 클래스 */
    .compare-cat { background:#0b3873; color:white; font-weight:bold; }
    .compare-legal { background:#6b8e23; color:white; font-weight:bold; }
    .compare-item { background:#ddebf7; font-weight:bold; }

    /* 고객용 비교 조건 설정표 */
    .rent-highlight {
        background-color: #e2efda !important;
        color: #375623 !important;
        font-weight: bold !important;
    }
    .lease-highlight {
        background-color: #ede7f6 !important;
        color: #4c1d95 !important;
        font-weight: bold !important;
    }

    @media (max-width: 768px) {
        .client-condition-table,
        .client-condition-table thead,
        .client-condition-table tbody,
        .client-condition-table tr,
        .client-condition-table th,
        .client-condition-table td {
            display: block !important;
            width: 100% !important;
            box-sizing: border-box !important;
        }

        .client-condition-table thead {
            display: none !important;
        }

        .client-condition-table tr {
            display: block !important;
        }

        .client-condition-table td {
            display: grid !important;
            grid-template-columns: 110px 1fr !important;
            align-items: center !important;
            text-align: left !important;
            padding: 8px !important;
            font-size: 13px !important;
            border-bottom: 1px solid #dee2e6 !important;
            word-break: keep-all !important;
        }

        .client-condition-table td::before {
            font-weight: 800 !important;
            color: #0b3873 !important;
            background: #f1f3f5 !important;
            padding: 8px !important;
            margin: -8px 8px -8px -8px !important;
        }

        .client-condition-table td:nth-child(1)::before { content: "법인 여부"; }
        .client-condition-table td:nth-child(2)::before { content: "할부 선납금"; }
        .client-condition-table td:nth-child(3)::before { content: "할부 금리"; }
        .client-condition-table td:nth-child(4)::before { content: "연 보험료"; }
        .client-condition-table td:nth-child(5)::before { content: "할부 잔존"; }
        .client-condition-table td:nth-child(6)::before { content: "렌트 잔존"; }
    }


    /* 실제 다크 테마에서만 적용되는 보정: 라이트 모드 영향 없음 */
    html.caprio-dark .common-info-box {
        background-color: #111821 !important;
        border-color: #2f3b4a !important;
        color: #f3f6fb !important;
    }

    html.caprio-dark .common-info-box div,
    html.caprio-dark .common-info-box b {
        color: #f3f6fb !important;
    }

    html.caprio-dark .common-info-box div[style*="color:#0b3873"],
    html.caprio-dark .common-info-box div[style*="color: #0b3873"] {
        color: #9fc7ff !important;
    }

    html.caprio-dark .common-table,
    html.caprio-dark .common-table tbody,
    html.caprio-dark .common-table tr {
        background-color: #0e141c !important;
        color: #f3f6fb !important;
    }

    html.caprio-dark .common-table th {
        background-color: #0b3873 !important;
        color: #ffffff !important;
        border-color: #354255 !important;
    }

    html.caprio-dark .common-table td {
        background-color: #0e141c !important;
        color: #f3f6fb !important;
        border-color: #354255 !important;
    }

    html.caprio-dark .common-table td.font-bold,
    html.caprio-dark .common-table td[style*="color:#111"],
    html.caprio-dark .common-table td[style*="color: #111"] {
        color: #ffffff !important;
    }

    html.caprio-dark .pure-table,
    html.caprio-dark .matrix-table {
        background-color: #0e141c !important;
        color: #f3f6fb !important;
        border-color: #354255 !important;
    }

    html.caprio-dark .pure-table th,
    html.caprio-dark .matrix-table th {
        background-color: #0b3873 !important;
        color: #ffffff !important;
        border-color: #46566d !important;
    }

    html.caprio-dark .pure-table td,
    html.caprio-dark .matrix-table td {
        background-color: #0e141c !important;
        color: #f3f6fb !important;
        border-color: #46566d !important;
    }

    html.caprio-dark .bg-light,
    html.caprio-dark tr.bg-light td {
        background-color: #151f2b !important;
        color: #f3f6fb !important;
    }

    html.caprio-dark .text-blue {
        color: #9fc7ff !important;
    }

    html.caprio-dark .matrix-table td.td-highlight,
    html.caprio-dark .matrix-table tr.td-highlight td {
        background-color: #173f1b !important;
        color: #d8ffd2 !important;
        font-weight: 900 !important;
    }

    html.caprio-dark .rent-highlight {
        background-color: #173f1b !important;
        color: #d8ffd2 !important;
        font-weight: 900 !important;
    }
    html.caprio-dark .lease-highlight {
        background-color: #2d1b4f !important;
        color: #e9d5ff !important;
        font-weight: 900 !important;
    }

    /* 할부·렌트·리스 비교표 - class 기반 다크모드 */
    html.caprio-dark .compare-cat{
        background:#144b96 !important;
        background-color:#144b96 !important;
        color:#ffffff !important;
        font-weight:900 !important;
    }

    html.caprio-dark .compare-item{
        background:#2b4461 !important;
        background-color:#2b4461 !important;
        color:#ffffff !important;
        font-weight:700 !important;
    }

    html.caprio-dark .compare-legal{
        background:#6d9a2e !important;
        background-color:#6d9a2e !important;
        color:#ffffff !important;
        font-weight:900 !important;
    }

    html.caprio-dark .compare-summary-table td:not(.compare-cat):not(.compare-item):not(.compare-legal):not([style*="background:#0b3873"]):not([style*="background: #0b3873"]):not([style*="background:#6b8e23"]):not([style*="background: #6b8e23"]):not([style*="background:#ddebf7"]):not([style*="background: #ddebf7"]) {
        background-color: #0e141c !important;
        color: #f3f6fb !important;
    }

    html.caprio-dark .guide-card {
        background-color: #111821 !important;
        border-color: #2f3b4a !important;
        color: #f3f6fb !important;
    }

    html.caprio-dark .guide-title {
        color: #9fc7ff !important;
    }

    html.caprio-dark .guide-copy,
    html.caprio-dark .guide-subtitle,
    html.caprio-dark .guide-list,
    html.caprio-dark .guide-list li,
    html.caprio-dark .reality-item,
    html.caprio-dark .reality-item b {
        color: #f3f6fb !important;
    }

    html.caprio-dark .reality-box {
        background-color: #151f2b !important;
        border-color: #344255 !important;
        color: #f3f6fb !important;
    }

    html.caprio-dark .reality-title {
        color: #ffffff !important;
    }

    html.caprio-dark .excel-header-gray {
        background-color: #243142 !important;
        color: #ffffff !important;
        border: 1px solid #46566d !important;
    }

    html.caprio-dark .excel-green {
        background-color: #20391f !important;
        color: #d8ffd2 !important;
        border-color: #4f7f46 !important;
    }

    html.caprio-dark .excel-red {
        background-color: #3b2323 !important;
        color: #ffd0d0 !important;
        border-color: #7a4040 !important;
    }

    html.caprio-dark span[style*="color:red"],
    html.caprio-dark span[style*="color: red"],
    html.caprio-dark div[style*="color:red"],
    html.caprio-dark div[style*="color: red"] {
        color: #ff7777 !important;
        white-space: nowrap !important;
    }


    .maturity-sale-label,
    .matrix-table td.maturity-sale-label,
    .matrix-table tr.maturity-section-start td.maturity-sale-label {
        color: #ef4444 !important;
        font-weight: 800 !important;
    }

    .maturity-sale-value,
    .matrix-table td.maturity-sale-value,
    .matrix-table tr.maturity-section-start td.maturity-sale-value {
        color: #ef4444 !important;
        font-weight: 400 !important;
    }

    .maturity-section-start td,
    .maturity-section-header td {
        border-top: 3px double #7b8794 !important;
    }

    .maturity-section-header td {
        background-color: #f8f9fa !important;
        color: #0b3873 !important;
        font-weight: 800 !important;
        text-align: center !important;
    }

    html.caprio-dark .maturity-sale-label,
    html.caprio-dark .matrix-table td.maturity-sale-label,
    html.caprio-dark .matrix-table tr.maturity-section-start td.maturity-sale-label {
        color: #ff6b6b !important;
        -webkit-text-fill-color: #ff6b6b !important;
        font-weight: 800 !important;
    }

    html.caprio-dark .maturity-sale-value,
    html.caprio-dark .matrix-table td.maturity-sale-value,
    html.caprio-dark .matrix-table tr.maturity-section-start td.maturity-sale-value {
        color: #ff6b6b !important;
        -webkit-text-fill-color: #ff6b6b !important;
        font-weight: 400 !important;
    }

    html.caprio-dark .maturity-section-start td,
    html.caprio-dark .maturity-section-header td {
        border-top: 3px double #7f8da3 !important;
    }

    html.caprio-dark .maturity-section-header td {
        background-color: #151f2b !important;
        color: #9fc7ff !important;
        font-weight: 800 !important;
    }

    html.caprio-dark .readonly-sidebar-value {
        background-color: #101722 !important;
        border: 1px solid #46566d !important;
        color: #f3f6fb !important;
    }

.rent-fixed-resale-label {
    color: var(--text-color) !important;
}

.rent-fixed-resale-value {
    background-color: var(--input-bg) !important;
    color: var(--text-color) !important;
    border: 1px solid var(--input-border) !important;
    padding: 9px 13px !important;
    border-radius: 8px !important;
    font-size: 16px !important;
    height: 38px !important;
    display: flex !important;
    align-items: center !important;
    box-sizing: border-box !important;
}
    

    @media (max-width: 768px) {
        html.caprio-dark .common-table td::before,
        html.caprio-dark .client-condition-table td::before {
            background-color: #1b2a3c !important;
            color: #9fc7ff !important;
        }

        /* 모바일 - 인수형 상단 간격 */
        .compare-card {
            margin-top: 18px !important;
        }
    }


    /* 다크모드 - 할부·렌트·리스 비교표 셀 클래스 기반 최종 보정 */
    html.caprio-dark .compare-summary-table .compare-cat {
        background:#0b3873 !important;
        background-color:#0b3873 !important;
    }

    html.caprio-dark .compare-summary-table .compare-item {
        background:#23364d !important;
        background-color:#23364d !important;
    }

    html.caprio-dark .compare-summary-table .compare-legal {
        background:#7fb52b !important;
        background-color:#7fb52b !important;
    }

    
    /* 렌트 견적 라벨 잘림 방지 */
    div[data-testid="stTextArea"] label {
        padding-top: 8px !important;
        min-height: 32px !important;
        overflow: visible !important;
    }

    div[data-testid="stTextArea"] label p {
        margin-top: 0 !important;
        line-height: 1.5 !important;
        overflow: visible !important;
    }

    /* 모바일 - 반납형/인수형 비교표 사이 간격 */
    .mobile-compare-gap {
        display: none;
    }

    @media (max-width: 768px) {
        .mobile-compare-gap {
            display: block;
            height: 34px;
        }

        /* 모바일 - 할부·렌트·리스 비교표 가로폭 보정 */
        .compare-summary-table {
            width: 100% !important;
            table-layout: fixed !important;
            font-size: 11px !important;
        }

        .compare-summary-table th,
        .compare-summary-table td {
            writing-mode: horizontal-tb !important;
            white-space: normal !important;
            word-break: keep-all !important;
            overflow-wrap: normal !important;
            line-height: 1.35 !important;
            padding: 6px 4px !important;
        }

        .compare-summary-table th:nth-child(1),
        .compare-summary-table td:nth-child(1) {
            width: 13% !important;
        }

        .compare-summary-table th:nth-child(2),
        .compare-summary-table td:nth-child(2) {
            width: 24% !important;
        }

        .compare-summary-table th:nth-child(3),
        .compare-summary-table td:nth-child(3),
        .compare-summary-table th:nth-child(4),
        .compare-summary-table td:nth-child(4),
        .compare-summary-table th:nth-child(5),
        .compare-summary-table td:nth-child(5) {
            width: 21% !important;
        }

        .compare-summary-table.compare-cols-2 {
            font-size: 13px !important;
        }

        .compare-summary-table.compare-cols-2 th:nth-child(1),
        .compare-summary-table.compare-cols-2 td:nth-child(1) {
            width: 15% !important;
        }

        .compare-summary-table.compare-cols-2 th:nth-child(2),
        .compare-summary-table.compare-cols-2 td:nth-child(2) {
            width: 29% !important;
        }

        .compare-summary-table.compare-cols-2 th:nth-child(3),
        .compare-summary-table.compare-cols-2 td:nth-child(3),
        .compare-summary-table.compare-cols-2 th:nth-child(4),
        .compare-summary-table.compare-cols-2 td:nth-child(4) {
            width: 28% !important;
        }
    }
    


    /* 카프리오 고정 브랜드 헤더 / 기본 Streamlit 메뉴 숨김 */
    header[data-testid="stHeader"],
    div[data-testid="stToolbar"],
    div[data-testid="stDecoration"],
    div[data-testid="stStatusWidget"],
    #MainMenu,
    footer {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
    }

    .stApp {
        padding-top: 0 !important;
    }

    div.block-container {
        padding-top: 5.6rem !important;
    }

    #caprio-brand-header {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        z-index: 2147483000;
        height: 72px;
        background: rgba(255,255,255,0.94);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border-bottom: 1px solid #e6edf7;
        box-shadow: 0 4px 18px rgba(15, 45, 90, 0.08);
        display: flex;
        align-items: center;
        justify-content: center;
        pointer-events: auto;
    }

    #caprio-brand-inner {
        width: min(1180px, 100%);
        height: 100%;
        display: flex;
        align-items: center;
        padding: 0 30px;
        box-sizing: border-box;
        gap: 18px;
    }

    #caprio-brand-logo {
        width: 178px;
        height: 44px;
        flex: 0 0 auto;
        background-image: url("data:image/png;base64,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�my��$z{-���jם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") !important;
    }

    html.caprio-dark #caprio-brand-divider {
        background: #2e4261 !important;
    }

    html.caprio-dark #caprio-brand-slogan {
        color: #f3f6fb !important;
    }

    html.caprio-dark #caprio-brand-slogan .free-word {
        color: #4aa3ff !important;
    }

    html.caprio-dark #caprio-theme-toggle {
        background: linear-gradient(180deg, #13243d, #0a1728) !important;
        color: #d9ecff !important;
        border-color: #34577f !important;
        box-shadow: 0 5px 14px rgba(0,0,0,0.25) !important;
    }

    html.caprio-dark .stApp {
        background-color: #0b1018 !important;
        color: #f3f6fb !important;
    }

    html:not(.caprio-dark) .stApp {
        background-color: #ffffff !important;
        color: #111827 !important;
    }

    @media (max-width: 768px) {
        div.block-container {
            padding-top: 5.25rem !important;
        }

        #caprio-brand-header {
            height: 66px;
        }

        #caprio-brand-inner {
            padding: 0 16px;
            gap: 12px;
        }

        #caprio-brand-logo {
            width: 116px;
            height: 36px;
        }

        #caprio-brand-divider {
            height: 30px;
        }

        #caprio-brand-slogan {
            font-size: 16px;
            letter-spacing: -0.04em;
            min-width: 0;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        #caprio-theme-toggle {
            min-width: 74px;
            height: 34px;
            padding: 0 10px;
            font-size: 12px;
        }
    }

    /* 모바일 공통조건 표 */
    .vehicle-table-mobile {
        display: none;
    }

    .vehicle-table-mobile {
        width: 100%;
        border-collapse: collapse;
        table-layout: fixed;
        text-align: center;
        font-size: 12px;
        overflow: hidden;
    }

    .vehicle-table-mobile th,
    .vehicle-table-mobile td {
        border: 1px solid #d9e3ef;
        padding: 8px 6px;
        word-break: keep-all;
        overflow-wrap: break-word;
        vertical-align: middle;
    }

    .vehicle-table-mobile .vehicle-primary-head th {
        background: #0b4a90;
        color: #ffffff;
        font-weight: 900;
        border-radius: 0 !important;
    }

    .vehicle-table-mobile .vehicle-secondary-head th {
        background: #dbeeff;
        color: #0b3873;
        font-weight: 900;
        border-radius: 0 !important;
    }

    .vehicle-table-mobile td {
        background: #ffffff;
        color: #0f172a;
        font-weight: 750;
    }

    html.caprio-dark .vehicle-table-mobile th,
    html.caprio-dark .vehicle-table-mobile td {
        border-color: #46566d !important;
    }

    html.caprio-dark .vehicle-table-mobile .vehicle-primary-head th {
        background: #0b3873 !important;
        color: #ffffff !important;
    }

    html.caprio-dark .vehicle-table-mobile .vehicle-secondary-head th {
        background: #1b2f4a !important;
        color: #9fc7ff !important;
    }

    html.caprio-dark .vehicle-table-mobile td {
        background: #0e141c !important;
        color: #f3f6fb !important;
    }

    @media (max-width: 768px) {
        .common-table-desktop {
            display: none !important;
        }

        .vehicle-table-mobile {
            display: table !important;
        }

        .common-info-box {
            padding: 14px !important;
            border-radius: 8px !important;
            box-shadow: 0 6px 18px rgba(9, 42, 85, 0.06);
        }
    }

    /* 헤더형 버튼/섹션 타이틀 톤 */
    .excel-header-gray {
        background: linear-gradient(180deg, #f3f9ff 0%, #e7f2ff 100%) !important;
        color: #0b3873 !important;
        border: 1px solid #cfe3ff !important;
        box-shadow: 0 8px 18px rgba(21, 91, 170, 0.10) !important;
    }

    html.caprio-dark .excel-header-gray {
        background: linear-gradient(180deg, #223247 0%, #162235 100%) !important;
        color: #ffffff !important;
        border: 1px solid #46566d !important;
        box-shadow: 0 8px 20px rgba(0,0,0,0.22) !important;
    }

    .excel-header-blue {
        background: linear-gradient(90deg, #0d4a91 0%, #082f63 50%, #0d4a91 100%) !important;
        color: #ffffff !important;
        box-shadow: 0 7px 16px rgba(3, 43, 94, 0.18) !important;
        border: 1px solid #0e4b94 !important;
    }

    html.caprio-dark .excel-header-blue {
        background: linear-gradient(90deg, #123f7c 0%, #071d39 50%, #123f7c 100%) !important;
        color: #ffffff !important;
        border-color: #294b75 !important;
        box-shadow: 0 7px 18px rgba(0,0,0,0.28) !important;
    }

    /* 서로 다른 큰 섹션 사이 간격 통일 */
    .section-spacer-soft {
        height: 28px !important;
        line-height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
    }

    @media (max-width: 768px) {
        .section-spacer-soft {
            height: 34px !important;
            line-height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
        }

        .excel-header-gray {
            margin-top: 0 !important;
        }
    }

    /* 하단 안내/저작권 */
    .caprio-footer-note {
        margin-top: 34px;
        padding: 16px 6px 4px;
        border-top: 1px solid #e2e8f0;
        color: #8a95a8;
        font-size: 10px;
        line-height: 1.55;
        text-align: center;
        letter-spacing: -0.02em;
    }

    .caprio-footer-note .caprio-footer-guide {
        margin-bottom: 8px;
    }

    html.caprio-dark .caprio-footer-note {
        border-top-color: #243142 !important;
        color: #68758a !important;
    }



    /* 최종 보정 - 로고/툴바/공통조건/모바일 비교표 */
    #caprio-brand-logo {
        width: 132px !important;
        height: 42px !important;
        background-size: contain !important;
        background-repeat: no-repeat !important;
        background-position: center !important;
        filter: none !important;
        box-shadow: none !important;
    }

    #caprio-brand-slogan {
        font-size: 18px !important;
        font-weight: 900 !important;
        white-space: nowrap !important;
    }

    #caprio-theme-toggle {
        min-width: 62px !important;
        height: 30px !important;
        padding: 0 9px !important;
        font-size: 12px !important;
        flex: 0 0 auto !important;
    }

    @media (max-width: 768px) {
        #caprio-brand-inner {
            justify-content: flex-start !important;
            padding-left: 12px !important;
            padding-right: 10px !important;
            gap: 10px !important;
        }

        #caprio-brand-logo {
            width: 108px !important;
            height: 34px !important;
            flex: 0 0 108px !important;
        }

        #caprio-brand-divider {
            height: 28px !important;
            flex: 0 0 1px !important;
        }

        #caprio-brand-slogan {
            font-size: 15px !important;
            flex: 1 1 auto !important;
            min-width: 0 !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
        }

        #caprio-theme-toggle {
            min-width: 58px !important;
            height: 28px !important;
            padding: 0 8px !important;
            font-size: 11px !important;
        }

        .compare-summary-title {
            width: 100% !important;
            display: block !important;
            box-sizing: border-box !important;
        }
    }

    .common-table-desktop { display: none !important; }
    .vehicle-table-mobile-primary,
    .vehicle-table-mobile-secondary { display: table; }

    .vehicle-table-mobile-primary,
    .vehicle-table-mobile-secondary {
        width: 100%;
        border-collapse: collapse;
        table-layout: fixed;
        text-align: center;
        font-size: 12px;
    }

    .vehicle-table-mobile-primary th,
    .vehicle-table-mobile-primary td,
    .vehicle-table-mobile-secondary th,
    .vehicle-table-mobile-secondary td {
        border: 1px solid #d9e3ef;
        padding: 8px 6px;
        word-break: keep-all;
        overflow-wrap: break-word;
        vertical-align: middle;
        border-radius: 0 !important;
    }

    .vehicle-table-mobile-primary th {
        background: #0b4a90;
        color: #ffffff;
        font-weight: 900;
    }

    .vehicle-table-mobile-secondary th {
        background: #dbeeff;
        color: #0b3873;
        font-weight: 900;
    }

    .vehicle-table-mobile-primary td,
    .vehicle-table-mobile-secondary td {
        background: #ffffff;
        color: #0f172a;
        font-weight: 750;
    }

    html.caprio-dark .vehicle-table-mobile-primary th,
    html.caprio-dark .vehicle-table-mobile-primary td,
    html.caprio-dark .vehicle-table-mobile-secondary th,
    html.caprio-dark .vehicle-table-mobile-secondary td {
        border-color: #46566d !important;
    }

    html.caprio-dark .vehicle-table-mobile-primary th {
        background: #0b3873 !important;
        color: #ffffff !important;
    }

    html.caprio-dark .vehicle-table-mobile-secondary th {
        background: #1b2f4a !important;
        color: #9fc7ff !important;
    }

    html.caprio-dark .vehicle-table-mobile-primary td,
    html.caprio-dark .vehicle-table-mobile-secondary td {
        background: #0e141c !important;
        color: #f3f6fb !important;
    }

    @media (max-width: 768px) {
        .common-table-desktop { display: none !important; }
        .vehicle-table-mobile-primary,
        .vehicle-table-mobile-secondary { display: table !important; }
        .vehicle-table-mobile-secondary { margin-top: -1px !important; }
    }

    /* Streamlit Cloud/하단 플로팅 요소 숨김 보강 */
    #MainMenu, footer,
    div[data-testid="stToolbar"],
    div[data-testid="stDecoration"],
    div[data-testid="stStatusWidget"],
    div[data-testid="stDeployButton"],
    div[data-testid="stActionButton"],
    button[title*="Fork"], button[title*="GitHub"], button[title*="Share"], button[title*="Edit"], button[title*="Rerun"],
    button[aria-label*="Fork"], button[aria-label*="GitHub"], button[aria-label*="Share"], button[aria-label*="Edit"], button[aria-label*="Rerun"],
    a[href*="github.com"], a[href*="streamlit.io"] {
        display: none !important;
        visibility: hidden !important;
        pointer-events: none !important;
    }


    /* [PATCH ONLY] 로고 원본형/화이트모드 입력 보정/플로팅 요소 숨김 보강 */
    #caprio-brand-logo {
        width: 136px !important;
        height: 38px !important;
        flex: 0 0 136px !important;
        background-image: url("data:image/png;base64,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") !important;
        background-size: contain !important;
        background-repeat: no-repeat !important;
        background-position: left center !important;
        filter: none !important;
        box-shadow: none !important;
        text-shadow: none !important;
        transform: none !important;
    }

    html.caprio-dark #caprio-brand-logo {
        background-image: url("data:image/png;base64,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") !important;
        filter: none !important;
        box-shadow: none !important;
        text-shadow: none !important;
    }

    @media (max-width: 768px) {
        #caprio-brand-inner {
            padding-left: 10px !important;
            padding-right: 8px !important;
            gap: 10px !important;
        }

        #caprio-brand-logo {
            width: 106px !important;
            height: 32px !important;
            flex: 0 0 106px !important;
            background-position: left center !important;
        }

        #caprio-brand-slogan {
            font-size: 15px !important;
            min-width: 0 !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
        }
    }

    html.caprio-light [data-testid="stSidebar"],
    html:not(.caprio-dark) [data-testid="stSidebar"] {
        background-color: #ffffff !important;
        color: #111827 !important;
    }

    html.caprio-light [data-testid="stSidebar"] *,
    html:not(.caprio-dark) [data-testid="stSidebar"] * {
        color: inherit;
    }

    html.caprio-light input,
    html.caprio-light textarea,
    html.caprio-light select,
    html.caprio-light [data-baseweb="input"] input,
    html.caprio-light [data-baseweb="textarea"] textarea,
    html.caprio-light [data-baseweb="select"] > div,
    html:not(.caprio-dark) input,
    html:not(.caprio-dark) textarea,
    html:not(.caprio-dark) select,
    html:not(.caprio-dark) [data-baseweb="input"] input,
    html:not(.caprio-dark) [data-baseweb="textarea"] textarea,
    html:not(.caprio-dark) [data-baseweb="select"] > div {
        background-color: #ffffff !important;
        color: #111827 !important;
        border-color: #d8dee8 !important;
        -webkit-text-fill-color: #111827 !important;
    }

    html.caprio-light label,
    html.caprio-light [data-testid="stMarkdownContainer"],
    html:not(.caprio-dark) label,
    html:not(.caprio-dark) [data-testid="stMarkdownContainer"] {
        color: #111827 !important;
    }

    div[data-testid="stDecoration"],
    div[data-testid="stStatusWidget"],
    div[data-testid="stToolbar"],
    header[data-testid="stHeader"],
    #MainMenu,
    footer {
        display: none !important;
        visibility: hidden !important;
        pointer-events: none !important;
        width: 0 !important;
        height: 0 !important;
        overflow: hidden !important;
    }


    /* [PATCH] 영업자 화면 테마 보정: PC 화이트 버튼 / MO 다크 라벨·적용 버튼 */
    html.caprio-light [data-testid="stSidebar"] div[data-testid="stNumberInput"] button,
    html:not(.caprio-dark) [data-testid="stSidebar"] div[data-testid="stNumberInput"] button,
    html.caprio-light [data-testid="stSidebar"] div[data-testid="stButton"] button,
    html:not(.caprio-dark) [data-testid="stSidebar"] div[data-testid="stButton"] button {
        background-color: #ffffff !important;
        color: #111827 !important;
        border: 1px solid #d8dee8 !important;
        box-shadow: none !important;
        -webkit-text-fill-color: #111827 !important;
    }

    html.caprio-light [data-testid="stSidebar"] div[data-testid="stNumberInput"] button svg,
    html:not(.caprio-dark) [data-testid="stSidebar"] div[data-testid="stNumberInput"] button svg,
    html.caprio-light [data-testid="stSidebar"] div[data-testid="stButton"] button svg,
    html:not(.caprio-dark) [data-testid="stSidebar"] div[data-testid="stButton"] button svg {
        color: #111827 !important;
        fill: #111827 !important;
    }

    html.caprio-light div[data-testid="stFormSubmitButton"] button,
    html:not(.caprio-dark) div[data-testid="stFormSubmitButton"] button {
        background-color: #ffffff !important;
        color: #111827 !important;
        border: 1px solid #d8dee8 !important;
        box-shadow: none !important;
        -webkit-text-fill-color: #111827 !important;
    }

    /* [PATCH] 화이트모드 사이드바 입력/구분선 시인성 보완 */
    html.caprio-light [data-testid="stSidebar"] input,
    html.caprio-light [data-testid="stSidebar"] textarea,
    html.caprio-light [data-testid="stSidebar"] select,
    html.caprio-light [data-testid="stSidebar"] div[data-baseweb="input"],
    html.caprio-light [data-testid="stSidebar"] div[data-baseweb="input"] > div,
    html.caprio-light [data-testid="stSidebar"] div[data-baseweb="base-input"],
    html.caprio-light [data-testid="stSidebar"] div[data-testid="stTextInput"] input,
    html.caprio-light [data-testid="stSidebar"] div[data-testid="stNumberInput"] input,
    html.caprio-light [data-testid="stSidebar"] div[data-testid="stNumberInput"] > div,
    html.caprio-light [data-testid="stSidebar"] div[data-testid="stNumberInput"] > div > div,
    html:not(.caprio-dark) [data-testid="stSidebar"] input,
    html:not(.caprio-dark) [data-testid="stSidebar"] textarea,
    html:not(.caprio-dark) [data-testid="stSidebar"] select,
    html:not(.caprio-dark) [data-testid="stSidebar"] div[data-baseweb="input"],
    html:not(.caprio-dark) [data-testid="stSidebar"] div[data-baseweb="input"] > div,
    html:not(.caprio-dark) [data-testid="stSidebar"] div[data-baseweb="base-input"],
    html:not(.caprio-dark) [data-testid="stSidebar"] div[data-testid="stTextInput"] input,
    html:not(.caprio-dark) [data-testid="stSidebar"] div[data-testid="stNumberInput"] input,
    html:not(.caprio-dark) [data-testid="stSidebar"] div[data-testid="stNumberInput"] > div,
    html:not(.caprio-dark) [data-testid="stSidebar"] div[data-testid="stNumberInput"] > div > div {
        border-color: #94a3b8 !important;
        outline-color: #94a3b8 !important;
        box-shadow: none !important;
    }

    html.caprio-light [data-testid="stSidebar"] div[data-testid="stNumberInput"] button,
    html:not(.caprio-dark) [data-testid="stSidebar"] div[data-testid="stNumberInput"] button {
        border-color: #94a3b8 !important;
    }

    html.caprio-light [data-testid="stSidebar"] hr,
    html:not(.caprio-dark) [data-testid="stSidebar"] hr {
        border-color: #cbd5e1 !important;
        background-color: #cbd5e1 !important;
        opacity: 1 !important;
    }

    html.caprio-light div[data-baseweb="tooltip"],
    html:not(.caprio-dark) div[data-baseweb="tooltip"] {
        background-color: #0b0f17 !important;
        color: #ffffff !important;
        border-radius: 6px !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.25) !important;
    }

    html.caprio-light div[data-baseweb="tooltip"] *,
    html:not(.caprio-dark) div[data-baseweb="tooltip"] * {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }

    html.caprio-light div[data-testid="stFormSubmitButton"] button p,
    html:not(.caprio-dark) div[data-testid="stFormSubmitButton"] button p {
        color: #111827 !important;
        -webkit-text-fill-color: #111827 !important;
    }



    /* [PATCH] 공유 선택/견적 이력 화이트모드 색상 보정 */
    html.caprio-light .common-info-box div[style*="color:#0b3873"],
    html:not(.caprio-dark) .common-info-box div[style*="color:#0b3873"] {
        color: #0b3873 !important;
    }
    html.caprio-light div[data-testid="stButton"] button,
    html:not(.caprio-dark) div[data-testid="stButton"] button {
        background-color: #ffffff !important;
        color: #111827 !important;
        border: 1px solid #d8dee8 !important;
        box-shadow: none !important;
        -webkit-text-fill-color: #111827 !important;
    }
    html.caprio-light div[data-testid="stButton"] button p,
    html:not(.caprio-dark) div[data-testid="stButton"] button p {
        color: #111827 !important;
        -webkit-text-fill-color: #111827 !important;
    }

    html.caprio-dark div[data-testid="stTextArea"] label,
    html.caprio-dark div[data-testid="stTextArea"] label p,
    html.caprio-dark div[data-testid="stTextInput"] label,
    html.caprio-dark div[data-testid="stTextInput"] label p,
    html.caprio-dark div[data-testid="stSelectbox"] label,
    html.caprio-dark div[data-testid="stSelectbox"] label p,
    html.caprio-dark div[data-testid="stNumberInput"] label,
    html.caprio-dark div[data-testid="stNumberInput"] label p {
        color: #f3f6fb !important;
        -webkit-text-fill-color: #f3f6fb !important;
        opacity: 1 !important;
    }

    html.caprio-dark div[data-testid="stFormSubmitButton"] button {
        background-color: #0b4a90 !important;
        color: #ffffff !important;
        border: 1px solid #2f6fb8 !important;
        box-shadow: none !important;
        -webkit-text-fill-color: #ffffff !important;
    }

    html.caprio-dark div[data-testid="stFormSubmitButton"] button p {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }


    /* [PATCH] 화이트모드 흐린 선 전체 보강: 입력칸/버튼/카드/구분선만 진하게 */
    html.caprio-light,
    html:not(.caprio-dark) {
        --caprio-light-border-strong: #64748b;
        --caprio-light-border-mid: #94a3b8;
        --caprio-light-border-soft: #94a3b8;
    }

    /* 전역 입력 박스: textarea 포함 */
    html.caprio-light div[data-testid="stTextArea"] textarea,
    html:not(.caprio-dark) div[data-testid="stTextArea"] textarea,
    html.caprio-light div[data-testid="stTextInput"] input,
    html:not(.caprio-dark) div[data-testid="stTextInput"] input,
    html.caprio-light div[data-testid="stNumberInput"] input,
    html:not(.caprio-dark) div[data-testid="stNumberInput"] input,
    html.caprio-light input,
    html:not(.caprio-dark) input,
    html.caprio-light textarea,
    html:not(.caprio-dark) textarea,
    html.caprio-light select,
    html:not(.caprio-dark) select,
    html.caprio-light div[data-baseweb="input"],
    html:not(.caprio-dark) div[data-baseweb="input"],
    html.caprio-light div[data-baseweb="input"] > div,
    html:not(.caprio-dark) div[data-baseweb="input"] > div,
    html.caprio-light div[data-baseweb="textarea"],
    html:not(.caprio-dark) div[data-baseweb="textarea"],
    html.caprio-light div[data-baseweb="textarea"] > div,
    html:not(.caprio-dark) div[data-baseweb="textarea"] > div,
    html.caprio-light div[data-baseweb="select"] > div,
    html:not(.caprio-dark) div[data-baseweb="select"] > div {
        border-color: var(--caprio-light-border-strong) !important;
        outline-color: var(--caprio-light-border-strong) !important;
        box-shadow: none !important;
    }

    /* 사이드바 입력/숫자 +/- 버튼: 조금 더 진하게 */
    html.caprio-light [data-testid="stSidebar"] div[data-testid="stTextInput"] input,
    html:not(.caprio-dark) [data-testid="stSidebar"] div[data-testid="stTextInput"] input,
    html.caprio-light [data-testid="stSidebar"] div[data-testid="stNumberInput"] input,
    html:not(.caprio-dark) [data-testid="stSidebar"] div[data-testid="stNumberInput"] input,
    html.caprio-light [data-testid="stSidebar"] div[data-testid="stNumberInput"] > div,
    html:not(.caprio-dark) [data-testid="stSidebar"] div[data-testid="stNumberInput"] > div,
    html.caprio-light [data-testid="stSidebar"] div[data-testid="stNumberInput"] > div > div,
    html:not(.caprio-dark) [data-testid="stSidebar"] div[data-testid="stNumberInput"] > div > div,
    html.caprio-light [data-testid="stSidebar"] div[data-baseweb="input"],
    html:not(.caprio-dark) [data-testid="stSidebar"] div[data-baseweb="input"],
    html.caprio-light [data-testid="stSidebar"] div[data-baseweb="input"] > div,
    html:not(.caprio-dark) [data-testid="stSidebar"] div[data-baseweb="input"] > div {
        border-color: #64748b !important;
        outline-color: #64748b !important;
    }

    html.caprio-light [data-testid="stSidebar"] div[data-testid="stNumberInput"] button,
    html:not(.caprio-dark) [data-testid="stSidebar"] div[data-testid="stNumberInput"] button {
        border-color: #64748b !important;
        color: #111827 !important;
        -webkit-text-fill-color: #111827 !important;
    }

    /* 버튼/이력 버튼/공유 선택 버튼: 흐린 테두리 보강 */
    html.caprio-light div[data-testid="stButton"] button,
    html:not(.caprio-dark) div[data-testid="stButton"] button,
    html.caprio-light div[data-testid="stFormSubmitButton"] button,
    html:not(.caprio-dark) div[data-testid="stFormSubmitButton"] button,
    html.caprio-light .share-selector-anchor + div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button,
    html:not(.caprio-dark) .share-selector-anchor + div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button {
        border-color: var(--caprio-light-border-strong) !important;
        box-shadow: none !important;
    }

    /* 고객명/저장영역/텍스트영역 주변 카드와 구분선 */
    html.caprio-light .quote-history-panel,
    html:not(.caprio-dark) .quote-history-panel,
    html.caprio-light .common-info-box,
    html:not(.caprio-dark) .common-info-box,
    html.caprio-light .capture-box,
    html:not(.caprio-dark) .capture-box,
    html.caprio-light div[data-testid="stForm"],
    html:not(.caprio-dark) div[data-testid="stForm"] {
        border-color: var(--caprio-light-border-mid) !important;
    }

    html.caprio-light .share-group-divider,
    html:not(.caprio-dark) .share-group-divider,
    html.caprio-light hr,
    html:not(.caprio-dark) hr {
        background-color: var(--caprio-light-border-soft) !important;
        border-color: var(--caprio-light-border-soft) !important;
        opacity: 1 !important;
    }


    /* [v11] 화이트모드 사이드바 구분선만 진하게 보정 - 기존 선 색상값만 보강 */
    html.caprio-light [data-testid="stSidebar"],
    html:not(.caprio-dark) [data-testid="stSidebar"] {
        border-right-color:#94a3b8 !important;
    }
    html.caprio-light [data-testid="stSidebar"] hr,
    html:not(.caprio-dark) [data-testid="stSidebar"] hr,
    html.caprio-light [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] hr,
    html:not(.caprio-dark) [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] hr {
        background-color:#94a3b8 !important;
        border-color:#94a3b8 !important;
        opacity:1 !important;
    }

    /* 테이블 선도 화이트에서 너무 흐리지 않게만 보강 */
    html.caprio-light .common-table th,
    html.caprio-light .common-table td,
    html.caprio-light .pure-table th,
    html.caprio-light .pure-table td,
    html.caprio-light .matrix-table th,
    html.caprio-light .matrix-table td,
    html:not(.caprio-dark) .common-table th,
    html:not(.caprio-dark) .common-table td,
    html:not(.caprio-dark) .pure-table th,
    html:not(.caprio-dark) .pure-table td,
    html:not(.caprio-dark) .matrix-table th,
    html:not(.caprio-dark) .matrix-table td {
        border-color: #cbd5e1 !important;
    }


    
    /* [PATCH] 다크모드 폼 입력칸/셀렉트 통일 (PC/MO) */
    html.caprio-dark div[data-testid="stForm"] {
        border: 1px solid #46566d !important;
        border-radius: 8px !important;
        background-color: transparent !important;
    }

    html.caprio-dark div[data-testid="stForm"] div[data-baseweb="input"],
    html.caprio-dark div[data-testid="stForm"] input,
    html.caprio-dark div[data-testid="stForm"] textarea,
    html.caprio-dark div[data-testid="stForm"] div[data-testid="stTextArea"] textarea,
    html.caprio-dark div[data-testid="stForm"] div[data-testid="stTextInput"] input,
    html.caprio-dark div[data-testid="stForm"] div[data-baseweb="select"] > div {
        background-color: #232631 !important;
        color: #f3f6fb !important;
        -webkit-text-fill-color: #f3f6fb !important;
        border: 1px solid #46566d !important;
        box-shadow: none !important;
    }

    html.caprio-dark div[data-testid="stForm"] div[data-baseweb="select"] svg {
        color: #f3f6fb !important;
        fill: #f3f6fb !important;
    }


    /* [PATCH] 다크모드 전역 입력/버튼 색상 보정: 폼 밖 영역 포함 */
    html.caprio-dark [data-testid="stSidebar"] {
        background-color: #111827 !important;
        color: #f3f6fb !important;
        border-right: 1px solid #26364c !important;
    }

    html.caprio-dark [data-testid="stSidebar"] * {
        color: inherit;
    }

    html.caprio-dark input,
    html.caprio-dark textarea,
    html.caprio-dark select,
    html.caprio-dark div[data-baseweb="input"],
    html.caprio-dark div[data-baseweb="input"] > div,
    html.caprio-dark div[data-baseweb="input"] input,
    html.caprio-dark div[data-baseweb="textarea"],
    html.caprio-dark div[data-baseweb="textarea"] textarea,
    html.caprio-dark div[data-baseweb="select"] > div {
        background-color: #232631 !important;
        color: #f3f6fb !important;
        -webkit-text-fill-color: #f3f6fb !important;
        border-color: #46566d !important;
        box-shadow: none !important;
    }

    html.caprio-dark input::placeholder,
    html.caprio-dark textarea::placeholder {
        color: #9aa7bb !important;
        -webkit-text-fill-color: #9aa7bb !important;
        opacity: 1 !important;
    }

    html.caprio-dark div[data-baseweb="select"] svg,
    html.caprio-dark div[data-baseweb="input"] svg {
        color: #f3f6fb !important;
        fill: #f3f6fb !important;
    }

    html.caprio-dark div[data-testid="stButton"] button,
    html.caprio-dark div[data-testid="stNumberInput"] button {
        background-color: #131a24 !important;
        color: #f3f6fb !important;
        border: 1px solid #46566d !important;
        box-shadow: none !important;
        -webkit-text-fill-color: #f3f6fb !important;
    }

    html.caprio-dark div[data-testid="stButton"] button p,
    html.caprio-dark div[data-testid="stNumberInput"] button p {
        color: #f3f6fb !important;
        -webkit-text-fill-color: #f3f6fb !important;
    }

    html.caprio-dark div[data-testid="stButton"] button svg,
    html.caprio-dark div[data-testid="stNumberInput"] button svg {
        color: #f3f6fb !important;
        fill: #f3f6fb !important;
    }

    /* 다크모드: number_input 내부 테두리/체크박스 텍스트 통합 보정 */
    html.caprio-dark [data-testid="stSidebar"] div[data-testid="stNumberInput"] > div,
    html.caprio-dark [data-testid="stSidebar"] div[data-testid="stNumberInput"] > div > div,
    html.caprio-dark [data-testid="stSidebar"] div[data-testid="stNumberInput"] div[data-baseweb="input"],
    html.caprio-dark [data-testid="stSidebar"] div[data-testid="stNumberInput"] div[data-baseweb="input"] > div,
    html.caprio-dark [data-testid="stSidebar"] div[data-testid="stNumberInput"] div[data-baseweb="base-input"],
    html.caprio-dark [data-testid="stSidebar"] div[data-testid="stNumberInput"] input,
    html.caprio-dark [data-testid="stSidebar"] div[data-testid="stNumberInput"] button,
    html.caprio-dark [data-testid="stSidebar"] div[data-testid="stNumberInput"] div[role="button"] {
        background-color: #232631 !important;
        color: #f3f6fb !important;
        -webkit-text-fill-color: #f3f6fb !important;
        border-color: #46566d !important;
        box-shadow: none !important;
        outline-color: #46566d !important;
    }

    html.caprio-dark div[data-testid="stCheckbox"],
    html.caprio-dark div[data-testid="stCheckbox"] *,
    html.caprio-dark div[data-testid="stCheckbox"] label,
    html.caprio-dark div[data-testid="stCheckbox"] label *,
    html.caprio-dark div[data-testid="stCheckbox"] [data-testid="stMarkdownContainer"],
    html.caprio-dark div[data-testid="stCheckbox"] [data-testid="stMarkdownContainer"] *,
    html.caprio-dark div[data-testid="stCheckbox"] [data-testid="stMarkdownContainer"] p,
    html.caprio-dark div[data-testid="stCheckbox"] [aria-disabled="true"],
    html.caprio-dark div[data-testid="stCheckbox"] [aria-disabled="true"] *,
    html.caprio-dark div[data-testid="stCheckbox"] [disabled],
    html.caprio-dark div[data-testid="stCheckbox"] [disabled] * {
        color: #f3f6fb !important;
        -webkit-text-fill-color: #f3f6fb !important;
        opacity: 1 !important;
        filter: none !important;
    }

    html.caprio-dark div[data-testid="stButton"] button:disabled,
    html.caprio-dark div[data-testid="stNumberInput"] button:disabled {
        background-color: #1a2230 !important;
        color: #8b98aa !important;
        border-color: #344256 !important;
        -webkit-text-fill-color: #8b98aa !important;
    }

    html.caprio-dark div[data-testid="stButton"] button:disabled p,
    html.caprio-dark div[data-testid="stNumberInput"] button:disabled p {
        color: #8b98aa !important;
        -webkit-text-fill-color: #8b98aa !important;
    }
    html.caprio-dark .share-selector-anchor + div[data-testid="stHorizontalBlock"],
    html.caprio-dark .share-selector-anchor + div[data-testid="stHorizontalBlock"] *,
    html.caprio-dark .share-selector-anchor + div[data-testid="stHorizontalBlock"] div[data-testid="stCheckbox"],
    html.caprio-dark .share-selector-anchor + div[data-testid="stHorizontalBlock"] div[data-testid="stCheckbox"] *,
    html.caprio-dark .share-selector-anchor + div[data-testid="stHorizontalBlock"] div[data-testid="stCheckbox"] label,
    html.caprio-dark .share-selector-anchor + div[data-testid="stHorizontalBlock"] div[data-testid="stCheckbox"] label *,
    html.caprio-dark .share-selector-anchor + div[data-testid="stHorizontalBlock"] div[data-testid="stCheckbox"] [data-testid="stMarkdownContainer"],
    html.caprio-dark .share-selector-anchor + div[data-testid="stHorizontalBlock"] div[data-testid="stCheckbox"] [data-testid="stMarkdownContainer"] *,
    html.caprio-dark .share-selector-anchor + div[data-testid="stHorizontalBlock"] div[data-testid="stCheckbox"] [data-testid="stMarkdownContainer"] p {
        color: #f3f6fb !important;
        -webkit-text-fill-color: #f3f6fb !important;
        opacity: 1 !important;
        filter: none !important;
    }

    html.caprio-dark .share-selector-anchor + div[data-testid="stHorizontalBlock"] div[data-testid="stCheckbox"] label:has(input:disabled),
    html.caprio-dark .share-selector-anchor + div[data-testid="stHorizontalBlock"] div[data-testid="stCheckbox"] label:has(input:disabled) *,
    html.caprio-dark .share-selector-anchor + div[data-testid="stHorizontalBlock"] div[data-testid="stCheckbox"] input:disabled ~ * {
        color: #f3f6fb !important;
        -webkit-text-fill-color: #f3f6fb !important;
        opacity: 1 !important;
        filter: none !important;
    }

    

    /* [PATCH] MO 섹션 간격 통일: 섹션별 중복 여백 제거 + 단일 간격 적용 */
    @media (max-width: 768px) {
        .excel-header-blue,
        .excel-header-gray {
            margin-top: 0 !important;
            margin-bottom: 8px !important;
        }

        .mobile-compare-gap {
            height: 34px !important;
            line-height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
        }

        .compare-card {
            margin-top: 12px !important;
        }

        .common-info-box,
        .capture-box {
            margin-bottom: 12px !important;
        }

        .matrix-table,
        .pure-table,
        .compare-summary-table {
            margin-bottom: 0 !important;
        }

        .guide-wrap {
            margin-top: 8px !important;
        }
    }


    /* [FINAL] MO 출력 섹션 간격 통일: 큰 섹션 사이 전용 간격 */
    .output-section-gap {
        display: none;
        height: 0;
        line-height: 0;
        margin: 0;
        padding: 0;
    }

    @media (max-width: 768px) {
        .output-section-gap {
            display: block !important;
            height: 34px !important;
            min-height: 34px !important;
            line-height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
        }

        .mobile-compare-gap {
            display: block !important;
            height: 34px !important;
            min-height: 34px !important;
            line-height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
        }

        .excel-header-blue,
        .excel-header-gray {
            margin-top: 0 !important;
            margin-bottom: 8px !important;
        }

        .matrix-table,
        .pure-table,
        .compare-summary-table {
            margin-bottom: 0 !important;
        }
    }



    /* [FINAL] MO 공유 체크: 대분류 아래 소항목은 한 줄 흐름으로 압축 */
    @media (max-width: 768px) {
        .share-selector-anchor + div[data-testid="stHorizontalBlock"] div[data-testid="stCheckbox"] {
            margin-bottom: 8px !important;
        }

        .share-selector-anchor + div[data-testid="stHorizontalBlock"] > div {
            border-bottom: 1px solid #d6e0eb !important;
            padding-bottom: 10px !important;
            margin-bottom: 10px !important;
        }

        html.caprio-dark .share-selector-anchor + div[data-testid="stHorizontalBlock"] > div {
            border-bottom-color: #46566d !important;
        }

        .share-selector-anchor + div[data-testid="stHorizontalBlock"] > div:first-child {
            border-bottom: 0 !important;
            padding-bottom: 0 !important;
        }
    }

    </style>
""", unsafe_allow_html=True)

if IS_CLIENT_VIEW:
    st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="stSidebarCollapsedControl"] { display: none !important; }
    </style>
    """, unsafe_allow_html=True)

# 카프리오 고정 헤더 / 자체 다크·화이트 토글 / Streamlit 기본 툴바 숨김
components.html(f"""
<script>
(function(){{
    const doc = window.parent.document;
    const root = doc.documentElement;
    const body = doc.body;

    function removeStreamlitChrome(){{
        const selectors = [
            'header[data-testid="stHeader"]',
            'div[data-testid="stToolbar"]',
            'div[data-testid="stDecoration"]',
            'div[data-testid="stStatusWidget"]',
            '#MainMenu',
            'footer',
            'button[title*="Deploy"]',
            'button[title*="Share"]',
            'button[title*="GitHub"]',
            'button[title*="Fork"]',
            'button[title*="Edit"]',
            'button[title*="Rerun"]',
            'button[aria-label*="Deploy"]',
            'button[aria-label*="Share"]',
            'button[aria-label*="GitHub"]',
            'button[aria-label*="Fork"]',
            'button[aria-label*="Edit"]',
            'button[aria-label*="Rerun"]',
            'a[href*="github.com"]'
        ];
        selectors.forEach(sel => {{
            doc.querySelectorAll(sel).forEach(el => {{
                if(el.id !== 'caprio-theme-toggle'){{
                    el.style.setProperty('display','none','important');
                    el.style.setProperty('visibility','hidden','important');
                    el.style.setProperty('pointer-events','none','important');
                }}
            }});
        }});

    }}

    function ensureHeader(){{
        let header = doc.getElementById('caprio-brand-header');
        if(!header){{
            header = doc.createElement('div');
            header.id = 'caprio-brand-header';
            header.innerHTML = `
                <div id="caprio-brand-inner">
                    <div id="caprio-brand-logo" aria-label="카프리오"></div>
                    <div id="caprio-brand-divider"></div>
                    <div id="caprio-brand-slogan">카 라이프에 <span class="free-word">자유</span>를 더하다</div>
                    <button id="caprio-theme-toggle" type="button">🌙 다크</button>
                </div>
            `;
            doc.body.appendChild(header);
        }}
        const btn = doc.getElementById('caprio-theme-toggle');
        if(btn && !btn.dataset.bound){{
            btn.dataset.bound = '1';
            btn.addEventListener('click', function(e){{
                e.preventDefault();
                const nowDark = root.classList.contains('caprio-dark');
                const next = nowDark ? 'light' : 'dark';
                window.parent.localStorage.setItem('caprioTheme', next);
                applyTheme();
            }});
        }}
    }}

    function applyTheme(){{
        const saved = window.parent.localStorage.getItem('caprioTheme') || 'light';
        const isDark = saved === 'dark';
        root.classList.toggle('caprio-dark', isDark);
        body.classList.toggle('caprio-dark', isDark);
        root.classList.toggle('caprio-light', !isDark);
        body.classList.toggle('caprio-light', !isDark);
        const btn = doc.getElementById('caprio-theme-toggle');
        if(btn) btn.textContent = isDark ? '☀️ 라이트' : '🌙 다크';
    }}

    function protectCopyDevTools(){{
        if(window.__caprioProtectionBound) return;
        window.__caprioProtectionBound = true;
        doc.addEventListener('contextmenu', function(e){{
            const tag = (e.target && e.target.tagName || '').toLowerCase();
            if(!['input','textarea'].includes(tag)) e.preventDefault();
        }}, true);
        doc.addEventListener('keydown', function(e){{
            const tag = (e.target && e.target.tagName || '').toLowerCase();
            const editable = ['input','textarea'].includes(tag) || (e.target && e.target.isContentEditable);
            const key = (e.key || '').toLowerCase();
            const blocked = key === 'f12' ||
                (e.ctrlKey && e.shiftKey && ['i','j','c'].includes(key)) ||
                (e.ctrlKey && ['u','s','p'].includes(key)) ||
                (!editable && e.ctrlKey && ['c','x'].includes(key));
            if(blocked){{
                e.preventDefault();
                e.stopPropagation();
                return false;
            }}
        }}, true);
    }}


    ensureHeader();
    applyTheme();
    removeStreamlitChrome();
    protectCopyDevTools();
    setInterval(function(){{
        ensureHeader();
        applyTheme();
        removeStreamlitChrome();
    }}, 700);
}})();
</script>
""", height=0, width=0)

# 초기 기본값 설정
car_name = "기아 카니발 가솔린 1.6 터보 하이브리드 2WD 7인승 노블레스"
car_option = "-"
car_price = 47810000
months = 60
mileage = "2만Km"
rent_monthly_pay = 600930
rent_deposit = 0
cc_text = "1600CC이하"
cc_raw_text = "1598cc"
fuel_text = "휘발유/전기"
passenger_count = 7
car_shape = "하이브리드"
installment_resale_pct = 50 # 할부 잔존가치(매각율) 기본값
rent_resale_pct = 58       # 렌트 고정 잔존가치(기본값 58%)
installment_car_price = car_price
finance_car_price = car_price

# 공유 링크로 접속한 경우 기본값 반영
shared_quote_data = {}
if st.query_params.get("q"):
    shared_quote_data = decode_share_data(st.query_params.get("q", ""))

if not IS_CLIENT_VIEW and isinstance(st.session_state.get("loaded_share_data"), dict):
    shared_quote_data = st.session_state.loaded_share_data

if shared_quote_data:
    car_name = shared_quote_data.get("car_name", car_name)
    car_option = shared_quote_data.get("car_option", car_option)
    car_price = int(shared_quote_data.get("car_price", car_price))
    installment_car_price = int(shared_quote_data.get("installment_car_price", car_price))
    finance_car_price = int(shared_quote_data.get("finance_car_price", car_price))
    months = int(shared_quote_data.get("months", months))
    mileage = shared_quote_data.get("mileage", mileage)
    rent_monthly_pay = int(shared_quote_data.get("rent_monthly_pay", rent_monthly_pay))
    rent_deposit = int(shared_quote_data.get("rent_deposit", rent_deposit))
    cc_text = shared_quote_data.get("cc_text", cc_text)
    cc_raw_text = shared_quote_data.get("cc_raw_text", cc_raw_text)
    fuel_text = shared_quote_data.get("fuel_text", fuel_text)
    passenger_count = int(shared_quote_data.get("passenger_count", passenger_count))
    car_shape = shared_quote_data.get("car_shape", car_shape)
    installment_resale_pct = int(shared_quote_data.get("installment_resale_pct", installment_resale_pct))
    rent_resale_pct = float(shared_quote_data.get("rent_resale_pct", rent_resale_pct))

# 고객명은 고객용에서는 공유 데이터 기준으로 고정,
# 영업자용에서는 불러오기 이후에도 입력창 변경값이 즉시 반영되도록 session_state를 우선합니다.
if IS_CLIENT_VIEW:
    customer_name = str(shared_quote_data.get("customer_name", "") or "").strip()
else:
    customer_name = str(st.session_state.get("customer_name", shared_quote_data.get("customer_name", "")) or "").strip()
    st.session_state.setdefault("customer_name", customer_name)

finance_mode = str(shared_quote_data.get("finance_mode", st.session_state.get("finance_mode", "rent")) or "rent")
if finance_mode not in ["rent", "lease"]:
    finance_mode = "rent"
lease_tax_included = bool(shared_quote_data.get("lease_tax_included", st.session_state.get("lease_tax_included", False)))
if not IS_CLIENT_VIEW:
    st.session_state.setdefault("finance_mode", finance_mode)
    st.session_state.setdefault("finance_mode_choice", "리스" if st.session_state.get("finance_mode", finance_mode) == "lease" else "렌트")
    st.session_state.setdefault("lease_tax_included", lease_tax_included)

visible_sections = normalize_visible_sections(shared_quote_data.get("visible_sections") if IS_CLIENT_VIEW else None)
from customer_v2 import presentation_settings, render_presentation_settings
if not IS_CLIENT_VIEW:
    pending_presentation = st.session_state.pop('pending_presentation', None)
    if pending_presentation is not None:
        st.session_state.update(presentation_settings(pending_presentation))
    for key, value in presentation_settings({}).items():
        st.session_state.setdefault(key, value)


def make_share_url():
    share_data = {
        **presentation_settings(shared_quote_data if IS_CLIENT_VIEW else st.session_state),
        "customer_name": str(st.session_state.get("customer_name", customer_name) or "").strip(),
        "finance_mode": st.session_state.get("finance_mode", finance_mode) if not IS_CLIENT_VIEW else finance_mode,
        "lease_tax_included": bool(st.session_state.get("lease_tax_included", lease_tax_included)) if not IS_CLIENT_VIEW else bool(lease_tax_included),
        "car_name": car_name,
        "car_option": car_option,
        "car_price": car_price,
        "installment_car_price": installment_car_price,
        "finance_car_price": finance_car_price,
        "months": months,
        "mileage": mileage,
        "rent_monthly_pay": rent_monthly_pay,
        "rent_deposit": rent_deposit,
        "cc_text": cc_text,
        "cc_raw_text": cc_raw_text,
        "fuel_text": fuel_text,
        "passenger_count": passenger_count,
        "car_shape": car_shape,
        "installment_resale_pct": installment_resale_pct,
        "insurance_annual": insurance_annual if "insurance_annual" in globals() else 1000000,
        "installment_rate": installment_rate if "installment_rate" in globals() else 5.0,
        "installment_prepaid": installment_prepaid if "installment_prepaid" in globals() else 0,
        "is_corporate": is_corporate if "is_corporate" in globals() else False,
        "rent_resale_pct": rent_resale_pct,
        "visible_sections": collect_visible_sections_from_state() if not IS_CLIENT_VIEW else normalize_visible_sections(visible_sections)
    }
    short_code = save_share_data(share_data)
    if short_code:
        return f"{APP_BASE_URL}/?view=client&q={short_code}"

    encoded = encode_share_data(share_data)
    return f"{APP_BASE_URL}/?view=client&q={encoded}"
    
# ==========================================
# [SIDEBAR] 조건 설정 구역
# ==========================================
# URL 불러오기 시 할부 조건 위젯값은 위젯 렌더 전에만 안전하게 반영한다.
def _safe_int_value(value, default_value=0):
    try:
        value_text = str(value if value is not None else "").replace(",", "").strip()
        if value_text == "":
            return int(default_value)
        return int(float(value_text))
    except Exception:
        return int(default_value)

def _safe_float_value(value, default_value=0.0):
    try:
        value_text = str(value if value is not None else "").replace(",", "").strip()
        if value_text == "":
            return float(default_value)
        return float(value_text)
    except Exception:
        return float(default_value)

if not IS_CLIENT_VIEW:
    _pending_installment_settings = st.session_state.pop("pending_installment_settings", None)
    if isinstance(_pending_installment_settings, dict):
        st.session_state["is_corporate_checkbox"] = bool(_pending_installment_settings.get("is_corporate", False))
        st.session_state["installment_prepaid_input"] = f"{_safe_int_value(_pending_installment_settings.get('installment_prepaid', 0), 0):,}"
        st.session_state["installment_rate_input"] = _safe_float_value(_pending_installment_settings.get("installment_rate", 5.0), 5.0)
        st.session_state["insurance_annual_input"] = f"{_safe_int_value(_pending_installment_settings.get('insurance_annual', 1000000), 1000000):,}"
        st.session_state["installment_resale_pct_input"] = _safe_int_value(_pending_installment_settings.get("installment_resale_pct", installment_resale_pct), installment_resale_pct)
    else:
        st.session_state.setdefault("is_corporate_checkbox", bool(shared_quote_data.get("is_corporate", False)))
        st.session_state.setdefault("installment_prepaid_input", f"{_safe_int_value(shared_quote_data.get('installment_prepaid', 0), 0):,}")
        st.session_state.setdefault("installment_rate_input", _safe_float_value(shared_quote_data.get("installment_rate", 5.0), 5.0))
        st.session_state.setdefault("insurance_annual_input", f"{_safe_int_value(shared_quote_data.get('insurance_annual', 1000000), 1000000):,}")
        st.session_state.setdefault("installment_resale_pct_input", _safe_int_value(shared_quote_data.get("installment_resale_pct", installment_resale_pct), installment_resale_pct))

if IS_CLIENT_VIEW:
    is_corporate = bool(shared_quote_data.get("is_corporate", False))
    installment_prepaid = int(shared_quote_data.get("installment_prepaid", 0))
    installment_rate = float(shared_quote_data.get("installment_rate", 5.0))
    insurance_annual = int(shared_quote_data.get("insurance_annual", 1000000))
else:
    # ==========================================
    # [SIDEBAR] 조건 설정 구역
    # ==========================================
    st.sidebar.header("📋 할부 조건설정")

    is_corporate = st.sidebar.checkbox("🏢 법인 고객 여부", key="is_corporate_checkbox")

    installment_prepaid = _safe_int_value(
        st.sidebar.text_input(
            "💵 할부 선납금",
            key="installment_prepaid_input"
        ),
        0
    )

    installment_rate = st.sidebar.number_input(
        "📈 할부 금리 (%)",
        step=0.1,
        key="installment_rate_input"
    )

    insurance_annual = _safe_int_value(
        st.sidebar.text_input(
            "🛡️ 연 개인 보험료",
            key="insurance_annual_input"
        ),
        1000000
    )

    st.sidebar.markdown("---")

    installment_resale_pct = st.sidebar.number_input(
        "📉 할부 잔존가치 (%)",
        min_value=0,
        max_value=100,
        step=1,
        key="installment_resale_pct_input"
    )


def auto_convert_quote(raw_text):
    """견적서 원문을 내부 TSV 형식으로 변환한다.

    신규/올드 견적서 모두 같은 출력 키로 정규화한다.
    렌트/리스 여부는 파싱 실패 조건으로 쓰지 않는다.
    - 신규: 최종차량가격 중심
    - 올드: 총차량가격 중심
    """
    if not raw_text or "견적서" not in raw_text:
        return raw_text

    text = str(raw_text).replace("\r\n", "\n").replace("\r", "\n")
    compact_text = re.sub(r"\s+", "", text)

    # 신규/올드 견적서 공통 진입 조건.
    # 렌트/리스 문구는 필수조건으로 보지 않는다.
    if not any(key in compact_text for key in ["최종차량가격", "총차량가격", "차량가격"]):
        return raw_text

    lines_raw = [line.strip() for line in text.split("\n")]
    lines_clean = [line for line in lines_raw if line]

    def only_num(v):
        return "".join(re.findall(r"\d+", str(v or "")))

    def money_after_labels(labels):
        """라벨 바로 뒤 같은 줄/다음 줄 금액 추출. ex) 총차량가격\n45,060,000원"""
        for label in labels:
            # 라벨과 금액 사이에 탭/공백/줄바꿈이 있어도 허용
            m = re.search(re.escape(label) + r"\s*([0-9][0-9,]*)\s*원", text)
            if m:
                return only_num(m.group(1))
        return ""

    def percent_after_labels(labels):
        for label in labels:
            m = re.search(re.escape(label) + r"\s*([0-9.]+)\s*%", text)
            if m:
                return m.group(1) + "%"
        return ""

    def money_after_percent_label(labels):
        """선수금/보증금처럼 % 다음 줄에 금액이 나오는 구조 대응."""
        for label in labels:
            m = re.search(re.escape(label) + r"\s*[0-9.]+\s*%\s*([0-9][0-9,]*)\s*원", text)
            if m:
                return only_num(m.group(1))
            m = re.search(re.escape(label) + r"\s*([0-9][0-9,]*)\s*원", text)
            if m:
                return only_num(m.group(1))
        return "0"

    def find_value_after_exact_label(label):
        for i, line in enumerate(lines_clean):
            if line == label and i + 1 < len(lines_clean):
                return lines_clean[i + 1].strip()
            if line.startswith(label) and line != label:
                value = line.replace(label, "", 1).strip()
                if value:
                    return value
        return ""

    # 차량명
    car_name_val = find_value_after_exact_label("차종")
    if not car_name_val:
        # 혹시 차종 라벨 앞뒤에 탭이 붙은 old copy 대응
        for i, line in enumerate(lines_clean):
            if "차종" == line.replace("\t", "").strip() and i + 1 < len(lines_clean):
                car_name_val = lines_clean[i + 1].strip()
                break

    car_name_val = re.sub(r"\b20\d{2}년형\b", "", car_name_val)
    car_name_val = re.sub(r"디 올-뉴|디 올 뉴|더 뉴|올 뉴", "", car_name_val)
    car_name_val = re.sub(r"\([^)]*개별소비세[^)]*\)", "", car_name_val)
    car_name_val = re.sub(r"\([A-Z0-9 ]*(?:F/L|FL)[A-Z0-9 /]*\)", "", car_name_val)
    car_name_val = re.sub(r"\s+", " ", car_name_val).strip()

    # 옵션: 신규/올드 모두 옵션~색상/총차량가격/옵션가격 전까지 수집
    option_val = ""
    if "옵션가격0원" not in compact_text:
        option_lines = []
        in_option = False
        option_stop_labels = {"색상", "외장", "내장", "총차량가격", "최종차량가격", "차량가격", "기간"}
        for line in lines_clean:
            if line == "옵션":
                in_option = True
                continue
            if in_option:
                if line.startswith("옵션가격") or line in option_stop_labels or any(line.startswith(stop) for stop in ["총차량가격", "최종차량가격", "차량가격"]):
                    break
                cleaned = re.sub(r"\(([0-9,]+)원\)", r"(\1)", line).strip()
                if cleaned and cleaned not in ["없음", "-", "0원"]:
                    option_lines.append(cleaned)
        option_val = " / ".join([v for v in option_lines if v])

    car_price_val = money_after_labels(["최종차량가격", "총차량가격", "차량가격"])

    months_val = ""
    m = re.search(r"기간\s*([0-9]+)\s*개월", text)
    if m:
        months_val = only_num(m.group(1))

    mileage_val = ""
    mileage_match = re.search(r"약정거리\s*([0-9.]+\s*만)\s*km", text, re.IGNORECASE)
    if mileage_match:
        mileage_val = mileage_match.group(1).replace(" ", "") + "Km"

    monthly_val = money_after_labels(["월 납입금", "월납입금", "월납입", "월 렌트료", "월리스료", "월 리스료"])
    prepaid_val = money_after_percent_label(["선수금", "선납금"])
    resale_val = percent_after_labels(["잔존가치(인수)", "잔존가치", "잔존(렌트)", "잔존"])

    # 출시/연비/cc 라인
    fuel_line = ""
    for line in lines_clean:
        if "출시" in line and "·" in line:
            fuel_line = line
            break

    fuel_parts = [p.strip() for p in fuel_line.split("·")]
    fuel_val = ""
    # 보통 2026.01 출시 · 휘발유 · 2,497cc 구조
    if len(fuel_parts) >= 2:
        fuel_val = fuel_parts[1].strip()

    cc_match = re.search(r"([0-9,]+)\s*cc", fuel_line, re.IGNORECASE)
    cc_num = int(only_num(cc_match.group(1))) if cc_match else 0
    cc_raw_val = cc_match.group(1).replace(",", "") + "cc" if cc_match else ""

    passenger_match = re.search(r"([0-9]+)\s*인승", car_name_val)
    passenger_val = int(passenger_match.group(1)) if passenger_match else 0

    if fuel_val in ["전기", "수소"]:
        cc_val = "전기차"
    elif cc_num and cc_num <= 1000:
        cc_val = "1000CC이하"
    elif cc_num and cc_num <= 1600:
        cc_val = "1600CC이하"
    elif cc_num and cc_num <= 2000:
        cc_val = "2000CC이하"
    elif cc_num and cc_num <= 2500:
        cc_val = "2500CC이하"
    elif cc_num:
        cc_val = "3000CC초과"
    else:
        cc_val = ""

    if fuel_val == "전기":
        shape_val = "전기"
    elif fuel_val == "수소":
        shape_val = "수소"
    elif cc_num > 0 and cc_num <= 1000:
        shape_val = "경차"
    elif "하이브리드" in car_name_val or fuel_val == "휘발유/전기":
        shape_val = "하이브리드"
    else:
        shape_val = "일반"

    return f"""차량명\t{car_name_val}
옵션\t{option_val}
차량가\t{car_price_val}
개월수\t{months_val}
약정거리\t{mileage_val}
월납입\t{monthly_val}
선납금\t{prepaid_val}
잔존(렌트)\t{resale_val}
CC\t{cc_val}
CC원문\t{cc_raw_val}
유종\t{fuel_val}
인승\t{passenger_val}
형태\t{shape_val}"""


# ==========================================
# [견적 이력 저장 / 견적 입력 / 사이드바 이력]
# ==========================================
if not IS_CLIENT_VIEW:
    st.markdown("""<style>
    .block-container{max-width:none!important;padding-left:1.5rem!important;padding-right:1.5rem!important}
    [data-testid="stSidebar"]{min-width:280px!important;max-width:320px!important}
    .st-key-customer-preview{position:sticky;top:1rem}
    </style>""", unsafe_allow_html=True)
    st.markdown(f'<style>#caprio-brand-logo{{background-image:url("{CAPRIO_LOGO_BLUE_DATA_URI}")!important;background-size:contain!important;width:160px!important;height:42px!important}}</style>', unsafe_allow_html=True)
    editor_column, preview_column = st.columns([1.65, 1], gap="large")
else:
    editor_column = st.container()
    preview_column = st.container()

with editor_column:
    raw_data = ""

    if not IS_CLIENT_VIEW:
        if "quote_history" not in st.session_state:
            st.session_state.quote_history = []

        if "raw_quote_input" not in st.session_state:
            st.session_state.raw_quote_input = ""

        if "pending_quote_input" not in st.session_state:
            st.session_state.pending_quote_input = None

        if "pending_quick_edit" not in st.session_state:
            st.session_state.pending_quick_edit = None

        if "pending_visible_sections" not in st.session_state:
            st.session_state.pending_visible_sections = None

        if "pending_lease_tax_included" not in st.session_state:
            st.session_state.pending_lease_tax_included = None

        if "active_quote_data" not in st.session_state:
            st.session_state.active_quote_data = None

        if "active_quote_raw" not in st.session_state:
            st.session_state.active_quote_raw = ""

        if "quote_parse_error" not in st.session_state:
            st.session_state.quote_parse_error = ""

        def clear_quote_parse_error():
            st.session_state.quote_parse_error = ""

        def safe_quote_pct_to_float(value, default_value):
            value_text = str(value or "").replace("%", "").replace(",", "").strip()
            if not value_text:
                return float(default_value)
            try:
                return float(value_text)
            except Exception:
                st.session_state.quote_parse_error = "잔존율 값이 비어있거나 숫자가 아닙니다. 견적 원문을 확인해 주세요."
                return float(default_value)

        if st.session_state.pending_visible_sections is not None:
            apply_visible_sections_to_state(st.session_state.pending_visible_sections)
            visible_sections = normalize_visible_sections(st.session_state.pending_visible_sections)
            st.session_state.pending_visible_sections = None

        visible_sections = normalize_visible_sections(visible_sections)
        for section_key, section_value in visible_sections.items():
            st.session_state.setdefault(f"share_{section_key}", section_value)

        # 초기 진입 기본값: 렌트 계산기 기준(할부+렌트만 선택, 리스 해제)
        if "finance_mode_initialized" not in st.session_state:
            st.session_state.finance_mode = st.session_state.get("finance_mode", "rent")
            if st.session_state.finance_mode not in ["rent", "lease"]:
                st.session_state.finance_mode = "rent"
            if st.session_state.finance_mode == "rent":
                st.session_state.share_compare = True
                st.session_state.share_compare_installment = True
                st.session_state.share_compare_rent = True
                st.session_state.share_compare_lease = False
                st.session_state.share_guide = True
                st.session_state.share_guide_installment = True
                st.session_state.share_guide_rent = True
                st.session_state.share_guide_lease = False
            st.session_state.finance_mode_initialized = True

        # ==========================================
        # [TOP MAIN] 고객 공유 선택 / 견적 저장 이력
        # ==========================================
        # 견적 입력칸보다 위에 배치하기 위해 현재 세션 입력값을 먼저 한 번 반영
        pre_raw_data = st.session_state.get("raw_quote_input", "")
        if pre_raw_data:
            pre_parsed_data = auto_convert_quote(pre_raw_data)
            pre_lines = pre_parsed_data.strip().split('\n')
            for pre_line in pre_lines:
                pre_parts = pre_line.split('\t') if '\t' in pre_line else (pre_line.split(':') if ':' in pre_line else pre_line.split())
                if len(pre_parts) >= 2:
                    pre_key = pre_parts[0].strip()
                    pre_val = "".join(pre_parts[1:]).strip()
                    def pre_clean_num(v): return int("".join(filter(str.isdigit, v))) if any(char.isdigit() for char in v) else 0

                    if "차량명" in pre_key: car_name = pre_val
                    elif "옵션" in pre_key: car_option = pre_val
                    elif "차량가" in pre_key:
                        car_price = pre_clean_num(pre_val)
                        installment_car_price = car_price
                        finance_car_price = car_price
                    elif "개월수" in pre_key: months = pre_clean_num(pre_val)
                    elif "약정거리" in pre_key: mileage = pre_val.replace(" ", "")
                    elif "월납입" in pre_key: rent_monthly_pay = pre_clean_num(pre_val)
                    elif "선납금" in pre_key or "보증금" in pre_key: rent_deposit = pre_clean_num(pre_val)
                    elif "잔존" in pre_key: rent_resale_pct = safe_quote_pct_to_float(pre_val, rent_resale_pct)
                    elif pre_key == "CC원문": cc_raw_text = pre_val.replace(" ", "")
                    elif pre_key == "유종": fuel_text = pre_val.replace(" ", "")
                    elif pre_key == "인승": passenger_count = pre_clean_num(pre_val)
                    elif "CC" in pre_key: cc_text = pre_val.replace(" ", "")
                    elif "형태" in pre_key: car_shape = pre_val.replace(" ", "")

            st.session_state.active_quote_data = {
                "car_name": car_name,
                "car_option": car_option,
                "car_price": car_price,
                "installment_car_price": installment_car_price,
                "finance_car_price": finance_car_price,
                "months": months,
                "mileage": mileage,
                "rent_monthly_pay": rent_monthly_pay,
                "rent_deposit": rent_deposit,
                "cc_text": cc_text,
                "cc_raw_text": cc_raw_text,
                "fuel_text": fuel_text,
                "passenger_count": passenger_count,
                "car_shape": car_shape,
                "rent_resale_pct": rent_resale_pct,
                "finance_mode": st.session_state.get("finance_mode", finance_mode),
                "lease_tax_included": bool(st.session_state.get("lease_tax_included", lease_tax_included)),
            }
            st.session_state.active_quote_raw = pre_raw_data
        elif st.session_state.active_quote_data:
            active_quote_data = st.session_state.active_quote_data
            car_name = active_quote_data.get("car_name", car_name)
            car_option = active_quote_data.get("car_option", car_option)
            car_price = int(active_quote_data.get("car_price", car_price))
            installment_car_price = int(active_quote_data.get("installment_car_price", car_price))
            finance_car_price = int(active_quote_data.get("finance_car_price", car_price))
            months = int(active_quote_data.get("months", months))
            mileage = active_quote_data.get("mileage", mileage)
            rent_monthly_pay = int(active_quote_data.get("rent_monthly_pay", rent_monthly_pay))
            rent_deposit = int(active_quote_data.get("rent_deposit", rent_deposit))
            cc_text = active_quote_data.get("cc_text", cc_text)
            cc_raw_text = active_quote_data.get("cc_raw_text", cc_raw_text)
            fuel_text = active_quote_data.get("fuel_text", fuel_text)
            passenger_count = int(active_quote_data.get("passenger_count", passenger_count))
            car_shape = active_quote_data.get("car_shape", car_shape)
            rent_resale_pct = float(active_quote_data.get("rent_resale_pct", rent_resale_pct))
            finance_mode = st.session_state.get("finance_mode", active_quote_data.get("finance_mode", finance_mode))
            lease_tax_included = bool(st.session_state.get("lease_tax_included", active_quote_data.get("lease_tax_included", lease_tax_included)))

        def pre_history_money_to_int(value):
            value_text = str(value).replace(",", "").strip()
            return int("".join(filter(str.isdigit, value_text))) if any(ch.isdigit() for ch in value_text) else 0

        def pre_history_pct_to_float(value, default_value):
            try:
                return float(str(value).replace("%", "").replace(",", "").strip())
            except Exception:
                return float(default_value)

        if st.session_state.get("quick_edit_applied"):
            rent_monthly_pay = pre_history_money_to_int(st.session_state.get("quick_rent_monthly_pay", rent_monthly_pay))
            rent_resale_pct = pre_history_pct_to_float(st.session_state.get("quick_rent_resale_pct", rent_resale_pct), rent_resale_pct)
            months = int(st.session_state.get("quick_months", months))
            mileage = st.session_state.get("quick_mileage", mileage)
            quick_prepayment_input_value = st.session_state.get("quick_prepayment_value", "")
            if st.session_state.get("quick_prepayment_mode", "%") == "%":
                rent_deposit = int(finance_car_price * (pre_history_pct_to_float(quick_prepayment_input_value, 0) / 100))
            else:
                rent_deposit = pre_history_money_to_int(quick_prepayment_input_value)
            st.session_state.active_quote_data = {
                "car_name": car_name,
                "car_option": car_option,
                "car_price": car_price,
                "installment_car_price": installment_car_price,
                "finance_car_price": finance_car_price,
                "months": months,
                "mileage": mileage,
                "rent_monthly_pay": rent_monthly_pay,
                "rent_deposit": rent_deposit,
                "cc_text": cc_text,
                "cc_raw_text": cc_raw_text,
                "fuel_text": fuel_text,
                "passenger_count": passenger_count,
                "car_shape": car_shape,
                "rent_resale_pct": rent_resale_pct,
                "finance_mode": st.session_state.get("finance_mode", finance_mode),
                "lease_tax_included": bool(st.session_state.get("lease_tax_included", lease_tax_included)),
            }

        # 렌트/리스 모드 전환은 체크박스 위젯이 생성되기 전에 적용한다.
        # 버튼은 빠른수정 영역에 있지만, 실제 체크값 변경은 다음 rerun 초반에 반영해야
        # Streamlit의 session_state 위젯 잠금 오류가 발생하지 않는다.
        def apply_finance_mode_defaults(mode):
            st.session_state.finance_mode = mode
            st.session_state.finance_mode_choice = "리스" if mode == "lease" else "렌트"
            if isinstance(st.session_state.get("active_quote_data"), dict):
                st.session_state.active_quote_data["finance_mode"] = mode
            st.session_state.share_compare = True
            st.session_state.share_compare_installment = True
            st.session_state.share_guide = True
            st.session_state.share_guide_installment = True
            if mode == "lease":
                st.session_state.share_compare_rent = False
                st.session_state.share_compare_lease = True
                st.session_state.share_guide_rent = False
                st.session_state.share_guide_lease = True
            else:
                st.session_state.share_compare_rent = True
                st.session_state.share_compare_lease = False
                st.session_state.share_guide_rent = True
                st.session_state.share_guide_lease = False

        pending_finance_mode = st.session_state.pop("pending_finance_mode", None)
        if pending_finance_mode in ["rent", "lease"]:
            apply_finance_mode_defaults(pending_finance_mode)

        pending_lease_tax_included = st.session_state.pop("pending_lease_tax_included", None)
        if pending_lease_tax_included is not None:
            st.session_state.lease_tax_included = bool(pending_lease_tax_included)
            if isinstance(st.session_state.get("active_quote_data"), dict):
                st.session_state.active_quote_data["lease_tax_included"] = bool(pending_lease_tax_included)

        # 금융방식 섹션 선렌더링용 콜백/상태 보장
        st.session_state.setdefault("finance_mode", finance_mode)
        st.session_state.setdefault("lease_tax_included", lease_tax_included)

        def set_finance_mode(mode):
            mode = mode if mode in ["rent", "lease"] else "rent"
            st.session_state.finance_mode = mode
            st.session_state.finance_mode_choice = "리스" if mode == "lease" else "렌트"
            st.session_state.finance_mode_user_override = True
            st.session_state.pending_finance_mode = mode
            if isinstance(st.session_state.get("active_quote_data"), dict):
                st.session_state.active_quote_data["finance_mode"] = mode

        def on_finance_mode_choice_change():
            selected_label = st.session_state.get("finance_mode_choice", "렌트")
            set_finance_mode("lease" if selected_label == "리스" else "rent")

        def sync_finance_option_to_active_quote():
            if isinstance(st.session_state.get("active_quote_data"), dict):
                st.session_state.active_quote_data["finance_mode"] = st.session_state.get("finance_mode", "rent")
                st.session_state.active_quote_data["lease_tax_included"] = bool(st.session_state.get("lease_tax_included", False))

        # 금융방식은 빠른수정 form 밖에서 즉시 반영되도록 독립 섹션으로 렌더링한다.
        # URL/query 이동 방식 제거: 로그인 화면 재진입 없이 session_state/on_change 흐름만 사용한다.
        current_finance_mode = st.session_state.get("finance_mode", "rent")
        st.session_state.finance_mode_choice = "리스" if current_finance_mode == "lease" else "렌트"

        st.markdown("""
        <style>
        /* ===== 공통 섹션 제목: 렌트 견적 붙여넣기 / 금융방식 / 빠른수정 통일 ===== */
        .caprio-section-title {
            font-size:22px;
            font-weight:900;
            line-height:1.25;
            color:#020617;
            margin:0 0 12px 0;
            padding:0;
            letter-spacing:-0.4px;
        }
        html.caprio-dark .caprio-section-title {
            color:#f8fafc !important;
        }

        /* ===== 금융방식 독립 섹션: radio를 버튼형으로 스타일링 ===== */
        .finance-mode-row-anchor + div[data-testid="stHorizontalBlock"] {
            align-items:center !important;
            gap:0 !important;
            margin:8px 0 26px 0 !important;
            padding:0 !important;
        }
        .finance-mode-row-anchor + div[data-testid="stHorizontalBlock"] > div {
            padding:0 8px !important;
            box-sizing:border-box !important;
        }
        .finance-mode-inline-title-wrap {
            min-height:48px;
            display:flex;
            align-items:center;
        }

        div[data-testid="stVerticalBlock"]:has(.finance-radio-anchor) div[data-testid="stRadio"] {
            margin:0 !important;
            padding:0 !important;
        }
        div[data-testid="stVerticalBlock"]:has(.finance-radio-anchor) div[data-testid="stRadio"] > label {
            display:none !important;
        }
        div[data-testid="stVerticalBlock"]:has(.finance-radio-anchor) div[role="radiogroup"] {
            display:grid !important;
            grid-template-columns:1fr 1fr !important;
            gap:14px !important;
            width:520px !important;
            max-width:100% !important;
            margin:0 !important;
            padding:0 !important;
        }
        div[data-testid="stVerticalBlock"]:has(.finance-radio-anchor) div[role="radiogroup"] label {
            height:38px !important;
            min-height:38px !important;
            border-radius:10px !important;
            display:flex !important;
            align-items:center !important;
            justify-content:center !important;
            padding:0 !important;
            margin:0 !important;
            box-sizing:border-box !important;
            cursor:pointer !important;
            font-size:14px !important;
            font-weight:950 !important;
            line-height:1 !important;
            background:#ffffff !important;
            box-shadow:none !important;
        }
        div[data-testid="stVerticalBlock"]:has(.finance-radio-anchor) div[role="radiogroup"] label > div:first-child {
            display:none !important;
        }
        div[data-testid="stVerticalBlock"]:has(.finance-radio-anchor) div[role="radiogroup"] label span,
        div[data-testid="stVerticalBlock"]:has(.finance-radio-anchor) div[role="radiogroup"] label p,
        div[data-testid="stVerticalBlock"]:has(.finance-radio-anchor) div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p {
            margin:0 !important;
            padding:0 !important;
            line-height:1 !important;
            font-size:14px !important;
            font-weight:950 !important;
            text-align:center !important;
        }
        div[data-testid="stVerticalBlock"]:has(.finance-radio-anchor) div[role="radiogroup"] label:nth-child(1) {
            border:1.5px solid #22c55e !important;
            color:#16a34a !important;
            -webkit-text-fill-color:#16a34a !important;
        }
        div[data-testid="stVerticalBlock"]:has(.finance-radio-anchor) div[role="radiogroup"] label:nth-child(2) {
            border:1.5px solid #8b5cf6 !important;
            color:#7c3aed !important;
            -webkit-text-fill-color:#7c3aed !important;
        }
        div[data-testid="stVerticalBlock"]:has(.finance-radio-anchor) div[role="radiogroup"] label:nth-child(1):has(input:checked) {
            background:#16a34a !important;
            color:#ffffff !important;
            -webkit-text-fill-color:#ffffff !important;
        }
        div[data-testid="stVerticalBlock"]:has(.finance-radio-anchor) div[role="radiogroup"] label:nth-child(2):has(input:checked) {
            background:#7c3aed !important;
            color:#ffffff !important;
            -webkit-text-fill-color:#ffffff !important;
        }
        div[data-testid="stVerticalBlock"]:has(.finance-radio-anchor) div[role="radiogroup"] label:has(input:checked) * {
            color:#ffffff !important;
            -webkit-text-fill-color:#ffffff !important;
        }
        html.caprio-dark div[data-testid="stVerticalBlock"]:has(.finance-radio-anchor) div[role="radiogroup"] label {
            background:#101826 !important;
        }
        html.caprio-dark div[data-testid="stVerticalBlock"]:has(.finance-radio-anchor) div[role="radiogroup"] label:nth-child(1) {
            border-color:#22c55e !important;
            color:#86efac !important;
            -webkit-text-fill-color:#86efac !important;
        }
        html.caprio-dark div[data-testid="stVerticalBlock"]:has(.finance-radio-anchor) div[role="radiogroup"] label:nth-child(2) {
            border-color:#a78bfa !important;
            color:#c4b5fd !important;
            -webkit-text-fill-color:#c4b5fd !important;
        }
        html.caprio-dark div[data-testid="stVerticalBlock"]:has(.finance-radio-anchor) div[role="radiogroup"] label:nth-child(1):has(input:checked) {
            background:#15803d !important;
            color:#ffffff !important;
            -webkit-text-fill-color:#ffffff !important;
        }
        html.caprio-dark div[data-testid="stVerticalBlock"]:has(.finance-radio-anchor) div[role="radiogroup"] label:nth-child(2):has(input:checked) {
            background:#6d28d9 !important;
            color:#ffffff !important;
            -webkit-text-fill-color:#ffffff !important;
        }

        .finance-lease-tax-empty {
            min-height:38px;
        }
        .finance-tax-checkbox-anchor + div[data-testid="stCheckbox"] label {
            min-height:38px !important;
            display:flex !important;
            align-items:center !important;
            margin:0 !important;
        }
        .finance-tax-checkbox-anchor + div[data-testid="stCheckbox"] [data-testid="stMarkdownContainer"] p {
            margin:0 !important;
            font-size:14px !important;
            font-weight:850 !important;
            color:#111827 !important;
            white-space:nowrap !important;
        }
        html.caprio-dark .finance-tax-checkbox-anchor + div[data-testid="stCheckbox"] [data-testid="stMarkdownContainer"] p {
            color:#f3f6fb !important;
        }


        /* [v11] 화이트모드 금융방식 박스 테두리만 진하게 보정 - 다크모드 영향 없음 */
        html.caprio-light div[data-testid="stVerticalBlockBorderWrapper"]:has(.finance-radio-anchor),
        html:not(.caprio-dark) div[data-testid="stVerticalBlockBorderWrapper"]:has(.finance-radio-anchor),
        html.caprio-light div[data-testid="stVerticalBlock"]:has(.finance-radio-anchor),
        html:not(.caprio-dark) div[data-testid="stVerticalBlock"]:has(.finance-radio-anchor) {
            border-color:#94a3b8 !important;
        }
        @media (max-width: 768px) {
            .finance-mode-row-anchor + div[data-testid="stHorizontalBlock"] {
                display:block !important;
                margin:8px 0 20px 0 !important;
            }
            .finance-mode-row-anchor + div[data-testid="stHorizontalBlock"] > div {
                width:100% !important;
                padding:0 !important;
                margin:0 0 8px 0 !important;
            }
            .finance-mode-inline-title-wrap {
                min-height:auto !important;
            }
            div[data-testid="stVerticalBlock"]:has(.finance-radio-anchor) div[role="radiogroup"] {
                width:100% !important;
                gap:10px !important;
            }
        }
        </style>
        """, unsafe_allow_html=True)

        st.markdown('<div class="finance-mode-row-anchor"></div>', unsafe_allow_html=True)
        finance_title_col, finance_control_col = st.container(), st.container()
        with finance_title_col:
            st.markdown('<div class="finance-mode-inline-title-wrap"><div class="caprio-section-title">🏢 금융방식</div></div>', unsafe_allow_html=True)
        with finance_control_col:
            with st.container(border=True):
                finance_button_col, finance_tax_col = st.columns([0.45, 0.55], gap="small")
                with finance_button_col:
                    st.markdown('<div class="finance-radio-anchor"></div>', unsafe_allow_html=True)
                    st.radio(
                        "금융방식",
                        options=["렌트", "리스"],
                        key="finance_mode_choice",
                        horizontal=True,
                        label_visibility="collapsed",
                        on_change=on_finance_mode_choice_change,
                    )
                with finance_tax_col:
                    if st.session_state.get("finance_mode", "rent") == "lease":
                        st.markdown('<div class="finance-tax-checkbox-anchor"></div>', unsafe_allow_html=True)
                        st.checkbox("리스 월이용료에 자동차세 포함", key="lease_tax_included", on_change=sync_finance_option_to_active_quote)
                    else:
                        st.markdown('<div class="finance-lease-tax-empty"></div>', unsafe_allow_html=True)

        # 저장/이력 영역은 화면상으로는 우측 상단에 두되,
        # 실제 렌더링은 견적 원문 확정/빠른수정 적용값이 모두 반영된 뒤에 실행한다.
        # 이렇게 해야 2번째 저장부터 이전 스냅샷이 저장되는 문제를 막을 수 있다.
        control_col, history_col = st.container(), st.container()
        with control_col:
            visible_sections = render_share_section_selector(visible_sections)
            render_presentation_settings()
        history_area_placeholder = history_col.container()

        # ==========================================
        # [TOP MAIN] 고객 공유 URL 불러오기
        # ==========================================
        st.markdown("#### 🔗 고객 공유 URL 불러오기")
        st.markdown("""
        <style>
        /* 고객 공유 URL 불러오기: Ctrl+Enter 전용으로 사용, 버튼은 화면에서만 숨김 */
        div[data-testid="stForm"]:has(textarea[aria-label="고객 공유 URL 불러오기"]) div[data-testid="stFormSubmitButton"] {
            display: none !important;
        }
        </style>
        """, unsafe_allow_html=True)
        with st.form("share_url_load_form", clear_on_submit=False):
            share_url_input = st.text_area(
                "고객 공유 URL 불러오기",
                placeholder="고객 공유 링크를 붙여넣고 Ctrl+Enter를 누르세요.",
                height=68,
                key="share_url_input",
                label_visibility="collapsed"
            )
            share_url_submitted = st.form_submit_button("불러오기", use_container_width=True)

        share_query_value = extract_share_query_value(share_url_input)
        # 사용자가 Ctrl+Enter/불러오기 버튼으로 명시 실행한 경우에만 불러온다.
        # 같은 URL이어도 직접 실행이면 현재 수정값을 버리고 저장된 URL 데이터로 강제 덮어쓴다.
        should_load_share_url = bool(share_query_value) and bool(share_url_submitted)
        if should_load_share_url:
            loaded_share_data = decode_share_data(share_query_value)
            if loaded_share_data:
                st.session_state.loaded_share_data = loaded_share_data
                st.session_state.loaded_share_query_value = share_query_value
                st.session_state.customer_name = str(loaded_share_data.get("customer_name", "") or "").strip()
                loaded_finance_mode = loaded_share_data.get("finance_mode", "rent")
                loaded_finance_mode = loaded_finance_mode if loaded_finance_mode in ["rent", "lease"] else "rent"
                st.session_state.finance_mode = loaded_finance_mode
                # finance_mode_choice는 이미 금융방식 위젯이 렌더된 뒤에는 직접 수정하면 Streamlit 오류가 납니다.
                # 불러오기 값은 pending으로 넘기고, 다음 rerun 초반(UI 렌더 전)에 반영합니다.
                st.session_state.pending_finance_mode = loaded_finance_mode
                st.session_state.finance_mode_user_override = False
                st.session_state.pending_lease_tax_included = bool(loaded_share_data.get("lease_tax_included", False))
                st.session_state.pending_installment_settings = {
                    "installment_prepaid": loaded_share_data.get("installment_prepaid", 0),
                    "installment_rate": loaded_share_data.get("installment_rate", 5.0),
                    "insurance_annual": loaded_share_data.get("insurance_annual", 1000000),
                    "installment_resale_pct": loaded_share_data.get("installment_resale_pct", installment_resale_pct),
                    "is_corporate": loaded_share_data.get("is_corporate", False),
                }
                st.session_state.active_quote_data = {
                    "car_name": loaded_share_data.get("car_name", car_name),
                    "car_option": loaded_share_data.get("car_option", car_option),
                    "car_price": int(loaded_share_data.get("car_price", car_price)),
                    "installment_car_price": int(loaded_share_data.get("installment_car_price", loaded_share_data.get("car_price", car_price))),
                    "finance_car_price": int(loaded_share_data.get("finance_car_price", loaded_share_data.get("car_price", car_price))),
                    "months": int(loaded_share_data.get("months", months)),
                    "mileage": loaded_share_data.get("mileage", mileage),
                    "rent_monthly_pay": int(loaded_share_data.get("rent_monthly_pay", rent_monthly_pay)),
                    "rent_deposit": int(loaded_share_data.get("rent_deposit", rent_deposit)),
                    "cc_text": loaded_share_data.get("cc_text", cc_text),
                    "cc_raw_text": loaded_share_data.get("cc_raw_text", cc_raw_text),
                    "fuel_text": loaded_share_data.get("fuel_text", fuel_text),
                    "passenger_count": int(loaded_share_data.get("passenger_count", passenger_count)),
                    "car_shape": loaded_share_data.get("car_shape", car_shape),
                    "installment_prepaid": _safe_int_value(loaded_share_data.get("installment_prepaid", 0), 0),
                    "installment_rate": _safe_float_value(loaded_share_data.get("installment_rate", 5.0), 5.0),
                    "insurance_annual": _safe_int_value(loaded_share_data.get("insurance_annual", 1000000), 1000000),
                    "installment_resale_pct": _safe_int_value(loaded_share_data.get("installment_resale_pct", installment_resale_pct), installment_resale_pct),
                    "is_corporate": bool(loaded_share_data.get("is_corporate", False)),
                    "rent_resale_pct": float(loaded_share_data.get("rent_resale_pct", rent_resale_pct)),
                    "finance_mode": loaded_share_data.get("finance_mode", "rent"),
                    "lease_tax_included": bool(loaded_share_data.get("lease_tax_included", False)),
                }
                st.session_state.active_quote_raw = ""
                st.session_state.raw_quote_input = ""
                st.session_state.pending_quick_edit = {
                    "rent_monthly_pay": int(loaded_share_data.get("rent_monthly_pay", rent_monthly_pay)),
                    "rent_resale_pct": float(loaded_share_data.get("rent_resale_pct", rent_resale_pct)),
                    "installment_car_price": int(loaded_share_data.get("installment_car_price", loaded_share_data.get("car_price", car_price))),
                    "finance_car_price": int(loaded_share_data.get("finance_car_price", loaded_share_data.get("car_price", car_price))),
                    "months": int(loaded_share_data.get("months", months)),
                    "mileage": loaded_share_data.get("mileage", mileage),
                    "rent_deposit": int(loaded_share_data.get("rent_deposit", rent_deposit)),
                    "prepayment_mode": "원" if int(loaded_share_data.get("rent_deposit", rent_deposit)) else "%",
                    "prepayment_value": f"{int(loaded_share_data.get('rent_deposit', rent_deposit)):,}" if int(loaded_share_data.get("rent_deposit", rent_deposit)) else "",
                    "finance_mode": loaded_share_data.get("finance_mode", "rent"),
                    "lease_tax_included": bool(loaded_share_data.get("lease_tax_included", False)),
                    "installment_prepaid": _safe_int_value(loaded_share_data.get("installment_prepaid", 0), 0),
                    "installment_rate": _safe_float_value(loaded_share_data.get("installment_rate", 5.0), 5.0),
                    "insurance_annual": _safe_int_value(loaded_share_data.get("insurance_annual", 1000000), 1000000),
                    "installment_resale_pct": _safe_int_value(loaded_share_data.get("installment_resale_pct", installment_resale_pct), installment_resale_pct),
                    "is_corporate": bool(loaded_share_data.get("is_corporate", False)),
                }
                loaded_visible_sections = normalize_visible_sections(loaded_share_data.get("visible_sections"))
                # 공유 항목 체크박스는 이미 렌더된 뒤 직접 수정하면 Streamlit 위젯 키 오류가 납니다.
                # 불러오기 값은 pending으로 저장하고, 다음 rerun 초반(UI 렌더 전)에 반영합니다.
                st.session_state.pending_visible_sections = loaded_visible_sections
                st.session_state.pending_presentation = presentation_settings(loaded_share_data)
                st.success("공유 견적을 불러왔습니다.")
                st.rerun()
            else:
                st.warning("유효한 고객 공유 URL 또는 코드가 아닙니다.")

        if st.session_state.get("quote_parse_error"):
            st.warning(st.session_state.quote_parse_error)
            st.markdown("#### 📋 렌트 견적 다시 붙여넣기")
            st.text_area(
                "렌트 견적 다시 붙여넣기",
                placeholder="견적 텍스트를 수정해서 다시 붙여넣고 Ctrl+Enter를 누르세요.",
                height=110,
                key="raw_quote_input",
                label_visibility="collapsed",
                on_change=clear_quote_parse_error,
            )
            st.stop()

        # ==========================================
        # [TOP MAIN] 타사 견적 파싱 구역
        # ==========================================
        if st.session_state.pending_quote_input is not None:
            st.session_state.raw_quote_input = st.session_state.pending_quote_input
            st.session_state.pending_quote_input = None

        st.markdown("#### 📋 렌트 견적 붙여넣기")
        raw_data = st.text_area(
            "렌트 견적 붙여넣기",
            placeholder="견적 텍스트를 입력하세요.",
            height=80,
            key="raw_quote_input",
            label_visibility="collapsed"
        )

        if raw_data:
            parsed_data = auto_convert_quote(raw_data)
            lines = parsed_data.strip().split('\n')
            for line in lines:
                parts = line.split('	') if '	' in line else (line.split(':') if ':' in line else line.split())
                if len(parts) >= 2:
                    key = parts[0].strip()
                    val = "".join(parts[1:]).strip()
                    def clean_num(v): return int("".join(filter(str.isdigit, v))) if any(char.isdigit() for char in v) else 0
                
                    if "차량명" in key: car_name = val
                    elif "옵션" in key: car_option = val
                    elif "차량가" in key:
                        car_price = clean_num(val)
                        installment_car_price = car_price
                        finance_car_price = car_price
                    elif "개월수" in key: months = clean_num(val)
                    elif "약정거리" in key: mileage = val.replace(" ", "")
                    elif "월납입" in key: rent_monthly_pay = clean_num(val)
                    elif "선납금" in key or "보증금" in key: rent_deposit = clean_num(val)
                    elif "잔존" in key: rent_resale_pct = safe_quote_pct_to_float(val, rent_resale_pct)
                    elif key == "CC원문": cc_raw_text = val.replace(" ", "")
                    elif key == "유종": fuel_text = val.replace(" ", "")
                    elif key == "인승": passenger_count = clean_num(val)
                    elif "CC" in key: cc_text = val.replace(" ", "")
                    elif "형태" in key: car_shape = val.replace(" ", "")

            st.session_state.active_quote_data = {
                "car_name": car_name,
                "car_option": car_option,
                "car_price": car_price,
                "installment_car_price": installment_car_price,
                "finance_car_price": finance_car_price,
                "months": months,
                "mileage": mileage,
                "rent_monthly_pay": rent_monthly_pay,
                "rent_deposit": rent_deposit,
                "cc_text": cc_text,
                "cc_raw_text": cc_raw_text,
                "fuel_text": fuel_text,
                "passenger_count": passenger_count,
                "car_shape": car_shape,
                "rent_resale_pct": rent_resale_pct,
                "finance_mode": st.session_state.get("finance_mode", finance_mode),
                "lease_tax_included": bool(st.session_state.get("lease_tax_included", lease_tax_included)),
            }
            st.session_state.active_quote_raw = raw_data

        # ==========================================
        # [렌트/리스 조건 빠른 수정]
        # ==========================================
        def set_finance_mode(mode):
            # share_compare_* / share_guide_* 는 이미 체크박스 위젯으로 렌더된 뒤에는
            # 즉시 수정할 수 없으므로 pending 값만 남기고 다음 rerun 초반에 적용한다.
            mode = mode if mode in ["rent", "lease"] else "rent"
            st.session_state.finance_mode = mode
            st.session_state.finance_mode_choice = "리스" if mode == "lease" else "렌트"
            st.session_state.finance_mode_user_override = True
            st.session_state.pending_finance_mode = mode
            if isinstance(st.session_state.get("active_quote_data"), dict):
                st.session_state.active_quote_data["finance_mode"] = mode

        def on_finance_mode_choice_change():
            selected_label = st.session_state.get("finance_mode_choice", "렌트")
            set_finance_mode("lease" if selected_label == "리스" else "rent")

        st.session_state.setdefault("finance_mode", finance_mode)
        st.session_state.setdefault("lease_tax_included", lease_tax_included)

        quick_edit_source_signature = raw_data.strip() if raw_data.strip() else f"{car_name}|{car_price}|{installment_car_price}|{finance_car_price}|{months}|{mileage}|{rent_monthly_pay}|{rent_resale_pct}|{rent_deposit}"

        def quick_money_to_int(value):
            value_text = str(value).replace(",", "").strip()
            return int("".join(filter(str.isdigit, value_text))) if any(ch.isdigit() for ch in value_text) else 0

        def quick_pct_to_float(value, default_value):
            try:
                return float(str(value).replace("%", "").replace(",", "").strip())
            except Exception:
                return float(default_value)

        def quick_prepayment_display_value(mode, value):
            amount = quick_money_to_int(value)
            if not amount or not car_price:
                return ""
            if mode == "%":
                prepayment_amount = int(car_price * (quick_pct_to_float(value, 0) / 100))
                return f"{prepayment_amount:,}원" if prepayment_amount else ""
            prepayment_pct = (amount / car_price) * 100
            return f"{prepayment_pct:.1f}%" if prepayment_pct else ""

        def convert_quick_prepayment_value(mode, value):
            if not car_price:
                return ""
            if mode == "%":
                converted_amount = int(car_price * (quick_pct_to_float(value, 0) / 100))
                return f"{converted_amount:,}" if converted_amount else ""
            converted_pct = (quick_money_to_int(value) / car_price) * 100
            return f"{converted_pct:.1f}" if converted_pct else ""

        def toggle_quick_prepayment_mode():
            current_mode = st.session_state.get("quick_prepayment_mode", "%")
            st.session_state.quick_prepayment_value = convert_quick_prepayment_value(
                current_mode,
                st.session_state.get("quick_prepayment_value", "")
            )
            st.session_state.quick_prepayment_mode = "원" if current_mode == "%" else "%"

        if st.session_state.get("quick_edit_source_signature") != quick_edit_source_signature:
            st.session_state.quick_rent_monthly_pay = f"{rent_monthly_pay:,}"
            st.session_state.quick_rent_resale_pct = f"{rent_resale_pct:g}"
            st.session_state.quick_installment_car_price = f"{installment_car_price:,}"
            st.session_state.quick_finance_car_price = f"{finance_car_price:,}"
            st.session_state.quick_months = int(months)
            st.session_state.quick_mileage = mileage
            st.session_state.quick_prepayment_mode = "원" if rent_deposit else "%"
            st.session_state.quick_prepayment_value = f"{rent_deposit:,}" if rent_deposit else ""
            st.session_state.quick_edit_applied = False
            st.session_state.quick_edit_source_signature = quick_edit_source_signature

        if st.session_state.pending_quick_edit is not None:
            pending_quick_edit = st.session_state.pending_quick_edit
            st.session_state.quick_rent_monthly_pay = f"{int(pending_quick_edit.get('rent_monthly_pay', rent_monthly_pay)):,}"
            st.session_state.quick_rent_resale_pct = f"{float(pending_quick_edit.get('rent_resale_pct', rent_resale_pct)):g}"
            installment_car_price = int(pending_quick_edit.get("installment_car_price", installment_car_price))
            finance_car_price = int(pending_quick_edit.get("finance_car_price", finance_car_price))
            st.session_state.quick_installment_car_price = f"{installment_car_price:,}"
            st.session_state.quick_finance_car_price = f"{finance_car_price:,}"
            st.session_state.quick_months = int(pending_quick_edit.get("months", months))
            st.session_state.quick_mileage = pending_quick_edit.get("mileage", mileage)
            rent_deposit = int(pending_quick_edit.get("rent_deposit", rent_deposit))
            st.session_state.quick_prepayment_mode = pending_quick_edit.get("prepayment_mode", st.session_state.get("quick_prepayment_mode", "원" if rent_deposit else "%"))
            st.session_state.quick_prepayment_value = pending_quick_edit.get("prepayment_value", st.session_state.get("quick_prepayment_value", f"{rent_deposit:,}" if rent_deposit else ""))
            if pending_quick_edit.get("finance_mode") in ["rent", "lease"]:
                st.session_state.finance_mode = pending_quick_edit.get("finance_mode")
                # finance_mode_choice 위젯 키는 현재 화면에서 이미 렌더된 뒤일 수 있으므로 직접 수정하지 않습니다.
                # 다음 rerun 초반에 pending_finance_mode를 통해 안전하게 동기화합니다.
                st.session_state.pending_finance_mode = st.session_state.finance_mode
            if "lease_tax_included" in pending_quick_edit:
                st.session_state.pending_lease_tax_included = bool(pending_quick_edit.get("lease_tax_included", False))
            st.session_state.quick_edit_applied = True
            st.session_state.pending_quick_edit = None

        # quick edit state 보장 (텍스트 공백/active 유지 대응)
        st.session_state.setdefault("quick_months", int(months))
        st.session_state.setdefault("quick_mileage", mileage)
        st.session_state.setdefault("quick_rent_monthly_pay", f"{rent_monthly_pay:,}")
        st.session_state.setdefault("quick_rent_resale_pct", f"{rent_resale_pct:g}")
        st.session_state.setdefault("quick_installment_car_price", f"{installment_car_price:,}")
        st.session_state.setdefault("quick_finance_car_price", f"{finance_car_price:,}")
        st.session_state.setdefault("quick_prepayment_mode", "원" if rent_deposit else "%")
        st.session_state.setdefault("quick_prepayment_value", f"{rent_deposit:,}" if rent_deposit else "")

        quick_month_options = [24, 36, 48, 60]
        if int(st.session_state.get("quick_months", months)) not in quick_month_options:
            quick_month_options.append(int(st.session_state.get("quick_months", months)))
            quick_month_options = sorted(quick_month_options)

        quick_mileage_options = ["1만KM", "1.5만KM", "2만Km", "3만KM"]
        if st.session_state.get("quick_mileage", mileage) not in quick_mileage_options:
            quick_mileage_options.append(st.session_state.get("quick_mileage", mileage))

        def sync_finance_option_to_active_quote():
            if isinstance(st.session_state.get("active_quote_data"), dict):
                st.session_state.active_quote_data["finance_mode"] = st.session_state.get("finance_mode", "rent")
                st.session_state.active_quote_data["lease_tax_included"] = bool(st.session_state.get("lease_tax_included", False))

        sync_finance_option_to_active_quote()

        current_finance_mode = st.session_state.get("finance_mode", "rent")
        finance_rent_active = current_finance_mode == "rent"
        finance_lease_active = current_finance_mode == "lease"

        st.markdown('<div class="quick-rent-condition">', unsafe_allow_html=True)
        st.markdown("#### 🔧 렌트/리스 조건 빠른 수정")

        quick_edit_submitted = False

        st.markdown("""
        <style>
        .quick-rent-condition-title { font-size:22px; font-weight:800; line-height:1.25; color:inherit; margin:8px 0 6px 0; padding:0; }
        html.caprio-dark .quick-rent-condition-title {
            color: #f8fafc !important;
        }
        .quick-prepayment-label {
            min-height: 22px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 6px;
            margin: 0 0 6px 0;
            font-size: 14px;
            font-weight: 700;
            color: #111827;
        }
        .quick-prepayment-helper {
            font-size: 13px;
            font-weight: 900;
            color: #d94b4b;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: 116px;
        }
        html.caprio-dark .quick-prepayment-label {
            color: #f3f6fb !important;
        }
        html.caprio-dark .quick-prepayment-helper {
            color: #ff8da1 !important;
        }
        .quick-price-mini-divider {
            height: 54px;
            width: 1px;
            margin: 20px auto 0 auto;
            background: #94a3b8;
            opacity: .85;
        }
        html.caprio-dark .quick-price-mini-divider {
            background: #64748b !important;
            opacity: .9;
        }
        .quick-price-label {
            min-height: 22px;
            display:flex;
            align-items:center;
            margin: 0 0 6px 0;
            font-size: 14px;
            font-weight: 850;
            line-height: 1.15;
            white-space: nowrap;
        }
        .installment-price-label {
            color:#ef4444 !important;
            -webkit-text-fill-color:#ef4444 !important;
        }
        .finance-price-label {
            color:#111827 !important;
            -webkit-text-fill-color:#111827 !important;
        }
        html.caprio-dark .finance-price-label {
            color:#f3f6fb !important;
            -webkit-text-fill-color:#f3f6fb !important;
        }
        .lease-tax-option-note {
            display:inline-block;
            margin: 0 0 6px 0;
            padding: 6px 10px;
            border: 1px solid #d4dfec;
            border-radius: 999px;
            background: #f8fafc;
            color: #475569;
            font-size: 12px;
            font-weight: 900;
            line-height: 1.1;
        }
        html.caprio-dark .lease-tax-option-note {
            background:#131a24 !important;
            border-color:#46566d !important;
            color:#c8d4e6 !important;
        }
        </style>
        """, unsafe_allow_html=True)


        if isinstance(st.session_state.get("active_quote_data"), dict):
            st.session_state.active_quote_data["finance_mode"] = st.session_state.get("finance_mode", "rent")
            st.session_state.active_quote_data["lease_tax_included"] = bool(st.session_state.get("lease_tax_included", False))

        with st.form("quick_rent_edit_form"):

            quick_col1, quick_col2, quick_col3 = st.columns(3)
            quick_col4, quick_col5, quick_col6 = st.columns([1, .4, 1])
            quick_sep_col, quick_col7, quick_col8, quick_col9 = st.columns([.02, 1, 1, .65])

            with quick_col1:
                st.text_input("월납입", key="quick_rent_monthly_pay")

            with quick_col2:
                st.text_input("렌트잔존(%)", key="quick_rent_resale_pct")

            with quick_col3:
                st.selectbox(
                    "개월수",
                    quick_month_options,
                    key="quick_months"
                )

            with quick_col4:
                st.selectbox(
                    "약정거리",
                    quick_mileage_options,
                    key="quick_mileage"
                )

            with quick_col5:
                st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
                quick_prepayment_toggle_clicked = st.form_submit_button(
                    st.session_state.get("quick_prepayment_mode", "%"),
                    use_container_width=True,
                    on_click=toggle_quick_prepayment_mode
                )

            with quick_col6:
                quick_prepayment_mode = st.session_state.get("quick_prepayment_mode", "%")
                quick_prepayment_helper = quick_prepayment_display_value(
                    quick_prepayment_mode,
                    st.session_state.get("quick_prepayment_value", "")
                )
                quick_prepayment_label = f"선납금({quick_prepayment_mode})"
                quick_prepayment_placeholder = "퍼센트 기준으로 입력" if quick_prepayment_mode == "%" else "원 기준으로 입력"
                st.markdown(
                    f'<div class="quick-prepayment-label"><span>{quick_prepayment_label}</span><span class="quick-prepayment-helper">{quick_prepayment_helper}</span></div>',
                    unsafe_allow_html=True
                )
                st.text_input(
                    "선납금",
                    key="quick_prepayment_value",
                    placeholder=quick_prepayment_placeholder,
                    label_visibility="collapsed"
                )

            with quick_sep_col:
                st.markdown("<div class='quick-price-mini-divider'></div>", unsafe_allow_html=True)

            with quick_col7:
                st.markdown('<div class="quick-price-label installment-price-label">할부 차량가</div>', unsafe_allow_html=True)
                st.text_input("할부 차량가", key="quick_installment_car_price", label_visibility="collapsed")

            with quick_col8:
                st.markdown('<div class="quick-price-label finance-price-label">렌트·리스 차량가</div>', unsafe_allow_html=True)
                st.text_input("렌트·리스 차량가", key="quick_finance_car_price", label_visibility="collapsed")

            with quick_col9:
                st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
                quick_edit_submitted = st.form_submit_button("적용", use_container_width=True)

        st.markdown('</div>', unsafe_allow_html=True)


        if quick_edit_submitted:
            st.session_state.quick_edit_applied = True

        if st.session_state.get("quick_edit_applied"):
            rent_monthly_pay = quick_money_to_int(st.session_state.quick_rent_monthly_pay)
            rent_resale_pct = quick_pct_to_float(st.session_state.quick_rent_resale_pct, rent_resale_pct)
            installment_car_price = quick_money_to_int(st.session_state.get("quick_installment_car_price", installment_car_price)) or car_price
            finance_car_price = quick_money_to_int(st.session_state.get("quick_finance_car_price", finance_car_price)) or car_price
            months = int(st.session_state.quick_months)
            mileage = st.session_state.quick_mileage
            quick_prepayment_input_value = st.session_state.get("quick_prepayment_value", "")
            if st.session_state.get("quick_prepayment_mode", "%") == "%":
                rent_deposit = int(finance_car_price * (quick_pct_to_float(quick_prepayment_input_value, 0) / 100))
            else:
                rent_deposit = quick_money_to_int(quick_prepayment_input_value)
            st.session_state.active_quote_data = {
                "car_name": car_name,
                "car_option": car_option,
                "car_price": car_price,
                "installment_car_price": installment_car_price,
                "finance_car_price": finance_car_price,
                "months": months,
                "mileage": mileage,
                "rent_monthly_pay": rent_monthly_pay,
                "rent_deposit": rent_deposit,
                "cc_text": cc_text,
                "cc_raw_text": cc_raw_text,
                "fuel_text": fuel_text,
                "passenger_count": passenger_count,
                "car_shape": car_shape,
                "rent_resale_pct": rent_resale_pct,
                "finance_mode": st.session_state.get("finance_mode", finance_mode),
                "lease_tax_included": bool(st.session_state.get("lease_tax_included", lease_tax_included)),
            }

        history_raw_data = st.session_state.get("active_quote_raw", pre_raw_data) if st.session_state.active_quote_data else pre_raw_data
        with history_area_placeholder:
            render_quote_history_area(
                history_raw_data,
                car_name,
                rent_monthly_pay,
                months,
                mileage,
                rent_resale_pct,
                rent_deposit,
                make_share_url,
                visible_sections,
                st.session_state.active_quote_data is not None,
            )

        st.sidebar.markdown(
            '<div class="rent-fixed-resale-label" style="font-size:14px; font-weight:400;">📉 렌트 고정 잔존가치 (%)</div>',
            unsafe_allow_html=True
        )
        st.sidebar.markdown(f"""
        <div class="readonly-sidebar-value rent-fixed-resale-value">
        {rent_resale_pct:g}
        </div>
        """, unsafe_allow_html=True)

    # ==========================================
    # [BACKEND] 연산 로직
    # ==========================================
    e15 = "O" if passenger_count >= 9 else ""
    e14 = "O" if "경차" in car_shape else ""
    g14 = "O" if "전기" in car_shape or "수소" in car_shape else ""
    i14 = "O" if "하이브리드" in car_shape else ""

    def calc_registration_tax(price):
        if e15 != "" and g14 != "":
            tax_raw = (price * 0.05) - 1400000
        elif e15 != "":
            tax_raw = price * 0.05
        elif e14 != "":
            tax_raw = (price * 0.04) - 750000
        elif g14 != "":
            tax_raw = (price * 0.07) - 1400000
        else:
            tax_raw = price * 0.07
        return max(0, int(tax_raw))

    installment_car_price = int(installment_car_price or car_price)
    finance_car_price = int(finance_car_price or car_price)
    reg_tax = calc_registration_tax(installment_car_price)
    finance_reg_tax = calc_registration_tax(finance_car_price)

    if "전기" in cc_text:
        tax_annual = 130000
    elif "1000" in cc_text:
        tax_annual = 104000
    elif "1600" in cc_text:
        tax_annual = 291200
    elif "2000" in cc_text:
        tax_annual = 520000
    elif "2500" in cc_text:
        tax_annual = 650000
    elif "3000" in cc_text:
        tax_annual = 780000
    else:
        tax_annual = 130000

    loan_amount = installment_car_price - installment_prepaid
    r = (installment_rate / 100) / 12
    inst_monthly_pay = int(loan_amount / months)
    installment_equal_pay = loan_amount * (r * (1 + r)**months) / ((1 + r)**months - 1) if r > 0 else loan_amount / months
    installment_interest = int((installment_equal_pay * months) - loan_amount)

    total_ins = int((insurance_annual / 12) * months)
    total_tax = int((tax_annual / 12) * months)

    # 할부 잔존가치(매각) 산출
    corporate_discount = 0.9 if (is_corporate and car_shape != "경차" and e15 == "") else 1.0
    car_sell_value = int(installment_car_price * (installment_resale_pct / 100) * corporate_discount)

    # 렌트 고정 잔존가치 산출 (수정: 렌트 고정값 58% 사용)
    rent_takeover_price = int(finance_car_price * (rent_resale_pct / 100))

    if e15 != "" and g14 != "":
        rent_takeover_tax_raw = (rent_takeover_price * 0.05) - 1400000
    elif e15 != "":
        rent_takeover_tax_raw = rent_takeover_price * 0.05
    elif e14 != "":
        rent_takeover_tax_raw = (rent_takeover_price * 0.04) - 750000
    elif g14 != "":
        rent_takeover_tax_raw = (rent_takeover_price * 0.07) - 1400000
    else:
        rent_takeover_tax_raw = rent_takeover_price * 0.07

    rent_takeover_tax = max(0, int(rent_takeover_tax_raw))

    finance_mode = st.session_state.get("finance_mode", finance_mode) if not IS_CLIENT_VIEW else finance_mode
    lease_tax_included = bool(st.session_state.get("lease_tax_included", lease_tax_included)) if not IS_CLIENT_VIEW else bool(lease_tax_included)
    finance_product_label = "리스" if finance_mode == "lease" else "장기렌트"
    lease_extra_tax_total = 0 if lease_tax_included else total_tax
    lease_extra_tax_display = "월 리스료 포함" if lease_tax_included else f"{total_tax:,} 원"

    resale_24_1 = "td-highlight" if mileage == "1만KM" and months == 24 else ""
    resale_36_1 = "td-highlight" if mileage == "1만KM" and months == 36 else ""
    resale_48_1 = "td-highlight" if mileage == "1만KM" and months == 48 else ""
    resale_60_1 = "td-highlight" if mileage == "1만KM" and months == 60 else ""
    resale_24_15 = "td-highlight" if mileage == "1.5만KM" and months == 24 else ""
    resale_36_15 = "td-highlight" if mileage == "1.5만KM" and months == 36 else ""
    resale_48_15 = "td-highlight" if mileage == "1.5만KM" and months == 48 else ""
    resale_60_15 = "td-highlight" if mileage == "1.5만KM" and months == 60 else ""
    resale_24_2 = "td-highlight" if mileage == "2만Km" and months == 24 else ""
    resale_36_2 = "td-highlight" if mileage == "2만Km" and months == 36 else ""
    resale_48_2 = "td-highlight" if mileage == "2만Km" and months == 48 else ""
    resale_60_2 = "td-highlight" if mileage == "2만Km" and months == 60 else ""
    resale_24_3 = "td-highlight" if mileage == "3만KM" and months == 24 else ""
    resale_36_3 = "td-highlight" if mileage == "3만KM" and months == 36 else ""
    resale_48_3 = "td-highlight" if mileage == "3만KM" and months == 48 else ""
    resale_60_3 = "td-highlight" if mileage == "3만KM" and months == 60 else ""

    rate_900_over = "td-highlight" if installment_rate >= 3.5 and installment_rate <= 4.8 else ""
    rate_801_900 = "td-highlight" if installment_rate >= 4.9 and installment_rate <= 6.9 else ""
    rate_701_800 = "td-highlight" if installment_rate >= 7.0 and installment_rate <= 8.9 else ""
    rate_601_700 = "td-highlight" if installment_rate >= 9.0 and installment_rate <= 11.9 else ""
    rate_600_under = "td-highlight" if installment_rate >= 12.0 and installment_rate <= 14.9 else ""

    tax_1000 = "td-highlight" if "1000" in cc_text else ""
    tax_1600 = "td-highlight" if "1600" in cc_text else ""
    tax_2000 = "td-highlight" if "2000" in cc_text else ""
    tax_2500 = "td-highlight" if "2500" in cc_text else ""
    tax_3000 = "td-highlight" if "3000" in cc_text else ""
    tax_ev = "td-highlight" if "전기" in cc_text else ""

    reg_general = "td-highlight" if car_shape == "일반" and e15 == "" else ""
    reg_light = "td-highlight" if "경차" in car_shape and e15 == "" else ""
    reg_ev = "td-highlight" if ("전기" in car_shape or "수소" in car_shape) and e15 == "" else ""
    reg_hybrid = "td-highlight" if "하이브리드" in car_shape and e15 == "" else ""
    reg_van = "td-highlight" if e15 != "" else ""

    tax_type_text = "승합차(9인승 이상)" if e15 != "" else car_shape

    car_option_display = format_option_html(car_option)
    if int(installment_car_price or car_price) == int(finance_car_price or car_price):
        car_price_display_html = f"{int(finance_car_price or car_price):,} 원"
    else:
        car_price_display_html = (
            f'<div class="vehicle-price-split"><div><span style="font-weight:900;">할부</span> {int(installment_car_price):,} 원</div>'
            f'<div><span style="font-weight:900;">렌트·리스</span> {int(finance_car_price):,} 원</div></div>'
        )


    def render_customer_intro_card(customer_name_value):
        safe_name = html.escape(str(customer_name_value or "").strip())
        customer_label = f"{safe_name}님" if safe_name else "고객님"
        st.markdown(f"""
        <div class="common-info-box customer-message-box caprio-polish-message">
            <div style="font-size:15px; font-weight:bold; margin-bottom:9px; line-height:1.45; color:#0b3873;">
                {customer_label},<br>
                더 합리적인 선택을 위해 준비했어요 🙂
            </div>
            <div style="font-size:13px; line-height:1.6; color:#333333;">
                복잡한 조건은 대신 정리하고,<br>
                편하게 비교하실 수 있게 만들었어요.
            </div>
        </div>
        """, unsafe_allow_html=True)


    def render_customer_outro_card():
        st.markdown("""
        <div class="common-info-box customer-message-box caprio-polish-message">
            <div style="font-size:15px; font-weight:bold; margin-bottom:9px; line-height:1.45; color:#0b3873;">
                혼자 비교하기 복잡하시다면<br>
                언제든 카프리오에 물어보세요 🙂
            </div>
            <div style="font-size:13px; line-height:1.6; color:#333333;">
                고객님 손해 안 보게<br>
                할부·렌트·리스까지 비교해드릴게요.
            </div>
        </div>
        """, unsafe_allow_html=True)


    if not IS_CLIENT_VIEW:
        if True:
            # ==========================================
            # [공통 조건 구역]
            # ==========================================
            st.markdown(f"""
            <div class="common-info-box">
                <div style="font-size:15px; font-weight:bold; margin-bottom:10px; color:#0b3873;">🚘 비교 차량 공통 조건</div>
                <table class="vehicle-table-mobile-primary">
                    <tbody>
                        <tr>
                            <th>차량명</th>
                            <th>옵션</th>
                            <th>차량가</th>
                        </tr>
                        <tr>
                            <td>{car_name}</td>
                            <td>{car_option_display}</td>
                            <td>{car_price_display_html}</td>
                        </tr>
                    </tbody>
                </table>
                <table class="vehicle-table-mobile-secondary">
                    <tbody>
                        <tr>
                            <th>계약기간</th>
                            <th>약정거리</th>
                            <th>유종</th>
                            <th>CC</th>
                        </tr>
                        <tr>
                            <td>{months}개월</td>
                            <td>{mileage}</td>
                            <td>{car_shape if fuel_text == "휘발유/전기" else fuel_text}</td>
                            <td>{cc_raw_text}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
            """, unsafe_allow_html=True)

        # 고객/영업자 할부 조건 설정표 노출
        condition_product_label = "리스" if finance_mode == "lease" else "렌트"
        condition_resale_class = "lease-highlight" if finance_mode == "lease" else "rent-highlight"
        if True:
            st.markdown(f"""
                <div class="common-info-box">
                    <div style="font-size:15px; font-weight:bold; margin-bottom:10px; color:#0b3873;">
                        📋 할부 조건 설정
                    </div>
                    <table class="common-table client-condition-table">
                        <thead>
                            <tr>
                                <th>법인 여부</th>
                                <th>할부 선납금</th>
                                <th>할부 금리</th>
                                <th>연 보험료</th>
                                <th>할부 잔존가치</th>
                                <th class="{condition_resale_class}">{condition_product_label} 잔존가치</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>{"O" if is_corporate else "X"}</td>
                                <td>{installment_prepaid:,} 원</td>
                                <td>{installment_rate:g}%</td>
                                <td>{insurance_annual:,} 원</td>
                                <td>{installment_resale_pct:g}%</td>
                                <td class="{condition_resale_class}">{rent_resale_pct:g}%</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            """, unsafe_allow_html=True)

        # ==========================================
        # [📊 MAIN VISUAL] 대칭형 비교 테이블
        # ==========================================
        selected_summary_views = []
        if True:
            selected_summary_views.append("return")
        if True:
            selected_summary_views.append("takeover")

        if selected_summary_views:
            if visible_sections.get("common", True) or visible_sections.get("installment_condition", True):
                render_output_section_gap()
            summary_cols = [st.container() for _ in selected_summary_views]
            summary_col_map = dict(zip(selected_summary_views, summary_cols))

            # 1. 반납형 테이블
            if "return" in summary_col_map:
                with summary_col_map["return"]:
                    st.markdown('<div class="excel-header-blue">카프리오 비교 프로그램 (반납형)</div>', unsafe_allow_html=True)
            
                    inst_total_cost_ret = installment_prepaid + (inst_monthly_pay * months) + installment_interest + reg_tax + total_tax + total_ins - car_sell_value
                    if finance_mode == "lease":
                        rent_total_cost_ret = (rent_monthly_pay * months) + rent_deposit + total_ins + lease_extra_tax_total
                        ret_product_rows = f"""
                        {"<tr><td class='font-bold'>취등록세</td><td>"+format(reg_tax,",")+" 원</td><td rowspan='2' class='bg-light text-blue' style='vertical-align:middle;'>월 리스료 포함</td></tr><tr><td class='font-bold'>자동차세</td><td>"+format(total_tax,",")+" 원</td></tr>" if lease_tax_included else f"<tr><td class='font-bold'>취등록세</td><td>{reg_tax:,} 원</td><td>월 리스료 포함</td></tr><tr><td class='font-bold'>자동차세</td><td>{total_tax:,} 원</td><td>{lease_extra_tax_display}</td></tr>"}
                        <tr><td class="font-bold">보험료</td><td>{total_ins:,} 원</td><td>{total_ins:,} 원</td></tr>
                        <tr class="maturity-section-start"><td class="maturity-sale-label">만기 차량 매각</td><td class="maturity-sale-value">-{car_sell_value:,} 원</td><td>-</td></tr>
                        <tr><td class="font-bold">-</td><td>-</td><td>-</td></tr>
                        """
                        ret_product_rows = textwrap.dedent(ret_product_rows).strip()
                    else:
                        rent_total_cost_ret = (rent_monthly_pay * months) + rent_deposit
                        ret_product_rows = f"""
                        <tr><td class="font-bold">취등록세</td><td>{reg_tax:,} 원</td><td rowspan="3" class="bg-light text-blue" style="vertical-align:middle;">월 렌트료<br>포함</td></tr>
                        <tr><td class="font-bold">자동차세</td><td>{total_tax:,} 원</td></tr>
                        <tr><td class="font-bold">보험료</td><td>{total_ins:,} 원</td></tr>
                        <tr class="maturity-section-start"><td class="maturity-sale-label">만기 차량 매각</td><td class="maturity-sale-value">-{car_sell_value:,} 원</td><td>-</td></tr>
                        <tr><td class="font-bold">-</td><td>-</td><td>-</td></tr>
                        """
                        ret_product_rows = textwrap.dedent(ret_product_rows).strip()
                    diff_ret = inst_total_cost_ret - rent_total_cost_ret
            
                    html_ret = f"""
                    <table class="pure-table">
                        <tr><th style="width:34%;">세부 항목</th><th style="width:33%;">일반 할부</th><th style="width:33%;">{finance_product_label}(반납형)</th></tr>
                        <tr><td class="font-bold">선납금</td><td>{installment_prepaid:,} 원</td><td>{rent_deposit:,} 원</td></tr>
                        <tr><td class="font-bold">(월)납입금<br><span style="color:red; font-size:10px; display:block; margin-top:-2px; line-height:1;">(선납금 제외)</span></td><td>{inst_monthly_pay:,} 원</td><td>{rent_monthly_pay:,} 원</td></tr>
                        <tr><td class="font-bold">할부이자</td><td>{installment_interest:,} 원</td><td>-</td></tr>
                        {ret_product_rows}
                        <tr class="bg-light font-bold"><td>📊 월 평균 환산 비용</td><td>{int(inst_total_cost_ret/months):,} 원</td><td>{int(rent_total_cost_ret/months):,} 원</td></tr>
                        <tr class="bg-light font-bold" style="background-color:#e9ecef;"><td>💰 총 투입 비용</td><td>{inst_total_cost_ret:,} 원</td><td>{rent_total_cost_ret:,} 원</td></tr>
                    </table>
                    """
                    st.markdown(textwrap.dedent(html_ret).strip(), unsafe_allow_html=True)
            
                    st.markdown('<div class="caprio-result-spacer"></div>', unsafe_allow_html=True)
                    if diff_ret > 0:
                        st.markdown(f'<div class="excel-green">🏆 {finance_product_label} 선택 시 할부 대비 {diff_ret:,}원 절감!</div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="excel-red">할부 이용이 {abs(diff_ret):,}원 더 유리합니다.</div>', unsafe_allow_html=True)

                    st.markdown('<div class="mobile-compare-gap"></div>', unsafe_allow_html=True)

            # 2. 인수형 테이블
            if "takeover" in summary_col_map:
                with summary_col_map["takeover"]:
                    st.markdown('<div class="excel-header-blue">카프리오 비교 프로그램 (인수형)</div>', unsafe_allow_html=True)
            
                    inst_total_cost_ins = installment_prepaid + (inst_monthly_pay * months) + installment_interest + reg_tax + total_tax + total_ins
                    if finance_mode == "lease":
                        rent_total_cost_ins = (rent_monthly_pay * months) + rent_takeover_price + rent_takeover_tax + rent_deposit + total_ins + lease_extra_tax_total
                        ins_tax_row_value = f"{rent_takeover_tax:,} 원"
                        ins_product_rows = f"""
                        {"<tr><td class='font-bold'>취등록세</td><td>"+format(reg_tax,",")+" 원</td><td rowspan='2' class='bg-light text-blue' style='vertical-align:middle;'>월 리스료 포함</td></tr><tr><td class='font-bold'>자동차세</td><td>"+format(total_tax,",")+" 원</td></tr>" if lease_tax_included else f"<tr><td class='font-bold'>취등록세</td><td>{reg_tax:,} 원</td><td>월 리스료 포함</td></tr><tr><td class='font-bold'>자동차세</td><td>{total_tax:,} 원</td><td>{lease_extra_tax_display}</td></tr>"}
                        <tr><td class="font-bold">보험료</td><td>{total_ins:,} 원</td><td>{total_ins:,} 원</td></tr>
                        """
                        ins_product_rows = textwrap.dedent(ins_product_rows).strip()
                    else:
                        rent_total_cost_ins = (rent_monthly_pay * months) + rent_takeover_price + rent_takeover_tax + rent_deposit
                        ins_tax_row_value = f"{rent_takeover_tax:,} 원"
                        ins_product_rows = f"""
                        <tr><td class="font-bold">취등록세</td><td>{reg_tax:,} 원</td><td rowspan="3" class="bg-light text-blue" style="vertical-align:middle;">월 렌트료<br>포함</td></tr>
                        <tr><td class="font-bold">자동차세</td><td>{total_tax:,} 원</td></tr>
                        <tr><td class="font-bold">보험료</td><td>{total_ins:,} 원</td></tr>
                        """
                        ins_product_rows = textwrap.dedent(ins_product_rows).strip()
                    diff_ins = inst_total_cost_ins - rent_total_cost_ins

                    html_ins = f"""
                    <table class="pure-table">
                        <tr><th style="width:34%;">세부 항목</th><th style="width:33%;">일반 할부</th><th style="width:33%;">{finance_product_label}(인수형)</th></tr>
                        <tr><td class="font-bold">선납금</td><td>{installment_prepaid:,} 원</td><td>{rent_deposit:,} 원</td></tr>
                        <tr><td class="font-bold">(월)납입금<br><span style="color:red; font-size:10px; display:block; margin-top:-2px; line-height:1;">(선납금 제외)</span></td><td>{inst_monthly_pay:,} 원</td><td>{rent_monthly_pay:,} 원</td></tr>
                        <tr><td class="font-bold">할부이자</td><td>{installment_interest:,} 원</td><td>-</td></tr>
                        {ins_product_rows}
                        <tr class="maturity-section-start"><td class="font-bold">만기 인수금</td><td>-</td><td>{rent_takeover_price:,} 원</td></tr>
                        <tr><td class="font-bold">인수 시 취등록세</td><td>-</td><td>{ins_tax_row_value}</td></tr>
                        <tr class="bg-light font-bold"><td>📊 월 평균 환산 비용</td><td>{int(inst_total_cost_ins/months):,} 원</td><td>{int(rent_total_cost_ins/months):,} 원</td></tr>
                        <tr class="bg-light font-bold" style="background-color:#e9ecef;"><td>💰 총 투입 비용</td><td>{inst_total_cost_ins:,} 원</td><td>{rent_total_cost_ins:,} 원</td></tr>
                    </table>
                    """
                    st.markdown(textwrap.dedent(html_ins).strip(), unsafe_allow_html=True)
            
                    st.markdown('<div class="caprio-result-spacer"></div>', unsafe_allow_html=True)
                    if diff_ins > 0:
                        st.markdown(f'<div class="excel-green">🏆 {finance_product_label} 선택 시 할부 대비 {diff_ins:,}원 절감!</div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="excel-red">할부 인수가 총 {abs(diff_ins):,}원 더 유리합니다.</div>', unsafe_allow_html=True)


with preview_column:
    if not IS_CLIENT_VIEW:
        st.markdown("### 고객 모바일 미리보기")
    with st.container(key="customer-preview"):
        from customer_v2 import render_customer_v2

        render_customer_v2(
                preview=not IS_CLIENT_VIEW,
                **presentation_settings(shared_quote_data if IS_CLIENT_VIEW else st.session_state),
                is_corporate=is_corporate, insurance_annual=insurance_annual,
                fuel_text=fuel_text, cc_raw_text=cc_raw_text,
                logo_data_uri=CAPRIO_LOGO_BLUE_DATA_URI,
                customer_name=customer_name if IS_CLIENT_VIEW else st.session_state.get("customer_name", customer_name),
                car_name=car_name, car_option=car_option,
                car_price=car_price, installment_car_price=installment_car_price,
                finance_car_price=finance_car_price, months=months, mileage=mileage,
                rent_monthly_pay=rent_monthly_pay, rent_deposit=rent_deposit,
                finance_mode=finance_mode, lease_tax_included=lease_tax_included,
                installment_prepaid=installment_prepaid, inst_monthly_pay=inst_monthly_pay,
                installment_interest=installment_interest, reg_tax=reg_tax,
                total_tax=total_tax, total_ins=total_ins, car_sell_value=car_sell_value,
                rent_takeover_price=rent_takeover_price, rent_takeover_tax=rent_takeover_tax,
                installment_rate=installment_rate,
                installment_resale_pct=installment_resale_pct,
                rent_resale_pct=rent_resale_pct,
                visible_sections=visible_sections if IS_CLIENT_VIEW else collect_visible_sections_from_state(),
            )

st.stop()

if visible_sections.get("intro", True):
    render_customer_intro_card(customer_name)

if visible_sections.get("common", True):
    # ==========================================
    # [공통 조건 구역]
    # ==========================================
    st.markdown(f"""
    <div class="common-info-box">
        <div style="font-size:15px; font-weight:bold; margin-bottom:10px; color:#0b3873;">🚘 비교 차량 공통 조건</div>
        <table class="vehicle-table-mobile-primary">
            <tbody>
                <tr>
                    <th>차량명</th>
                    <th>옵션</th>
                    <th>차량가</th>
                </tr>
                <tr>
                    <td>{car_name}</td>
                    <td>{car_option_display}</td>
                    <td>{car_price_display_html}</td>
                </tr>
            </tbody>
        </table>
        <table class="vehicle-table-mobile-secondary">
            <tbody>
                <tr>
                    <th>계약기간</th>
                    <th>약정거리</th>
                    <th>유종</th>
                    <th>CC</th>
                </tr>
                <tr>
                    <td>{months}개월</td>
                    <td>{mileage}</td>
                    <td>{car_shape if fuel_text == "휘발유/전기" else fuel_text}</td>
                    <td>{cc_raw_text}</td>
                </tr>
            </tbody>
        </table>
    </div>
    """, unsafe_allow_html=True)

# 고객/영업자 할부 조건 설정표 노출
condition_product_label = "리스" if finance_mode == "lease" else "렌트"
condition_resale_class = "lease-highlight" if finance_mode == "lease" else "rent-highlight"
if visible_sections.get("installment_condition", True):
    st.markdown(f"""
        <div class="common-info-box">
            <div style="font-size:15px; font-weight:bold; margin-bottom:10px; color:#0b3873;">
                📋 할부 조건 설정
            </div>
            <table class="common-table client-condition-table">
                <thead>
                    <tr>
                        <th>법인 여부</th>
                        <th>할부 선납금</th>
                        <th>할부 금리</th>
                        <th>연 보험료</th>
                        <th>할부 잔존가치</th>
                        <th class="{condition_resale_class}">{condition_product_label} 잔존가치</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>{"O" if is_corporate else "X"}</td>
                        <td>{installment_prepaid:,} 원</td>
                        <td>{installment_rate:g}%</td>
                        <td>{insurance_annual:,} 원</td>
                        <td>{installment_resale_pct:g}%</td>
                        <td class="{condition_resale_class}">{rent_resale_pct:g}%</td>
                    </tr>
                </tbody>
            </table>
        </div>
    """, unsafe_allow_html=True)

# ==========================================
# [📊 MAIN VISUAL] 대칭형 비교 테이블
# ==========================================
selected_summary_views = []
if visible_sections.get("summary", True) and visible_sections.get("summary_return", True):
    selected_summary_views.append("return")
if visible_sections.get("summary", True) and visible_sections.get("summary_takeover", True):
    selected_summary_views.append("takeover")

if selected_summary_views:
    if visible_sections.get("common", True) or visible_sections.get("installment_condition", True):
        render_output_section_gap()
    summary_cols = st.columns(len(selected_summary_views))
    summary_col_map = dict(zip(selected_summary_views, summary_cols))

    # 1. 반납형 테이블
    if "return" in summary_col_map:
        with summary_col_map["return"]:
            st.markdown('<div class="excel-header-blue">카프리오 비교 프로그램 (반납형)</div>', unsafe_allow_html=True)
            
            inst_total_cost_ret = installment_prepaid + (inst_monthly_pay * months) + installment_interest + reg_tax + total_tax + total_ins - car_sell_value
            if finance_mode == "lease":
                rent_total_cost_ret = (rent_monthly_pay * months) + rent_deposit + total_ins + lease_extra_tax_total
                ret_product_rows = f"""
                {"<tr><td class='font-bold'>취등록세</td><td>"+format(reg_tax,",")+" 원</td><td rowspan='2' class='bg-light text-blue' style='vertical-align:middle;'>월 리스료 포함</td></tr><tr><td class='font-bold'>자동차세</td><td>"+format(total_tax,",")+" 원</td></tr>" if lease_tax_included else f"<tr><td class='font-bold'>취등록세</td><td>{reg_tax:,} 원</td><td>월 리스료 포함</td></tr><tr><td class='font-bold'>자동차세</td><td>{total_tax:,} 원</td><td>{lease_extra_tax_display}</td></tr>"}
                <tr><td class="font-bold">보험료</td><td>{total_ins:,} 원</td><td>{total_ins:,} 원</td></tr>
                <tr class="maturity-section-start"><td class="maturity-sale-label">만기 차량 매각</td><td class="maturity-sale-value">-{car_sell_value:,} 원</td><td>-</td></tr>
                <tr><td class="font-bold">-</td><td>-</td><td>-</td></tr>
                """
                ret_product_rows = textwrap.dedent(ret_product_rows).strip()
            else:
                rent_total_cost_ret = (rent_monthly_pay * months) + rent_deposit
                ret_product_rows = f"""
                <tr><td class="font-bold">취등록세</td><td>{reg_tax:,} 원</td><td rowspan="3" class="bg-light text-blue" style="vertical-align:middle;">월 렌트료<br>포함</td></tr>
                <tr><td class="font-bold">자동차세</td><td>{total_tax:,} 원</td></tr>
                <tr><td class="font-bold">보험료</td><td>{total_ins:,} 원</td></tr>
                <tr class="maturity-section-start"><td class="maturity-sale-label">만기 차량 매각</td><td class="maturity-sale-value">-{car_sell_value:,} 원</td><td>-</td></tr>
                <tr><td class="font-bold">-</td><td>-</td><td>-</td></tr>
                """
                ret_product_rows = textwrap.dedent(ret_product_rows).strip()
            diff_ret = inst_total_cost_ret - rent_total_cost_ret
            
            html_ret = f"""
            <table class="pure-table">
                <tr><th style="width:34%;">세부 항목</th><th style="width:33%;">일반 할부</th><th style="width:33%;">{finance_product_label}(반납형)</th></tr>
                <tr><td class="font-bold">선납금</td><td>{installment_prepaid:,} 원</td><td>{rent_deposit:,} 원</td></tr>
                <tr><td class="font-bold">(월)납입금<br><span style="color:red; font-size:10px; display:block; margin-top:-2px; line-height:1;">(선납금 제외)</span></td><td>{inst_monthly_pay:,} 원</td><td>{rent_monthly_pay:,} 원</td></tr>
                <tr><td class="font-bold">할부이자</td><td>{installment_interest:,} 원</td><td>-</td></tr>
                {ret_product_rows}
                <tr class="bg-light font-bold"><td>📊 월 평균 환산 비용</td><td>{int(inst_total_cost_ret/months):,} 원</td><td>{int(rent_total_cost_ret/months):,} 원</td></tr>
                <tr class="bg-light font-bold" style="background-color:#e9ecef;"><td>💰 총 투입 비용</td><td>{inst_total_cost_ret:,} 원</td><td>{rent_total_cost_ret:,} 원</td></tr>
            </table>
            """
            st.markdown(textwrap.dedent(html_ret).strip(), unsafe_allow_html=True)
            
            st.markdown('<div class="caprio-result-spacer"></div>', unsafe_allow_html=True)
            if diff_ret > 0:
                st.markdown(f'<div class="excel-green">🏆 {finance_product_label} 선택 시 할부 대비 {diff_ret:,}원 절감!</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="excel-red">할부 이용이 {abs(diff_ret):,}원 더 유리합니다.</div>', unsafe_allow_html=True)

            st.markdown('<div class="mobile-compare-gap"></div>', unsafe_allow_html=True)

    # 2. 인수형 테이블
    if "takeover" in summary_col_map:
        with summary_col_map["takeover"]:
            st.markdown('<div class="excel-header-blue">카프리오 비교 프로그램 (인수형)</div>', unsafe_allow_html=True)
            
            inst_total_cost_ins = installment_prepaid + (inst_monthly_pay * months) + installment_interest + reg_tax + total_tax + total_ins
            if finance_mode == "lease":
                rent_total_cost_ins = (rent_monthly_pay * months) + rent_takeover_price + rent_takeover_tax + rent_deposit + total_ins + lease_extra_tax_total
                ins_tax_row_value = f"{rent_takeover_tax:,} 원"
                ins_product_rows = f"""
                {"<tr><td class='font-bold'>취등록세</td><td>"+format(reg_tax,",")+" 원</td><td rowspan='2' class='bg-light text-blue' style='vertical-align:middle;'>월 리스료 포함</td></tr><tr><td class='font-bold'>자동차세</td><td>"+format(total_tax,",")+" 원</td></tr>" if lease_tax_included else f"<tr><td class='font-bold'>취등록세</td><td>{reg_tax:,} 원</td><td>월 리스료 포함</td></tr><tr><td class='font-bold'>자동차세</td><td>{total_tax:,} 원</td><td>{lease_extra_tax_display}</td></tr>"}
                <tr><td class="font-bold">보험료</td><td>{total_ins:,} 원</td><td>{total_ins:,} 원</td></tr>
                """
                ins_product_rows = textwrap.dedent(ins_product_rows).strip()
            else:
                rent_total_cost_ins = (rent_monthly_pay * months) + rent_takeover_price + rent_takeover_tax + rent_deposit
                ins_tax_row_value = f"{rent_takeover_tax:,} 원"
                ins_product_rows = f"""
                <tr><td class="font-bold">취등록세</td><td>{reg_tax:,} 원</td><td rowspan="3" class="bg-light text-blue" style="vertical-align:middle;">월 렌트료<br>포함</td></tr>
                <tr><td class="font-bold">자동차세</td><td>{total_tax:,} 원</td></tr>
                <tr><td class="font-bold">보험료</td><td>{total_ins:,} 원</td></tr>
                """
                ins_product_rows = textwrap.dedent(ins_product_rows).strip()
            diff_ins = inst_total_cost_ins - rent_total_cost_ins

            html_ins = f"""
            <table class="pure-table">
                <tr><th style="width:34%;">세부 항목</th><th style="width:33%;">일반 할부</th><th style="width:33%;">{finance_product_label}(인수형)</th></tr>
                <tr><td class="font-bold">선납금</td><td>{installment_prepaid:,} 원</td><td>{rent_deposit:,} 원</td></tr>
                <tr><td class="font-bold">(월)납입금<br><span style="color:red; font-size:10px; display:block; margin-top:-2px; line-height:1;">(선납금 제외)</span></td><td>{inst_monthly_pay:,} 원</td><td>{rent_monthly_pay:,} 원</td></tr>
                <tr><td class="font-bold">할부이자</td><td>{installment_interest:,} 원</td><td>-</td></tr>
                {ins_product_rows}
                <tr class="maturity-section-start"><td class="font-bold">만기 인수금</td><td>-</td><td>{rent_takeover_price:,} 원</td></tr>
                <tr><td class="font-bold">인수 시 취등록세</td><td>-</td><td>{ins_tax_row_value}</td></tr>
                <tr class="bg-light font-bold"><td>📊 월 평균 환산 비용</td><td>{int(inst_total_cost_ins/months):,} 원</td><td>{int(rent_total_cost_ins/months):,} 원</td></tr>
                <tr class="bg-light font-bold" style="background-color:#e9ecef;"><td>💰 총 투입 비용</td><td>{inst_total_cost_ins:,} 원</td><td>{rent_total_cost_ins:,} 원</td></tr>
            </table>
            """
            st.markdown(textwrap.dedent(html_ins).strip(), unsafe_allow_html=True)
            
            st.markdown('<div class="caprio-result-spacer"></div>', unsafe_allow_html=True)
            if diff_ins > 0:
                st.markdown(f'<div class="excel-green">🏆 {finance_product_label} 선택 시 할부 대비 {diff_ins:,}원 절감!</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="excel-red">할부 인수가 총 {abs(diff_ins):,}원 더 유리합니다.</div>', unsafe_allow_html=True)

if visible_sections.get("rate_table", True):
    if (visible_sections.get("common", True) or visible_sections.get("installment_condition", True) or selected_summary_views):
        render_output_section_gap()
    # ==========================================
    # [📊 BOTTOM] 검증 요율표 구역
    # ==========================================
    st.markdown('<div class="excel-header-gray">💻 내부 데이터 산출 요율 검증표</div>', unsafe_allow_html=True)
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)

    with m_col1:
        st.markdown('''
    **■ 잔존가치 예상표** 
    <span style="color:#ff7a7a; font-size:10px;">*가솔린 무사고 기준</span>
    ''', unsafe_allow_html=True)

        st.markdown(f"""
        <table class="matrix-table">
            <tr><th>구분</th><th>24개월</th><th>36개월</th><th>48개월</th><th>60개월</th></tr>
            <tr><td>1만KM</td><td class="{resale_24_1}">78%</td><td class="{resale_36_1}">70%</td><td class="{resale_48_1}">63%</td><td class="{resale_60_1}">56%</td></tr>
            <tr><td>1.5만KM</td><td class="{resale_24_15}">75%</td><td class="{resale_36_15}">67%</td><td class="{resale_48_15}">60%</td><td class="{resale_60_15}">53%</td></tr>
            <tr><td>2만KM</td><td class="{resale_24_2}">72%</td><td class="{resale_36_2}">64%</td><td class="{resale_48_2}">57%</td><td class="{resale_60_2}">50%</td></tr>
            <tr><td>3만KM</td><td class="{resale_24_3}">65%</td><td class="{resale_36_3}">55%</td><td class="{resale_48_3}">48%</td><td class="{resale_60_3}">40%</td></tr>
        </table>
        """, unsafe_allow_html=True)

        st.markdown(
            """
            <div style="margin-top:6px; margin-bottom:10px; margin-left:0px; line-height:1.25;">
                <span style="color:#ff7a7a; font-size:11px; font-weight:600;">
                    * 차량별 상이 · 시세 확인 필수
                </span>
            </div>
            """,
            unsafe_allow_html=True
        )


    with m_col2:
        st.markdown("**■ 신용별 할부이자**")
        st.markdown(f"""
        <table class="matrix-table">
            <tr><th>구분</th><th>할부이자</th></tr>
            <tr class="{rate_900_over}"><td>900점 초과</td><td>3.5 ~ 4.8%</td></tr>
            <tr class="{rate_801_900}"><td>801 ~ 900점</td><td>4.9 ~ 6.9%</td></tr>
            <tr class="{rate_701_800}"><td>701 ~ 800점</td><td>7.0 ~ 8.9%</td></tr>
            <tr class="{rate_601_700}"><td>601 ~ 700점</td><td>9.0 ~ 11.9%</td></tr>
            <tr class="{rate_600_under}"><td>600점 이하</td><td>12.0 ~ 14.9%</td></tr>
        </table>
        """, unsafe_allow_html=True)

    with m_col3:
        st.markdown("**■ 자동차세 (연간)**")
        st.markdown(f"""
        <table class="matrix-table">
            <tr><th>구분</th><th>연간 비용</th></tr>
            <tr class="{tax_1000}"><td>1000CC 이하</td><td>₩ 104,000</td></tr>
            <tr class="{tax_1600}"><td>1600CC 이하</td><td>₩ 291,200</td></tr>
            <tr class="{tax_2000}"><td>2000CC 이하</td><td>₩ 520,000</td></tr>
            <tr class="{tax_2500}"><td>2500CC 이하</td><td>₩ 650,000</td></tr>
            <tr class="{tax_3000}"><td>3000CC 초과</td><td>₩ 780,000</td></tr>
            <tr class="{tax_ev}"><td>전기차</td><td>₩ 130,000</td></tr>
        </table>
        """, unsafe_allow_html=True)

    with m_col4:
        st.markdown("**■ 취등록세 감면율**")
        st.markdown(f"""
        <table class="matrix-table">
            <tr><th>구분</th><th>세율</th><th>감면 한도</th></tr>
            <tr class="{reg_general}"><td>일반</td><td>7%</td><td>-</td></tr>
            <tr class="{reg_light}"><td>경차</td><td>4%</td><td>75만 원</td></tr>
            <tr class="{reg_ev}"><td>전기/수소차</td><td>7%</td><td>140만 원</td></tr>
            <tr class="{reg_hybrid}"><td>하이브리드</td><td>7%</td><td>-</td></tr>
            <tr class="{reg_van}">
                <td>
                    승합차
                    <div style="color:red; font-size:10px; line-height:1; margin-top:-4px;">(9인승 이상 포함)</div>
                </td>
                <td>5%</td>
                <td>-</td>
            </tr>
        </table>
        """, unsafe_allow_html=True)



# ==========================================
# [할부 · 렌트 · 리스 비교표]
# ==========================================
if visible_sections.get("compare", True):
    selected_compare_methods = []
    if visible_sections.get("compare_installment", True):
        selected_compare_methods.append("installment")
    if visible_sections.get("compare_rent", True):
        selected_compare_methods.append("rent")
    if visible_sections.get("compare_lease", True):
        selected_compare_methods.append("lease")

    if len(selected_compare_methods) >= 2:
        if (visible_sections.get("common", True) or visible_sections.get("installment_condition", True) or selected_summary_views or visible_sections.get("rate_table", True)):
            render_output_section_gap()
        st.markdown('<div class="excel-header-gray compare-summary-title" style="width:55%;">🚗 할부 · 렌트 · 리스 비교표</div>', unsafe_allow_html=True)
        st.markdown(render_compare_summary_table(selected_compare_methods), unsafe_allow_html=True)

# ==========================================
# [나에게 맞는 방식 선택 가이드]
# ==========================================
# ==========================
# [나에게 맞는 방식 선택 가이드]
# ==========================================

GUIDE_STYLE_HTML = """
<style>
.mo-br{
    display:none;
}
@media (max-width:768px){
    .mo-br{
        display:block;
    }
    .installment-guide-list{
        padding-left:14px !important;
    }
}
.guide-wrap{
    width:100%;
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:18px;
    margin-top:12px;
}
.guide-mobile-carousel-shell{
    width:100%;
    overflow:visible;
}
.guide-swipe-hint{
    display:none !important;
}
.guide-card{
    width:100%;
    background:#ffffff;
    border:1px solid #d9e2ec;
    border-radius:8px;
    padding:18px;
    box-sizing:border-box;
}
.guide-title{
    font-size:23px;
    font-weight:800;
    color:#0b3873;
    margin-bottom:6px;
}
.guide-copy{
    font-size:18px;
    font-weight:700;
    color:#333;
    margin-bottom:12px;
    line-height:1.5;
}
.guide-subtitle{
    font-size:15px;
    font-weight:800;
    margin-bottom:6px;
}
.guide-list{
    font-size:14px;
    line-height:1.9;
    padding-left:18px;
    margin:0 0 12px 0;
}
.reality-box{
    background:#f4f6f8;
    border:1px solid #d9dee5;
    border-radius:6px;
    padding:12px;
}
.reality-title{
    font-size:18px;
    font-weight:800;
    margin-bottom:6px;
}
.reality-item{
    font-size:15px;
    line-height:1.7;
    margin-bottom:5px;
}
.match-card{
    margin-top:14px;
    border-radius:14px;
    padding:15px 16px;
    display:grid;
    grid-template-columns:1fr;
    gap:8px;
    align-items:start;
    box-sizing:border-box;
    border:1px solid rgba(0,0,0,0.08);
}
.match-icon{
    width:0;
    height:0;
    border-radius:999px;
    display:none;
    align-items:center;
    justify-content:center;
    font-size:33px;
    box-shadow:inset 0 0 0 1px rgba(255,255,255,0.3);
}
.match-title{
    font-size:18px;
    font-weight:900;
    margin-bottom:8px;
}
.match-list{
    margin:0;
    padding:0;
    list-style:none;
    font-size:14px;
    line-height:1.72;
}
.match-card > div{
    margin:0;
    padding:0;
}
.match-list li{
    margin-bottom:2px;
    padding-left:0;
    text-indent:0;
}
.match-title,
.match-list li{
    color:#333333;
}
.match-result{
    margin-top:9px;
    padding-top:8px;
    border-top:1px dashed rgba(255,255,255,0.35);
    font-size:16px;
    font-weight:900;
}
.match-installment{
    background:linear-gradient(135deg,#eaf4ff 0%,#f7fbff 100%);
    border-color:#b9d8ff;
}
.match-installment .match-icon{
    background:linear-gradient(135deg,#79b8ff,#2478dc);
}
.match-installment .match-result{
    color:#0b4f9c;
}
.match-rent{
    background:linear-gradient(135deg,#e8fff4 0%,#f7fffb 100%);
    border-color:#aee8cc;
}
.match-rent .match-icon{
    background:linear-gradient(135deg,#6fe7b2,#12a86f);
}
.match-rent .match-result{
    color:#08784f;
}
.match-lease{
    background:linear-gradient(135deg,#f0ebff 0%,#fbf9ff 100%);
    border-color:#cfc1ff;
}
.match-lease .match-icon{
    background:linear-gradient(135deg,#a68cff,#5d3fd3);
}
.match-lease .match-result{
    color:#5a35c9;
}
html.caprio-dark .match-card{
    border-color:#344255;
    box-shadow:0 8px 22px rgba(0,0,0,0.18);
}
html.caprio-dark .match-installment{
    background:linear-gradient(135deg,#0f3564 0%,#102337 100%);
    border-color:#2f6eac;
}
html.caprio-dark .match-rent{
    background:linear-gradient(135deg,#0c4a3d 0%,#102b26 100%);
    border-color:#1a846b;
}
html.caprio-dark .match-lease{
    background:linear-gradient(135deg,#2d256c 0%,#181d42 100%);
    border-color:#6555c8;
}
html.caprio-dark .match-title,
html.caprio-dark .match-list li{
    color:#ffffff !important;
}
html.caprio-dark .match-installment .match-result{
    color:#9fc7ff !important;
}
html.caprio-dark .match-rent .match-result{
    color:#76f0bd !important;
}
html.caprio-dark .match-lease .match-result{
    color:#b9a7ff !important;
}
@media (max-width:768px){
    .guide-mobile-carousel-shell{
        position:relative;
        width:100%;
        overflow:hidden;
        margin-top:12px;
    }
    .guide-wrap{
        display:flex !important;
        grid-template-columns:none !important;
        gap:0 !important;
        column-gap:0 !important;
        overflow-x:auto !important;
        overflow-y:hidden !important;
        scroll-snap-type:x mandatory !important;
        scroll-padding:0 !important;
        -webkit-overflow-scrolling:touch !important;
        overscroll-behavior-x:contain !important;
        touch-action:pan-x pan-y !important;
        padding:0 0 12px 0 !important;
        margin-top:0 !important;
        scrollbar-width:none !important;
    }
    .guide-wrap::-webkit-scrollbar{
        display:none !important;
    }
    .guide-wrap > .guide-card{
        flex:0 0 100% !important;
        width:100% !important;
        min-width:100% !important;
        max-width:100% !important;
        margin-left:0 !important;
        margin-right:0 !important;
    }
    .guide-wrap > .guide-card:last-child{
        margin-right:0 !important;
        scroll-snap-align:end !important;
    }
    .guide-card{
        flex:0 0 100% !important;
        width:100% !important;
        min-width:100% !important;
        max-width:100% !important;
        margin-right:0 !important;
        scroll-snap-align:start !important;
        scroll-snap-stop:always !important;
        box-sizing:border-box !important;
        padding:16px !important;
    }
    .guide-title{
        font-size:21px !important;
    }
    .guide-copy{
        font-size:17px !important;
        line-height:1.42 !important;
        margin-bottom:10px !important;
    }
    .guide-subtitle{
        font-size:16px !important;
        font-weight:800 !important;
        margin-bottom:7px !important;
    }
    .guide-list{
        font-size:13.5px !important;
        line-height:1.68 !important;
        margin-bottom:10px !important;
    }
    .reality-box{
        padding:11px !important;
    }
    .reality-title{
        font-size:16px !important;
        font-weight:800 !important;
        margin-bottom:7px !important;
    }
    .reality-item{
        font-size:13px !important;
        line-height:1.52 !important;
        margin-bottom:4px !important;
    }
    .guide-swipe-hint{
        position:absolute;
        left:50%;
        top:46%;
        transform:translate(-50%,-50%);
        z-index:999;
        pointer-events:none;
        display:flex !important;
        flex-direction:column;
        align-items:center;
        justify-content:center;
        gap:7px;
        opacity:0;
        animation:caprioSwipeHintWrap 6.4s ease-in-out 0.6s infinite both;
        will-change:opacity, transform;
    }
    .guide-swipe-hand{
        width:78px;
        height:78px;
        border-radius:999px;
        display:flex;
        align-items:center;
        justify-content:center;
        background:rgba(15,55,115,0.78);
        color:#ffffff;
        font-size:42px;
        box-shadow:0 16px 34px rgba(15,55,115,0.26);
        backdrop-filter:blur(6px);
        animation:caprioSwipeHandMove 3.0s ease-in-out 0.6s infinite both;
        will-change:opacity, transform;
    }
    .guide-swipe-text{
        padding:7px 12px;
        border-radius:999px;
        background:rgba(15,55,115,0.70);
        color:#ffffff;
        font-size:13px;
        font-weight:800;
        letter-spacing:-0.02em;
        white-space:nowrap;
        box-shadow:0 8px 20px rgba(15,55,115,0.16);
        backdrop-filter:blur(6px);
    }
    .guide-card{
        position:relative;
        z-index:1;
    }
    html.caprio-dark .guide-swipe-hand{
        background:rgba(92,142,220,0.70) !important;
        box-shadow:0 12px 28px rgba(0,0,0,0.28);
    }
    html.caprio-dark .guide-swipe-text{
        background:rgba(92,142,220,0.62) !important;
    }
    @keyframes caprioSwipeHintWrap{
        0%{opacity:0;}
        8%{opacity:0.84;}
        46%{opacity:0.84;}
        56%{opacity:0;}
        100%{opacity:0;}
    }
    @keyframes caprioSwipeHandMove{
        0%{transform:translateX(54px); opacity:0;}
        8%{transform:translateX(54px); opacity:0.9;}
        30%{transform:translateX(-54px); opacity:0.9;}
        38%{transform:translateX(-54px); opacity:0;}
        48%{transform:translateX(54px); opacity:0;}
        56%{transform:translateX(54px); opacity:0.9;}
        78%{transform:translateX(-54px); opacity:0.9;}
        88%{transform:translateX(-54px); opacity:0;}
        100%{transform:translateX(-54px); opacity:0;}
    }
    .match-card{
        display:block;
        margin-top:12px;
        grid-template-columns:1fr !important;
        padding:15px 16px !important;
        border-width:1.5px !important;
        box-shadow:0 10px 24px rgba(15,55,115,0.10) !important;
    }
    .match-icon{
        display:none !important;
    }
    .match-title{
        font-size:16px !important;
        font-weight:900 !important;
        margin-bottom:7px !important;
    }
    .match-list{
        font-size:14px !important;
        line-height:1.42 !important;
    }
    .match-list li{
        margin-bottom:0 !important;
        padding-bottom:0 !important;
    }
    .match-result{
        font-size:16px !important;
        padding-top:9px !important;
        margin-top:10px !important;
        letter-spacing:-0.02em;
    }
    html.caprio-dark .match-card{
        box-shadow:0 10px 28px rgba(0,0,0,0.26) !important;
    }
}


    /* [FINAL GAP CLEANUP] 요율표 내부 주석/소제목 겹침 방지 */
    @media (max-width: 768px) {
        .matrix-table {
            margin-bottom: 10px !important;
        }
    }
</style>
"""


def guide_card_installment():
    return """
<div class="guide-card">
<div class="guide-title">💳 [소유형] 할부 구매</div>
<div class="guide-copy">내 차라는 확실한 자산<br class="mo-br"> 오래도록 변함없이 타고 싶다면?</div>
<div class="guide-subtitle">✅ 할부 체크리스트</div>
<ol class="guide-list installment-guide-list">
<li>5~10년 이상 장기 보유할 목적이 확실해요.</li>
<li>취등록세와 같은 초기 목돈을 지출할 여력이 있어요.</li>
<li>명의가 개인 또는 법인 소유인 온전한 자산을 원해요.</li>
</ol>
<div class="reality-box">
<div class="reality-title">💡 현실 체크</div>
<div class="reality-item">🏠 <b>집 대출 한도 축소</b> : 내 명의로 대출이 잡히기 때문에,<br class="mo-br"> DSR 한도체크는 필수예요</div>
<div class="reality-item">💸 <b>부대 비용 발생</b> : 자동차세·취등록세·보험료 등<br class="mo-br"> 지속적인 비용이 발생해요.</div>
<div class="reality-item">🛡️ <b>자산 가치 관리</b> : 사고주의 & 관리를 통해<br class="mo-br"> 감가를 최소화하는게 중요해요.</div>
<div class="reality-item">🏢 <b>법인 시 주의</b> : 판매 시 부가세 10%가 발생하니<br class="mo-br"> 미리 대비해야해요!</div>
</div>
<div class="match-card match-installment">
<div class="match-icon">💳</div>
<div>
<div class="match-title">🔥 할부는 이런 경우 고민없이!</div>
<ul class="match-list">
<li>✔ 5년 이상 장기 보유 예정이며</li>
<li>✔ 사고·감가 리스크가 크게 부담되지 않고</li>
<li>✔ 차량가 30% 이상 초기비용 부담 가능하고</li>
<li>✔ DSR·대출한도 영향이 중요하지 않다면?</li>
</ul>
<div class="match-result">→ 할부가 잘 맞아요.</div>
</div>
</div>
</div>
"""


def guide_card_rent():
    return """
<div class="guide-card">
<div class="guide-title">🚗 [재테크형] 장기렌트</div>
<div class="guide-copy">대출 한도 보호와<br class="mo-br"> 차량 관리의 효율성을 동시에!</div>
<div class="guide-subtitle">✅ 렌트 체크리스트</div>
<ol class="guide-list">
<li>주택 마련 등을 위해 대출한도를 확보해야 해요.</li>
<li>3~5년마다 새 차량으로 교체하는 걸 선호해요.</li>
<li>정비·세금·사고처리 등 번거로운 일은 싫어요.</li>
</ol>
<div class="reality-box">
<div class="reality-title">💡 현실 체크</div>
<div class="reality-item">🔓 <b>대출 한도 영향 없음</b> : 렌트사 명의라<br class="mo-br"> 개인 대출 한도에 영향이 없어요.</div>
<div class="reality-item">💵 <b>세금 할증 없음</b> : 재산세 등 세금 인상은<br class="mo-br"> 걱정하지 않으셔도 괜찮아요.</div>
<div class="reality-item">🚫 <b>보험·사고 기록</b> : 사고 시, 면책금으로 해결하고<br class="mo-br"> 사고이력은 남지 않아요.</div>
<div class="reality-item">🗓️ <b>관리 비용 최소화</b> : 보험·세금이 모두 월 이용료로<br class="mo-br"> 추가비용 부담을 없애요!</div>
</div>
<div class="match-card match-rent">
<div class="match-icon">🚗</div>
<div>
<div class="match-title">🔥 렌트는 이런 경우 고민없이!</div>
<ul class="match-list">
<li>✔ 5년 이하 운행, 신차 교체를 선호하고</li>
<li>✔ 보험료가 높거나 사고이력이 부담되며</li>
<li>✔ 사고·세금·보험 처리를 간편한 걸 원하고</li>
<li>✔ DSR·대출한도 보호까지 신경 쓴다면?</li>
</ul>
<div class="match-result">→ 장기렌트가 잘 맞아요.</div>
</div>
</div>
</div>
"""


def guide_card_lease():
    return """
<div class="guide-card">
<div class="guide-title">✨ [이미지형] 리스</div>
<div class="guide-copy">품격은 일반 번호판으로,<br class="mo-br"> 초기 비용은 리스로 합리적으로!</div>
<div class="guide-subtitle">✅ 리스 체크리스트</div>
<ol class="guide-list">
<li>취등록세 초기 목돈 지출이 부담스러워요.</li>
<li>하·허·호 대신 일반 번호판을 원해요.</li>
<li>렌트보다 자차와 유사한 만족감을 원해요.</li>
</ol>
<div class="reality-box">
<div class="reality-title">💡 현실 체크</div>
<div class="reality-item">📉 <b>개인 보험요율 유지</b> : 무사고 경력이 길고<br class="mo-br">보험료가 낮다면 유리할 수 있어요.</div>
<div class="reality-item">✨ <b>일반 번호판</b> : 자가용과 같은 번호판을 유지해요.</div>
<div class="reality-item">💰 <b>월 납입금</b> : 부담을 줄여 이용할 수 있어요.</div>
<div class="reality-item">💵 <b>세금 인상</b> : 재산세 등 세금 인상은<br class="mo-br"> 걱정하지 않으셔도 괜찮아요!</div>
</div>
<div class="match-card match-lease">
<div class="match-icon">✨</div>
<div>
<div class="match-title">🔥 리스는 이런 경우 고민없이!</div>
<ul class="match-list">
<li>✔ 초기비용은 줄이고 싶고</li>
<li>✔ 무사고 경력이 길어 보험료가 낮으며</li>
<li>✔ 할부보다 대출 영향은 줄이고 싶다면</li>
</ul>
<div class="match-result">→ 리스가 잘 맞아요.</div>
</div>
</div>
</div>
"""


if visible_sections.get("guide", True):
    selected_guide_cards = []

    if visible_sections.get("guide_installment", True):
        selected_guide_cards.append(guide_card_installment())

    if visible_sections.get("guide_rent", True):
        selected_guide_cards.append(guide_card_rent())

    if visible_sections.get("guide_lease", True):
        selected_guide_cards.append(guide_card_lease())

    if selected_guide_cards:
        if (
            visible_sections.get("common", True)
            or visible_sections.get("installment_condition", True)
            or selected_summary_views
            or visible_sections.get("rate_table", True)
            or (
                visible_sections.get("compare", True)
                and len(selected_compare_methods) >= 2
            )
        ):
            render_output_section_gap()

        st.markdown(
            '<div class="excel-header-gray">🚗 나에게 맞는 방식 선택 가이드</div>',
            unsafe_allow_html=True
        )

        guide_cards_html = "".join(selected_guide_cards)
        guide_html = f"""{GUIDE_STYLE_HTML}
<div class="guide-mobile-carousel-shell">
    <div class="guide-swipe-hint" aria-hidden="true">
        <div class="guide-swipe-hand">☝️</div>
        <div class="guide-swipe-text">왼쪽으로 밀어 확인하세요</div>
    </div>
    <div class="guide-wrap">{guide_cards_html}</div>
</div>
"""

        st.markdown(guide_html, unsafe_allow_html=True)

if visible_sections.get("outro", True):
    if (
        visible_sections.get("common", True)
        or visible_sections.get("installment_condition", True)
        or selected_summary_views
        or visible_sections.get("rate_table", True)
        or (
            visible_sections.get("compare", True)
            and len(selected_compare_methods) >= 2
        )
        or (
            visible_sections.get("guide", True)
            and (
                visible_sections.get("guide_installment", True)
                or visible_sections.get("guide_rent", True)
                or visible_sections.get("guide_lease", True)
            )
        )
    ):
        render_output_section_gap()
    render_customer_outro_card()

st.markdown("""
<div class="caprio-footer-note">
    <div class="caprio-footer-guide">
        ※ 본 비교 결과는 입력 조건 및 금융사 기준에 따른 참고용 자료이며, 실제 승인·금리·잔존가치·보험조건 등에 따라 최종 견적은 달라질 수 있습니다.
    </div>
    <div>
        © (주)카프리오. All rights reserved.<br>
        카프리오 비교 프로그램·디자인·산출 로직의 무단 복제·배포·도용을 금지하며, 위반 시 법적 대응이 진행될 수 있습니다.
    </div>
</div>
""", unsafe_allow_html=True)
