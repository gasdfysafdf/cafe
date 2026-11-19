-- =====================================================================
-- 카페 러쉬 멀티플레이어 DB (전체 재생성 스크립트)
-- Supabase SQL Editor에서 실행하세요.
-- 주의: 기존 테이블을 삭제하고 다시 만들기 때문에 기존 게임 데이터는 초기화됩니다.
-- =====================================================================

DROP VIEW IF EXISTS v_daily_sales CASCADE;
DROP VIEW IF EXISTS v_menu_stats CASCADE;
DROP VIEW IF EXISTS v_player_summary CASCADE;
DROP TABLE IF EXISTS purchase_log CASCADE;
DROP TABLE IF EXISTS sales_log CASCADE;
DROP TABLE IF EXISTS player_inventory CASCADE;
DROP TABLE IF EXISTS recipes CASCADE;
DROP TABLE IF EXISTS menus CASCADE;
DROP TABLE IF EXISTS ingredients CASCADE;
DROP TABLE IF EXISTS players CASCADE;
DROP FUNCTION IF EXISTS register_player(VARCHAR) CASCADE;
DROP FUNCTION IF EXISTS delete_player(VARCHAR) CASCADE;
DROP FUNCTION IF EXISTS brew_drink(VARCHAR, INT[]) CASCADE;
DROP FUNCTION IF EXISTS discard_ingredients(VARCHAR, INT[]) CASCADE;
DROP FUNCTION IF EXISTS serve_order(VARCHAR, INT, INT) CASCADE;
DROP FUNCTION IF EXISTS customer_left(VARCHAR, INT) CASCADE;
DROP FUNCTION IF EXISTS buy_ingredient(VARCHAR, INT, INT) CASCADE;
DROP FUNCTION IF EXISTS reset_game(VARCHAR) CASCADE;

CREATE TABLE players (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) UNIQUE NOT NULL,
    money INT NOT NULL DEFAULT 5000 CHECK (money >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 공통 재료 정보. 재고는 player_inventory에 플레이어별로 저장합니다.
CREATE UNIQUE INDEX players_username_ci_unique ON players (lower(username));

CREATE TABLE ingredients (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    icon VARCHAR(10),
    price INT NOT NULL CHECK (price >= 0),
    description TEXT
);

CREATE TABLE player_inventory (
    player_id UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    ingredient_id INT NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
    stock INT NOT NULL DEFAULT 2 CHECK (stock >= 0),
    PRIMARY KEY (player_id, ingredient_id)
);

CREATE TABLE menus (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    price INT NOT NULL,
    icon VARCHAR(10),
    image_url TEXT
);

CREATE TABLE recipes (
    menu_id INT REFERENCES menus(id) ON DELETE CASCADE,
    ingredient_id INT REFERENCES ingredients(id) ON DELETE CASCADE,
    step_order INT NOT NULL,
    PRIMARY KEY (menu_id, step_order)
);

CREATE TABLE sales_log (
    id BIGSERIAL PRIMARY KEY,
    player_id UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    menu_id INT REFERENCES menus(id),
    success BOOLEAN,
    earned INT NOT NULL DEFAULT 0,
    result VARCHAR(20),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE purchase_log (
    id BIGSERIAL PRIMARY KEY,
    player_id UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    ingredient_id INT REFERENCES ingredients(id),
    quantity INT NOT NULL,
    total_cost INT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 재료 가격: 기존 가격의 정확히 5배
INSERT INTO ingredients (name, icon, price, description) VALUES
('에스프레소', '☕', 1000, '진한 커피의 기본! 대부분의 커피 메뉴에 들어가요.'),
('물', '💧', 250, '아메리카노와 에이드에 쓰이는 기본 재료예요.'),
('얼음', '🧊', 500, '시원한 음료를 만들 때 사용돼요.'),
('우유', '🥛', 750, '라떼와 스무디의 부드러움을 책임져요.'),
('시럽', '🍯', 650, '달콤함을 더해 주는 재료예요.'),
('밀가루', '🌾', 600, '머핀과 케이크 같은 디저트의 기본이에요.'),
('계란', '🥚', 500, '디저트 반죽에 꼭 필요해요.'),
('휘핑크림', '🍦', 900, '스무디와 케이크 위에 올리는 크림이에요.'),
('딸기', '🍓', 750, '상큼달콤한 제철 과일이에요.'),
('블루베리', '🫐', 750, '머핀과 스무디에 들어가는 베리예요.'),
('오렌지', '🍊', 600, '에이드의 상큼함을 담당해요.'),
('초코', '🍫', 900, '초코라떼의 달콤쌉싸름한 맛이에요.');

INSERT INTO menus (name, price, icon) VALUES
('아메리카노', 3000, '☕'),
('아이스 아메리카노', 3500, '🧊'),
('카페라떼', 4000, '🥛'),
('초코라떼', 4500, '🍫'),
('딸기라떼', 4500, '🍓'),
('오렌지에이드', 4000, '🍊'),
('블루베리 스무디', 5000, '🫐'),
('블루베리 머핀', 3500, '🧁'),
('딸기 케이크', 6000, '🍰');

INSERT INTO recipes (menu_id, ingredient_id, step_order) VALUES
(1,2,1),(1,1,2),
(2,3,1),(2,2,2),(2,1,3),
(3,1,1),(3,4,2),
(4,1,1),(4,12,2),(4,4,3),
(5,9,1),(5,3,2),(5,4,3),
(6,3,1),(6,11,2),(6,5,3),(6,2,4),
(7,3,1),(7,10,2),(7,4,3),(7,8,4),
(8,6,1),(8,7,2),(8,10,3),
(9,6,1),(9,7,2),(9,8,3),(9,9,4);

-- 닉네임 중복은 UNIQUE 제약으로 원자적으로 차단합니다.
CREATE OR REPLACE FUNCTION register_player(p_username VARCHAR) RETURNS UUID AS $$
DECLARE v_player UUID;
BEGIN
    IF length(trim(p_username)) = 0 THEN RAISE EXCEPTION '닉네임을 입력해 주세요.'; END IF;
    INSERT INTO players(username, money) VALUES (trim(p_username), 5000)
    RETURNING id INTO v_player;
    INSERT INTO player_inventory(player_id, ingredient_id, stock)
    SELECT v_player, id, 2 FROM ingredients;
    RETURN v_player;
EXCEPTION WHEN unique_violation THEN
    RAISE EXCEPTION '이미 사용 중인 닉네임입니다.';
END;
$$ LANGUAGE plpgsql;

-- 처음 화면으로 나가면 해당 플레이어 행을 삭제하고 FK CASCADE로 관련 데이터도 삭제합니다.
CREATE OR REPLACE FUNCTION delete_player(p_username VARCHAR) RETURNS BOOLEAN AS $$
DECLARE v_player UUID;
BEGIN
    DELETE FROM players WHERE username = trim(p_username) RETURNING id INTO v_player;
    RETURN v_player IS NOT NULL;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION brew_drink(p_username VARCHAR, p_used INT[]) RETURNS INT AS $$
DECLARE
    v_player UUID;
    v_menu_id INT := 0;
    v_steps INT;
    v_match INT;
    i INT;
    m RECORD;
BEGIN
    SELECT id INTO v_player FROM players WHERE username = p_username;
    IF v_player IS NULL THEN RAISE EXCEPTION '플레이어를 찾을 수 없습니다.'; END IF;
    IF p_used IS NULL OR array_length(p_used,1) IS NULL THEN RAISE EXCEPTION '재료를 선택해 주세요.'; END IF;

    -- 플레이어 본인의 재고만 차감. 동시 요청에도 음수 재고가 되지 않도록 조건부 UPDATE.
    FOREACH i IN ARRAY p_used LOOP
        UPDATE player_inventory SET stock = stock - 1
         WHERE player_id = v_player AND ingredient_id = i AND stock >= 1;
        IF NOT FOUND THEN RAISE EXCEPTION '재고가 부족합니다.'; END IF;
    END LOOP;

    FOR m IN SELECT id FROM menus LOOP
        SELECT COUNT(*) INTO v_steps FROM recipes WHERE menu_id = m.id;
        SELECT COUNT(*) INTO v_match FROM recipes
         WHERE menu_id = m.id AND ingredient_id = p_used[step_order];
        IF v_steps = v_match AND v_steps = array_length(p_used,1) THEN v_menu_id := m.id; END IF;
    END LOOP;

    IF v_menu_id = 0 THEN
        INSERT INTO sales_log(player_id, menu_id, success, earned, result)
        VALUES (v_player, NULL, FALSE, 0, 'wasted');
    END IF;
    RETURN v_menu_id;
END;
$$ LANGUAGE plpgsql;

-- 제조 전 재료를 접시에 올렸다가 쓰레기통을 누르면 재고를 돌려주지 않고 소모 처리합니다.
CREATE OR REPLACE FUNCTION discard_ingredients(p_username VARCHAR, p_used INT[]) RETURNS BOOLEAN AS $$
DECLARE v_player UUID; i INT;
BEGIN
    SELECT id INTO v_player FROM players WHERE username = p_username;
    IF v_player IS NULL THEN RAISE EXCEPTION '플레이어를 찾을 수 없습니다.'; END IF;
    FOREACH i IN ARRAY p_used LOOP
        UPDATE player_inventory SET stock = stock - 1
         WHERE player_id = v_player AND ingredient_id = i AND stock >= 1;
        IF NOT FOUND THEN RAISE EXCEPTION '재고가 부족해 폐기할 수 없습니다.'; END IF;
    END LOOP;
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION serve_order(p_username VARCHAR, p_menu_id INT, p_tip INT DEFAULT 0) RETURNS INT AS $$
DECLARE v_player UUID; v_price INT; v_earned INT;
BEGIN
    SELECT id INTO v_player FROM players WHERE username = p_username;
    SELECT price INTO v_price FROM menus WHERE id = p_menu_id;
    IF v_player IS NULL OR v_price IS NULL THEN RAISE EXCEPTION '플레이어 또는 메뉴를 찾을 수 없습니다.'; END IF;
    v_earned := v_price + GREATEST(p_tip,0);
    UPDATE players SET money = money + v_earned WHERE id = v_player;
    INSERT INTO sales_log(player_id, menu_id, success, earned, result)
    VALUES (v_player, p_menu_id, TRUE, v_earned, 'served');
    RETURN v_earned;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION customer_left(p_username VARCHAR, p_menu_id INT) RETURNS VOID AS $$
DECLARE v_player UUID;
BEGIN
    SELECT id INTO v_player FROM players WHERE username = p_username;
    IF v_player IS NULL THEN RETURN; END IF;
    INSERT INTO sales_log(player_id, menu_id, success, earned, result)
    VALUES (v_player, p_menu_id, FALSE, 0, 'angry_left');
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION buy_ingredient(p_username VARCHAR, p_ingredient_id INT, p_qty INT) RETURNS INT AS $$
DECLARE v_player UUID; v_money INT; v_price INT; v_cost INT;
BEGIN
    IF p_qty < 1 OR p_qty > 30 THEN RAISE EXCEPTION '구매 수량이 올바르지 않습니다.'; END IF;
    SELECT id, money INTO v_player, v_money FROM players WHERE username = p_username FOR UPDATE;
    SELECT price INTO v_price FROM ingredients WHERE id = p_ingredient_id;
    IF v_player IS NULL OR v_price IS NULL THEN RAISE EXCEPTION '플레이어 또는 재료를 찾을 수 없습니다.'; END IF;
    v_cost := v_price * p_qty;
    IF v_money < v_cost THEN RAISE EXCEPTION '돈이 부족합니다 (필요 %원 / 보유 %원)', v_cost, v_money; END IF;
    UPDATE players SET money = money - v_cost WHERE id = v_player;
    INSERT INTO player_inventory(player_id, ingredient_id, stock) VALUES (v_player, p_ingredient_id, p_qty)
    ON CONFLICT(player_id, ingredient_id) DO UPDATE SET stock = player_inventory.stock + EXCLUDED.stock;
    INSERT INTO purchase_log(player_id, ingredient_id, quantity, total_cost)
    VALUES (v_player, p_ingredient_id, p_qty, v_cost);
    RETURN v_money - v_cost;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION reset_game(p_username VARCHAR) RETURNS TEXT AS $$
DECLARE v_player UUID;
BEGIN
    SELECT id INTO v_player FROM players WHERE username = p_username;
    IF v_player IS NULL THEN RAISE EXCEPTION '플레이어를 찾을 수 없습니다.'; END IF;
    DELETE FROM sales_log WHERE player_id = v_player;
    DELETE FROM purchase_log WHERE player_id = v_player;
    UPDATE players SET money = 5000 WHERE id = v_player;
    INSERT INTO player_inventory(player_id, ingredient_id, stock)
    SELECT v_player, id, 2 FROM ingredients
    ON CONFLICT(player_id, ingredient_id) DO UPDATE SET stock = 2;
    RETURN 'reset done';
END;
$$ LANGUAGE plpgsql;

CREATE VIEW v_player_summary AS
SELECT p.id, p.username, p.money,
       COALESCE((SELECT SUM(earned) FROM sales_log WHERE player_id=p.id),0) AS total_income,
       COALESCE((SELECT SUM(total_cost) FROM purchase_log WHERE player_id=p.id),0) AS total_spent,
       (SELECT COUNT(*) FROM sales_log WHERE player_id=p.id AND success=TRUE) AS served_count,
       (SELECT COUNT(*) FROM sales_log WHERE player_id=p.id AND success=FALSE) AS fail_count
FROM players p;

CREATE VIEW v_menu_stats AS
SELECT p.id AS player_id, m.id AS menu_id, m.name,
       COALESCE(SUM(CASE WHEN s.success=TRUE THEN 1 ELSE 0 END),0) AS sold,
       COALESCE(SUM(CASE WHEN s.result='angry_left' THEN 1 ELSE 0 END),0) AS angry_left,
       COALESCE(SUM(s.earned),0) AS revenue
FROM players p CROSS JOIN menus m
LEFT JOIN sales_log s ON s.player_id=p.id AND s.menu_id=m.id
GROUP BY p.id,m.id,m.name;

CREATE VIEW v_daily_sales AS
SELECT player_id, DATE(created_at) AS day,
       SUM(CASE WHEN success=TRUE THEN 1 ELSE 0 END) AS sold,
       SUM(CASE WHEN success=FALSE THEN 1 ELSE 0 END) AS failed,
       SUM(earned) AS revenue
FROM sales_log GROUP BY player_id,DATE(created_at)
ORDER BY day DESC;

-- 실습용 공개 정책. 실제 공개 서비스라면 Supabase Auth 기반 RLS로 교체해야 합니다.
ALTER TABLE players ENABLE ROW LEVEL SECURITY;
ALTER TABLE ingredients ENABLE ROW LEVEL SECURITY;
ALTER TABLE player_inventory ENABLE ROW LEVEL SECURITY;
ALTER TABLE menus ENABLE ROW LEVEL SECURITY;
ALTER TABLE recipes ENABLE ROW LEVEL SECURITY;
ALTER TABLE sales_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE purchase_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY players_demo_all ON players FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY ingredients_demo_read ON ingredients FOR SELECT USING (true);
CREATE POLICY inventory_demo_all ON player_inventory FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY menus_demo_read ON menus FOR SELECT USING (true);
CREATE POLICY recipes_demo_read ON recipes FOR SELECT USING (true);
CREATE POLICY sales_demo_all ON sales_log FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY purchases_demo_all ON purchase_log FOR ALL USING (true) WITH CHECK (true);
