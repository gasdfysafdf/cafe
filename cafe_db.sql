-- =====================================================================
--  카페 러쉬 - 전체 DB 스크립트 (이 파일 하나만 실행하면 됩니다)
--  Supabase > SQL Editor > New query 에 통째로 붙여넣고 Run
--
--  ※ 맨 위에서 기존 테이블을 DROP 하고 처음부터 다시 만들기 때문에
--    여러 번 실행해도 되지만, 실행할 때마다 데이터가 초기 상태로 돌아갑니다.
--  ※ Supabase 는 PostgreSQL 이라 함수 문법(plpgsql)만 MySQL 과 조금 다릅니다.
--
--  구성: 0.초기화  1.테이블  2.기초 데이터  3.함수  4.뷰  5.RLS 해제
-- =====================================================================


-- ---------------------------------------------------------------------
-- 0. 기존 객체 삭제 (자식 테이블 → 부모 테이블 순서)
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS purchase_log CASCADE;
DROP TABLE IF EXISTS sales_log    CASCADE;
DROP TABLE IF EXISTS recipes      CASCADE;
DROP TABLE IF EXISTS menus        CASCADE;
DROP TABLE IF EXISTS ingredients  CASCADE;
DROP TABLE IF EXISTS players      CASCADE;
DROP FUNCTION IF EXISTS serve_drink(VARCHAR, INT, INT[], BOOLEAN);   -- 예전 버전 함수


-- ---------------------------------------------------------------------
-- 1. 테이블 6개
-- ---------------------------------------------------------------------
-- 1-1. 플레이어
CREATE TABLE players (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username   VARCHAR(50) UNIQUE NOT NULL,
    money      INT DEFAULT 0 CHECK (money >= 0),             -- 돈은 음수가 될 수 없음
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 1-2. 재료 / 재고
CREATE TABLE ingredients (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(50) NOT NULL,
    stock       INT NOT NULL DEFAULT 2 CHECK (stock >= 0),   -- 재고는 음수가 될 수 없음
    icon        VARCHAR(10),                                 -- 화면에 보이는 이모지
    price       INT NOT NULL DEFAULT 100,                    -- 재료 1개 구매 가격
    description TEXT                                         -- 재고 화면 설명
);

-- 1-3. 메뉴
CREATE TABLE menus (
    id        SERIAL PRIMARY KEY,
    name      VARCHAR(50) NOT NULL,
    price     INT NOT NULL,
    icon      VARCHAR(10),
    image_url TEXT
);

-- 1-4. 레시피 (step_order = 재료 넣는 순서, 순서가 중요함)
CREATE TABLE recipes (
    menu_id       INT REFERENCES menus(id),
    ingredient_id INT REFERENCES ingredients(id),
    step_order    INT NOT NULL,
    PRIMARY KEY (menu_id, step_order)
);

-- 1-5. 판매 기록 (menu_id 가 NULL 이면 레시피에 없는 실패작)
CREATE TABLE sales_log (
    id         SERIAL PRIMARY KEY,
    player_id  UUID REFERENCES players(id),
    menu_id    INT REFERENCES menus(id),
    success    BOOLEAN,
    earned     INT NOT NULL DEFAULT 0,                       -- 실제로 번 돈(팁 포함)
    result     VARCHAR(20),                                  -- served / wasted / angry_left
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 1-6. 재료 구매 기록
CREATE TABLE purchase_log (
    id            SERIAL PRIMARY KEY,
    player_id     UUID REFERENCES players(id),
    ingredient_id INT REFERENCES ingredients(id),
    quantity      INT NOT NULL,
    total_cost    INT NOT NULL,
    created_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);


-- ---------------------------------------------------------------------
-- 2. 기초 데이터
--    재료 id: 1 에스프레소, 2 물, 3 얼음, 4 우유, 5 시럽, 6 밀가루,
--             7 계란, 8 휘핑크림, 9 딸기, 10 블루베리, 11 오렌지, 12 초코
--    메뉴 id: 1 아메리카노, 2 아이스 아메리카노, 3 카페라떼, 4 초코라떼, 5 딸기라떼,
--             6 오렌지에이드, 7 블루베리 스무디, 8 블루베리 머핀, 9 딸기 케이크
-- ---------------------------------------------------------------------
INSERT INTO players (username, money) VALUES ('player1', 5000);

INSERT INTO ingredients (name, stock, icon, price, description) VALUES
('에스프레소', 2, '☕', 200, '진한 커피의 기본! 대부분의 커피 메뉴에 들어가요.'),
('물',         2, '💧',  50, '아메리카노와 에이드에 쓰이는 기본 재료예요.'),
('얼음',       2, '🧊', 100, '시원한 음료를 만들 때 사용돼요.'),
('우유',       2, '🥛', 150, '라떼와 스무디의 부드러움을 책임져요.'),
('시럽',       2, '🍯', 130, '달콤함을 더해 주는 재료예요.'),
('밀가루',     2, '🌾', 120, '머핀과 케이크 같은 디저트의 기본이에요.'),
('계란',       2, '🥚', 100, '디저트 반죽에 꼭 필요해요.'),
('휘핑크림',   2, '🍦', 180, '스무디와 케이크 위에 올리는 크림이에요.'),
('딸기',       2, '🍓', 150, '상큼달콤한 제철 과일이에요.'),
('블루베리',   2, '🫐', 150, '머핀과 스무디에 들어가는 베리예요.'),
('오렌지',     2, '🍊', 120, '에이드의 상큼함을 담당해요.'),
('초코',       2, '🍫', 180, '초코라떼의 달콤쌉싸름한 맛이에요.');

INSERT INTO menus (name, price, icon) VALUES
('아메리카노',        3000, '☕'),
('아이스 아메리카노', 3500, '🧊'),
('카페라떼',          4000, '🥛'),
('초코라떼',          4500, '🍫'),
('딸기라떼',          4500, '🍓'),
('오렌지에이드',      4000, '🍊'),
('블루베리 스무디',   5000, '🫐'),
('블루베리 머핀',     3500, '🧁'),
('딸기 케이크',       6000, '🍰');

INSERT INTO recipes (menu_id, ingredient_id, step_order) VALUES
(1, 2, 1),  (1, 1, 2),                              -- 아메리카노: 물 → 에스프레소
(2, 3, 1),  (2, 2, 2),  (2, 1, 3),                  -- 아이스 아메리카노: 얼음 → 물 → 에스프레소
(3, 1, 1),  (3, 4, 2),                              -- 카페라떼: 에스프레소 → 우유
(4, 1, 1),  (4, 12, 2), (4, 4, 3),                  -- 초코라떼: 에스프레소 → 초코 → 우유
(5, 9, 1),  (5, 3, 2),  (5, 4, 3),                  -- 딸기라떼: 딸기 → 얼음 → 우유
(6, 3, 1),  (6, 11, 2), (6, 5, 3), (6, 2, 4),       -- 오렌지에이드: 얼음 → 오렌지 → 시럽 → 물
(7, 3, 1),  (7, 10, 2), (7, 4, 3), (7, 8, 4),       -- 블루베리 스무디: 얼음 → 블루베리 → 우유 → 휘핑크림
(8, 6, 1),  (8, 7, 2),  (8, 10, 3),                 -- 블루베리 머핀: 밀가루 → 계란 → 블루베리
(9, 6, 1),  (9, 7, 2),  (9, 8, 3), (9, 9, 4);       -- 딸기 케이크: 밀가루 → 계란 → 휘핑크림 → 딸기


-- =====================================================================
-- 3. 함수 (MySQL 의 PROCEDURE 와 같은 역할)
--    문법 메모: DECLARE(변수선언) → BEGIN ~ END(본문), 대입은 :=, 에러는 RAISE EXCEPTION
-- =====================================================================

-- 5-1. 음료 제조: 재고 차감 + 레시피와 같은지 비교 (같으면 메뉴번호, 틀리면 0)
CREATE OR REPLACE FUNCTION brew_drink(p_username VARCHAR, p_used INT[]) RETURNS INT AS $$
DECLARE
    v_player  UUID;
    v_menu_id INT := 0;
    v_stock   INT;
    v_steps   INT;
    v_match   INT;
    i         INT;
    m         RECORD;
BEGIN
    SELECT id INTO v_player FROM players WHERE username = p_username;

    -- (1) 컵에 담은 재료를 하나씩 재고에서 빼기
    FOREACH i IN ARRAY p_used LOOP
        SELECT stock INTO v_stock FROM ingredients WHERE id = i;
        IF v_stock < 1 THEN
            RAISE EXCEPTION '재고가 부족합니다';      -- 에러가 나면 지금까지 뺀 것도 모두 취소(롤백)
        END IF;
        UPDATE ingredients SET stock = stock - 1 WHERE id = i;
    END LOOP;

    -- (2) 모든 메뉴의 레시피와 비교 (단계 수가 같고, 단계마다 재료가 같으면 성공)
    FOR m IN SELECT id FROM menus LOOP
        SELECT COUNT(*) INTO v_steps FROM recipes WHERE menu_id = m.id;
        SELECT COUNT(*) INTO v_match FROM recipes
         WHERE menu_id = m.id AND ingredient_id = p_used[step_order];
        IF v_steps = v_match AND v_steps = array_length(p_used, 1) THEN
            v_menu_id := m.id;
        END IF;
    END LOOP;

    -- (3) 레시피에 없는 조합이면 실패 기록
    IF v_menu_id = 0 THEN
        INSERT INTO sales_log (player_id, menu_id, success, earned, result)
        VALUES (v_player, NULL, FALSE, 0, 'wasted');
    END IF;

    RETURN v_menu_id;
END;
$$ LANGUAGE plpgsql;

-- 5-2. 서빙: 돈 증가 + 판매 기록 (번 돈을 돌려줌)
CREATE OR REPLACE FUNCTION serve_order(p_username VARCHAR, p_menu_id INT, p_tip INT DEFAULT 0) RETURNS INT AS $$
DECLARE
    v_player UUID;
    v_price  INT;
    v_earned INT;
BEGIN
    SELECT id    INTO v_player FROM players WHERE username = p_username;
    SELECT price INTO v_price  FROM menus   WHERE id = p_menu_id;
    v_earned := v_price + p_tip;

    UPDATE players SET money = money + v_earned WHERE id = v_player;
    INSERT INTO sales_log (player_id, menu_id, success, earned, result)
    VALUES (v_player, p_menu_id, TRUE, v_earned, 'served');

    RETURN v_earned;
END;
$$ LANGUAGE plpgsql;

-- 5-3. 손님이 화나서 떠남: 실패 기록
CREATE OR REPLACE FUNCTION customer_left(p_username VARCHAR, p_menu_id INT) RETURNS VOID AS $$
DECLARE
    v_player UUID;
BEGIN
    SELECT id INTO v_player FROM players WHERE username = p_username;
    INSERT INTO sales_log (player_id, menu_id, success, earned, result)
    VALUES (v_player, p_menu_id, FALSE, 0, 'angry_left');
END;
$$ LANGUAGE plpgsql;

-- 5-4. 재료 구매: 돈이 충분한지 확인 → 돈 차감 → 재고 증가 → 구매 기록
CREATE OR REPLACE FUNCTION buy_ingredient(p_username VARCHAR, p_ingredient_id INT, p_qty INT) RETURNS INT AS $$
DECLARE
    v_player UUID;
    v_money  INT;
    v_price  INT;
    v_cost   INT;
BEGIN
    SELECT id, money INTO v_player, v_money FROM players WHERE username = p_username;
    SELECT price     INTO v_price FROM ingredients WHERE id = p_ingredient_id;
    v_cost := v_price * p_qty;

    IF v_money < v_cost THEN
        RAISE EXCEPTION '돈이 부족합니다 (필요 %원 / 보유 %원)', v_cost, v_money;
    END IF;

    UPDATE players     SET money = money - v_cost WHERE id = v_player;
    UPDATE ingredients SET stock = stock + p_qty  WHERE id = p_ingredient_id;
    INSERT INTO purchase_log (player_id, ingredient_id, quantity, total_cost)
    VALUES (v_player, p_ingredient_id, p_qty, v_cost);

    RETURN v_money - v_cost;
END;
$$ LANGUAGE plpgsql;

-- 5-5. 게임 처음부터 다시 (기록 삭제, 돈 5000원, 재고 2개)
CREATE OR REPLACE FUNCTION reset_game(p_username VARCHAR) RETURNS TEXT AS $$
DECLARE
    v_player UUID;
BEGIN
    SELECT id INTO v_player FROM players WHERE username = p_username;
    DELETE FROM sales_log    WHERE player_id = v_player;
    DELETE FROM purchase_log WHERE player_id = v_player;
    UPDATE players     SET money = 5000 WHERE id = v_player;
    UPDATE ingredients SET stock = 2 WHERE id > 0;
    RETURN 'reset done';
END;
$$ LANGUAGE plpgsql;


-- =====================================================================
-- 4. 뷰 (자주 쓰는 SELECT 를 이름 붙여 저장 / 게임 통계 화면에서 사용)
-- =====================================================================

-- 6-1. 플레이어 요약 (서브쿼리 + COALESCE: 값이 NULL 이면 0)
DROP VIEW IF EXISTS v_player_summary;
CREATE VIEW v_player_summary AS
SELECT p.username,
       p.money,
       COALESCE((SELECT SUM(earned)     FROM sales_log    WHERE player_id = p.id), 0) AS total_income,
       COALESCE((SELECT SUM(total_cost) FROM purchase_log WHERE player_id = p.id), 0) AS total_spent,
       (SELECT COUNT(*) FROM sales_log WHERE player_id = p.id AND success = TRUE)     AS served_count,
       (SELECT COUNT(*) FROM sales_log WHERE player_id = p.id AND success = FALSE)    AS fail_count
FROM players p;

-- 6-2. 메뉴별 판매 통계 (LEFT JOIN + GROUP BY + CASE)
DROP VIEW IF EXISTS v_menu_stats;
CREATE VIEW v_menu_stats AS
SELECT m.id,
       m.name,
       COALESCE(SUM(CASE WHEN s.success = TRUE THEN 1 ELSE 0 END), 0)        AS sold,
       COALESCE(SUM(CASE WHEN s.result = 'angry_left' THEN 1 ELSE 0 END), 0) AS angry_left,
       COALESCE(SUM(s.earned), 0)                                            AS revenue
FROM menus m
LEFT JOIN sales_log s ON m.id = s.menu_id
GROUP BY m.id, m.name;

-- 6-3. 날짜별 매출 (GROUP BY 날짜)
DROP VIEW IF EXISTS v_daily_sales;
CREATE VIEW v_daily_sales AS
SELECT DATE(created_at) AS day,
       SUM(CASE WHEN success = TRUE  THEN 1 ELSE 0 END) AS sold,
       SUM(CASE WHEN success = FALSE THEN 1 ELSE 0 END) AS failed,
       SUM(earned)                                      AS revenue
FROM sales_log
GROUP BY DATE(created_at)
ORDER BY day DESC;


-- =====================================================================
-- 5. RLS(행 단위 보안) 설정
--    Supabase 는 새 테이블에 RLS 가 자동으로 켜져서, 정책이 없으면 SELECT 결과가 빈 값이에요.
--    그래서 "모든 접근 허용" 정책을 테이블마다 만들어 줍니다. (과제/실습용 설정)
-- =====================================================================
ALTER TABLE players ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS allow_all ON players;
CREATE POLICY allow_all ON players FOR ALL USING (true) WITH CHECK (true);

ALTER TABLE ingredients ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS allow_all ON ingredients;
CREATE POLICY allow_all ON ingredients FOR ALL USING (true) WITH CHECK (true);

ALTER TABLE menus ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS allow_all ON menus;
CREATE POLICY allow_all ON menus FOR ALL USING (true) WITH CHECK (true);

ALTER TABLE recipes ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS allow_all ON recipes;
CREATE POLICY allow_all ON recipes FOR ALL USING (true) WITH CHECK (true);

ALTER TABLE sales_log ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS allow_all ON sales_log;
CREATE POLICY allow_all ON sales_log FOR ALL USING (true) WITH CHECK (true);

ALTER TABLE purchase_log ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS allow_all ON purchase_log;
CREATE POLICY allow_all ON purchase_log FOR ALL USING (true) WITH CHECK (true);

