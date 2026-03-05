import pandas as pd
import sqlite3
import io
import streamlit as st

# (기존 clean_data 함수가 있다고 가정)
def clean_data(df, target_type):
    # 공백 제거 및 날짜 형식 변환 로직 (예시)
    df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
    date_cols = ['수리일자', '선적기한', '선적일자', '매출일자', '계획일자']
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce').dt.strftime('%Y-%m-%d')
    return df

# DB 연결 (기존 연결 객체 conn 사용 가정)
# conn = sqlite3.connect('my_data.db', check_same_thread=False)

# --- 파일 업로드 섹션 ---
excel_files = st.file_uploader(
    "엑셀 파일을 선택하세요 (다중 선택 가능)", 
    type=['xlsx', 'xls'], 
    accept_multiple_files=True  # 여러 파일을 받으려면 True여야 합니다
)

# --- 로직 2: 엑셀 파일 처리 ---
if excel_files:
    for file in excel_files:
        fname = file.name
        str_converters = {}
        
        # 1. 파일 유형별 설정 정의
        if "수출이행내역기간조회" in fname:
            target_table = "Export_Execution"
            target_type = "EXPORT"
            str_converters = {'수출신고번호': str, '란번호': str, '규격번호': str}
        elif "SLSSPN" in fname:
            target_table = "sales_plan_data"
            target_type = "SLSSPN"
            str_converters = {'매출처': str, '품목코드': str}
        elif "BILBIV" in fname:
            target_table = "sales_actual_data"
            target_type = "BILBIV"
            str_converters = {'매출처': str, '품목': str, '수금처': str, '납품처': str}
        else:
            st.warning(f"⚠️ 처리할 수 없는 파일 형식입니다: {fname}")
            continue

        # 2. 엑셀 읽기 및 전처리
        try:
            df = pd.read_excel(file, converters=str_converters)
            df = clean_data(df, target_type)

            # BILBIV 특이 로직 (합계 행 제외)
            if target_type == "BILBIV" and '매출번호' in df.columns:
                df = df[~df['매출번호'].astype(str).str.contains('합계')]

            # 3. DB 스키마 맞춤 및 저장 (안전한 Append)
            try:
                # 기존 테이블의 컬럼 리스트 확인
                existing_cols = pd.read_sql(f"SELECT * FROM {target_table} LIMIT 0", conn).columns.tolist()
                
                # 엑셀에 없는 컬럼은 None으로 채우고, 순서를 기존 DB와 맞춤
                for col in existing_cols:
                    if col not in df.columns:
                        df[col] = None
                df = df[existing_cols]
                
                df.to_sql(target_table, conn, if_exists="append", index=False)
            except:
                # 테이블이 없는 경우 최초 생성
                df.to_sql(target_table, conn, if_exists="replace", index=False)

            # 4. SQL 기반 중복 제거 (전체 컬럼 비교 방식)
            # 모든 컬럼을 쌍따옴표로 감싸서 공백이나 특수문자 대응
            safe_columns = [f'"{col}"' for col in df.columns]
            group_cols = ", ".join(safe_columns)
            
            # rowid가 가장 큰(최신) 데이터 하나만 남기고 삭제
            dedup_sql = f"""
            DELETE FROM {target_table} 
            WHERE rowid NOT IN (
                SELECT MAX(rowid) FROM {target_table} GROUP BY {group_cols}
            )
            """
            conn.execute(dedup_sql)
            conn.commit()
            st.success(f"✅ {fname} 반영 완료 (Table: {target_table})")

        except Exception as e:
            st.error(f"❌ {fname} 처리 중 오류 발생: {e}")

# --- 데이터 확인 (탭 구성) ---
st.divider()
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
            st.info("조회할 테이블이 아직 생성되지 않았습니다.")

display_tab_data("sales_plan_data", tab1)
display_tab_data("sales_actual_data", tab2)
display_tab_data("Export_Execution", tab3)

# --- 내보내기 (Excel 통합 파일) ---
st.sidebar.divider()
if st.sidebar.button("📥 Excel 통합 파일 생성"):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        tables = {
            "sales_plan_data": "판매계획",
            "sales_actual_data": "매출실적",
            "Export_Execution": "수출이행"
        }
        for table, sheet in tables.items():
            try:
                pd.read_sql(f"SELECT * FROM {table}", conn).to_excel(writer, sheet_name=sheet, index=False)
            except:
                pass
    
    st.sidebar.download_button(
        label="📊 통합 파일 다운로드",
        data=output.getvalue(),
        file_name="integrated_data.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
