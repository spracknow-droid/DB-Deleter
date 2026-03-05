import streamlit as st
import sqlite3
import os
import tempfile
import shutil

# 페이지 설정
st.set_page_config(page_title="DB-Deleter", page_icon="🗑️")
st.title("🗑️ DB-Deleter")

# 1. 파일 업로드 관리 (Session State 이용)
if 'db_path' not in st.session_state:
    st.session_state.db_path = None

with st.sidebar:
    st.header("1. 파일 업로드")
    uploaded_file = st.file_uploader("SQLite DB 파일을 선택하세요", type=["db", "sqlite", "sqlite3"])
    
    if uploaded_file:
        # 새로운 파일이 업로드되면 임시 파일 생성
        if st.session_state.db_path is None:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
                tmp.write(uploaded_file.getvalue())
                st.session_state.db_path = tmp.name
    else:
        # 파일이 제거되면 경로 초기화
        st.session_state.db_path = None

# 2. DB 작업 로직
if st.session_state.db_path and os.path.exists(st.session_state.db_path):
    try:
        conn = sqlite3.connect(st.session_state.db_path)
        cursor = conn.cursor()

        # 목록 가져오기
        cursor.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%';")
        items = cursor.fetchall()
        tables = [i[0] for i in items if i[1] == 'table']
        views = [i[0] for i in items if i[1] == 'view']

        col1, col2 = st.columns(2)
        col1.write("📊 **Tables:**")
        col1.write(tables)
        col2.write("👁️ **Views:**")
        col2.write(views)

        st.divider()

        # 3. 삭제 실행
        to_delete = st.multiselect("삭제할 항목 선택", tables + views)
        
        if st.button("🔥 선택한 항목 삭제 실행"):
            if to_delete:
                for name in to_delete:
                    # 테이블인지 뷰인지 판별해서 삭제
                    t_type = "TABLE" if name in tables else "VIEW"
                    cursor.execute(f"DROP {t_type} IF EXISTS {name}")
                
                conn.commit()
                conn.execute("VACUUM") # 실제 파일 용량 줄이기
                st.success(f"'{', '.join(to_delete)}' 삭제 완료!")
                st.rerun() # 변경사항 반영을 위해 앱 재실행
            else:
                st.warning("삭제할 항목을 먼저 선택하세요.")

        # 4. 다운로드
        st.divider()
        with open(st.session_state.db_path, "rb") as f:
            st.download_button(
                label="✅ 삭제 반영된 DB 다운로드",
                data=f,
                file_name=f"deleted_{uploaded_file.name if uploaded_file else 'db'}.db",
                mime="application/x-sqlite3"
            )
        
        conn.close()

    except Exception as e:
        st.error(f"오류 발생: {e}")
else:
    st.info("파일을 업로드하면 DB-Deleter가 가동됩니다.")
