import streamlit as st
import sqlite3, json, re
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).with_name("memfind.db")

st.set_page_config(page_title="MemFind 2.0", page_icon="📦", layout="wide")

def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS items(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, aliases TEXT, color TEXT, urgency TEXT,
            zone TEXT, shelf TEXT, level TEXT, slot TEXT, batch TEXT,
            quantity INTEGER DEFAULT 0, updated_at TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS events(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT, content TEXT, created_at TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS orders(
            id TEXT PRIMARY KEY, product TEXT, quantity INTEGER, due TEXT, priority TEXT, status TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS equipment(
            id TEXT PRIMARY KEY, name TEXT, status TEXT, temperature REAL, vibration REAL, note TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS quality(
            batch TEXT PRIMARY KEY, inspected INTEGER, defects INTEGER, defect_type TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS materials(
            sku TEXT PRIMARY KEY, name TEXT, stock INTEGER, safety_stock INTEGER, lead_days INTEGER, supplier TEXT
        )""")
        count = c.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        if count == 0:
            rows = [
                ("红色急件箱","红盒,红色箱子,急件","红色","高","A区","03","2","05","B2026-011",12),
                ("蓝色连接器","蓝连接器,连接头","蓝色","普通","A区","01","1","02","B2026-008",240),
                ("耐高温密封圈","密封圈,高温圈","黑色","高","B区","02","3","01","B2026-014",60),
                ("温湿度传感器","温湿度模块,传感器","白色","普通","C区","04","1","06","B2026-006",35),
                ("电机驱动模块","驱动板,L298N","红色","高","B区","01","2","03","B2026-019",18),
            ]
            now = datetime.now().isoformat(timespec="seconds")
            c.executemany("""INSERT INTO items(name,aliases,color,urgency,zone,shelf,level,slot,batch,quantity,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""", [r+(now,) for r in rows])
        if c.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0:
            c.executemany("INSERT INTO orders VALUES(?,?,?,?,?,?)", [
                ("O-1001","连接器组件",120,"今天 17:00","高","待排产"),
                ("O-1002","密封组件",60,"明天 12:00","普通","待排产"),
                ("O-1003","传感器组件",30,"明天 18:00","高","待排产")])
        if c.execute("SELECT COUNT(*) FROM equipment").fetchone()[0] == 0:
            c.executemany("INSERT INTO equipment VALUES(?,?,?,?,?,?)", [
                ("M-01","注塑机1号","运行",62.0,2.1,"温度略高，建议观察"),
                ("M-02","装配线2号","待检修",78.5,6.8,"振动偏高，建议停机检查"),
                ("M-03","包装机3号","运行",48.0,1.4,"状态正常")])
        if c.execute("SELECT COUNT(*) FROM quality").fetchone()[0] == 0:
            c.executemany("INSERT INTO quality VALUES(?,?,?,?)", [
                ("B2026-011",100,4,"尺寸偏差"),
                ("B2026-014",80,1,"外观划痕"),
                ("B2026-019",120,9,"焊点异常")])
        if c.execute("SELECT COUNT(*) FROM materials").fetchone()[0] == 0:
            c.executemany("INSERT INTO materials VALUES(?,?,?,?,?,?)", [
                ("SKU-01","连接器",80,100,3,"华东电子"),
                ("SKU-02","密封圈",220,80,5,"精密橡塑"),
                ("SKU-03","传感器",12,30,7,"智感科技")])

def log(kind, content):
    with db() as c:
        c.execute("INSERT INTO events(event_type,content,created_at) VALUES(?,?,?)",
                  (kind, content, datetime.now().isoformat(timespec="seconds")))

def item_rows():
    with db() as c:
        return c.execute("SELECT * FROM items ORDER BY id DESC").fetchall()


def find_items(q):
    # 文本标准化
    def norm(s):
        return re.sub(r"[\s，。！？、：；,.!?]", "", str(s or "")).lower()

    qn = norm(q)
    rows = item_rows()
    scored = []

    # 用户表达与数据库字段的语义映射
    color_words = {
        "红色": ["红色", "红"],
        "蓝色": ["蓝色", "蓝"],
        "白色": ["白色", "白"],
        "黑色": ["黑色", "黑"]
    }

    urgency_words = {
        "高": ["急件", "紧急", "加急", "优先", "高优先级"],
        "普通": ["普通", "一般", "常规"]
    }

    # 判断用户是否提出了颜色条件
    target_color = None
    for color, words in color_words.items():
        if any(w in qn for w in words):
            target_color = color
            break

    # 判断用户是否提出了紧急程度条件
    target_urgency = None
    for urgency, words in urgency_words.items():
        if any(w in qn for w in words):
            target_urgency = urgency
            break

    for r in rows:
        def val(key):
            return str(r[key] or "") if key in r.keys() else ""

        name = norm(val("name"))
        aliases = [
            norm(x) for x in re.split(
                r"[,，、;/；]", val("aliases")
            ) if norm(x)
        ]

        color = norm(val("color"))
        urgency = norm(val("urgency"))

        score = 0

        # 1. 名称匹配：权重最高
        if name and name in qn:
            score += 10

        # 2. 别名匹配
        for alias in aliases:
            if alias and alias in qn:
                score += 8

        # 3. 颜色匹配
        if target_color:
            if color == norm(target_color):
                score += 5
            else:
                score -= 3

        # 4. 紧急程度匹配
        if target_urgency:
            if urgency == norm(target_urgency):
                score += 5
            else:
                score -= 3

        # 5. 区域匹配
        zone = norm(val("zone"))
        if zone and zone in qn:
            score += 3

        # 6. 批次匹配
        batch = norm(val("batch"))
        if batch and batch in qn:
            score += 6

        # 7. 货架号匹配
        shelf = norm(val("shelf"))
        if shelf and shelf in qn:
            score += 3

        if score > 0:
            scored.append((score, r))

    # 按匹配得分排序
    scored.sort(key=lambda x: x[0], reverse=True)

    return [r for score, r in scored]




def classify(q):
    ql = str(q or "").strip().lower()

    # 1. 质量检测：优先识别高特征词
    if any(x in ql for x in [
        "质量", "缺陷", "不良", "检测",
        "批次异常", "不良率", "抽检",
        "瑕疵", "质量异常"
    ]):
        return "质量检测Agent"

    # 2. 设备运维
    if any(x in ql for x in [
        "设备", "故障", "维修", "温度",
        "振动", "停机", "运维"
    ]):
        return "设备运维Agent"

    # 3. 智能排产
    if any(x in ql for x in [
        "排产", "订单", "交期", "产能",
        "生产计划", "插单"
    ]):
        return "智能排产Agent"

    # 4. 供应链优化
    if any(x in ql for x in [
        "库存", "采购", "供应商",
        "补货", "缺料", "安全库存"
    ]):
        return "供应链优化Agent"

    # 5. 空间记忆：只保留明确的寻址特征
    if any(x in ql for x in [
        "在哪", "位置", "库位", "货架",
        "红色", "蓝色", "物品", "物料",
        "寻址", "找一下", "帮我找",
        "存放位置", "存在哪里"
    ]):
        return "空间记忆Agent"

    return "Master Agent"



def run_agent(q):
    agent=classify(q)
    logs=[f"Master Agent：识别用户请求，初步分派至 {agent}。"]
    if agent=="空间记忆Agent":
        found=find_items(q)
        
if not found:
    answer = (
        "暂时没有找到匹配物品。"
        "请补充物品名称、颜色、批次或大致区域。"
    )

elif len(found) > 1:
    # 多个候选结果，不直接选择第一条
    candidates = found[:5]

    answer = "找到多个候选物品，请确认你要查找的是哪一个：\n"

    for i, r in enumerate(candidates, 1):
        answer += (
            f"\n{i}. {r['name']}"
            f"（批次：{r['batch']}）"
            f"（颜色：{r['color']}）"
        )

    answer += (
        "\n\n请补充物品名称或批次，"
        "确认后再查询具体库位。"
    )

else:
    # 唯一匹配，返回完整位置
    r = found[0]

    answer = (
        f"找到物品：{r['name']}\n"
        f"匹配批次：{r['batch']}\n"
        f"位置：{r['zone']} / "
        f"{r['shelf']}号货架 / "
        f"第{r['level']}层 / "
        f"{r['slot']}号位\n"
        f"库存数量：{r['quantity']}件"
    )

    elif agent=="智能排产Agent":
        with db() as c: rows=c.execute("SELECT * FROM orders ORDER BY CASE priority WHEN '高' THEN 0 ELSE 1 END, due").fetchall()
        answer="模拟排产建议（演示数据）：\n"+ "\n".join([f"- {r['id']}｜{r['product']} × {r['quantity']}｜交期：{r['due']}｜优先级：{r['priority']}｜状态：{r['status']}" for r in rows])
        answer += "\n建议先处理高优先级且交期较近的订单；实际排程仍需接入工序节拍、设备日历和换线时间。"
        logs += ["排产Agent：按优先级与交期排序订单。","排产规则：当前为规则模拟，未连接真实MES。"]
    elif agent=="设备运维Agent":
        with db() as c: rows=c.execute("SELECT * FROM equipment ORDER BY vibration DESC").fetchall()
        answer="设备状态（演示数据）：\n"+ "\n".join([f"- {r['id']} {r['name']}：{r['status']}；温度 {r['temperature']}℃；振动 {r['vibration']}；备注：{r['note']}" for r in rows])
        answer += "\n建议优先复核 M-02 的振动异常；以上为模拟阈值提示，不构成真实设备诊断。"
        logs += ["设备运维Agent：读取设备状态与模拟传感指标。","运维规则：异常项按振动值排序，输出检查建议。"]
    elif agent=="质量检测Agent":
        with db() as c: rows=c.execute("SELECT * FROM quality ORDER BY defects DESC").fetchall()
        answer="质量检测记录（演示数据）：\n"+ "\n".join([f"- {r['batch']}：抽检 {r['inspected']} 件，不良 {r['defects']} 件，缺陷：{r['defect_type']}，不良率 {r['defects']/max(1,r['inspected'])*100:.1f}%" for r in rows])
        answer += "\n建议优先复核不良数量较高的批次，并关联供应商、工序和设备记录进行追溯。"
        logs += ["质量Agent：统计批次抽检与缺陷记录。","质量规则：按不良数量排序，计算模拟不良率。"]
    else:
        with db() as c: rows=c.execute("SELECT * FROM materials ORDER BY stock*1.0/CASE WHEN safety_stock=0 THEN 1 ELSE safety_stock END ASC").fetchall()
        answer="库存与采购建议（演示数据）：\n"+ "\n".join([f"- {r['sku']} {r['name']}：库存 {r['stock']}，安全库存 {r['safety_stock']}，交期 {r['lead_days']}天，供应商：{r['supplier']}；"+("低于安全库存，建议评估补货" if r['stock']<r['safety_stock'] else "库存暂高于安全库存") for r in rows])
        answer += "\n采购量需结合未来订单需求和供应商最小起订量进一步计算。"
        logs += ["供应链Agent：检查库存与安全库存阈值。","供应链规则：识别低于安全库存的物料。"]
    log(agent, q+" | "+answer[:500])
    return agent, answer, logs

init_db()

st.markdown("""
<style>
.block-container {padding-top: 1.5rem; max-width: 1400px;}
[data-testid="stMetric"] {background: #f6f8fb; padding: 14px; border-radius: 12px;}
.small-muted {color:#718096;font-size:0.85rem}
</style>
""", unsafe_allow_html=True)

st.title("📦 MemFind 2.0")
st.caption("面向柔性制造与仓储供应链的空间语义记忆 Agent｜可运行模拟原型")

with db() as c:
    item_n=c.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    order_n=c.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    equip_n=c.execute("SELECT COUNT(*) FROM equipment").fetchone()[0]
    low_n=c.execute("SELECT COUNT(*) FROM materials WHERE stock < safety_stock").fetchone()[0]

m1,m2,m3,m4=st.columns(4)
m1.metric("记忆物品",item_n)
m2.metric("待处理订单",order_n)
m3.metric("设备记录",equip_n)
m4.metric("低库存物料",low_n)

tabs=st.tabs(["智能体工作台","空间记忆库","制造业务看板","运行记录"])

with tabs[0]:
    st.subheader("用自然语言描述你的任务")
    st.write("示例：帮我找红色急件箱｜查看设备故障｜哪些物料低于安全库存？｜分析质量异常批次")
    if "history" not in st.session_state: st.session_state.history=[]
    q=st.chat_input("例如：帮我找红色急件箱，它在哪个货架？")
    if q:
        agent, answer, logs=run_agent(q)
        st.session_state.history.append((q,agent,answer,logs))
    for q0,agent,answer,logs in reversed(st.session_state.history):
        with st.chat_message("user"): st.write(q0)
        with st.chat_message("assistant"):
            st.caption("调度结果："+agent)
            st.write(answer)
            with st.expander("查看Agent执行过程"):
                for x in logs: st.write("• "+x)
    st.info("当前版本使用可解释的规则路由与SQLite模拟数据；尚未接入真实大模型、MES、ERP或实体小车。")

with tabs[1]:
    st.subheader("空间语义记忆库")
    rows=item_rows()
    st.dataframe([dict(r) for r in rows], use_container_width=True, hide_index=True)
    st.markdown("#### 新增一条物品记忆")
    with st.form("add_item"):
        a,b,c1=st.columns(3)
        name=a.text_input("物品名称")
        aliases=b.text_input("别名（逗号分隔）")
        color=c1.text_input("颜色")
        d,e,f=st.columns(3)
        zone=d.text_input("区域", "A区")
        shelf=e.text_input("货架", "01")
        level=f.text_input("层", "1")
        g,h,i=st.columns(3)
        slot=g.text_input("货位", "01")
        batch=h.text_input("批次")
        qty=i.number_input("库存数量", min_value=0, value=1)
        urgency=st.selectbox("紧急程度",["普通","高"])
        submitted=st.form_submit_button("保存记忆")
        if submitted and name:
            with db() as conn:
                conn.execute("INSERT INTO items(name,aliases,color,urgency,zone,shelf,level,slot,batch,quantity,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                             (name,aliases,color,urgency,zone,shelf,level,slot,batch,int(qty),datetime.now().isoformat(timespec="seconds")))
            log("记忆写入",f"新增物品：{name}")
            st.success("已保存。刷新页面后可检索。")
    if st.button("恢复演示数据（清空后重置）"):
        if DB_PATH.exists(): DB_PATH.unlink()
        init_db()
        st.rerun()

with tabs[2]:
    st.subheader("制造业务模拟数据")
    c1,c2=st.columns(2)
    with c1:
        st.markdown("**生产订单**")
        with db() as conn: st.dataframe([dict(x) for x in conn.execute("SELECT * FROM orders")], use_container_width=True, hide_index=True)
        st.markdown("**设备状态**")
        with db() as conn: st.dataframe([dict(x) for x in conn.execute("SELECT * FROM equipment")], use_container_width=True, hide_index=True)
    with c2:
        st.markdown("**质量批次**")
        with db() as conn: st.dataframe([dict(x) for x in conn.execute("SELECT * FROM quality")], use_container_width=True, hide_index=True)
        st.markdown("**库存与供应商**")
        with db() as conn: st.dataframe([dict(x) for x in conn.execute("SELECT * FROM materials")], use_container_width=True, hide_index=True)

with tabs[3]:
    st.subheader("Agent运行记录")
    with db() as conn: ev=conn.execute("SELECT * FROM events ORDER BY id DESC LIMIT 100").fetchall()
    if ev: st.dataframe([dict(x) for x in ev], use_container_width=True, hide_index=True)
    else: st.write("暂无运行记录。先在智能体工作台发起一次任务。")

st.divider()
st.caption("MemFind 2.0 Prototype · 演示数据仅用于功能验证，不代表真实工厂运行结果。")
