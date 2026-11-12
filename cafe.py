import random
import time
from collections import Counter

import pandas as pd
import streamlit as st
from supabase import create_client, Client

st.set_page_config(page_title="☕ 카페 러쉬!", layout="wide")

# ---------------- Supabase ----------------
@st.cache_resource
def init_connection():
    return create_client("https://ccmsgkiqyolowhhgkxnl.supabase.co",
                         "sb_publishable_B3WFuDeKlbBQRWjaBXbNXQ_QgLp0JP0")

supabase: Client = init_connection()

PLAYER_NAME = "player1"
GAME_TITLE = "카페 러쉬!"
ARRIVE_SEC = 2.5        # 손님이 걸어 들어오는 시간
LEAVE_SEC = 2.5         # 손님이 나가는 시간
PATIENCE_SEC = 40       # 도착 후 인내심 (초)
MAX_CUP = 6
MAX_CUST = 3            # 동시에 카운터에 서는 손님 수
TRAY_N = 2              # 카운터 위 트레이 개수
SLOT_X = [6, 36, 66]    # 손님 자리(%)
PLATE_X = [24, 54]      # 트레이 위치(%)
OPEN_MIN, CLOSE_MIN = 8 * 60, 22 * 60   # 영업 08:00 ~ 22:00
MIN_PER_SEC = 1.5       # 현실 1초 = 게임 1.5분


# ---------------- DB 계층 (쿼리는 전부 여기) ----------------
def err_text(e):
    return getattr(e, "message", None) or str(e)

def rpc(name, params):
    return supabase.rpc(name, params).execute().data

@st.cache_data(ttl=30)
def load_menus_recipes():
    menus = supabase.table("menus").select("*").order("id").execute().data
    rows = (supabase.table("recipes").select("menu_id,ingredient_id,step_order")
            .order("step_order").execute().data)
    rec = {}
    for r in rows:
        rec.setdefault(r["menu_id"], []).append(r["ingredient_id"])
    return menus, rec

def fetch_ingredients():
    return supabase.table("ingredients").select("*").order("id").execute().data

def fetch_player():
    return (supabase.table("v_player_summary").select("*")
            .eq("username", PLAYER_NAME).execute().data[0])

# ---------------- 상태 ----------------
S = st.session_state
for k, v in dict(
    screen="title", cup=[], custs=[], tray=[None] * TRAY_N,
    msg="영업 시작! 손님을 기다리는 중...", shop_msg="필요한 재료를 골라 구매하세요.",
    gain=0, gt=0.0, last_tick=time.time(), last_spawn=-10.0, next_gap=2.0,
    served=0, buy_qty={}, sel_ing=None, day=1, closed_notice=False,
).items():
    S.setdefault(k, v)

def refresh():
    S.player = fetch_player()
    S.ings = fetch_ingredients()

if "player" not in S:
    try:
        refresh()
    except Exception as e:
        st.error("DB를 읽지 못했어요. migration.sql 을 Supabase SQL Editor에서 먼저 실행했는지 확인하세요.")
        st.code(err_text(e))
        st.stop()

menus, recipes = load_menus_recipes()
menu_by_id = {m["id"]: m for m in menus}
ing_by_id = {i["id"]: i for i in S.ings}

COLORS = {"물": "#8ecae6", "에스프레소": "#3b2314", "얼음": "#d9f2ff", "우유": "#fff4e0", "시럽": "#c9772e",
          "초코": "#5a3420", "휘핑크림": "#ffffff", "딸기": "#e63950", "블루베리": "#4a4fa8",
          "오렌지": "#ff9f1c", "밀가루": "#f1e3c0", "계란": "#ffe08a"}
def color_of(ing):
    return COLORS.get(ing["name"], f"hsl({ing['id'] * 67 % 360},55%,55%)")

def micon(m):
    return m.get("icon") or "☕"

FACES = ["🧑", "👩", "👨", "👵", "🧔", "👧", "👴", "🧑‍🦰"]
SHIRTS = ["#ff6b57", "#ffcf4a", "#6c8ef5", "#b583e8", "#4cc38a", "#f58fb3"]


# ---------------- 게임 로직 (콜백) ----------------
def goto(screen):
    S.screen = screen

def patience(c):
    t = S.gt - c["t_spawn"] - ARRIVE_SEC
    return 100.0 if t <= 0 else 100 - t / PATIENCE_SEC * 100

def add_ingredient(ing_id):
    if len(S.cup) < MAX_CUP:
        S.cup.append(ing_id)

def clear_cup():
    S.cup = []
    S.msg = "컵을 비웠어요. (재료는 아직 쓰지 않았어요)"

def brew():
    if not S.cup:
        S.msg = "컵이 비어있어요."
        return
    if None not in S.tray:
        S.msg = "트레이가 가득 찼어요! 먼저 서빙하세요."
        return
    try:
        menu_id = rpc("brew_drink", {"p_username": PLAYER_NAME, "p_used": S.cup})
    except Exception as e:
        S.msg = f"제조 실패: {err_text(e)}"
        refresh()
        return
    S.cup = []
    if menu_id and menu_id in menu_by_id:
        S.tray[S.tray.index(None)] = menu_id
        S.msg = f"✅ {menu_by_id[menu_id]['name']} 완성! 트레이에 올렸어요."
    else:
        S.msg = "💥 레시피에 없는 조합이에요! 재료만 낭비했어요."
    refresh()

def serve_tray(idx):
    menu_id = S.tray[idx]
    if menu_id is None:
        return
    cands = [c for c in S.custs if not c["t_leave"] and S.gt - c["t_spawn"] >= ARRIVE_SEC
             and c["menu"]["id"] == menu_id]
    if not cands:
        S.msg = "이 음료를 주문한 손님이 아직 없어요."
        return
    c = min(cands, key=lambda x: x["t_spawn"])
    price = menu_by_id[menu_id]["price"]
    tip = int(price * 0.2 * max(patience(c), 0) / 100)       # 빨리 줄수록 팁
    try:
        S.gain = rpc("serve_order", {"p_username": PLAYER_NAME, "p_menu_id": menu_id, "p_tip": tip})
    except Exception as e:
        S.msg = f"서빙 실패: {err_text(e)}"
        return
    S.tray[idx] = None
    c["t_leave"], c["happy"] = S.gt, True
    S.served += 1
    S.msg = f"완벽해! +{S.gain:,}원 (팁 {tip:,}원)"
    refresh()

def new_day():
    S.update(gt=0.0, last_tick=time.time(), last_spawn=-10.0, custs=[], tray=[None] * TRAY_N,
             cup=[], day=S.day + 1, closed_notice=False, msg=f"{S.day + 1}일차 영업 시작!")

def qty_change(ing_id, d):
    S.buy_qty[ing_id] = max(1, min(30, S.buy_qty.get(ing_id, 1) + d))
    S.sel_ing = ing_id

def buy(ing_id):
    q = S.buy_qty.get(ing_id, 1)
    S.sel_ing = ing_id
    try:
        rpc("buy_ingredient", {"p_username": PLAYER_NAME, "p_ingredient_id": ing_id, "p_qty": q})
        S.shop_msg = f"✅ {ing_by_id[ing_id]['name']} {q}개를 구매했어요!"
    except Exception as e:
        S.shop_msg = f"❌ {err_text(e)}"
    refresh()

def reset_game():
    try:
        rpc("reset_game", {"p_username": PLAYER_NAME})
        S.update(custs=[], tray=[None] * TRAY_N, cup=[], served=0, gain=0, gt=0.0, day=1,
                 last_spawn=-10.0, closed_notice=False, msg="게임을 초기화했어요.")
        refresh()
    except Exception as e:
        st.error(err_text(e))


# ---------------- 스타일 ----------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Jua&display=swap');
html, body, [class*="st-"], button { font-family: 'Jua', sans-serif !important; }
.block-container { padding-top: 1rem; }

/* ---- 공통 HUD ---- */
.hudbar { display:flex; justify-content:space-between; gap:10px; margin-bottom:8px; font-size:19px; }
.hudbar span { background:#2a1d17; color:#ffcf4a; padding:6px 14px; border-radius:14px; }
.hudbar .msg { flex:1; color:#fff; }

/* ---- 카페 장면 ---- */
.scene { position:relative; height:440px; overflow:hidden; border-radius:18px; border:4px solid #5a3a22;
  background:#e9c58f; }
.wall { position:absolute; left:0; right:0; top:0; height:62%; background:linear-gradient(#f7e0b6,#ebc791); }
.winrow { position:absolute; left:0; right:0; top:0; height:120px; border-bottom:8px solid #8b5a35;
  background:repeating-linear-gradient(90deg,#bfe6f5 0 16%,#8b5a35 16% 17%); }
.floor { position:absolute; left:0; right:0; top:62%; bottom:0;
  background:repeating-linear-gradient(90deg,#d9a566 0 58px,#c28d4c 58px 60px); }
.chalk { position:absolute; left:16px; top:112px; padding:6px 14px; background:#2f4a3f; color:#fff;
  border:6px solid #8b5a35; border-radius:8px; font-size:18px; z-index:2; }
.plant { position:absolute; left:130px; top:84px; font-size:40px; z-index:2; }
.hudcoin { position:absolute; left:50%; top:10px; transform:translateX(-50%); z-index:9; padding:6px 18px;
  background:#fff3d6; border:4px solid #8b5a35; border-radius:14px; font-size:19px; color:#5a3a22; white-space:nowrap; }
.clock { position:absolute; right:12px; top:8px; z-index:9; width:84px; height:84px; border-radius:50%;
  background:#fff6dc; border:5px solid #8b5a35; display:flex; flex-direction:column; align-items:center;
  justify-content:center; font-size:15px; line-height:1.25; color:#5a3a22; text-align:center; }
.counter { position:absolute; left:0; right:0; bottom:0; height:130px; z-index:5;
  background:linear-gradient(#9a9aa0 0 30px,#7a5535 30px); border-top:6px solid #6a6a72; box-shadow:0 -6px 14px #0003; }
.plate { position:absolute; bottom:96px; width:110px; height:50px; z-index:6; background:#f6e8c8;
  border:3px solid #cbb48a; border-radius:10px; display:flex; align-items:center; justify-content:center;
  font-size:34px; }
.reg { position:absolute; left:12px; bottom:108px; font-size:44px; z-index:6; }
.menusign { position:absolute; left:12px; bottom:14px; z-index:6; font-size:15px; background:#fff3d6; color:#5a3a22;
  border:3px solid #5a3a22; padding:6px 10px; border-radius:6px; transform:rotate(-4deg); }
.cust { position:absolute; bottom:100px; width:110px; height:230px; z-index:3; }
.cust .head { position:absolute; left:0; right:0; top:20px; text-align:center; font-size:74px; line-height:1; z-index:2; }
.cust .body { position:absolute; left:14px; right:14px; top:100px; bottom:0; border-radius:34px 34px 0 0; }
.cust.walk .head { animation: bob .45s infinite; }
.cust.wait .head { animation: wig 1s infinite; }
.bubble { position:absolute; left:50%; transform:translateX(-50%); bottom:100%; margin-bottom:-14px; min-width:150px;
  padding:7px 12px; background:#fff; border:3px solid #3a2318; border-radius:16px; font-size:16px; text-align:center;
  white-space:nowrap; z-index:4; }
.pat { height:7px; margin-top:5px; background:#e8dccb; border-radius:8px; overflow:hidden; }
.pat i { display:block; height:100%; }
@keyframes walkin  { from { left:-18%; } to { left:var(--x); } }
@keyframes walkout { from { left:var(--x); } to { left:120%; } }
@keyframes bob { 50% { transform: translateY(-8px); } }
@keyframes wig { 0%,100% { transform: rotate(-4deg); } 50% { transform: rotate(4deg); } }

/* ---- 컵 ---- */
.cup { width:120px; height:130px; margin:6px auto 0; border:5px solid #aaa; border-top:0; border-radius:0 0 30px 30px;
  background:#00000010; overflow:hidden; display:flex; flex-direction:column-reverse; }
.cup div { flex:0 0 16.66%; }
.cupicons { text-align:center; font-size:24px; min-height:34px; margin-top:4px; }

/* ---- 버튼 ---- */
div.stButton > button { height:64px; border-radius:16px; border:3px solid #3a2318; font-size:17px;
  box-shadow:0 5px 0 #3a2318; transition:transform .1s; }
div.stButton > button:hover:not(:disabled) { transform:translateY(-3px); }
div.stButton > button:active:not(:disabled) { transform:translateY(3px); box-shadow:0 1px 0 #3a2318; }

/* ---- 타이틀 ---- */
.title-wrap { text-align:center; padding:60px 10px 30px; border-radius:22px; margin-bottom:18px;
  background:linear-gradient(#f7e0b6,#e5b97c); border:4px solid #5a3a22; }
.ttl { font-size:96px; line-height:1.1; color:#ffd36b; -webkit-text-stroke:8px #5a3a22; paint-order:stroke fill; }
.sub { display:inline-block; margin-top:10px; padding:6px 30px; font-size:26px; color:#fff; background:#6b3f2a;
  border-radius:10px; }

/* ---- 재고 화면 ---- */
.big { text-align:center; font-size:56px; line-height:1.2; }
.cname { text-align:center; font-size:20px; }
.own { text-align:center; font-size:15px; color:#8a6a4a; }
.qty { text-align:center; font-size:24px; line-height:64px; }
.detail { display:flex; gap:20px; align-items:center; padding:12px 20px; border-radius:16px; background:#fff3d6;
  border:4px solid #8b5a35; color:#5a3a22; font-size:19px; }
.detail .ic { font-size:48px; }
</style>
""", unsafe_allow_html=True)


# ---------------- 화면: 타이틀 ----------------
def title_screen():
    st.markdown(f"<div class='title-wrap'><div style='font-size:60px'>☕</div>"
                f"<div class='ttl'>{GAME_TITLE}</div><div class='sub'>🐾 운영 시뮬레이터 🐾</div></div>",
                unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.button("▶  시작하기", type="primary", use_container_width=True, on_click=goto, args=("game",))
        st.button("📖  게임 방법", use_container_width=True, on_click=goto, args=("howto",))
        st.button("📊  통계 (DB)", use_container_width=True, on_click=goto, args=("stats",))


def howto_screen():
    st.header("📖 게임 방법")
    st.markdown("""
1. **손님이 도착하면** 머리 위 말풍선에 주문이 떠요.
2. 오른쪽 **재료 선반**에서 레시피 **순서대로** 재료를 클릭해 컵에 담아요. (📜 레시피북 참고)
3. **제조하기**를 누르면 재료가 차감되고, 레시피가 맞으면 음료가 **트레이**에 올라가요.
   - 레시피에 없는 조합이면 재료만 낭비돼요. 🗑️ 버튼은 아직 제조 전인 컵을 비워요.
4. 트레이의 **서빙** 버튼을 누르면 그 음료를 주문한 손님에게 전달돼요. 빨리 줄수록 **팁**이 붙어요!
5. 재료가 떨어지면 **📦 재고 관리**에서 구매하세요. 돈이 부족하면 구매할 수 없어요.
6. 영업시간은 08:00 ~ 22:00. 마감 후엔 **📊 통계**에서 매출을 확인하고 **새 하루**를 시작하세요.
""")
    st.button("← 뒤로가기", on_click=goto, args=("title",))


# ---------------- 화면: 게임 ----------------
@st.fragment(run_every=1)
def scene():
    now = time.time()
    S.gt += min(now - S.last_tick, 2.0)          # 다른 화면에 있던 시간은 게임시간에서 제외
    S.last_tick = now
    minutes = OPEN_MIN + int(S.gt * MIN_PER_SEC)
    closed = minutes >= CLOSE_MIN
    minutes = min(minutes, CLOSE_MIN)

    # 퇴장 완료한 손님 제거
    S.custs = [c for c in S.custs if not (c["t_leave"] and S.gt - c["t_leave"] > LEAVE_SEC)]

    # 인내심 바닥 → 화나서 퇴장 (DB에 기록)
    for c in S.custs:
        if not c["t_leave"] and patience(c) <= 0:
            c["t_leave"], c["happy"] = S.gt, False
            try:
                rpc("customer_left", {"p_username": PLAYER_NAME, "p_menu_id": c["menu"]["id"]})
            except Exception:
                pass
            S.msg = "손님이 화나서 떠났어요! 😡"

    # 새 손님 입장
    if not closed and len(S.custs) < MAX_CUST and S.gt - S.last_spawn > S.next_gap:
        used = {c["slot"] for c in S.custs}
        free = [i for i in range(MAX_CUST) if i not in used]
        if free:
            S.custs.append({"slot": random.choice(free), "menu": random.choice(menus),
                            "face": random.choice(FACES), "shirt": random.choice(SHIRTS),
                            "t_spawn": S.gt, "t_leave": None, "happy": False})
            S.last_spawn, S.next_gap = S.gt, random.uniform(4, 9)

    if closed and not S.custs and not S.closed_notice:
        S.msg, S.closed_notice = "🌙 영업 종료! 📊 통계를 확인하고 새 하루를 시작하세요.", True

    # 손님 HTML
    cust_html = ""
    for c in S.custs:
        x = SLOT_X[c["slot"]]
        if c["t_leave"]:
            el = min(S.gt - c["t_leave"], LEAVE_SEC)
            style = f"--x:{x}%;left:{x}%;animation:walkout {LEAVE_SEC}s linear forwards;animation-delay:-{el:.2f}s;"
            cls, face = "walk", ("😍" if c["happy"] else "😡")
            text = "완벽해요! 😍" if c["happy"] else "흥! 안 마셔요!"
        elif S.gt - c["t_spawn"] < ARRIVE_SEC:
            el = S.gt - c["t_spawn"]
            style = f"--x:{x}%;left:-18%;animation:walkin {ARRIVE_SEC}s linear forwards;animation-delay:-{el:.2f}s;"
            cls, face, text = "walk", c["face"], ""
        else:
            pat = patience(c)
            col = "#4cc38a" if pat > 50 else "#ffcf4a" if pat > 25 else "#e0452f"
            style, cls = f"left:{x}%;", "wait"
            face = "😡" if pat < 25 else c["face"]
            text = (f"{micon(c['menu'])} {c['menu']['name']} 주세요!"
                    f"<div class='pat'><i style='width:{max(pat, 0):.0f}%;background:{col}'></i></div>")
        bubble = f"<div class='bubble'>{text}</div>" if text else ""
        cust_html += (f"<div class='cust {cls}' style='{style}'>{bubble}<div class='head'>{face}</div>"
                      f"<div class='body' style='background:{c['shirt']}'></div></div>")

    plates = "".join(
        f"<div class='plate' style='left:{PLATE_X[i]}%'>{micon(menu_by_id[t]) if t else ''}</div>"
        for i, t in enumerate(S.tray))

    h = minutes // 60
    clock = f"{'AM' if h < 12 else 'PM'}<br><b>{(h if h <= 12 else h - 12):02d}:{minutes % 60:02d}</b>"
    p = S.player
    html = (
        f"<div class='hudbar'><span>💰 {p['money']:,}원</span><span>☕ {S.served}잔</span>"
        f"<span>📅 {S.day}일차</span><span class='msg'>📢 {S.msg}</span></div>"
        "<div class='scene'>"
        "<div class='wall'></div><div class='winrow'></div><div class='floor'></div>"
        "<div class='chalk'>Coffee ☕</div><div class='plant'>🪴</div>"
        f"<div class='hudcoin'>🪙 +{S.gain:,} &nbsp;|&nbsp; 총 수입 : {int(p['total_income']):,}</div>"
        f"<div class='clock'>{clock}</div>"
        f"{cust_html}<div class='counter'></div>{plates}"
        "<div class='reg'>🖥️</div><div class='menusign'>📋 MENU</div>"
        "</div>")
    st.markdown(html, unsafe_allow_html=True)


def game_screen():
    col_main, col_side = st.columns([2.2, 1])

    with col_main:
        scene()

        # 트레이 서빙 버튼
        tc = st.columns(TRAY_N)
        for i, t in enumerate(S.tray):
            if t:
                m = menu_by_id[t]
                label = f"🍽️ 트레이 {i + 1} 서빙 · {micon(m)} {m['name']}"
            else:
                label = f"트레이 {i + 1} 비어있음"
            tc[i].button(label, key=f"tray_{i}", disabled=t is None, type="primary" if t else "secondary",
                         use_container_width=True, on_click=serve_tray, args=(i,))

        # 메뉴 이동 줄
        n1, n2, n3, n4 = st.columns(4)
        n1.button("📦 재고 관리", use_container_width=True, on_click=goto, args=("inventory",))
        n2.button("📊 통계", use_container_width=True, on_click=goto, args=("stats",))
        n3.button("🌅 새 하루", use_container_width=True, on_click=new_day)
        n4.button("🏠 타이틀", use_container_width=True, on_click=goto, args=("title",))

    with col_side:
        st.markdown("##### 🗄️ 재료 선반")
        used = Counter(S.cup)
        ings = S.ings
        for r in range(0, len(ings), 4):
            cs = st.columns(4)
            for col, ing in zip(cs, ings[r:r + 4]):
                left = ing["stock"] - used.get(ing["id"], 0)
                col.button(f"{ing['icon']}\n{left}", key=f"ing_{ing['id']}", help=f"{ing['name']} (재고 {left})",
                           use_container_width=True, disabled=left <= 0 or len(S.cup) >= MAX_CUP,
                           on_click=add_ingredient, args=(ing["id"],))

        layers = "".join(f"<div style='background:{color_of(ing_by_id[i])}'></div>" for i in S.cup)
        icons = " ".join(ing_by_id[i]["icon"] for i in S.cup)
        st.markdown(f"<div class='cup'>{layers}</div><div class='cupicons'>{icons}</div>", unsafe_allow_html=True)

        b1, b2 = st.columns([3, 1])
        b1.button("🧑‍🍳 제조하기", type="primary", use_container_width=True, on_click=brew)
        b2.button("🗑️", use_container_width=True, on_click=clear_cup, help="컵 비우기")

        with st.popover("📜 레시피북", use_container_width=True):
            for m in menus:
                steps = " → ".join(ing_by_id[i]["icon"] + ing_by_id[i]["name"] for i in recipes.get(m["id"], []))
                st.write(f"{micon(m)} **{m['name']}** ({m['price']:,}원): {steps}")


# ---------------- 화면: 재고 관리 ----------------
def inventory_screen():
    st.markdown(f"<div class='hudbar'><span>💰 {S.player['money']:,}원</span>"
                f"<span class='msg'>📢 {S.shop_msg}</span></div>", unsafe_allow_html=True)
    ings = S.ings
    for r in range(0, len(ings), 4):
        cols = st.columns(4)
        for col, ing in zip(cols, ings[r:r + 4]):
            iid = ing["id"]
            q = S.buy_qty.get(iid, 1)
            with col.container(border=True):
                st.markdown(f"<div class='big'>{ing['icon']}</div><div class='cname'>{ing['name']}</div>"
                            f"<div class='own'>보유 {ing['stock']}개 · 개당 {ing['price']:,}원</div>",
                            unsafe_allow_html=True)
                a, b, c = st.columns([1, 1, 1])
                a.button("−", key=f"m_{iid}", use_container_width=True, on_click=qty_change, args=(iid, -1))
                b.markdown(f"<div class='qty'>{q}</div>", unsafe_allow_html=True)
                c.button("＋", key=f"p_{iid}", use_container_width=True, on_click=qty_change, args=(iid, 1))
                st.button(f"🪙 {ing['price'] * q:,} 구매", key=f"buy_{iid}", type="primary",
                          use_container_width=True, on_click=buy, args=(iid,))

    sel = ing_by_id.get(S.sel_ing or ings[0]["id"])
    back, info = st.columns([1, 4])
    back.button("← 뒤로가기", use_container_width=True, on_click=goto, args=("game",))
    info.markdown(f"<div class='detail'><span class='ic'>{sel['icon']}</span><span><b>{sel['name']}</b><br>"
                  f"{sel.get('description') or ''}</span><span style='margin-left:auto'>보유 수량 : "
                  f"<b>{sel['stock']}개</b></span></div>", unsafe_allow_html=True)


# ---------------- 화면: 통계 (DB 쿼리 결과 보여주기) ----------------
def stats_screen():
    st.header("📊 영업 통계")
    st.caption("아래 데이터는 모두 Supabase 뷰/조인 쿼리 결과입니다.")
    refresh()
    p = S.player
    c = st.columns(5)
    c[0].metric("보유금", f"{p['money']:,}원")
    c[1].metric("총 수입", f"{int(p['total_income']):,}원")
    c[2].metric("재료 구매 지출", f"{int(p['total_spent']):,}원")
    c[3].metric("서빙 성공", f"{p['served_count']}건")
    c[4].metric("실패/이탈", f"{p['fail_count']}건")

    left, right = st.columns(2)
    with left:
        st.subheader("메뉴별 매출 (v_menu_stats)")
        ms = supabase.table("v_menu_stats").select("*").order("revenue", desc=True).execute().data
        df = pd.DataFrame(ms)
        if not df.empty:
            st.dataframe(df.rename(columns={"name": "메뉴", "sold": "판매", "angry_left": "이탈", "revenue": "매출"})
                         .drop(columns=["id"]), hide_index=True, use_container_width=True)
            st.bar_chart(df.set_index("name")[["revenue"]])
    with right:
        st.subheader("일별 매출 (v_daily_sales)")
        ds = supabase.table("v_daily_sales").select("*").execute().data
        if ds:
            st.dataframe(pd.DataFrame(ds).rename(columns={"day": "날짜", "sold": "판매", "failed": "실패", "revenue": "매출"}),
                         hide_index=True, use_container_width=True)
        else:
            st.info("아직 판매 기록이 없어요.")

    st.subheader("최근 판매 로그 (sales_log JOIN menus)")
    logs = (supabase.table("sales_log").select("created_at,success,result,earned,menus(name)")
            .order("created_at", desc=True).limit(15).execute().data)
    if logs:
        st.dataframe(pd.DataFrame([{
            "시각": r["created_at"][:19].replace("T", " "),
            "메뉴": (r.get("menus") or {}).get("name", "(실패작)"),
            "결과": r.get("result") or ("served" if r["success"] else "fail"),
            "수입": r["earned"]} for r in logs]), hide_index=True, use_container_width=True)

    st.subheader("최근 구매 로그 (purchase_log JOIN ingredients)")
    buys = (supabase.table("purchase_log").select("created_at,quantity,total_cost,ingredients(name)")
            .order("created_at", desc=True).limit(10).execute().data)
    if buys:
        st.dataframe(pd.DataFrame([{
            "시각": r["created_at"][:19].replace("T", " "),
            "재료": (r.get("ingredients") or {}).get("name", "-"),
            "수량": r["quantity"], "금액": r["total_cost"]} for r in buys]), hide_index=True, use_container_width=True)

    b1, b2 = st.columns([1, 1])
    b1.button("← 게임으로", use_container_width=True, on_click=goto, args=("game",))
    b2.button("♻️ 게임 초기화 (DB 리셋)", use_container_width=True, on_click=reset_game)


# ---------------- 라우팅 ----------------
SCREENS = {"title": title_screen, "howto": howto_screen, "game": game_screen,
           "inventory": inventory_screen, "stats": stats_screen}
SCREENS[S.screen]()
