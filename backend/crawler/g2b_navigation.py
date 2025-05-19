"""
나라장터 웹페이지 탐색 모듈

나라장터 웹사이트 내 페이지 탐색 및 메뉴 접근 기능을 제공합니다.
"""

import asyncio
import logging
import traceback
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

# 로거 설정
logger = logging.getLogger("backend.crawler.navigation")

class G2BNavigator:
    """나라장터 페이지 탐색 클래스"""
    
    def __init__(self, driver=None, wait=None):
        """
        나라장터 네비게이터 초기화
        
        Args:
            driver: Selenium WebDriver 인스턴스
            wait: WebDriverWait 인스턴스
        """
        self.driver = driver
        self.wait = wait
        self.base_url = "https://www.g2b.go.kr"
    
    async def navigate_to_main(self):
        """나라장터 메인 페이지로 이동"""
        try:
            logger.info(f"나라장터 메인 페이지 접속 중: {self.base_url}")
            self.driver.get(self.base_url)
            
            # 페이지 로딩 대기
            await asyncio.sleep(3)
            
            # 팝업창 닫기
            await self._close_popups()
            
            return True
        except Exception as e:
            logger.error(f"메인 페이지 접속 실패: {str(e)}")
            logger.debug(traceback.format_exc())
            return False
    
    async def navigate_to_bid_list(self):
        """입찰공고 목록 페이지로 이동"""
        try:
            logger.info("입찰공고 목록 페이지로 이동 중...")
            
            # 먼저 메인 페이지로 이동
            if not await self.navigate_to_main():
                logger.error("메인 페이지 접속 실패")
                return False
            
            for attempt in range(3):  # 최대 3번 시도
                try:
                    # 페이지 안정화를 위한 짧은 대기
                    await asyncio.sleep(1)
                    
                    # 메뉴 클릭을 통한 탐색
                    try:
                        # '입찰' 메뉴 직접 클릭
                        bid_menu = self.wait.until(
                            EC.element_to_be_clickable((By.ID, "mf_wfm_gnb_wfm_gnbMenu_genDepth1_1_btn_menuLvl1_span"))
                        )
                        bid_menu.click()
                        await asyncio.sleep(1)
                        
                        # '입찰공고목록' 직접 클릭
                        bid_list = self.wait.until(
                            EC.element_to_be_clickable((By.ID, "mf_wfm_gnb_wfm_gnbMenu_genDepth1_1_genDepth2_0_genDepth3_0_btn_menuLvl3_span"))
                        )
                        bid_list.click()
                        await asyncio.sleep(3)
                    except Exception as e:
                        logger.error(f"메뉴 클릭 실패: {str(e)}")
                        if attempt == 2:  # 마지막 시도에서 실패
                            raise
                        continue
                    
                    # 팝업창 다시 닫기
                    await self._close_popups()
                    
                    # 페이지 상태 확인
                    try:
                        # 검색 버튼 존재 확인 (테스트 페이지와 실제 페이지 모두 지원)
                        search_button = None
                        try:
                            # 실제 운영 페이지 버튼 ID
                            search_button = self.wait.until(
                                EC.presence_of_element_located((By.ID, "mf_wfm_container_tacBidPbancLst_contents_tab2_body_btnS0004"))
                            )
                        except Exception:
                            # 테스트 페이지 버튼 ID
                            search_button = self.wait.until(
                                EC.presence_of_element_located((By.ID, "buttonSearch"))
                            )
                        
                        logger.info("입찰공고 목록 페이지 이동 성공")
                        return True
                    except Exception:
                        logger.warning(f"페이지 확인 실패 (재시도 {attempt+1}/3)")
                        continue
                
                except Exception as e:
                    logger.warning(f"입찰공고 목록 페이지 이동 시도 {attempt+1}/3 실패: {str(e)}")
                    if attempt == 2:  # 마지막 시도에서도 실패
                        raise
                    # 페이지 새로고침 후 재시도
                    self.driver.refresh()
                    await asyncio.sleep(3)
                    await self._close_popups()
            
            # 모든 시도 실패
            raise Exception("3번의 시도 후에도 입찰공고 목록 페이지 이동 실패")
        
        except Exception as e:
            logger.error(f"입찰공고 목록 페이지 이동 실패: {str(e)}")
            logger.debug(traceback.format_exc())
            return False
    
    async def setup_search_conditions(self):
        """검색 조건 설정"""
        try:
            logger.info("검색 조건 설정 중...")
            
            # 탭 선택 (검색조건 탭이 있는 경우)
            try:
                tab_element = self.driver.find_element(By.CSS_SELECTOR, ".tab_wrap li:nth-child(2) a")
                tab_element.click()
                await asyncio.sleep(1)
            except NoSuchElementException:
                logger.info("검색조건 탭을 찾을 수 없습니다. 계속 진행합니다.")
            
            # '입찰마감제외' 체크박스 클릭
            # try:
            #     checkbox = self.driver.find_element(By.ID, "mf_wfm_container_tacBidPbancLst_contents_tab2_body_chkSlprRcptDdlnYn_input_0")
            #     if not checkbox.is_selected():
            #         checkbox.click()
            #         logger.info("'입찰마감제외' 체크박스 선택 완료")
            # except Exception as e:
            #     logger.warning(f"'입찰마감제외' 체크박스 선택 실패 (무시): {str(e)}")
            
            # 보기 개수 설정 (100개)
            try:
                select_element = self.driver.find_element(By.ID, "mf_wfm_container_tacBidPbancLst_contents_tab2_body_sbxRecordCountPerPage1")
                select = Select(select_element)
                select.select_by_visible_text("100")
                logger.info("보기 개수 100개로 설정 완료")
            except Exception as e:
                logger.warning(f"보기 개수 설정 실패 (무시): {str(e)}")
            
            return True
        except Exception as e:
            logger.error(f"검색 조건 설정 실패: {str(e)}")
            logger.debug(traceback.format_exc())
            return False
    
    async def _close_popups(self):
        """팝업창 닫기 (성공적인 부분만 유지)"""
        try:
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
            
            # 2. 팝업 윈도우 닫기 (CrawlerBase의 코드 활용)
            current_window = self.driver.current_window_handle
            all_windows = self.driver.window_handles
            
            for window in all_windows:
                if window != current_window:
                    self.driver.switch_to.window(window)
                    self.driver.close()
                    logger.info("팝업 윈도우 닫기 완료")
            
            self.driver.switch_to.window(current_window)
            
            # 3. 공지사항 팝업 닫기 (성공했던 방식만 유지)
            try:
                # ID 패턴으로 공지사항 팝업 찾기
                popup_close_buttons = self.driver.find_elements(By.CSS_SELECTOR, 
                                                            "[id*='poupR'][id*='close']")
                
                for button in popup_close_buttons:
                    try:
                        button_id = button.get_attribute("id")
                        logger.info(f"공지사항 팝업 닫기 버튼 발견 (ID: {button_id})")
                        button.click()
                        logger.info("공지사항 팝업 닫기 성공")
                        await asyncio.sleep(0.5)  # 잠시 대기
                    except Exception as click_err:
                        logger.debug(f"버튼 클릭 실패, 다음 버튼 시도: {str(click_err)}")
                        continue
            except Exception as popup_err:
                logger.debug(f"공지사항 팝업 처리 중 오류 (무시): {str(popup_err)}")
            
            # 4. ESC 키 입력으로 남은 팝업 닫기 시도
            try:
                actions = ActionChains(self.driver)
                actions.send_keys(Keys.ESCAPE).perform()
                logger.debug("ESC 키 입력으로 남은 팝업 닫기 시도")
            except Exception:
                pass
            
            logger.info("페이지 내 팝업창이 처리되었습니다.")
            return True
            
        except Exception as e:
            logger.warning(f"팝업 처리 중 오류 (계속 진행): {str(e)}")
            return True  # 팝업 처리에 실패해도 계속 진행