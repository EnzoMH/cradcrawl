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
    
    def __init__(self, driver=None, wait=None, navigator=None):
        """
        나라장터 검색기 초기화
        
        Args:
            driver: Selenium WebDriver 인스턴스
            wait: WebDriverWait 인스턴스
            navigator: G2BNavigator 인스턴스 (선택사항)
        """
        self.driver = driver
        self.wait = wait
        self.navigator = navigator
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
        
    async def search_keyword(self, keyword: str = None):
        try:
            # 키워드 설정
            if keyword:
                self.keyword = keyword
                
            if not self.keyword:
                self.keyword = "AI"  # 기본 검색어
                
            logger.info(f"키워드 검색 시작: '{self.keyword}'")
            
            # 검색어 입력 필드 찾기
            search_field = self.find_search_input()
            if not search_field:
                return False
                
            # 입력 필드 초기화 및 키워드 입력
            search_field.clear()
            search_field.send_keys(self.keyword)
            logger.info(f"검색어 입력 완료: '{self.keyword}'")
            
            # 검색 버튼 찾기 (여러 셀렉터 시도)
            search_button = None
            button_selectors = [
                (By.ID, "mf_wfm_container_tacBidPbancLst_contents_tab2_body_btnS0004"),
                (By.CSS_SELECTOR, "[id*='btnSearch']"),
                (By.CSS_SELECTOR, "button[title*='검색']"),
                (By.XPATH, "//button[contains(text(), '검색')]")
            ]
            
            for selector_type, selector_value in button_selectors:
                try:
                    search_button = self.wait.until(EC.element_to_be_clickable((selector_type, selector_value)))
                    break
                except Exception:
                    continue
            
            if not search_button:
                # JavaScript로 검색 버튼 찾기 시도
                try:
                    search_button = self.driver.execute_script("""
                        return document.querySelector("[id*='btnSearch']") || 
                            document.querySelector("button[title*='검색']")
                    """)
                except Exception:
                    pass
                    
            if search_button:
                search_button.click()
                logger.info("검색 버튼 클릭 완료")
                await asyncio.sleep(3)
                return True
            else:
                # 대안: ENTER 키 입력으로 검색 시도
                from selenium.webdriver.common.keys import Keys
                search_field.send_keys(Keys.RETURN)
                logger.info("ENTER 키로 검색 시도")
                await asyncio.sleep(3)
                return True
                
        except Exception as e:
            logger.error(f"키워드 검색 중 오류: {str(e)}")
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
    
    def _extract_items_from_table(self, soup, current_date):
        """테이블 구조를 기반으로 항목 추출 (BS4 방식)"""
        try:
            # 1. 테이블 찾기
            # 테이블은 보통 class나 id가 없는 경우가 많아 일반 테이블 태그로 찾음
            tables = soup.find_all('table')
            
            items = []
            processed_count = 0
            
            for table in tables:
                # 테이블에 최소 2개 이상의 행이 있는지 확인 (헤더 + 데이터)
                rows = table.find_all('tr')
                if len(rows) < 2:
                    continue
                
                # 테이블 구조 확인을 위해 첫 행 검사
                header_row = rows[0]
                header_cells = header_row.find_all(['th', 'td'])
                
                # 공고명 열과 기타 정보 열의 위치 확인을 위한 변수
                title_col_index = None
                bid_num_col_index = None
                dept_col_index = None
                date_start_col_index = None
                date_end_col_index = None
                
                # 헤더 행에서 각 열의 용도 파악
                for i, cell in enumerate(header_cells):
                    cell_text = cell.text.strip().lower()
                    if '공고명' in cell_text or '입찰명' in cell_text or '제목' in cell_text:
                        title_col_index = i
                    elif '공고번호' in cell_text or '입찰번호' in cell_text:
                        bid_num_col_index = i
                    elif '공고기관' in cell_text or '발주기관' in cell_text or '기관' in cell_text:
                        dept_col_index = i
                    elif '게시일' in cell_text or '등록일' in cell_text:
                        date_start_col_index = i
                    elif '마감일' in cell_text or '종료일' in cell_text:
                        date_end_col_index = i
                
                # 공고명 열이 확인되지 않은 경우 표준 위치 추정 시도
                if title_col_index is None:
                    # 일반적으로 공고명은 표의 중간 부분에 위치
                    title_col_index = len(header_cells) // 2
                    logger.info(f"공고명 열 위치를 추정: {title_col_index}")
                
                # 데이터 행 처리 (헤더 행 제외)
                for row_idx, row in enumerate(rows[1:], 1):
                    # 처리 제한 확인
                    if processed_count >= 1000:
                        break
                        
                    cells = row.find_all(['td'])
                    if len(cells) <= title_col_index:
                        continue  # 열 개수가 충분하지 않음
                    
                    # 셀에서 텍스트 추출 함수
                    def get_cell_text(index):
                        if index is not None and index < len(cells):
                            # a 태그 내 텍스트 우선 추출
                            a_tag = cells[index].find('a')
                            if a_tag:
                                return a_tag.text.strip()
                            # 일반 텍스트 추출
                            return cells[index].text.strip()
                        return ""
                    
                    # 공고명 추출 (a 태그 내에 있을 가능성 높음)
                    title = ""
                    title_cell = cells[title_col_index] if title_col_index < len(cells) else None
                    
                    if title_cell:
                        # a 태그 내 텍스트 우선 추출
                        a_tag = title_cell.find('a')
                        if a_tag:
                            title = a_tag.text.strip()
                        else:
                            title = title_cell.text.strip()
                    
                    # 숫자만으로 된 제목이나 너무 짧은 제목은 무시
                    if not title or title.isdigit() or len(title) < 5:
                        continue
                    
                    # 기타 필드 추출
                    bid_number = get_cell_text(bid_num_col_index)
                    department = get_cell_text(dept_col_index)
                    date_start = get_cell_text(date_start_col_index)
                    date_end = get_cell_text(date_end_col_index)
                    
                    # 상태 정보 설정
                    status = '알수없음'
                    if date_end:
                        try:
                            current_date_obj = datetime.strptime(current_date, "%Y-%m-%d")
                            # 날짜 형식 다양성 처리
                            date_formats = ["%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y년%m월%d일"]
                            for date_format in date_formats:
                                try:
                                    end_date_obj = datetime.strptime(date_end, date_format)
                                    if end_date_obj < current_date_obj:
                                        status = '마감'
                                    else:
                                        status = '공고중'
                                    break
                                except ValueError:
                                    continue
                        except Exception:
                            pass
                    
                    # 항목 데이터 생성
                    item = {
                        'title': title,
                        'bid_number': bid_number,
                        'department': department,
                        'date_start': date_start,
                        'date_end': date_end,
                        'status': status,
                        'row_index': row_idx,
                        'extraction_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    
                    # onclick 속성 추출 (a 태그가 있는 경우)
                    if title_cell:
                        a_tag = title_cell.find('a')
                        if a_tag and a_tag.get('onclick'):
                            item['onclick'] = a_tag['onclick']
                            item['detail_function'] = a_tag['onclick']
                        
                        # cell ID 패턴 생성 (나중에 상세 페이지 접근에 활용)
                        try:
                            cell_id = title_cell.get('id')
                            if cell_id and 'cell' in cell_id:
                                item['cell_id'] = cell_id
                        except:
                            pass
                    
                    # 유효한 항목만 추가
                    if item['title'] and (item['bid_number'] or item['department']):
                        items.append(item)
                        processed_count += 1
                        logger.info(f"항목 {processed_count}: {item['title'][:30]}...")
            
            return items
            
        except Exception as e:
            logger.error(f"테이블 기반 항목 추출 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return []
    
    def _extract_items_from_cells(self, soup, current_date):
        """셀 ID 패턴을 기반으로 항목 추출"""
        try:
            items = []
            processed_count = 0
            
            # gridView1_cell_X_Y 패턴으로 셀 찾기
            # Y=6은 공고명, Y=2는 공고번호, Y=4는 기관명 등의 패턴
            title_cells = soup.find_all('td', id=lambda x: x and 'gridView1_cell' in x and x.endswith('_6'))
            
            for cell in title_cells:
                # 처리 제한 확인
                if processed_count >= 1000:
                    break
                    
                # cell_id 형식: gridView1_cell_ROW_COL
                cell_id = cell.get('id', '')
                if not cell_id:
                    continue
                    
                # ID에서 행과 열 번호 추출
                id_parts = cell_id.split('_')
                if len(id_parts) < 4:
                    continue
                    
                row_idx = id_parts[-2]  # 행 번호
                
                # 공고명 추출 (nobr > a 태그 내)
                nobr = cell.find('nobr')
                a_tag = nobr.find('a') if nobr else cell.find('a')
                
                title = ""
                onclick = ""
                detail_function = ""
                
                if a_tag:
                    title = a_tag.text.strip()
                    # onclick 속성 저장
                    onclick = a_tag.get('onclick', '')
                    if onclick:
                        detail_function = onclick
                else:
                    title = cell.text.strip()
                
                # 숫자만으로 된 제목이나 너무 짧은 제목은 무시
                if not title or title.isdigit() or len(title) < 5:
                    continue
                
                # 다른 정보가 있는 셀 찾기 (ID 패턴 기반)
                bid_num_cell_id = cell_id.replace('_6', '_2')
                dept_cell_id = cell_id.replace('_6', '_4')
                date_start_cell_id = cell_id.replace('_6', '_7')
                date_end_cell_id = cell_id.replace('_6', '_8')
                
                # 각 셀에서 정보 추출
                bid_num_cell = soup.find('td', id=bid_num_cell_id)
                dept_cell = soup.find('td', id=dept_cell_id)
                date_start_cell = soup.find('td', id=date_start_cell_id)
                date_end_cell = soup.find('td', id=date_end_cell_id)
                
                bid_number = bid_num_cell.text.strip() if bid_num_cell else ""
                department = dept_cell.text.strip() if dept_cell else ""
                date_start = date_start_cell.text.strip() if date_start_cell else ""
                date_end = date_end_cell.text.strip() if date_end_cell else ""
                
                # 상태 정보 설정
                status = '알수없음'
                if date_end:
                    try:
                        current_date_obj = datetime.strptime(current_date, "%Y-%m-%d")
                        end_date_obj = datetime.strptime(date_end, "%Y-%m-%d")
                        if end_date_obj < current_date_obj:
                            status = '마감'
                        else:
                            status = '공고중'
                    except Exception:
                        pass
                
                # 항목 데이터 생성
                item = {
                    'title': title,
                    'bid_number': bid_number,
                    'department': department,
                    'date_start': date_start,
                    'date_end': date_end,
                    'status': status,
                    'onclick': onclick,
                    'detail_function': detail_function,
                    'row_index': row_idx,
                    'extraction_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                # 유효한 항목만 추가
                if item['title'] and (item['bid_number'] or item['department']):
                    items.append(item)
                    processed_count += 1
                    logger.info(f"항목 {processed_count}: {item['title'][:30]}...")
            
            return items
            
        except Exception as e:
            logger.error(f"셀 ID 기반 항목 추출 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return []
    
    def _extract_items_from_grid(self, soup, current_date):
        """일반 그리드뷰 구조를 기반으로 항목 추출"""
        try:
            # 그리드뷰 관련 div 찾기
            grid_divs = soup.find_all('div', id=lambda x: x and ('grid' in x.lower() or 'list' in x.lower()))
            
            items = []
            processed_count = 0
            
            # 각 그리드뷰 처리
            for grid in grid_divs:
                # 그리드 내 모든 a 태그 찾기 (공고명은 보통 링크로 표시됨)
                links = grid.find_all('a')
                
                for link in links:
                    # 처리 제한 확인
                    if processed_count >= 1000:
                        break
                        
                    # 링크 텍스트가 공고명일 가능성이 높음
                    title = link.text.strip()
                    
                    # 숫자만으로 된 제목이나 너무 짧은 제목은 무시
                    if not title or title.isdigit() or len(title) < 5:
                        continue
                    
                    # onclick 속성 추출
                    onclick = link.get('onclick', '')
                    
                    # 부모 행 찾기
                    parent_row = link.find_parent('tr')
                    if not parent_row:
                        continue
                    
                    # 같은 행에 있는 다른 셀 찾기
                    cells = parent_row.find_all('td')
                    
                    # 셀 위치 추정 (일반적인 패턴)
                    bid_number = ""
                    department = ""
                    date_start = ""
                    date_end = ""
                    
                    if len(cells) >= 3:
                        # 일반적인 패턴: 번호, 공고번호, 공고명, 기관명, 게시일, 마감일
                        for i, cell in enumerate(cells):
                            cell_text = cell.text.strip()
                            # 이미 링크 텍스트를 공고명으로 추출했으므로 건너뛰기
                            if cell.find('a') and cell.find('a').text.strip() == title:
                                continue
                                
                            # 위치 기반 추정
                            if not bid_number and i < 2 and cell_text and any(c.isdigit() for c in cell_text):
                                bid_number = cell_text
                            elif not department and i < 4:
                                department = cell_text
                            elif not date_start and i < 6:
                                date_start = cell_text
                            elif not date_end and i < 7:
                                date_end = cell_text
                    
                    # 상태 정보 설정
                    status = '알수없음'
                    if date_end:
                        try:
                            current_date_obj = datetime.strptime(current_date, "%Y-%m-%d")
                            end_date_obj = datetime.strptime(date_end, "%Y-%m-%d")
                            if end_date_obj < current_date_obj:
                                status = '마감'
                            else:
                                status = '공고중'
                        except Exception:
                            pass
                    
                    # 항목 데이터 생성
                    item = {
                        'title': title,
                        'bid_number': bid_number,
                        'department': department,
                        'date_start': date_start,
                        'date_end': date_end,
                        'status': status,
                        'onclick': onclick,
                        'detail_function': onclick,
                        'extraction_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    
                    # 유효한 항목만 추가 (최소한 제목은 있어야 함)
                    if item['title']:
                        items.append(item)
                        processed_count += 1
                        logger.info(f"항목 {processed_count}: {item['title'][:30]}...")
            
            return items
            
        except Exception as e:
            logger.error(f"그리드뷰 기반 항목 추출 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return []
    
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
    
    def find_search_results(self):
        """다양한 방법으로 검색 결과 테이블/요소 찾기"""
        
        # 여러 셀렉터 시도 (우선순위 순)
        selectors = [
            # 1. 현재 사이트 구조 (기본 테이블)
            (By.CSS_SELECTOR, "#mf_wfm_container_tacBidPbancLst_contents_tab2_body_gridView1 tr[id*='row']"),
            (By.XPATH, "//div[contains(@id, 'gridView')]//tr[contains(@id, 'row')]"),
            
            # 2. 일반적인 테이블 구조
            (By.CSS_SELECTOR, "table.bid_list tr, table.search_result tr"),
            (By.XPATH, "//table[contains(@class, 'list') or contains(@class, 'result')]//tr"),
            
            # 3. 목록 형식
            (By.CSS_SELECTOR, "ul.list_item li, div.result_list li"),
            
            # 4. 일반 링크
            (By.CSS_SELECTOR, "a[onclick*='bid'], a[href*='bid']"),
            
            # 5. 매우 일반적인 테이블 찾기
            (By.XPATH, "//table//tr[position() > 1]"),  # 헤더 제외 모든 행
            
            # 6. JavaScript로 테이블 검색
            (None, "js:document.querySelectorAll('table tr:not(:first-child)')"),
            (None, "js:document.querySelectorAll('div[id*=\"grid\"] tr')"),
        ]
        
        # 각 셀렉터 시도
        for selector_type, selector_value in selectors:
            try:
                if selector_type is None and selector_value.startswith("js:"):
                    # JavaScript 실행
                    js_code = selector_value[3:]  # "js:" 제거
                    elements = self.driver.execute_script(f"return Array.from({js_code})")
                    if elements and len(elements) > 0:
                        logger.info(f"JavaScript로 검색 결과 {len(elements)}개 발견: {js_code}")
                        return elements
                else:
                    # 일반 셀렉터
                    elements = self.driver.find_elements(selector_type, selector_value)
                    if elements and len(elements) > 0:
                        logger.info(f"검색 결과 {len(elements)}개 발견: {selector_type} - {selector_value}")
                        return elements
            except Exception:
                continue
        
        # 검색 결과 페이지의 테이블을 인식할 수 없는 경우
        logger.warning("검색 결과를 찾을 수 없습니다. 인식할 수 없는 페이지 구조입니다.")
        
        # 디버깅을 위해 현재 페이지 소스 저장
        try:
            with open("search_results_debug.html", "w", encoding="utf-8") as f:
                f.write(self.driver.page_source)
            logger.info("디버깅을 위해 페이지 소스를 search_results_debug.html에 저장했습니다.")
        except Exception as e:
            logger.warning(f"디버그 파일 저장 실패: {str(e)}")
            
        return []
    
    async def _enhance_with_gemini(self, items):
        """Gemini AI를 사용하여 데이터 검증 및 보완"""
        try:
            for item in items[:3]:  # 처음 3개 항목만 처리 (API 요청 제한을 위해)
                # 제목과 기타 정보를 조합해 프롬프트 생성
                prompt = f"""
                다음은 나라장터 입찰공고 정보입니다. 이 정보를 분석하여 다음 질문에 답해주세요:
                
                1. 공고명: {item.get('title', '정보 없음')}
                2. 공고번호: {item.get('bid_number', '정보 없음')} 
                3. 공고기관: {item.get('department', '정보 없음')}
                4. 게시일: {item.get('date_start', '정보 없음')}
                5. 마감일: {item.get('date_end', '정보 없음')}
                
                질문:
                1. 이 공고가 검색어 '{self.keyword}'와 연관성이 있습니까? (있음/없음)
                2. 이 공고의 주요 키워드나 업무 분야는 무엇입니까?
                3. 이 공고는 어떤 종류의 계약인가요? (물품/용역/공사 등)
                
                각 질문에 대해 간결하게 답변하고, 최종적으로 JSON 형태로 정리해 주세요:
                {
                  "relevance": "있음/없음",
                  "keywords": "주요 키워드들",
                  "contract_type": "계약 종류"
                }
                """
                
                try:
                    # Gemini API 호출 (비동기로 처리)
                    result = await extract_with_gemini_text(text_content=prompt)
                    
                    # 결과 저장
                    item['gemini_analysis'] = result
                    
                    # JSON 형식 결과 파싱 시도
                    json_match = re.search(r'\{[\s\S]*\}', result)
                    if json_match:
                        try:
                            json_data = json.loads(json_match.group(0))
                            item.update(json_data)
                            logger.info(f"Gemini 분석 완료: 연관성={json_data.get('relevance', '알 수 없음')}")
                        except json.JSONDecodeError:
                            # JSON 파싱 실패
                            item['relevance'] = "알 수 없음"
                    else:
                        # 텍스트 기반 파싱
                        lines = result.strip().split('\n')
                        for line in lines:
                            if "연관성" in line and "있음" in line.lower():
                                item['relevance'] = "있음"
                                break
                        else:
                            item['relevance'] = "없음"
                        
                        logger.info(f"Gemini 분석 완료: 연관성={item.get('relevance', '알 수 없음')}")
                    
                except Exception as api_err:
                    logger.warning(f"Gemini API 호출 오류: {str(api_err)}")
                    
        except Exception as e:
            logger.error(f"Gemini 강화 중 오류: {str(e)}")
    
    async def _extract_items_from_selenium_table(self, table):
        """Selenium 테이블에서 항목 추출"""
        results = []
        try:
            # 테이블 행 추출
            rows = table.find_elements(By.XPATH, ".//tr")
            
            # 첫 번째 행은 헤더이므로 제외
            if len(rows) > 1:
                current_date = datetime.now().strftime("%Y-%m-%d")
                
                # 행별로 항목 추출
                for i, row in enumerate(rows[1:], 0):  # 인덱스 0부터 시작 (실제 행은 1부터)
                    item = await self._extract_item_from_row(row, i, current_date)
                    if item:
                        results.append(item)
            
            logger.info(f"테이블에서 {len(results)}개 항목 추출 완료")
        except Exception as e:
            logger.error(f"테이블 항목 추출 중 오류: {str(e)}")
        
        return results
        
    