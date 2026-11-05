import streamlit as st
from datetime import time

RESOURCES = {
    "R1": {"name": "示波器",   "capacity": 1},
    "R2": {"name": "3D打印机", "capacity": 1},
    "R3": {"name": "工位区",   "capacity": 10},
}

# ==================== 状态初始化 ====================
if "events" not in st.session_state:
    st.session_state.events = []
    st.session_state.next_id = 1
if "pending_event" not in st.session_state:
    st.session_state.pending_event = None  # 暂存待处理的更替请求
if "replace_target_id" not in st.session_state:
    st.session_state.replace_target_id = None  # 暂存要被踢掉的旧事件ID

def to_min(t):
    return t.hour * 60 + t.minute

def to_str(m):
    return f"{m // 60:02d}:{m % 60:02d}"

def is_overlap(a, b):
    return a["start"] < b["end"] and b["start"] < a["end"]

# ==================== 核心算法 ====================

def get_available_slots(resource_id, req_start, req_end, ignore_id=None):
    cap = RESOURCES[resource_id]["capacity"]
    occupied = 0
    for ev in st.session_state.events:
        if ev["id"] == ignore_id:
            continue
        if ev["resource"] == resource_id and is_overlap({"start": req_start, "end": req_end}, ev):
            occupied += ev["headcount"]
    return cap - occupied

def process_booking(new_ev):
    """纯业务判定：返回状态和需要操作的对象"""
    # 1. 身份冲突判定
    if new_ev["user_id"]:
        for ev in st.session_state.events:
            if ev["user_id"] == new_ev["user_id"] and is_overlap(new_ev, ev):
                if new_ev["priority"] > ev["priority"]:
                    return "REPLACE_NEEDED", ev["id"], f"此时段已有安排（{ev['title']}），需更替为高优事项？"
                else:
                    return "DENY", None, "您在此时间段已有安排，请调整时间。"
    
    # 2. 容量判定
    avail = get_available_slots(new_ev["resource"], new_ev["start"], new_ev["end"])
    if avail <= 0:
        return "DENY", None, "该时段设备已满。"
    if new_ev["headcount"] > avail:
        # 容量不足，这里为了简单，直接拒绝（要降级逻辑的话你之前已经有了）
        return "DENY", None, f"当前仅剩 {avail} 个空位，无法满足人数。"

    return "OK", None, "预约成功"

def commit_event(ev, replace_id=None):
    """真正入库"""
    if replace_id:
        st.session_state.events = [e for e in st.session_state.events if e["id"] != replace_id]
    
    ev["id"] = f"E{st.session_state.next_id}"
    st.session_state.next_id += 1
    st.session_state.events.append(ev)
    
    # 清理暂存区
    st.session_state.pending_event = None
    st.session_state.replace_target_id = None
    st.rerun()

# ==================== 页面渲染 ====================

st.set_page_config(page_title="设备预约系统 V3.2", layout="wide")
st.title("设备预约系统 V3.2")

tab1, tab2, tab3 = st.tabs(["教师排课", "学生预约", "实时状态"])

# --- 学生预约 ---
with tab2:
    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    s_title = c1.text_input("事项", value="上课")
    s_uid = c2.text_input("学生学号", value="S202301")
    s_res = c3.selectbox("设备 ", list(RESOURCES), format_func=lambda x: RESOURCES[x]["name"])
    s_prio = c4.selectbox("重要度", [1, 2, 3], format_func=lambda x: {1:"低", 2:"中", 3:"高"}[x], index=2)
    s_s = c5.time_input("开始 ", value=time(10, 0))
    s_e = c6.time_input("结束 ", value=time(11, 0))
    
    if c7.button("提交预约"):
        new_ev = {
            "title": s_title, "user_id": s_uid, "resource": s_res, 
            "priority": s_prio, "start": to_min(s_s), "end": to_min(s_e), "headcount": 1
        }
        
        status, target_id, msg = process_booking(new_ev)
        
        if status == "OK":
            commit_event(new_ev)
            st.success(msg)
        elif status == "REPLACE_NEEDED":
            # 存入暂存区，等待用户点击确认按钮
            st.session_state.pending_event = new_ev
            st.session_state.replace_target_id = target_id
            st.warning(msg)
        else:
            st.error(msg)

# 如果暂存区里有待处理的更替请求，渲染一个确认按钮
if st.session_state.pending_event:
    if st.button("确认更替高优事项", type="primary"):
        commit_event(st.session_state.pending_event, st.session_state.replace_target_id)
        st.success("已更替！")

# --- 教师排课（简化版，为了聚焦当前bug） ---
with tab1:
    st.write("教师排课逻辑同前，这里略作精简。")
    t_title = st.text_input("课程名", value="实验课")
    t_uid = st.text_input("教师工号", value="T1001")
    t_res = st.selectbox("设备", list(RESOURCES), format_func=lambda x: RESOURCES[x]["name"])
    t_hc = st.number_input("人数", min_value=1, value=7)
    t_s = st.time_input("开始", value=time(14, 0))
    t_e = st.time_input("结束", value=time(16, 0))
    
    if st.button("提交排课"):
        new_ev = {
            "title": t_title, "user_id": t_uid, "resource": t_res, 
            "priority": 3, "start": to_min(t_s), "end": to_min(t_e), "headcount": t_hc
        }
        status, target_id, msg = process_booking(new_ev)
        if status == "OK":
            commit_event(new_ev)
            st.success(msg)
        elif status == "REPLACE_NEEDED":
            st.session_state.pending_event = new_ev
            st.session_state.replace_target_id = target_id
            st.warning(msg)
        else:
            st.error(msg)

# --- 资源公示 ---
with tab3:
    for rid, r in RESOURCES.items():
        st.markdown(f"**{r['name']}**")
        evs = sorted([e for e in st.session_state.events if e["resource"] == rid], key=lambda x: x["start"])
        for ev in evs:
            col1, col2, col3, col4, col5 = st.columns([2, 2, 1, 1, 1])
            col1.write(f"{to_str(ev['start'])} - {to_str(ev['end'])}")
            col2.write(f"{ev['title']}")
            col3.write(f"用户: {ev['user_id']}")
            col4.write(f"人数: {ev['headcount']}")
            if col5.button("取消", key=f"del_{ev['id']}"):
                st.session_state.events.remove(ev)
                st.rerun()
        st.divider()