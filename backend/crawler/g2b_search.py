"""
나라장터 검색 및 결과 추출 모듈

나라장터 웹사이트에서 검색 수행 및 결과 추출 기능을 제공합니다.
"""

import asyncio
import logging
import traceback
import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from bs4 import BeautifulSoup

from backend.crawler.g2b_navigation import G2BNavigator
from backend.utils.ai_helpers import check_relevance_with_ai, extract_with_gemini_text

# 로거 설정
logger = logging.getLogger("backend.crawler.search")

class G2BSearcher:
    """나라장터 검색 및 결과 추출 클래스"""
    
    def __init__(self, driver=None, wait=None):
        """
        나라장터 검색기 초기화
        
        Args:
            driver: Selenium WebDriver 인스턴스
            wait: WebDriverWait 인스턴스
            navigator: G2BNavigator 인스턴스 (선택사항)
        """
        self.driver = driver
        self.wait = wait
        self.results = []
        self.keyword = ""
        
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
            
            # # '입찰마감제외' 체크박스 클릭
            # try:
            #     checkbox = self.driver.find_element(By.ID, "mf_wfm_container_tacBidPbancLst_contents_tab2_body_chkSlprRcptDdlnYn_input_0")
            #     if not checkbox.is_selected():
            #         checkbox.click()
            #         logger.info("'입찰마감제외' 체크박스 선택 완료")
            #     else:
            #         logger.info("'입찰마감제외' 체크박스가 이미 선택되어 있음")
            # except Exception as e:
            #     logger.warning(f"'입찰마감제외' 체크박스 선택 실패 (계속 진행): {str(e)}")
            
            # 보기 개수 설정 (100개)
            try:
                select_element = self.driver.find_element(By.ID, "mf_wfm_container_tacBidPbancLst_contents_tab2_body_sbxRecordCountPerPage1")
                select = Select(select_element)
                select.select_by_visible_text("100")
                logger.info("보기 개수 100개로 설정 완료")
            except Exception as e:
                logger.warning(f"보기 개수 설정 실패 (계속 진행): {str(e)}")
            
            # 시간 지연으로 UI 반영 대기
            await asyncio.sleep(1)
            
            return True
        except Exception as e:
            logger.error(f"검색 조건 설정 실패: {str(e)}")
            logger.debug(traceback.format_exc())
            return False
        
    async def search_keyword(self, search_keyword):
        """
        키워드로 입찰공고 검색 수행 (순수 검색 기능만 담당)
        
        Args:
            search_keyword: 검색할 키워드
        
        Returns:
            bool: 검색 성공 여부
        """
        try:
            logger.info(f"키워드 '{search_keyword}' 검색 시작")
            
            # 검색어 입력 필드 찾기
            search_input = self.find_search_input()
            if not search_input:
                logger.error("검색어 입력 필드를 찾을 수 없습니다")
                return False
            
            # 검색어 입력
            search_input.clear()
            search_input.send_keys(search_keyword)
            
            # 검색 버튼 찾아 클릭
            search_button = self.find_search_button()
            if not search_button:
                logger.error("검색 버튼을 찾을 수 없습니다")
                return False
            
            search_button.click()
            
            # 검색 결과 로딩 대기
            await asyncio.sleep(2)
            
            logger.info(f"키워드 '{search_keyword}' 검색 성공")
            return True
            
        except Exception as e:
            logger.error(f"키워드 검색 중 오류 발생: {str(e)}")
            logger.debug(traceback.format_exc())
            return False
    
    def find_search_input(self):
        """다양한 방법으로 검색어 입력 필드 찾기"""
        selectors = [
            # ID로 직접 찾기 (현재 ID)
            By.ID, "mf_wfm_container_tacBidPbancLst_contents_tab2_body_bidPbancNm",
            # 이전 ID (이전 버전 호환)
            By.ID, "mf_wfm_container_tacBidPbancLst_contents_tab2_body_txtBidNm",
            # 부분 ID 매칭
            By.CSS_SELECTOR, "[id*='bidPbancNm']",
            By.CSS_SELECTOR, "[id*='txtBidNm']",
            # title 속성 활용
            By.CSS_SELECTOR, "input[title='공고명']",
            # XPath 활용
            By.XPATH, "//*[contains(@id, 'bidPbancNm')]",
            By.XPATH, "//input[@title='공고명']"
        ]
        
        for i in range(0, len(selectors), 2):
            try:
                selector_type = selectors[i]
                selector_value = selectors[i+1]
                element = self.wait.until(EC.presence_of_element_located((selector_type, selector_value)))
                logger.info(f"검색 입력 필드 발견: {selector_type} - {selector_value}")
                return element
            except Exception:
                continue
        
        # JavaScript로 직접 찾기 (최후의 수단)
        try:
            element = self.driver.execute_script("""
                return document.querySelector("input[title='공고명']") || 
                    document.querySelector("[id*='bidPbancNm']") ||
                    document.querySelector("[id*='txtBidNm']")
            """)
            if element:
                logger.info("JavaScript로 검색 입력 필드 발견")
                return element
        except Exception:
            pass
        
        logger.error("검색 입력 필드를 찾을 수 없습니다.")
        return None
    
    async def extract_search_results(self):
        """
        검색 결과 목록에서 항목 추출
        
        Returns:
            검색 결과 항목 리스트
        """
        try:
            logger.info("검색 결과 항목 추출 시작")
            
            # BS4 방식 추출 시도 (더 안정적)
            try:
                items = await self.extract_search_results_bs4()
                if items and len(items) > 0:
                    logger.info(f"BS4 방식으로 {len(items)}개 항목 추출 성공")
                    return items
            except Exception as bs4_err:
                logger.warning(f"BS4 방식 추출 실패: {str(bs4_err)}")
            
            # 결과 항목 저장소
            items = []
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            # 전략 1: 셀 ID 패턴 활용하여 직접 항목 추출
            try:
                logger.info("셀 ID 패턴 방식으로 항목 추출 시도")
                
                # 셀 ID 패턴으로 직접 공고명 셀 탐색
                for row_idx in range(20):  # 최대 20행까지 시도
                    try:
                        cell_id = f"mf_wfm_container_tacBidPbancLst_contents_tab2_body_gridView1_cell_{row_idx}_6"
                        cell = self.driver.find_element(By.ID, cell_id)
                        
                        # 셀에서 링크 찾기
                        try:
                            link = cell.find_element(By.CSS_SELECTOR, "nobr > a")
                        except:
                            try:
                                link = cell.find_element(By.TAG_NAME, "a")
                            except:
                                continue
                        
                        if not link.is_displayed():
                            continue
                            
                        title = link.text.strip()
                        onclick = link.get_attribute("onclick")
                        
                        if title:
                            item = {
                                "title": title,
                                "onclick": onclick,
                                "cell_id": cell_id,
                                "row_index": row_idx
                            }
                            
                            # 다른 필드 추출 시도
                            try:
                                # 공고번호 (일반적으로 셀 ID의 마지막 숫자만 다름)
                                for col_idx in [1, 2, 3]:  # 1~3번째 열에서 시도
                                    try:
                                        num_cell_id = f"mf_wfm_container_tacBidPbancLst_contents_tab2_body_gridView1_cell_{row_idx}_{col_idx}"
                                        num_cell = self.driver.find_element(By.ID, num_cell_id)
                                        item["bid_number"] = num_cell.text.strip()
                                        if item["bid_number"]:
                                            break
                                    except:
                                        continue
                            except Exception:
                                pass
                            
                            items.append(item)
                            logger.info(f"셀 ID 패턴으로 항목 추출: {title[:30]}... (행 {row_idx})")
                    except Exception:
                        continue
                
                if items:
                    logger.info(f"셀 ID 패턴으로 {len(items)}개 항목 추출 성공")
                    return items
            except Exception as cell_err:
                logger.warning(f"셀 ID 패턴 접근 실패: {str(cell_err)}")
            
            # 전략 2: 테이블 구조 분석 후 행 처리
            try:
                logger.info("테이블 구조 기반 항목 추출 시도")
                
                # 검색 결과 테이블 찾기
                tables = self.find_search_results()
                
                if tables:
                    for table in tables:
                        # 테이블 행 추출
                        rows = table.find_elements(By.XPATH, ".//tr")
                        
                        # 첫 번째 행은 헤더이므로 제외
                        if len(rows) > 1:
                            # 행별로 항목 추출
                            for i, row in enumerate(rows[1:], 0):  # 인덱스 0부터 시작 (실제 행은 1부터)
                                item = await self._extract_item_from_row(row, i, current_date)
                                if item:
                                    items.append(item)
                        
                        logger.info(f"테이블 {tables.index(table)+1}에서 {len(items)}개 항목 추출")
                
                if items:
                    logger.info(f"테이블 기반 방식으로 총 {len(items)}개 항목 추출 성공")
                    return items
            except Exception as table_err:
                logger.warning(f"테이블 구조 기반 추출 실패: {str(table_err)}")
            
            # 전략 3: XPath로 모든 행 추출
            try:
                logger.info("XPath 기반 행 추출 시도")
                
                # 행 추출 (첫 번째 행은 헤더일 수 있으므로 생략)
                xpath = "//table//tr[position() > 1]"
                rows = self.driver.find_elements(By.XPATH, xpath)
                
                logger.info(f"XPath {xpath}로 {len(rows)}개 행 발견")
                
                for i, row in enumerate(rows):
                    try:
                        item = await self._extract_item_from_row(row, i, current_date)
                        if item:
                            items.append(item)
                    except Exception as row_err:
                        logger.debug(f"행 {i+1} 처리 실패: {str(row_err)}")
                
                if items:
                    logger.info(f"XPath 방식으로 {len(items)}개 항목 추출 성공")
                    return items
            except Exception as xpath_err:
                logger.warning(f"XPath 방식 추출 실패: {str(xpath_err)}")
            
            # 모든 방법을 시도했지만 결과가 없는 경우
            if not items:
                logger.error("모든 항목 추출 방법 실패")
                return []
            
            return items
            
        except Exception as e:
            logger.error(f"검색 결과 추출 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return []

    async def extract_search_results_bs4(self):
        """
        BeautifulSoup를 사용하여 검색 결과 목록에서 항목 추출
        
        Returns:
            검색 결과 항목 리스트
        """
        try:
            logger.info("검색 결과 항목 추출 시작 (BS4 방식)")
            
            # 현재 날짜 설정 (날짜 비교용)
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            # 페이지 소스 가져오기
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # 디버깅을 위해 페이지 소스 저장
            try:
                with open("search_results_debug.html", "w", encoding="utf-8") as f:
                    f.write(page_source)
                logger.info("디버깅을 위해 페이지 소스를 search_results_debug.html에 저장했습니다.")
            except Exception as e:
                logger.warning(f"디버그 파일 저장 실패: {str(e)}")
            
            # 테이블 기반 추출 (이미지 확인 기반)
            items = self._extract_items_from_table(soup, current_date)
            if items:
                logger.info(f"테이블에서 {len(items)}개 항목 추출 성공")
            else:
                # 기존 방식 시도
                logger.info("테이블 추출 실패, 셀 ID 기반 방식 시도")
                items = self._extract_items_from_cells(soup, current_date)
                
                if not items:
                    logger.warning("셀 ID 기반 추출도 실패, 일반 그리드뷰 탐색 시도")
                    items = self._extract_items_from_grid(soup, current_date)
            
            if not items:
                logger.warning("모든 추출 방식 실패, 비어있는 결과 반환")
                return []
                
            # 추출된 항목에 추가 정보 포함
            valid_items = []
            for item in items:
                item['keyword'] = self.keyword
                valid_items.append(item)
            
            logger.info(f"최종 {len(valid_items)}개 유효 항목 반환")
            
            # Gemini AI를 사용하여 데이터 검증 및 보완 (비활성화: 성능 문제)
            # if valid_items:
            #     await self._enhance_with_gemini(valid_items)
                
            return valid_items
            
        except Exception as e:
            logger.error(f"BS4 검색 결과 추출 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            raise  # 상위 호출자에게 예외 전달하여 기존 방식 시도
    
    def _extract_item_from_row(self, row, index, current_date):
        """행에서 항목 데이터 추출"""
        try:
            # 행 요소에서 ID 추출 (상세 페이지 이동을 위한 네이티브 이벤트에 사용)
            row_id = None
            try:
                row_id = row.get_attribute("id")
            except:
                pass
                
            item = {
                "row_index": index,
            }
            
            # 공고명 추출 시도 - 셀 ID 패턴 직접 활용
            try:
                # 공고명은 6번째 열에 위치한 경우가 많음 (인덱스 5)
                cell_id = f"mf_wfm_container_tacBidPbancLst_contents_tab2_body_gridView1_cell_{index}_6"
                cell = self.driver.find_element(By.ID, cell_id)
                link = cell.find_element(By.CSS_SELECTOR, "nobr > a") or cell.find_element(By.TAG_NAME, "a")
                
                title = link.text.strip()
                onclick = link.get_attribute("onclick")
                
                item["title"] = title
                item["onclick"] = onclick
                item["cell_id"] = cell_id  # 셀 ID 저장 - 상세 페이지 접근에 활용
                
                logger.info(f"셀 ID 패턴으로 공고명 추출: {title[:30]}...")
                
                # 셀렉터 시도 - 성공 시 반환
                return item
            except Exception as cell_err:
                logger.debug(f"셀 ID 패턴 실패: {str(cell_err)}")
                
            # 대체 공고명 패턴 시도 (XPath 활용)
            try:
                xpath_patterns = [
                    f"//tr[position()={index+1}]//td[position()=6]//a",
                    f"//tr[{index+1}]//td[6]//a",
                    f"//tr[{index+1}]//td//a[contains(@onclick, 'Detail') or contains(@onclick, 'detail')]",
                ]
                
                for xpath in xpath_patterns:
                    try:
                        link_element = row.find_element(By.XPATH, xpath)
                        title = link_element.text.strip()
                        onclick = link_element.get_attribute("onclick")
                        
                        item["title"] = title
                        item["onclick"] = onclick
                        
                        # 셀 ID 추출 시도
                        try:
                            parent_cell = link_element.find_element(By.XPATH, "./..")
                            while parent_cell:
                                cell_id = parent_cell.get_attribute("id")
                                if cell_id and "cell" in cell_id:
                                    item["cell_id"] = cell_id
                                    break
                                parent_cell = parent_cell.find_element(By.XPATH, "./..")
                        except:
                            # 셀 ID 추출에 실패해도 계속 진행
                            pass
                            
                        logger.info(f"XPath 패턴으로 공고명 추출: {title[:30]}...")
                        return item
                    except:
                        continue
            except Exception as xpath_err:
                logger.debug(f"XPath 패턴 실패: {str(xpath_err)}")
            
            # 기타 필드 추출 (공고번호, 개찰일시 등)
            try:
                # 입찰공고번호 (보통 첫 번째 열)
                try:
                    bid_number_element = row.find_element(By.XPATH, ".//td[1]")
                    item["bid_number"] = bid_number_element.text.strip()
                except:
                    pass
                
                # 기관명 (보통 두 번째 열)
                try:
                    agency_element = row.find_element(By.XPATH, ".//td[2]")
                    item["agency"] = agency_element.text.strip()
                except:
                    pass
                
                # 마감일시 (보통 다섯 번째 열)
                try:
                    deadline_element = row.find_element(By.XPATH, ".//td[5]")
                    item["deadline"] = deadline_element.text.strip()
                except:
                    pass
                
                # 개찰일시 (보통 일곱 번째 열)
                try:
                    opening_element = row.find_element(By.XPATH, ".//td[7]")
                    item["opening_date"] = opening_element.text.strip()
                except:
                    pass
                
                if "title" not in item:
                    # 최후의 수단: 모든 링크 중 가장 긴 텍스트를 공고명으로 간주
                    links = row.find_elements(By.TAG_NAME, "a")
                    if links:
                        longest_text = ""
                        longest_link = None
                        for link in links:
                            text = link.text.strip()
                            if len(text) > len(longest_text):
                                longest_text = text
                                longest_link = link
                        
                        if longest_link and longest_text:
                            item["title"] = longest_text
                            item["onclick"] = longest_link.get_attribute("onclick")
                            
                            # 셀 ID 추출 시도
                            try:
                                parent_cell = longest_link.find_element(By.XPATH, "./..")
                                while parent_cell:
                                    cell_id = parent_cell.get_attribute("id")
                                    if cell_id and "cell" in cell_id:
                                        item["cell_id"] = cell_id
                                        break
                                    parent_cell = parent_cell.find_element(By.XPATH, "./..")
                            except:
                                pass
                                
                            logger.info(f"최장 텍스트 방식으로 공고명 추출: {longest_text[:30]}...")
                    
            except Exception as fields_err:
                logger.debug(f"기타 필드 추출 실패: {str(fields_err)}")
            
            # 필수 필드가 없는 경우 None 반환
            if "title" not in item:
                logger.warning(f"행 {index}에서 공고명을 추출하지 못함")
                return None
                
            return item
            
        except Exception as e:
            logger.error(f"행 {index} 처리 중 오류: {str(e)}")
            return None 
        
    def find_search_button(self):
        """다양한 방법으로 검색 버튼 찾기"""
        selectors = [
            # ID로 직접 찾기 (현재 ID)
            By.ID, "mf_wfm_container_tacBidPbancLst_contents_tab2_body_btnS0004",
            # 이전 ID (이전 버전 호환)
            By.ID, "buttonSearch",
            # 부분 ID 매칭
            By.CSS_SELECTOR, "[id*='btnS0004']",
            By.CSS_SELECTOR, "button[id*='Search']",
            # title 또는 텍스트 속성 활용
            By.XPATH, "//button[contains(text(), '검색')]",
            By.CSS_SELECTOR, "button[title='검색']",
            # 이미지 버튼 시도
            By.CSS_SELECTOR, "img[alt='검색']"
        ]
        
        for i in range(0, len(selectors), 2):
            try:
                selector_type = selectors[i]
                selector_value = selectors[i+1]
                element = self.wait.until(EC.element_to_be_clickable((selector_type, selector_value)))
                logger.info(f"검색 버튼 발견: {selector_type} - {selector_value}")
                return element
            except Exception:
                continue
        
        # JavaScript로 직접 찾기 (최후의 수단)
        try:
            element = self.driver.execute_script("""
                return document.querySelector("button[id*='Search']") || 
                    document.querySelector("[id*='btnS0004']") ||
                    document.querySelector("button:contains('검색')")
            """)
            if element:
                logger.info("JavaScript로 검색 버튼 발견")
                return element
        except Exception:
            pass
        
        logger.error("검색 버튼을 찾을 수 없습니다.")
        return None
    