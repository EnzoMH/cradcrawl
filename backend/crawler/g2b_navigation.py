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
        """팝업창 닫기"""
        try:
            # 모든 팝업창 탐색 및 닫기
            logger.info("팝업창 닫기 시도 중...")
            
            # 메인 윈도우 핸들 저장
            main_window = self.driver.current_window_handle
            
            # 모든 윈도우 핸들 가져오기
            all_windows = self.driver.window_handles
            
            # 팝업 윈도우 닫기
            popup_count = 0
            for window in all_windows:
                if window != main_window:
                    self.driver.switch_to.window(window)
                    self.driver.close()
                    popup_count += 1
                    logger.info(f"윈도우 팝업 닫기 성공 ({popup_count})")
            
            if popup_count > 0:
                logger.info(f"총 {popup_count}개의 윈도우 팝업을 닫았습니다.")
            
            # 메인 윈도우로 복귀
            self.driver.switch_to.window(main_window)
            
            # 페이지 내 팝업창 닫기 (반복적으로 처리)
            closed_count = 0
            max_attempts = 5  # 최대 시도 횟수
            
            for attempt in range(max_attempts):
                # 페이지 안정화를 위한 짧은 대기
                await asyncio.sleep(0.3)
                
                # 1. 공지사항 팝업 (우선적으로 처리)
                try:
                    notice_close = self.driver.find_element(By.XPATH, "//div[contains(@class,'w2window')]//button[contains(@class,'w2window_close')]")
                    if notice_close.is_displayed() and notice_close.is_enabled():
                        button_id = notice_close.get_attribute('id') or "공지사항 팝업"
                        logger.info(f"공지사항 팝업 닫기 버튼 발견 (ID: {button_id})")
                        notice_close.click()
                        closed_count += 1
                        logger.info(f"공지사항 팝업 닫기 성공")
                        await asyncio.sleep(0.5)
                        continue  # 다음 반복으로 (DOM이 변경되었을 수 있음)
                except Exception:
                    # 공지사항 팝업이 없거나 닫기 실패
                    pass
                
                # 2. 가장 일반적인 닫기 버튼 찾기 (한 번에 하나씩 처리)
                close_button_found = False
                
                # 주요 셀렉터 순서대로 시도
                selectors = [
                    # 가장 흔한 패턴부터 시도
                    "[id*='poupR'][id*='_close']",  # 나라장터 특정 패턴
                    "[id*='poup'][id*='Close']",    # 팝업 닫기 버튼
                    "[id$='_close']",               # ~_close로 끝나는 ID
                    ".w2window_close",              # 일반적인 클래스
                    "[aria-label='창닫기']",         # 접근성 속성
                    ".close",                       # 범용 닫기 클래스
                    ".popup_close",                 # 팝업 닫기 클래스
                    "input[type='button'][value='닫기']", # 닫기 버튼 값
                    "button:contains('닫기')"        # 닫기 텍스트가 있는 버튼
                ]
                
                for selector in selectors:
                    try:
                        buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for button in buttons:
                            if button.is_displayed() and button.is_enabled():
                                button_id = button.get_attribute('id') or "알 수 없음"
                                logger.info(f"팝업 닫기 버튼 발견 (ID: {button_id}), 클릭 시도...")
                                button.click()
                                closed_count += 1
                                logger.info(f"페이지 내 팝업창 닫기 성공: {button_id}")
                                await asyncio.sleep(0.5)
                                close_button_found = True
                                break  # 한 버튼을 성공적으로 클릭했으면 중단
                        
                        if close_button_found:
                            break  # 버튼을 찾았으면 셀렉터 루프 중단
                    except Exception as e:
                        # 특정 셀렉터로 찾기 실패, 다음 셀렉터 시도
                        logger.debug(f"셀렉터 '{selector}' 사용 버튼 찾기 실패: {str(e)}")
                        continue
                
                # 버튼을 하나 클릭했으면 다음 반복으로 (DOM이 변경되었을 수 있음)
                if close_button_found:
                    continue
                
                # 3. iframe 내부 팝업 처리 (한 번에 하나의 iframe만 처리)
                iframe_processed = False
                iframe_elements = self.driver.find_elements(By.TAG_NAME, "iframe")
                
                for iframe in iframe_elements:
                    try:
                        iframe_id = iframe.get_attribute("id") or "알 수 없음"
                        if iframe.is_displayed():
                            logger.debug(f"iframe 확인: {iframe_id}")
                            self.driver.switch_to.frame(iframe)
                            
                            # iframe 내부의 닫기 버튼 찾기
                            for selector in selectors:
                                try:
                                    iframe_buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                                    for button in iframe_buttons:
                                        if button.is_displayed() and button.is_enabled():
                                            button_id = button.get_attribute('id') or "iframe 내부"
                                            logger.info(f"iframe 내부 팝업 닫기 버튼 발견 (ID: {button_id})")
                                            button.click()
                                            closed_count += 1
                                            logger.info(f"iframe 내부 팝업창 닫기 성공: {button_id}")
                                            iframe_processed = True
                                            await asyncio.sleep(0.5)
                                            break
                                        
                                    if iframe_processed:
                                        break
                                except Exception:
                                    continue
                            
                            # 기본 컨텐츠로 복귀
                            self.driver.switch_to.default_content()
                            
                            # iframe 내부에서 버튼을 클릭했으면 중단
                            if iframe_processed:
                                break
                    except Exception as iframe_err:
                        logger.debug(f"iframe 접근 실패 (무시): {str(iframe_err)}")
                        # iframe 처리 중 오류 발생 시 기본 컨텐츠로 복귀
                        self.driver.switch_to.default_content()
                
                # iframe 내부에서 버튼을 클릭했으면 다음 반복으로
                if iframe_processed:
                    continue
                
                # 4. 더이상 닫을 팝업이 없는 경우
                if not close_button_found and not iframe_processed:
                    # ESC 키를 눌러 혹시 남은 팝업 닫기 시도
                    try:
                        actions = ActionChains(self.driver)
                        actions.send_keys(Keys.ESCAPE).perform()
                        await asyncio.sleep(0.5)
                        logger.debug("ESC 키 입력으로 남은 팝업 닫기 시도")
                    except Exception as e:
                        logger.debug(f"ESC 키 입력 실패 (무시): {str(e)}")
                    
                    # 더 이상 팝업이 없으면 반복 종료
                    break
            
            # 최종 팝업 닫기 결과 출력
            if closed_count > 0:
                logger.info(f"총 {closed_count}개의 페이지 내 팝업창을 닫았습니다.")
            else:
                logger.info("페이지 내 팝업창이 발견되지 않았습니다.")
            
            # 메인 컨텐츠 영역 클릭해서 포커스 주기
            try:
                main_content = self.driver.find_element(By.ID, "container")
                main_content.click()
                logger.debug("메인 컨텐츠 영역 포커스 설정")
            except Exception:
                try:
                    # 대체 방법: 본문 영역 클릭
                    body = self.driver.find_element(By.TAG_NAME, "body")
                    body.click()
                    logger.debug("본문 영역 포커스 설정")
                except Exception:
                    pass
                
        except Exception as e:
            logger.warning(f"팝업창 닫기 중 오류 (계속 진행): {str(e)}") 