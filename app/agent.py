import datetime
from zoneinfo import ZoneInfo
from google.adk.agents import Agent
import os
import requests
from typing import Dict
import requests
import feedparser
from typing import Dict, List

county_city_aliases = {
    '臺北市': ['台北', '臺北', '台北市', '北市', '首都', '天龍國'],
    '新北市': ['新北', '新北市', '台北縣'],
    '桃園市': ['桃園', '桃園市', '桃縣'],
    '臺中市': ['台中', '臺中', '台中市'],
    '臺南市': ['台南', '臺南', '台南市'],
    '高雄市': ['高雄', '高雄市', '港都'],
    '基隆市': ['基隆', '基隆市'],
    '新竹市': ['新竹市', '竹市'],
    '新竹縣': ['新竹縣', '竹縣'],
    '苗栗縣': ['苗栗', '苗栗縣'],
    '彰化縣': ['彰化', '彰化縣'],
    '南投縣': ['南投', '南投縣', '中央山脈'],
    '雲林縣': ['雲林', '雲林縣'],
    '嘉義市': ['嘉義市', '嘉市'],
    '嘉義縣': ['嘉義縣', '嘉縣'],
    '屏東縣': ['屏東', '屏東縣'],
    '宜蘭縣': ['宜蘭', '宜蘭縣'],
    '花蓮縣': ['花蓮', '花蓮縣'],
    '臺東縣': ['台東', '臺東', '台東縣', '臺東縣'],
    '澎湖縣': ['澎湖', '澎湖縣', '澎湖群島'],
    '金門縣': ['金門', '金門縣'],
    '連江縣': ['連江', '連江縣', '馬祖'],
}

# 查詢函式
def get_standard_county(input_name):
    for standard_name, aliases in county_city_aliases.items():
        if input_name in aliases:
            return standard_name
    return input_name

def get_weather(city: str) -> Dict:
    """根據指定城市查詢中央氣象署三十六小時天氣預報，並格式化成英文天氣報告。

    Args:
        city (str): 查詢城市名稱，需為中央氣象署資料中的有效名稱。

    Returns:
        dict: 包含查詢狀態與格式化天氣報告或錯誤訊息。
    """
    city = get_standard_county(city)
    try:
        api_url = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001"
        params = {
            "Authorization": os.getenv("CWB_API_KEY"),
            "format": "JSON",
            "locationName": city
        }
        response = requests.get(api_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data["success"] != "true":
            return {
                "status": "error",
                "error_message": "API 回傳失敗，請確認授權碼或參數。"
            }

        location_data = data["records"]["location"][0]
        weather_elements = {element["elementName"]: element["time"] for element in location_data["weatherElement"]}

        # 取第一個時間區段的預報
        first_period = weather_elements["Wx"][0]
        weather_desc = first_period["parameter"]["parameterName"]

        min_temp = weather_elements["MinT"][0]["parameter"]["parameterName"]
        max_temp = weather_elements["MaxT"][0]["parameter"]["parameterName"]

        # 格式化英文報告
        report = (
            f"The weather in {city} is '{weather_desc}' with a temperature range of "
            f"{min_temp} to {max_temp} degrees Celsius."
        )

        return {
            "status": "success",
            "report": report
        }

    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "error_message": f"HTTP request error: {str(e)}"
        }
    except (KeyError, IndexError):
        return {
            "status": "error",
            "error_message": f"Weather information for '{city}' is not available."
        }

def get_current_time(city: str) -> dict:
    """Returns the current time in a specified city.

    Args:
        city (str): The name of the city for which to retrieve the current time.

    Returns:
        dict: status and result or error msg.
    """

    if city.lower() == "new york":
        tz_identifier = "America/New_York"
    else:
        return {
            "status": "error",
            "error_message": (
                f"Sorry, I don't have timezone information for {city}."
            ),
        }

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    report = (
        f'The current time in {city} is {now.strftime("%Y-%m-%d %H:%M:%S %Z%z")}'
    )
    return {"status": "success", "report": report}

def chcg_search_news(keyword: str) -> Dict:
    """
    從彰化縣政府 RSS 搜尋與關鍵字最相近的新聞。

    Args:
        keyword (str): 搜尋的關鍵字。

    Returns:
        dict: 包含搜尋結果的狀態與相關新聞，或錯誤訊息。
    """
    rss_url = "https://www.chcg.gov.tw/ch2/rssnews2b.aspx"
    # 自訂 User-Agent 模擬瀏覽器請求，避免被伺服器封鎖
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/115.0.0.0 Safari/537.36"
        )
    }

    try:
        # 1. 使用 requests 取得 RSS 內容
        resp = requests.get(rss_url, headers=headers, timeout=10)
        # 2. 確認 HTTP 回應狀態碼
        if resp.status_code != 200:
            return {
                "status": "error",
                "error_message": f"HTTP 錯誤，狀態碼：{resp.status_code}"
            }
        # 3. 設定編碼並解析
        resp.encoding = "utf-8"
        feed = feedparser.parse(resp.text)

        # 4. 檢查 XML 格式錯誤
        if getattr(feed, "bozo", False):
            return {
                "status": "error",
                "error_message": f"RSS 格式解析失敗：{feed.bozo_exception}"
            }
        # 5. 確認有新聞項目
        if not feed.entries:
            return {
                "status": "error",
                "error_message": "RSS 中找不到任何新聞項目。"
            }

        # 6. 搜尋相關新聞
        matched_news: List[Dict] = []
        for entry in feed.entries:
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            link = entry.get("link", "")
            if keyword.lower() in title.lower() or keyword.lower() in summary.lower():
                matched_news.append({
                    "title": title,
                    "summary": summary,
                    "link": link
                })

        # 7. 回傳搜尋結果或空結果
        if not matched_news:
            return {
                "status": "error",
                "error_message": f"未找到與關鍵字「{keyword}」相關的新聞。"
            }

        # 8. 組成前 3 筆新聞報表
        report_lines = [
            f"Title: {news['title']}\n"
            f"Summary: {news['summary']}\n"
            f"Link: {news['link']}\n"
            for news in matched_news[:3]
        ]
        return {
            "status": "success",
            "report": "\n".join(report_lines)
        }

    except requests.RequestException as re:
        # 網路或 HTTP 相關錯誤
        return {
            "status": "error",
            "error_message": f"網路請求異常：{str(re)}"
        }
    except Exception as e:
        # 其他意外錯誤
        return {
            "status": "error",
            "error_message": f"RSS 解析異常：{str(e)}"
        }

root_agent = Agent(
    name="weather_time_news_agent",
    model="gemini-2.0-flash",
    description=(
        "An intelligent agent capable of providing real-time weather forecasts for Taiwanese cities and retrieving the latest related news from Changhua County's official RSS feed."
    ),
    instruction=(
        "You can ask me about the weather forecast for any city in Taiwan, "
        "and I can also search for recent news from Changhua County Government based on your keywords."
    ),
    tools=[get_weather, chcg_search_news],
)
