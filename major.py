# main.py
import datetime
import requests
import pandas as pd
import streamlit as st

# 1. 스트림릿 페이지 레이아웃 및 제목 설정
st.set_page_config(
    page_title="어제 박스오피스 순위",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 어제일자 일별 박스오피스")

# 2. 한국 표준시(KST, UTC+9) 기준으로 '어제' 날짜 계산
# (배포 서버 시계가 해외 기준이어도 시차 문제를 방지합니다)
kst_timezone = datetime.timezone(datetime.timedelta(hours=9))
today_kst = datetime.datetime.now(kst_timezone)
yesterday_kst = today_kst - datetime.timedelta(days=1)

# API 요청용 날짜 형식 (YYYYMMDD)
target_dt = yesterday_kst.strftime("%Y%m%d")
# 화면 표시용 날짜 형식 (YYYY년 MM월 DD일)
formatted_date = yesterday_kst.strftime("%Y년 %m월 %d일")

st.caption(f"📅 **조회 기준일:** {formatted_date}")

# 3. KOBIS API 데이터 불러오기 함수 (1시간 동안 데이터 재사용)
@st.cache_data(ttl=3600)
def get_box_office_data(api_key: str, date_str: str):
    url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
    params = {
        "key": api_key,
        "targetDt": date_str
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        
        # HTTP 응답 코드 확인
        if response.status_code != 200:
            return None, f"서버 통신 실패 (상태 코드: {response.status_code})"
        
        data = response.json()
        
        # API 오류 상자(faultInfo)가 반환된 경우 처리
        if "faultInfo" in data:
            error_msg = data["faultInfo"].get("message", "API 키가 올바르지 않거나 오류가 발생했습니다.")
            return None, f"API 오류 발생: {error_msg}"
        
        # 영화 목록 추출 및 빈 데이터 확인
        box_office_result = data.get("boxOfficeResult", {})
        daily_list = box_office_result.get("dailyBoxOfficeList", [])
        
        if not daily_list:
            return None, "해당 날짜의 영화 목록이 비어 있습니다."
            
        return daily_list, None

    except requests.exceptions.RequestException as e:
        return None, f"네트워크 요청에 실패했습니다: {e}"

# 4. Streamlit Secrets에서 API 키 불러오기
if "KOBIS_KEY" not in st.secrets:
    st.error("🚨 API 키를 찾을 수 없습니다.")
    st.warning(
        """
        **확인해야 할 사항:**
        1. **Streamlit Cloud 배포 환경:** 앱 설정(App settings) -> **Secrets** 메뉴에 `KOBIS_KEY`를 등록했는지 확인하세요.
        2. **로컬 실행 환경:** 프로젝트 폴더 내 `.streamlit/secrets.toml` 파일에 아래와 같이 입력되어 있는지 확인하세요.
           ```toml
           KOBIS_KEY = "발급받은_인증키_입력"
           ```
        """
    )
    st.stop()

api_key = st.secrets["KOBIS_KEY"]

# 5. 데이터 요청 및 예외 처리
data_list, error_message = get_box_office_data(api_key, target_dt)

if error_message:
    st.error(f"🚨 데이터를 불러오지 못했습니다: {error_message}")
    st.info(
        """
        **문제 해결 가이드:**
        - **API 키 확인:** `KOBIS_KEY`에 전달된 값이 영화관입장권통합전산망(KOBIS)에서 발급받은 정식 키인지 확인하세요.
        - **일일 트래픽 초과:** KOBIS API의 일일 허용 호출 수(기본 3,000회)를 초과했는지 확인하세요.
        - **집계 시간 확인:** 오늘 날짜가 아닌 '어제' 날짜로 정상 요청되었는지 확인하세요.
        """
    )
else:
    # 6. 데이터 변환 및 데이터 타입 변경 (문자열 -> 숫자)
    df = pd.DataFrame(data_list)
    
    # 문자로 들어오는 숫자 데이터들을 정수형(int)으로 변경
    numeric_columns = ["rank", "audiCnt", "audiAcc", "scrnCnt"]
    for col in numeric_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    
    # 순위 기준 정렬
    df = df.sort_values(by="rank").reset_index(drop=True)
    
    # 7. 1위 영화 대형 지표 카드 표시
    top_1 = df.iloc[0]
    st.subheader(f"🥇 1위 영화: **{top_1['movieNm']}**")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("어제 관객수", f"{int(top_1['audiCnt']):,} 명")
    col2.metric("누적 관객수", f"{int(top_1['audiAcc']):,} 명")
    col3.metric("스크린수", f"{int(top_1['scrnCnt']):,} 개")
    
    st.divider()
    
    # 8. 관객수 상위 5편 막대그래프
    st.subheader("📊 관객수 TOP 5 영화")
    top_5_df = df.head(5)[["movieNm", "audiCnt"]].set_index("movieNm")
    st.bar_chart(top_5_df["audiCnt"])
    
    st.divider()
    
    # 9. 전체 순위 표 출력
    st.subheader("📋 박스오피스 전체 순위")
    
    # 표에 출력할 컬럼 선택 및 이름 변경
    table_df = df[["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]].copy()
    table_df.columns = ["순위", "영화명", "개봉일", "관객수", "누적관객", "스크린수"]
    
    st.dataframe(
        table_df,
        column_config={
            "순위": st.column_config.NumberColumn(format="%d위"),
            "관객수": st.column_config.NumberColumn(format="%d명"),
            "누적관객": st.column_config.NumberColumn(format="%d명"),
            "스크린수": st.column_config.NumberColumn(format="%d개"),
        },
        use_container_width=True,
        hide_index=True
    )
