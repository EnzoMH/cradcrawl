"""
나라장터 크롤러 기본 모듈

나라장터 크롤링의 기본 기능을 제공하는 베이스 클래스 모듈입니다.
"""

import os
import time
import logging
import traceback
from typing import Optional
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# 로거 설정
logger = logging.getLogger("backend.crawler.base")

class CrawlerBase:
    """나라장터 크롤러 기본 클래스"""
    
    def __init__(self, headless: bool = True):
        """
        크롤러 기본 클래스 초기화
        
        Args:
            headless (bool): 헤드리스 모드 사용 여부
        """
        self.headless = headless
        self.driver = None
        self.wait = None
        self._initialize_webdriver()
    
    def _initialize_webdriver(self):
        """웹드라이버 초기화"""
        try:
            chrome_options = Options()
            
            if self.headless:
                chrome_options.add_argument("--headless")
            
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_argument("--disable-popup-blocking")
            
            # Windows 환경에서 한글 깨짐 방지
            chrome_options.add_argument("--lang=ko_KR.UTF-8")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option("useAutomationExtension", False)
            
            # 사용자 에이전트 설정
            chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36")
            
            # 드라이버 초기화
            self.driver = webdriver.Chrome(options=chrome_options)
            
            # 명시적 대기 설정
            self.wait = WebDriverWait(self.driver, 10)
            
            logger.info(f"웹드라이버 초기화 성공 (헤드리스: {self.headless})")
            
        except Exception as e:
            logger.error(f"웹드라이버 초기화 실패: {str(e)}")
            logger.debug(traceback.format_exc())
            raise
    
    def _handle_popups(self):
        """팝업창 처리"""
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
            
            # 팝업 창 처리
            current_window = self.driver.current_window_handle
            
            # 모든 윈도우 핸들 가져오기
            all_windows = self.driver.window_handles
            
            # 팝업 윈도우 닫기
            for window in all_windows:
                if window != current_window:
                    self.driver.switch_to.window(window)
                    self.driver.close()
                    logger.info("팝업 윈도우 닫기 완료")
            
            # 원래 윈도우로 돌아가기
            self.driver.switch_to.window(current_window)
            
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
    
    def close(self):
        """웹드라이버 종료"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("웹드라이버 종료 완료")
            except Exception as e:
                logger.error(f"웹드라이버 종료 중 오류: {str(e)}")
    
    def __del__(self):
        """소멸자에서 웹드라이버 종료"""
        self.close() 