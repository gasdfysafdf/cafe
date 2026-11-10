import random
import time

import streamlit as st
from supabase import create_client, Client

st.set_page_config(page_title="☕ 갓썸 카페 타이쿤", layout="wide")

# ---------------- Supabase ----------------
@st.cache_resource
def init_connection():
    return create_client("https://ccmsgkiqyolowhhgkxnl.supabase.co", "sb_publishable_B3WFuDeKlbBQRWjaBXbNXQ_QgLp0JP0")

supabase: Client = init_connection()
PLAYER_NAME = "player1"
ARRIVE_SEC = 2.5      # 손님이 걸어 들어오는 시간
LEAVE_SEC = 2.5       # 손님이 나가는 시간
PATIENCE_SEC = 45     # 주문 후 인내심 (초)
MAX_CUP = 6

@st.cache_data(ttl=30)
def load_menus_recipes():
    menus = supabase.table("menus").select("*").execute().data
    rec = {}
    rows = supabase.table("recipes").select("menu_id,ingredient_id,step_order").order("step_order").execute().data
    for r in rows:
        rec.setdefault(r["menu_id"], []).append(r["ingredient_id"])
    return menus, rec

def get_ingredients():
    return supabase.table("ingredients").select("*").order("id").execute().data

def get_money():
    return supabase.table("players").select("money").eq("username", PLAYER_NAME).execute().data[0]["money"]

def call_serve(menu_id, cup, ok):
    supabase.rpc("serve_drink", {
        "p_username": PLAYER_NAME, "p_menu_id": menu_id,
        "p_used_ingredients": cup, "p_is_success": ok,
    }).execute()

# ---------------- 상태 ----------------
S = st.session_state
S.setdefault("cup", [])
S.setdefault("cust", None)          # 현재 손님 dict
S.setdefault("last_leave", time.time() - 10)
S.setdefault("msg", "영업 시작! 손님을 기다리는 중...")
S.setdefault("served", 0)
S.money = get_money()
menus, recipes = load_menus_recipes()
ings = get_ingredients()
ing_by_id = {i["id"]: i for i in ings}

COLORS = {"물": "#8ecae6", "에스프레소": "#3b2314", "얼음": "#d9f2ff", "우유": "#fff4e0",
          "시럽": "#c9772e", "초코": "#5a3420", "휘핑": "#ffffff", "카라멜": "#d08a3a"}
def color_of(ing):
    return COLORS.get(ing["name"], f"hsl({ing['id'] * 67 % 360},55%,55%)")

FACES = ["🧑", "👩", "👨", "👵", "🧔", "👧", "👴", "🧑‍🦰"]
SHIRTS = ["#ff6b57", "#ffcf4a", "#6c8ef5", "#b583e8", "#4cc38a", "#f58fb3"]

# ---------------- 게임 로직 (콜백) ----------------
def take_order():
    c, now = S.cust, time.time()
    if not c or c["t_leave"]:
        S.msg = "받을 주문이 없어요."
    elif c["t_order"]:
        S.msg = "이미 주문을 받았어요. 음료를 만들어 보세요!"
    elif now - c["t_spawn"] < ARRIVE_SEC:
        S.msg = "손님이 아직 걸어오는 중이에요."
    else:
        c["t_order"] = now
        S.msg = f"주문 접수! '{c['menu']['name']}' 만들어 주세요."

def add_ingredient(ing_id):
    if len(S.cup) < MAX_CUP:
        S.cup.append(ing_id)

def throw_trash():
    if not S.cup:
        S.msg = "버릴 컵이 비어있습니다."
        return
    mid = S.cust["menu"]["id"] if S.cust else menus[0]["id"]  # 손님 없을 때도 재고 차감 기록
    call_serve(mid, S.cup, False)
    S.cup = []
    S.msg = "으악 망했다! 쓰레기통에 버렸습니다. (재고 낭비)"

def serve_drink():
    c = S.cust
    if not c or not c["t_order"] or c["t_leave"]:
        S.msg = "먼저 손님의 주문을 받으세요!"
        return
    if not S.cup:
        S.msg = "컵이 비어있어요."
        return
    ok = S.cup == recipes.get(c["menu"]["id"], [])   # 순서까지 일치해야 성공
    call_serve(c["menu"]["id"], S.cup, ok)
    S.cup = []
    if ok:
        c["t_leave"], c["happy"] = time.time(), True
        S.served += 1
        S.msg = f"완벽해! +{c['menu']['price']:,}원 획득!"
    else:
        c["penalty"] += 20
        S.msg = "손님: 이게 무슨 맛인가요?! 😡 (버리고 다시 만들어 보세요)"

# ---------------- 스타일 ----------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Jua&display=swap');
html, body, [class*="st-"], button { font-family: 'Jua', sans-serif !important; }
.block-container { padding-top: 1rem; }
.scene { position: relative; height: 430px; overflow: hidden; border-radius: 18px; border: 4px solid #3a2318;
  background: linear-gradient(#0000 0 60%, #0000 60%), linear-gradient(#9ad3c2 0 58%, #2e6b63 58% 66%, #f2e3c6 66%); }
.floor { position:absolute; left:0; right:0; top:66%; bottom:0;
  background: conic-gradient(#f2e3c6 25%,#d9b98a 0 50%,#f2e3c6 0 75%,#d9b98a 0) 0 0/60px 60px; }
.win { position:absolute; left:50px; top:40px; width:150px; height:140px; border:9px solid #6b3f2a;
  border-radius:75px 75px 4px 4px; background:linear-gradient(#ffe9a8,#bfe6f5); font-size:42px; text-align:right; }
.board { position:absolute; right:40px; top:30px; width:230px; padding:10px 18px; background:#2a1d17; color:#fff;
  border:8px solid #6b3f2a; border-radius:8px; font-size:17px; }
.board h4 { color:#ffcf4a; margin:0 0 4px; font-weight:400; font-size:20px; }
.board p { display:flex; justify-content:space-between; margin:0; line-height:1.6; }
.counter { position:absolute; left:0; right:0; bottom:0; height:120px; z-index:5;
  background:linear-gradient(#a8693f 0 16px,#6b3f2a 16px); box-shadow:0 -6px 14px #0004; }
.deco { position:absolute; bottom:105px; font-size:48px; z-index:6; }
.cust { position:absolute; bottom:90px; width:110px; height:230px; z-index:3; }
.cust .head { position:absolute; left:0; right:0; top:20px; text-align:center; font-size:74px; line-height:1; z-index:2; }
.cust .body { position:absolute; left:14px; right:14px; top:100px; bottom:0; border-radius:34px 34px 0 0; }
.cust.walk .head { animation: bob .45s infinite; }
.cust.wait .head { animation: wig 1s infinite; }
.bubble { position:absolute; left:40px; bottom:100%; margin-bottom:-14px; min-width:150px; padding:8px 14px; background:#fff;
  border:3px solid #3a2318; border-radius:16px; font-size:17px; text-align:center; white-space:nowrap; z-index:4; }
.pat { height:7px; margin-top:6px; background:#e8dccb; border-radius:8px; overflow:hidden; }
.pat i { display:block; height:100%; }
.hudbar { display:flex; justify-content:space-between; gap:12px; margin-bottom:8px; font-size:20px; }
.hudbar span { background:#2a1d17; color:#ffcf4a; padding:6px 16px; border-radius:14px; }
.hudbar .msg { flex:1; color:#fff; }
.cup { width:130px; height:150px; margin:0 auto; border:5px solid #aaa; border-top:0; border-radius:0 0 30px 30px;
  background:#00000010; overflow:hidden; display:flex; flex-direction:column-reverse; }
.cup div { flex:0 0 16.66%; }
.cupicons { text-align:center; font-size:26px; min-height:36px; margin-top:6px; }
div.stButton > button { height: 78px; border-radius: 16px; border: 3px solid #3a2318; font-size: 18px;
  box-shadow: 0 5px 0 #3a2318; transition: transform .1s; }
div.stButton > button:hover:not(:disabled) { transform: translateY(-4px); }
div.stButton > button:active:not(:disabled) { transform: translateY(3px); box-shadow: 0 1px 0 #3a2318; }
@keyframes walkin  { from { left:-15%; } to { left:42%; } }
@keyframes walkout { from { left:42%; } to { left:120%; } }
@keyframes bob { 50% { transform: translateY(-8px); } }
@keyframes wig { 0%,100% { transform: rotate(-4deg); } 50% { transform: rotate(4deg); } }
</style>
""", unsafe_allow_html=True)

st.title("☕ 갓썸 카페 타이쿤")

# ---------------- 실시간 장면 (1초마다 자동 갱신) ----------------
@st.fragment(run_every=1)
def scene():
    now = time.time()
    c = S.cust

    # 새 손님 입장
    if c is None and now - S.last_leave > 3:
        S.cust = c = {"menu": random.choice(menus), "face": random.choice(FACES), "shirt": random.choice(SHIRTS),
                      "t_spawn": now, "t_order": None, "t_leave": None, "happy": False, "penalty": 0}
        S.msg = "손님이 들어옵니다..."
    # 퇴장 완료
    if c and c["t_leave"] and now - c["t_leave"] > LEAVE_SEC:
        S.cust, S.last_leave, c = None, now, None
    # 인내심 바닥 → 화나서 퇴장
    pat = 100.0
    if c and c["t_order"] and not c["t_leave"]:
        pat = 100 - (now - c["t_order"]) / PATIENCE_SEC * 100 - c["penalty"]
        if pat <= 0:
            c["t_leave"], c["happy"] = now, False
            S.cup, S.msg = [], "손님이 화나서 떠났어요! 😡"
            st.rerun()

    cust_html = ""
    if c:
        if c["t_leave"]:
            el = min(now - c["t_leave"], LEAVE_SEC)
            style, cls = f"animation:walkout {LEAVE_SEC}s linear forwards;animation-delay:-{el:.2f}s;left:42%;", "walk"
            text = "완벽해요! 😍" if c["happy"] else "흥! 안 마셔요!"
            face = "😍" if c["happy"] else "😡"
        elif now - c["t_spawn"] < ARRIVE_SEC:
            el = now - c["t_spawn"]
            style, cls = f"animation:walkin {ARRIVE_SEC}s linear forwards;animation-delay:-{el:.2f}s;left:-15%;", "walk"
            text, face = "", c["face"]
        elif c["t_order"]:
            col = "#4cc38a" if pat > 50 else "#ffcf4a" if pat > 25 else "#e0452f"
            style, cls = "left:42%;", "wait"
            text = (f"{c['menu']['name']} 한 잔 주세요!<div class='pat'><i style='width:{max(pat,0):.0f}%;background:{col}'></i></div>")
            face = "😡" if c["penalty"] else c["face"]
        else:
            style, cls, text, face = "left:42%;", "wait", "🔔 주문할게요!", c["face"]
        bubble = f"<div class='bubble'>{text}</div>" if text else ""
        cust_html = (f"<div class='cust {cls}' style='{style}'>{bubble}<div class='head'>{face}</div>"
                     f"<div class='body' style='background:{c['shirt']}'></div></div>")

    board = "".join(f"<p><span>{m['name']}</span><span>{m['price']:,}</span></p>" for m in menus)
    st.markdown(f"""
    <div class='hudbar'><span>💰 {S.money:,}원</span><span>☕ {S.served}잔</span><span class='msg'>📢 {S.msg}</span></div>
    <div class='scene'>
      <div class='floor'></div>
      <div class='win'>☀️</div>
      <div class='board'><h4>오늘의 메뉴</h4>{board}</div>
      {cust_html}
      <div class='counter'></div>
      <div class='deco' style='left:40px'>🪴</div><div class='deco' style='right:60px'>🧾</div>
    </div>""", unsafe_allow_html=True)

scene()

# ---------------- 조작 영역 ----------------
col_main, col_side = st.columns([4, 1])

with col_main:
    if st.button("🔔 주문 받기 (손님이 도착하면 클릭)", use_container_width=True, type="primary", on_click=take_order):
        pass

    st.markdown("##### 🗄️ 재료 선반 — 클릭해서 컵에 담기")
    used = {i: S.cup.count(i) for i in set(S.cup)}
    cols = st.columns(len(ings))
    for col, ing in zip(cols, ings):
        left = ing["stock"] - used.get(ing["id"], 0)
        col.button(f"{ing['icon']}\n{ing['name']} ({left})", key=f"ing_{ing['id']}", use_container_width=True,
                   disabled=left <= 0 or len(S.cup) >= MAX_CUP, on_click=add_ingredient, args=(ing["id"],))

    layers = "".join(f"<div style='background:{color_of(ing_by_id[i])}'></div>" for i in S.cup)
    icons = " ".join(ing_by_id[i]["icon"] for i in S.cup)
    st.markdown(f"<div class='cup'>{layers}</div><div class='cupicons'>{icons}</div>", unsafe_allow_html=True)

    a, b = st.columns(2)
    a.button("🛎️ 서빙하기", type="primary", use_container_width=True, on_click=serve_drink)
    b.button("🗑️ 쓰레기통에 버리기", use_container_width=True, on_click=throw_trash)

with col_side:
    st.markdown("##### 📦 재고")
    for ing in ings:
        st.write(f"{ing['icon']} {ing['name']}: {ing['stock']}개")
        if ing["stock"] < 10:
            st.error("재고 부족!")
    with st.popover("📜 레시피북", use_container_width=True):
        for m in menus:
            steps = " → ".join(ing_by_id[i]["icon"] + ing_by_id[i]["name"] for i in recipes.get(m["id"], []))
            st.write(f"**{m['name']}**: {steps}")
