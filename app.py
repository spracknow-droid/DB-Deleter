# --- 로직 2: 엑셀 파일 처리 ---
if excel_files:
    for file in excel_files:
        fname = file.name
        
        str_converters = {}
        # [수정] 수출이행내역기간조회 조건 추가
        if "수출이행내역기간조회" in fname:
            target_table = "Export_Execution"
            target_type = "EXPORT"
            # 날짜 및 번호 형식 컬럼을 문자열로 유지 (필요시 컬럼명 조정)
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
            continue

        # 엑셀 읽기
        df = pd.read_excel(file, converters=str_converters)
        
        # 전처리 (공백 제거 및 지정된 3대 날짜 컬럼 '수리일자', '선적기한', '선적일자' 시분초 변환)
        df = clean_data(df, target_type)

        # (기존 BILBIV 합계 제외 로직 유지)
        if target_type == "BILBIV" and '매출번호' in df.columns:
            df = df[df['매출번호'].astype(str).str.contains('합계') == False]

        try:
            # 기존 테이블 구조에 맞춰 컬럼 보정
            existing_columns = pd.read_sql(f"SELECT * FROM {target_table} LIMIT 0", conn).columns.tolist()
            for col in existing_columns:
                if col not in df.columns:
                    df[col] = None
            
            if existing_columns:
                df = df[existing_columns]
                
            df.to_sql(target_table, conn, if_exists="append", index=False)
        except Exception:
            df.to_sql(target_table, conn, if_exists="replace", index=False)

        # SQL 기반 중복 제거
        safe_columns = [f'"{col}"' for col in df.columns]
        group_cols = ", ".join(safe_columns)
        try:
            conn.execute(f"DELETE FROM {target_table} WHERE rowid NOT IN (SELECT MIN(rowid) FROM {target_table} GROUP BY {group_cols})")
            conn.commit()
            st.success(f"✅ {fname} 반영 완료 (Table: {target_table})")
        except sqlite3.OperationalError as e:
            st.error(f"⚠️ {fname} SQL 오류: {e}")

# --- 데이터 확인 (탭 추가) ---
st.divider()
tab1, tab2, tab3 = st.tabs(["판매계획 (Plan)", "매출리스트 (Actual)", "수출이행내역 (Export)"])

# ... (tab1, tab2 로직은 기존과 동일) ...

with tab3:
    try:
        df_e = pd.read_sql("SELECT * FROM Export_Execution", conn)
        if not df_e.empty:
            st.write(f"현재 데이터: **{len(df_e)}** 행")
            st.dataframe(df_e, use_container_width=True)
        else: st.info("데이터가 비어있습니다.")
    except: st.info("데이터가 없습니다.")

# --- 내보내기 (엑셀 시트 추가) ---
# ... (중략) ...
with col2:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        try: pd.read_sql("SELECT * FROM sales_plan_data", conn).to_excel(writer, sheet_name='sales_plan_data', index=False)
        except: pass
        try: pd.read_sql("SELECT * FROM sales_actual_data", conn).to_excel(writer, sheet_name='sales_actual_data', index=False)
        except: pass
        # 수출 데이터 시트 추가
        try: pd.read_sql("SELECT * FROM Export_Execution", conn).to_excel(writer, sheet_name='Export_Execution', index=False)
        except: pass
    st.download_button("📊 Excel 통합 파일 다운로드", output.getvalue(), "integrated_data.xlsx")
