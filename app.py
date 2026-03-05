import pandas as pd
import sqlite3
import io
import streamlit as st
import os

# --- [설정] 페이지 레이아웃 및 DB 연결 ---
st.set_page_config(layout="wide")
db_name = 'my_data.db'

# 데이터베이스 연결 (자동 닫기를 위해 함수 내에서 처리하거나 유지)
conn = sqlite3.connect(db_name, check_same_thread=False)

# --- [함수] 데이터 전처리 ---
def clean_data(df, target_type):
    # applymap 대신 최신 Pandas 권장 사항인 map 사용 (경고 방지)
    df = df.map(lambda x: x.strip() if isinstance(x, str) else x)
    date_cols = ['수리일자', '선적기한', '선적일자', '매출일자', '계획일자', '신고일자']
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce').dt.strftime('%Y-%m-%d')
    return df

# --- [사이드바] 데이터 업로드 ---
with st.sidebar:
    st.header("📂 데이터 업로드")
    excel_files = st.file_uploader(
        "엑셀 파일을 선택하세요", 
        type=['xlsx', 'xls'], 
        accept_multiple_files=True
    )

# --- [메인 로직] 엑셀 파일 처리 ---
if excel_files:
    for file in excel_files:
        fname = file.name
        str_converters = {}
        
        if "수출이행내역기간조회" in fname:
            target_table, target_type = "Export_Execution", "EXPORT"
            str_converters = {'수출신고번호': str, '란번호': str, '규격번호': str}
        elif "SLSSPN" in fname:
            target_table, target_type = "sales_plan_data", "SLSSPN"
            str_converters = {'매출처': str, '품목코드': str}
        elif "BILBIV" in fname:
            target_table, target_type = "sales_actual_data", "BILBIV"
            str_converters = {'매출처': str, '품목': str, '수금처': str, '납품처': str}
        else:
            continue

        try:
            df = pd.read_excel(file, converters=str_converters)
            df = clean_data(df, target_type)
            
            if target_type == "BILBIV" and '매출번호' in df.columns:
                df = df[~df['매출번호'].astype(str).str.contains('합계')]

            try:
                existing_cols = pd.read_sql(f"SELECT * FROM {target_table} LIMIT 0", conn).columns.tolist()
                for col in existing_cols:
                    if col not in df.columns: df[col] = None
                df = df[existing_cols]
                df.to_sql(target_table, conn, if_exists="append", index=False)
            except:
                df.to_sql(target_table, conn, if_exists="replace", index=False)

            # 중복 제거 (rowid 기반)
            safe_columns = [f'"{col}"' for col in df.columns]
            group_cols = ", ".join(safe_columns)
            conn.execute(f"DELETE FROM {target_table} WHERE rowid NOT IN (SELECT MAX(rowid) FROM {target_table} GROUP BY {group_cols})")
            conn.commit()
            st.toast(f"✅ {fname} 반영 완료")
        except Exception as e:
            st.error(f"❌ {fname} 오류: {e}")

# --- [메인 화면] 데이터 확인 ---
st.title("📈 통합 데이터 관리 시스템")
tabs = st.tabs(["📊 판매계획", "📋 매출리스트", "🚢 수출이행내역"])
tables = ["sales_plan_data", "sales_actual_data", "Export_Execution"]

for tab, table in zip(tabs, tables):
    with tab:
        try:
            df_view = pd.read_sql(f"SELECT * FROM {table}", conn)
            if not df_view.empty:
                st.write(f"현재 데이터: **{len(df_view)}** 행")
                st.dataframe(df_view, use_container_width=True)
            else:
                st.info("데이터가 비어있습니다.")
        except:
            st.info("아직 데이터가 업로드되지 않았습니다.")

# --- [사이드바 하단] 내보내기 전용 ---
st.sidebar.divider()
st.sidebar.header("📥 데이터베이스 내보내기")

if os.path.exists(db_name):
    with open(db_name, "rb") as f:
        db_byte = f.read()
    st.sidebar.download_button(
        label="🗄️ SQLite DB 파일 다운로드",
        data=db_byte,
        file_name="integrated_data.db",
        mime="application/x-sqlite3"
    )
else:
    st.sidebar.info("생성된 DB 파일이 없습니다.")
