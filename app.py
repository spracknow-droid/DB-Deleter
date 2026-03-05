import streamlit as st
import sqlite3
import os
import tempfile

st.set_page_config(page_title="SQLite 테이블 관리자", layout="wide")

st.title("📂 SQLite DB 관리 및 테이블 삭제 도구")
st.markdown("사이드바에서 DB 파일을 업로드하고, 삭제할 테이블이나 뷰를 선택하세요.")

# --- 사이드바: 파일 업로드 ---
with st.sidebar:
    st.header("1. 파일 업로드")
    uploaded_file = st.file_uploader("SQLite DB 파일을 선택하세요", type=["db", "sqlite", "sqlite3"])

if uploaded_file is not None:
    # 임시 디렉토리에 파일 저장 (sqlite3는 파일 경로가 필요함)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        tmp_path = tmp_file.name

    try:
        # DB 연결
        conn = sqlite3.connect(tmp_path)
        cursor = conn.cursor()

        # --- 데이터베이스 구조 읽기 ---
        # 물리적 테이블과 VIEW를 모두 가져옵니다.
        cursor.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%';")
        items = cursor.fetchall()
        
        tables = [item[0] for item in items if item[1] == 'table']
        views = [item[0] for item in items if item[1] == 'view']

        # --- 메인 화면: 정보 표시 ---
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("📊 물리적 테이블")
            st.write(tables if tables else "테이블이 없습니다.")
            
        with col2:
            st.subheader("👁️ VIEW 목록")
            st.write(views if views else "View가 없습니다.")

        st.divider()

        # --- 삭제 섹션 ---
        st.header("2. 테이블/뷰 삭제")
        all_options = tables + views
        to_delete = st.multiselect("삭제할 항목을 선택하세요 (영구 삭제되니 주의하세요!)", all_options)

        if st.button("선택한 항목 삭제 실행"):
            if to_delete:
                for name in to_delete:
                    target_type = "TABLE" if name in tables else "VIEW"
                    cursor.execute(f"DROP {target_type} IF EXISTS {name}")
                
                conn.commit()
                # 공간 최적화 (파일 용량 줄이기)
                conn.execute("VACUUM")
                st.success(f"성공적으로 삭제되었습니다: {', '.join(to_delete)}")
                st.rerun() # 상태 업데이트를 위해 재실행
            else:
                st.warning("삭제할 항목을 선택하지 않았습니다.")

        # --- 다운로드 섹션 ---
        st.divider()
        st.header("3. 결과 다운로드")
        
        with open(tmp_path, "rb") as f:
            st.download_button(
                label="수정된 DB 파일 다운로드",
                data=f,
                file_name=f"modified_{uploaded_file.name}",
                mime="application/x-sqlite3"
            )

        conn.close()

    except Exception as e:
        st.error(f"에러가 발생했습니다: {e}")
    
    finally:
        # 임시 파일 삭제는 세션 종료 시나 로직에 따라 관리 필요
        pass

else:
    st.info("왼쪽 사이드바에서 SQLite 파일을 업로드해주세요.")
