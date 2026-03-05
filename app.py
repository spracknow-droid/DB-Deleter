import pandas as pd
import sqlite3
import io
import streamlit as st

# --- [설정] 페이지 레이아웃 및 DB 연결 ---
st.set_page_config(layout="wide") # 넓은 화면 사용
conn = sqlite3.connect('my_data.db', check_same_thread=False)

# --- [함수] 데이터 전처리 ---
def clean_data(df, target_type):
    # 공백 제거
    df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
    # 날짜 컬럼 변환
    date_cols = ['수리일자', '선적기한', '선적일자', '매출일자', '계획일자', '신고일자']
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce').dt.strftime('%Y-%m-%d')
    return df

# --- [사이드바] 파일 업로드 섹션 ---
with st.sidebar:
    st.header("📂 데이터 업로드")
    excel_files = st.file_uploader(
        "엑셀 파일을 선택하세요 (다중 선택 가능)", 
        type=['xlsx', 'xls'], 
        accept_multiple_files=True
    )
    st.info("수출이행, SLSSPN, BILBIV 키워드가 포함된 파일을 올려주세요.")

# --- [메인 로직] 엑셀 파일 처리 ---
if excel_files:
    for file in excel_files:
        fname = file.name
        str_converters = {}
        
        # 1. 파일 유형별 설정
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

        # 2. 읽기 및 저장
        try:
            df = pd.read_excel(file, converters=str_converters)
            df = clean_data(df, target_type)

            if target_type == "BILBIV" and '매출번호' in df.columns:
                df = df[~df['매출번호'].astype(str).str.contains('합계')]

            # DB 저장 (Schema Matching)
            try:
                existing_cols = pd.read_sql(f"SELECT * FROM {target_table} LIMIT 0", conn).columns.tolist()
                for col in existing_cols:
                    if col not in df.columns: df[col] = None
                df = df[existing_cols]
                df.to_sql(target_table, conn, if_exists="append", index=False)
            except:
                df.to_sql(target_table, conn, if_exists="replace", index=False)

            # 3. 중복 제거
            safe_columns = [f'"{col}"' for col in df.columns]
            group_cols = ", ".join(safe_columns)
            dedup_sql = f"""
                DELETE FROM {target_table} 
                WHERE rowid NOT IN (SELECT MAX(rowid) FROM {target_table} GROUP BY {group_cols})
            """
            conn.execute(dedup_sql)
            conn.commit()
            st.toast(f"✅ {fname} 업로드 완료!") # 화면 하단에 가볍게 알림

        except Exception as e:
            st.error(f"❌ {fname} 처리 중 오류: {e}")

# --- [메인 화면] 데이터 확인 (탭) ---
st.title("📈 통합 데이터 관리 시스템")
tab1, tab2, tab3 = st.tabs(["📊 판매계획 (Plan)", "📋 매출리스트 (Actual)", "🚢 수출이행내역 (Export)"])

def display_tab_data(table_name, tab_obj):
    with tab_obj:
        try:
            df_view = pd.read_sql(f"SELECT * FROM {table_name}", conn)
            if not df_view.empty:
                st.write(f"현재 데이터: **{len(df_view)}** 행")
                st.dataframe(df_view, use_container_width=True)
            else:
                st.info("데이터가 비어있습니다.")
        except:
            st.info("데이터가 없습니다. 파일을 먼저 업로드해주세요.")

display_tab_data("sales_plan_data", tab1)
display_tab_data("sales_actual_data", tab2)
display_tab_data("Export_Execution", tab3)

# --- [사이드바 하단] 내보내기 섹션 ---
st.sidebar.divider()
st.sidebar.header("📥 데이터 내보내기")
if st.sidebar.button("Excel 통합 파일 생성"):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        tables = {"sales_plan_data": "판매계획", "sales_actual_data": "매출실적", "Export_Execution": "수출이행"}
        found_any = False
        for table, sheet in tables.items():
            try:
                temp_df = pd.read_sql(f"SELECT * FROM {table}", conn)
                if not temp_df.empty:
                    temp_df.to_excel(writer, sheet_name=sheet, index=False)
                    found_any = True
            except: pass
        
    if found_any:
        st.sidebar.download_button(
            label="📊 통합 파일 다운로드",
            data=output.getvalue(),
            file_name="integrated_data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.sidebar.error("내보낼 데이터가 없습니다.")
