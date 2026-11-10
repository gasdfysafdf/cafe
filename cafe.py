import streamlit as st
from supabase import create_client, Client
import random
import time

# --- Supabase 연결 ---
@st.cache_resource
def init_connection():
    url = "https://ccmsgkiqyolowhhgkxnl.supabase.co"
    key = "sb_publishable_B3WFuDeKlbBQRWjaBXbNXQ_QgLp0JP0"
    return create_client(url, key)

supabase: Client = init_connection()
PLAYER_NAME = 'player1'

# --- 세션 상태 초기화 (게임 데이터 저장) ---
if 'current_cup' not in st.session_state:
    st.session_state.current_cup = [] # 유저가 넣은 재료 ID 리스트
if 'current_order' not in st.session_state:
    st.session_state.current_order = None # 현재 손님의 주문 (menu_id)
if 'message' not in st.session_state:
    st.session_state.message = "영업을 시작하세요!"

# --- DB 데이터 불러오기 ---
def get_menus():
    return supabase.table('menus').select('*').execute().data

def get_ingredients():
    return supabase.table('ingredients').select('*').order('id').execute().data

def get_recipe(menu_id):
    return supabase.table('recipes').select('ingredient_id').eq('menu_id', menu_id).order('step_order').execute().data

def get_player_info():
    return supabase.table('players').select('money').eq('username', PLAYER_NAME).execute().data[0]

# --- 게임 로직 함수 ---
def new_customer():
    menus = get_menus()
    st.session_state.current_order = random.choice(menus)
    st.session_state.current_cup = []
    st.session_state.message = f"손님: '{st.session_state.current_order['name']} 한 잔 주세요!'"

def add_ingredient(ing_id):
    st.session_state.current_cup.append(ing_id)

def throw_trash():
    if len(st.session_state.current_cup) > 0:
        # DB RPC 호출 (실패 처리 - 재고만 깎임)
        supabase.rpc('serve_drink', {
            'p_username': PLAYER_NAME,
            'p_menu_id': st.session_state.current_order['id'],
            'p_used_ingredients': st.session_state.current_cup,
            'p_is_success': False
        }).execute()
        st.session_state.current_cup = []
        st.session_state.message = "으악 망했다! 쓰레기통에 버렸습니다. (재고 낭비)"
    else:
        st.session_state.message = "버릴 컵이 비어있습니다."

def serve_drink():
    if not st.session_state.current_order:
        return

    # 정답 레시피 가져오기
    correct_recipe_data = get_recipe(st.session_state.current_order['id'])
    correct_recipe = [item['ingredient_id'] for item in correct_recipe_data]
    
    # 레시피 검증 (순서까지 완벽히 맞아야 함)
    is_success = (st.session_state.current_cup == correct_recipe)
    
    # DB RPC 호출 (트랜잭션 처리)
    response = supabase.rpc('serve_drink', {
        'p_username': PLAYER_NAME,
        'p_menu_id': st.session_state.current_order['id'],
        'p_used_ingredients': st.session_state.current_cup,
        'p_is_success': is_success
    }).execute()

    if is_success:
        st.session_state.message = f"완벽해! +{st.session_state.current_order['price']}원 획득!"
        # 손님 돌아가고 컵 비우기
        st.session_state.current_order = None
        st.session_state.current_cup = []
    else:
        st.session_state.message = "손님: 이게 무슨 맛인가요?! 환불해주세요! 😡 (실패)"
        # 실패 시 컵은 그대로 두거나 버리도록 유도

# --- UI 레이아웃 ---
st.set_page_config(page_title="☕ 갓썸 카페 타이쿤", layout="wide")

st.title("☕ 갓썸 카페 타이쿤")

# 상단 상태바 (돈 & 메세지)
player = get_player_info()
col_status1, col_status2 = st.columns([2, 1])
with col_status1:
    st.info(f"📢 알림: {st.session_state.message}")
with col_status2:
    st.success(f"💰 현재 잔고: {player['money']:,} 원")

st.markdown("---")

# 메인 화면 영역
col_desk, col_inventory = st.columns([3, 1])

with col_desk:
    st.subheader("👨‍💼 메인 데스크")
    
    # 손님 주문 영역
    if st.session_state.current_order is None:
        if st.button("🔔 다음 손님 받기", use_container_width=True):
            new_customer()
            st.rerun()
    else:
        st.warning(f"🗣️ 현재 주문: **{st.session_state.current_order['name']}**")
    
    st.write("### 🗄️ 재료 선택 (클릭하여 컵에 담기)")
    ingredients = get_ingredients()
    
    # 재료 버튼들 (가로로 배치)
    cols = st.columns(len(ingredients))
    for i, ing in enumerate(ingredients):
        with cols[i]:
            # 재고가 없으면 비활성화 구현도 가능
            if st.button(f"{ing['icon']}\n{ing['name']}", key=f"ing_{ing['id']}", use_container_width=True):
                add_ingredient(ing['id'])
                st.rerun()

    st.markdown("---")
    st.write("### 🥤 현재 컵 (제조 중)")
    
    # 현재 컵에 담긴 재료 시각화
    if st.session_state.current_cup:
        cup_display = []
        for c_id in st.session_state.current_cup:
            # ID로 이름 찾기
            ing_name = next(item['icon'] + item['name'] for item in ingredients if item['id'] == c_id)
            cup_display.append(ing_name)
        
        st.markdown(f"<h3 style='text-align: center;'>{' ➡️ '.join(cup_display)}</h3>", unsafe_allow_html=True)
    else:
        st.write("컵이 비어있습니다.")

    # 액션 버튼
    col_serve, col_trash = st.columns(2)
    with col_serve:
        if st.button("🛎️ 서빙하기", type="primary", use_container_width=True):
            serve_drink()
            st.rerun()
    with col_trash:
        if st.button("🗑️ 쓰레기통에 버리기", use_container_width=True):
            throw_trash()
            st.rerun()

# 우측 사이드바: 실시간 재고 현황
with col_inventory:
    st.subheader("📦 실시간 재고")
    for ing in ingredients:
        st.write(f"{ing['icon']} {ing['name']}: {ing['stock']}개")
        if ing['stock'] < 10:
            st.error("재고 부족 위험!")

    st.markdown("---")
    st.write("📜 **레시피 힌트**")
    st.caption("아메리카노: 물 -> 에스프레소")
    st.caption("아이스 아메리카노: 얼음 -> 물 -> 에스프레소")
    st.caption("카페라떼: 에스프레소 -> 우유")
