"""
크롤러 기본 모듈

모든 크롤러의 기본 클래스와 유틸리티 함수를 제공합니다.
"""

import asyncio
import logging
import traceback
import os
import time
from pathlib import Path
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import chromedriver_autoinstaller
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import NoSuchElementException, TimeoutException

# 로거 설정
logger = logging.getLogger("backend.crawler.base")

# 결과 저장 경로
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

class CrawlerBase:
    """모든 크롤러의 기본 클래스"""
    
    def __init__(self, headless: bool = False):
        """
        크롤러 초기화
        
        Args:
            headless (bool): 헤드리스 모드 사용 여부
        """
        self.driver = None
        self.wait = None
        self.headless = headless
        self.current_page = None  # 페이지 상태 추적
    
    async def initialize(self):
        """크롤러 초기화 및 웹드라이버 설정"""
        try:
            logger.info("크롤러 초기화 시작")
            
            # ChromeDriver 자동 설치
            chromedriver_autoinstaller.install(True)
            
            # Chrome 옵션 설정
            chrome_options = Options()
            
            # 헤드리스 모드 설정
            if self.headless:
                chrome_options.add_argument('--headless=new')
                logger.info("헤드리스 모드 활성화")
            
            # 기타 옵션 설정
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--disable-popup-blocking')
            chrome_options.add_argument('--lang=ko_KR.UTF-8')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option("useAutomationExtension", False)
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
            
            # 웹드라이버 초기화
            self.driver = webdriver.Chrome(options=chrome_options)
            self.wait = WebDriverWait(self.driver, 10)
            
            logger.info("크롤러 초기화 성공")
            return True
        except Exception as e:
            logger.error(f"크롤러 초기화 실패: {str(e)}")
            logger.debug(traceback.format_exc())
            return False
    
    """ 웹드라이버 종료 """
    async def close(self):
        """웹드라이버 종료 및 리소스 정리"""
        if self.driver:
            try:
                logger.info("웹드라이버 종료 시작")
                
                # 열려있는 모든 팝업창 닫기
                try:
                    main_window = self.driver.current_window_handle
                    for handle in self.driver.window_handles:
                        if handle != main_window:
                            self.driver.switch_to.window(handle)
                            self.driver.close()
                    self.driver.switch_to.window(main_window)
                except Exception as e:
                    logger.warning(f"팝업창 닫기 중 오류 (무시): {str(e)}")
                
                # 드라이버 종료
                self.driver.quit()
                logger.info("웹드라이버 종료 완료")
            except Exception as e:
                logger.error(f"웹드라이버 종료 중 오류: {str(e)}")
            finally:
                self.driver = None
                self.wait = None
                self.current_page = None
    
    """ 팝업창 닫기 """
    async def close_popups(self):
        """팝업창 닫기 (통합 버전)"""
        try:
            # 모든 팝업창 탐색 및 닫기
            logger.info("팝업창 닫기 시도 중...")
            
            # 1. 알림창(alert) 확인
            try:
                alert = self.driver.switch_to.alert
                alert_text = alert.text
                logger.info(f"알림창 감지: {alert_text}")
                alert.accept()
                logger.info("알림창 확인 완료")
            except Exception:
                pass  # 알림창이 없는 경우 무시
            
            # 2. 팝업 윈도우 닫기
            current_window = self.driver.current_window_handle
            all_windows = self.driver.window_handles
            
            popup_count = 0
            for window in all_windows:
                if window != current_window:
                    self.driver.switch_to.window(window)
                    self.driver.close()
                    popup_count += 1
                    logger.info(f"윈도우 팝업 닫기 성공 ({popup_count})")
            
            self.driver.switch_to.window(current_window)
            
            # 3. 나라장터 특정 팝업창 닫기 (공지사항 등)
            try:
                # 공지사항 팝업 닫기 (가장 일반적인 팝업)
                notice_close = WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, "//div[contains(@class,'w2window')]//button[contains(@class,'w2window_close')]"))
                )
                notice_close.click()
                logger.info("공지사항 팝업 닫기 성공")
                await asyncio.sleep(0.5)
            except Exception:
                pass
            
            # 4. 다양한 닫기 버튼 찾기 및 클릭
            popup_close_buttons = self.driver.find_elements(By.CSS_SELECTOR, 
                ".w2window_close, .close, [aria-label='창닫기'], .popup_close, [id*='poupR'][id$='_close']")
            
            closed_count = 0
            for button in popup_close_buttons:
                try:
                    button_id = button.get_attribute('id') or "알 수 없음"
                    logger.info(f"팝업 닫기 버튼 발견 (ID: {button_id}), 클릭 시도...")
                    button.click()
                    closed_count += 1
                    logger.info(f"페이지 내 팝업창 닫기 성공: {button_id}")
                    await asyncio.sleep(0.3)
                except Exception:
                    pass
            
            # 5. ESC 키를 눌러 혹시 남은 팝업 닫기 시도
            try:
                actions = ActionChains(self.driver)
                actions.send_keys(Keys.ESCAPE).perform()
                await asyncio.sleep(0.5)
            except Exception:
                pass
                
        except Exception as e:
            logger.warning(f"팝업창 닫기 중 오류 (계속 진행): {str(e)}")
            
    def set_page_state(self, page_name):
        """현재 페이지 상태 설정"""
        self.current_page = page_name
        logger.info(f"페이지 상태 변경: {page_name}")
        
    def is_on_page(self, page_name):
        """현재 페이지가 지정된 페이지인지 확인"""
        return self.current_page == page_name
    
    def __del__(self):
        """웹드라이버 종료 및 리소스 정리"""
        if hasattr(self, 'driver') and self.driver:
            try: 
                self.driver.quit()
                logger.info("웹드라이버 종료 완료")
            except:
                pass
    

        """상세 페이지 내 팝업 처리"""
        try:
            # 알림창(alert) 확인
            try:
                alert = self.driver.switch_to.alert
                alert_text = alert.text
                logger.info(f"알림창 감지: {alert_text}")
                alert.accept()
                logger.info("알림창 확인 완료")
            except Exception:
                pass  # 알림창이 없는 경우 무시
            
            # 모달 팝업 확인 및 닫기
            try:
                modal_close_buttons = self.driver.find_elements(By.CSS_SELECTOR, 
                                                              ".modal .close, .popup .close, [aria-label='닫기']")
                for button in modal_close_buttons:
                    button.click()
                    logger.info("모달 팝업 닫기 버튼 클릭")
                    time.sleep(0.5)
            except Exception:
                pass  # 모달이 없는 경우 무시
        
        except Exception as e:
            logger.warning(f"팝업 처리 중 오류 (무시): {str(e)}") 