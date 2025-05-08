import logging
import traceback
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

# 로거 설정
logger = logging.getLogger(__name__)

def convert_tables_to_text(table_data):
    """
    테이블 데이터를 텍스트 형식으로 변환합니다.
    
    Args:
        table_data: 테이블 데이터 리스트
        
    Returns:
        변환된 텍스트
    """
    text_output = []
    
    for table in table_data:
        table_text = []
        for key, value in table.items():
            if key != 'table_index':  # table_index는 제외
                table_text.append(f"{key}: {value}")
        
        if table_text:
            text_output.append("\n".join(table_text))
    
    return "\n\n".join(text_output)

def extract_detail_page_data_from_soup(soup, driver=None):
    """
    입찰 상세 페이지에서 주요 데이터를 추출합니다.
    
    Args:
        soup: BeautifulSoup 객체
        driver: Selenium WebDriver 인스턴스 (선택사항)
        
    Returns:
        추출된 데이터 딕셔너리
    """
    data = {}
    
    try:
        # 1. 공고 번호 추출
        bid_number_elements = soup.select('th:contains("공고번호"), th:contains("입찰공고번호"), th:contains("입찰번호")')
        for el in bid_number_elements:
            if el and el.find_next('td'):
                data['공고번호'] = el.find_next('td').get_text(strip=True)
                break
        
        # 2. 공고 제목 추출
        title_elements = soup.select('th:contains("공고명"), th:contains("입찰건명"), th:contains("사업명"), th:contains("공사명"), th:contains("물품명"), th:contains("용역명")')
        for el in title_elements:
            if el and el.find_next('td'):
                data['공고명'] = el.find_next('td').get_text(strip=True)
                break
        
        # 3. 발주기관 추출
        org_elements = soup.select('th:contains("공고기관"), th:contains("수요기관"), th:contains("발주기관")')
        for el in org_elements:
            if el and el.find_next('td'):
                data['발주기관'] = el.find_next('td').get_text(strip=True)
                break
        
        # 4. 계약방법 추출
        method_elements = soup.select('th:contains("계약방법"), th:contains("입찰방식"), th:contains("낙찰자선정방법")')
        for el in method_elements:
            if el and el.find_next('td'):
                data['계약방법'] = el.find_next('td').get_text(strip=True)
                break
        
        # 5. 금액 관련 정보 추출
        price_elements = soup.select('th:contains("추정가격"), th:contains("사업금액"), th:contains("기초금액"), th:contains("예정가격")')
        for el in price_elements:
            if el and el.find_next('td'):
                key = el.get_text(strip=True)
                data[key] = el.find_next('td').get_text(strip=True)
        
        # 6. 날짜 관련 정보 추출
        date_elements = soup.select('th:contains("게시일시"), th:contains("공고일시"), th:contains("마감일시"), th:contains("개찰일시")')
        for el in date_elements:
            if el and el.find_next('td'):
                key = el.get_text(strip=True)
                data[key] = el.find_next('td').get_text(strip=True)
        
        # 7. 첨부파일 추출
        attachments = []
        attachment_elements = soup.select('a[href*="download"], a[href*=".pdf"], a[href*=".hwp"], a[href*=".doc"], a[href*=".xls"], a[href*=".zip"]')
        for el in attachment_elements:
            # 파일명만 추출
            file_name = el.get_text(strip=True)
            if file_name and not file_name.lower() in ['', '목록', '이전', '다음']:
                file_url = el.get('href', '')
                # 상대 URL을 절대 URL로 변환
                if file_url and not file_url.startswith('http'):
                    base_url = driver.current_url if driver else ""
                    if file_url.startswith('/'):
                        # 도메인부터 시작하는 절대 경로
                        parsed_url = urlparse(base_url)
                        base_domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
                        file_url = base_domain + file_url
                    else:
                        # 현재 페이지 기준 상대 경로
                        file_url = urljoin(base_url, file_url)
                
                if file_url:
                    attachments.append({
                        'name': file_name,
                        'url': file_url
                    })
        
        if attachments:
            data['첨부파일'] = attachments
        
        # 8. 담당자 정보 추출
        contact_elements = soup.select('th:contains("담당자"), th:contains("담당부서"), th:contains("계약담당자"), th:contains("문의처"), th:contains("연락처")')
        for el in contact_elements:
            if el and el.find_next('td'):
                key = el.get_text(strip=True)
                data[key] = el.find_next('td').get_text(strip=True)
        
        # 9. 입찰 참가자격 추출
        qualification_elements = soup.select('th:contains("참가자격"), th:contains("참가조건"), th:contains("입찰참가자격")')
        for el in qualification_elements:
            if el and el.find_next('td'):
                data['참가자격'] = el.find_next('td').get_text(strip=True)
                break
        
        # 10. 테이블 데이터 추출
        tables = soup.find_all('table')
        if tables:
            table_data = []
            for idx, table in enumerate(tables):
                table_dict = {'table_index': idx}
                rows = table.find_all('tr')
                for row in rows:
                    headers = row.find_all('th')
                    cells = row.find_all('td')
                    
                    if headers and cells:
                        for header, cell in zip(headers, cells):
                            header_text = header.get_text(strip=True)
                            cell_text = cell.get_text(strip=True)
                            if header_text and cell_text:
                                table_dict[header_text] = cell_text
                
                if len(table_dict) > 1:  # table_index 외에 다른 데이터가 있는 경우에만 추가
                    table_data.append(table_dict)
            
            if table_data:
                data['테이블_데이터'] = table_data
                
                # 테이블 데이터를 텍스트로 변환
                data['테이블_텍스트'] = convert_tables_to_text(table_data)
        
        # 11. 공고 본문 텍스트 추출 (가장 긴 텍스트 블록)
        content_divs = soup.select('div.detail_content, div.contents, div#contents, div.bid-detail, div.body, div.text')
        if content_divs:
            longest_text = ""
            for div in content_divs:
                text = div.get_text(strip=True)
                if len(text) > len(longest_text):
                    longest_text = text
            
            if longest_text:
                data['공고_본문'] = longest_text
        
        # 12. 공고 상태 추출
        status_elements = soup.select('th:contains("공고상태"), th:contains("진행상황"), th:contains("입찰상태")')
        for el in status_elements:
            if el and el.find_next('td'):
                data['공고상태'] = el.find_next('td').get_text(strip=True)
                break
        
        # 13. 장소 관련 정보 추출
        location_elements = soup.select('th:contains("납품장소"), th:contains("이행장소"), th:contains("설치장소")')
        for el in location_elements:
            if el and el.find_next('td'):
                key = el.get_text(strip=True)
                data[key] = el.find_next('td').get_text(strip=True)
        
        # 14. 기간 관련 정보 추출
        period_elements = soup.select('th:contains("납품기한"), th:contains("계약기간"), th:contains("이행기간"), th:contains("완료기한")')
        for el in period_elements:
            if el and el.find_next('td'):
                key = el.get_text(strip=True)
                data[key] = el.find_next('td').get_text(strip=True)
        
        # 15. 프론트엔드 추가 정보 (JavaScript 실행 결과 병합)
        if driver:
            try:
                from backend.crawler.g2b_extractor import G2BExtractor
                extractor = G2BExtractor(driver=driver)
                js_data = extractor._js_extract_values()
                for key, value in js_data.items():
                    if key not in data and value:  # 중복되지 않으면서 값이 있는 필드만 추가
                        data[key] = value
            except Exception as js_err:
                logger.warning(f"JavaScript 데이터 추출 실패: {str(js_err)}")
    
    except Exception as e:
        logger.error(f"입찰 상세 데이터 추출 중 오류: {str(e)}")
        logger.debug(traceback.format_exc())
    
    return data

def extract_table_data(soup, table_selector=None):
    """
    테이블에서 구조화된 데이터 추출
    
    Args:
        soup: BeautifulSoup 객체
        table_selector: 테이블 선택자 (선택사항)
        
    Returns:
        테이블 데이터 딕셔너리
    """
    data = {}
    
    try:
        tables = []
        if table_selector:
            tables = soup.select(table_selector)
        else:
            tables = soup.find_all('table')
            
        for idx, table in enumerate(tables):
            table_name = f"table_{idx+1}"
            
            # 테이블 캡션 확인
            caption = table.find('caption')
            if caption:
                table_name = caption.get_text(strip=True)
            
            data[table_name] = []
            rows = table.find_all('tr')
            
            # 헤더 행 분석
            headers = []
            header_row = table.find('thead')
            if header_row:
                header_cells = header_row.find_all(['th', 'td'])
                headers = [cell.get_text(strip=True) for cell in header_cells]
            
            # 헤더가 없을 경우 첫 번째 행의 th 태그 사용
            if not headers:
                first_row = rows[0] if rows else None
                if first_row:
                    header_cells = first_row.find_all('th')
                    if header_cells:
                        headers = [cell.get_text(strip=True) for cell in header_cells]
                        rows = rows[1:]  # 헤더 행 제외
            
            # 행 데이터 추출
            for row in rows:
                row_data = {}
                cells = row.find_all(['th', 'td'])
                
                # 헤더가 있는 경우 헤더와 셀 매핑
                if headers and len(headers) == len(cells):
                    for i, cell in enumerate(cells):
                        row_data[headers[i]] = cell.get_text(strip=True)
                else:
                    # 헤더가 없는 경우 인덱스 기반 키 사용
                    for i, cell in enumerate(cells):
                        # 첫 번째 셀이 th인 경우 헤더로 간주
                        if i == 0 and cell.name == 'th':
                            row_data['header'] = cell.get_text(strip=True)
                        else:
                            row_data[f'col_{i+1}'] = cell.get_text(strip=True)
                
                # 비어있지 않은 행만 추가
                if row_data:
                    data[table_name].append(row_data)
        
    except Exception as e:
        logger.error(f"테이블 데이터 추출 중 오류: {str(e)}")
        logger.debug(traceback.format_exc())
    
    return data

def extract_attachments(soup, base_url=None):
    """
    첨부 파일 정보 추출
    
    Args:
        soup: BeautifulSoup 객체
        base_url: 기본 URL (선택사항)
        
    Returns:
        첨부 파일 정보 리스트
    """
    attachments = []
    
    try:
        # 다양한 패턴의 첨부 파일 링크 검색
        file_links = soup.select('a[href*="download"], a[href*="fileDown"], a[href*=".pdf"], a[href*=".hwp"], a[href*=".doc"], a[href*=".xls"]')
        
        for link in file_links:
            # 파일명 추출
            file_name = link.get_text(strip=True)
            if not file_name or file_name.lower() in ['목록', '이전', '다음']:
                continue
                
            # URL 추출
            file_url = link.get('href', '')
            if not file_url:
                continue
                
            # 상대 URL을 절대 URL로 변환
            if file_url and not file_url.startswith('http') and base_url:
                if file_url.startswith('/'):
                    # 도메인부터 시작하는 절대 경로
                    parsed_url = urlparse(base_url)
                    base_domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
                    file_url = base_domain + file_url
                else:
                    # 현재 페이지 기준 상대 경로
                    file_url = urljoin(base_url, file_url)
            
            # JavaScript 링크 처리
            if file_url.startswith('javascript:'):
                onclick = file_url
                file_url = None
            else:
                onclick = link.get('onclick', '')
            
            attachments.append({
                'name': file_name,
                'url': file_url,
                'onclick': onclick if onclick else None
            })
    
    except Exception as e:
        logger.error(f"첨부 파일 추출 중 오류: {str(e)}")
        logger.debug(traceback.format_exc())
    
    return attachments 