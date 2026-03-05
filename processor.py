import pandas as pd

def clean_data(df, file_type):
    """
    사용자가 지정한 3대 핵심 날짜 컬럼의 시분초를 완벽하게 제거
    지정 컬럼: '수리일자', '선적기한', '선적일자'
    """
    # 1. 모든 데이터의 앞뒤 공백 제거
    df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)

    # 2. 새롭게 지정된 3대 날짜 컬럼 정밀 타격
    target_date_cols = ['수리일자', '선적기한', '선적일자'] # 수정됨

    for col in df.columns:
        if col in target_date_cols:
            try:
                # 시분초를 잘라내고 YYYY-MM-DD 포맷으로 변환
                temp_date = pd.to_datetime(df[col], errors='coerce')
                df[col] = temp_date.dt.strftime('%Y-%m-%d')
                
                # 변환 실패 시 원본 데이터 유지
                df[col] = df[col].fillna(df[col])
            except:
                pass

    return df
