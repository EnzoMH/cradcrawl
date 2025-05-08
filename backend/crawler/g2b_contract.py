import logging
import traceback
import asyncio
from bs4 import BeautifulSoup
from datetime import datetime
import os

# 로거 설정
logger = logging.getLogger(__name__)

# Gemini API 키 설정
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

class G2BContractExtractor:
    """나라장터 계약 정보 추출 클래스"""
    
    def __init__(self, driver):
        """
        초기화
        
        Args:
            driver: Selenium WebDriver 인스턴스
        """
        self.driver = driver
    
    async def extract_contract_details(self, soup, custom_logger=None):
        """
        세부 계약 정보 추출 함수
        
        Args:
            soup: BeautifulSoup 객체
            custom_logger: 외부에서 제공된 로거 (선택사항)
            
        Returns:
            dict: 추출된 계약 상세 정보
        """
        try:
            # 로거 설정 - 외부 로거가 없으면 클래스 로거 사용
            log = custom_logger or logger
            log.info("계약 상세 정보 추출 중...")
            contract_details = {}
            
            # 모든 테이블 콘텐츠 추출
            all_tables_html = ""
            tables = soup.find_all('table')
            for table in tables:
                all_tables_html += str(table) + "\n\n"
                
            # 테이블과 raw_tables 데이터 분석
            # 계약 상세 정보를 raw_tables에서 추출
            raw_tables_data = {}
            for i, table in enumerate(tables):
                caption = table.find('caption')
                caption_text = caption.get_text(strip=True) if caption else f"테이블_{i+1}"
                
                # 테이블 내 tbody 요소 찾기
                tbody = table.find('tbody')
                if tbody:
                    # tbody 내 모든 행과 셀 데이터 수집
                    rows_data = []
                    rows = tbody.find_all('tr')
                    for row in rows:
                        cells_data = {}
                        th_cells = row.find_all('th')
                        td_cells = row.find_all('td')
                        
                        # th 셀 처리
                        for j, cell in enumerate(th_cells):
                            header_key = f"th_{j+1}"
                            cells_data[header_key] = {
                                "text": cell.get_text(strip=True),
                                "attributes": dict(cell.attrs)
                            }
                        
                        # td 셀 처리
                        for j, cell in enumerate(td_cells):
                            cell_key = f"td_{j+1}"
                            # 셀 내 input 필드 확인 (readonly 포함)
                            input_fields = cell.find_all('input')
                            input_data = []
                            for input_field in input_fields:
                                input_data.append({
                                    "value": input_field.get('value', ''),
                                    "title": input_field.get('title', ''),
                                    "id": input_field.get('id', ''),
                                    "readonly": input_field.get('readonly', False),
                                    "class": input_field.get('class', [])
                                })
                                
                            # 셀 내 링크 추출
                            links = cell.find_all('a')
                            links_data = []
                            for link in links:
                                link_data = {
                                    "text": link.get_text(strip=True),
                                    "href": link.get('href', ''),
                                    "onclick": link.get('onclick', ''),
                                    "attributes": dict(link.attrs)
                                }
                                links_data.append(link_data)
                            
                            cells_data[cell_key] = {
                                "text": cell.get_text(strip=True),
                                "links": links_data,
                                "inputs": input_data,
                                "attributes": dict(cell.attrs)
                            }
                        
                        rows_data.append(cells_data)
                    
                    raw_tables_data[caption_text] = rows_data
            
            # 저장된 raw_tables 데이터에서 필요한 정보 추출
            for table_name, rows in raw_tables_data.items():
                for row in rows:
                    for key, cell in row.items():
                        if key.startswith('th_'):
                            header_text = cell["text"]
                            # 해당 헤더에 매칭되는 value 셀 찾기
                            header_idx = int(key.split('_')[1])
                            value_key = f"td_{header_idx}"
                            
                            if value_key in row:
                                value_cell = row[value_key]
                                value_text = value_cell["text"]
                                
                                # 계약방법 추출
                                if any(keyword in header_text for keyword in ["계약방법", "계약형태", "계약구분"]):
                                    contract_details["contract_method"] = value_text
                                    log.info(f"계약방법 추출: {value_text}")
                                
                                # 입찰방법 추출
                                elif any(keyword in header_text for keyword in ["입찰방법", "입찰형태", "경쟁방법", "낙찰방법"]):
                                    # 텍스트 값이 있으면 사용, 없으면 input 필드 확인
                                    if value_text and value_text.strip():
                                        contract_details["bidding_method"] = value_text
                                        log.info(f"입찰방법 추출: {value_text}")
                                    elif 'inputs' in value_cell and value_cell['inputs']:
                                        # input 필드 확인
                                        for input_field in value_cell['inputs']:
                                            # 낙찰방법 관련 input 필드인 경우
                                            if input_field.get('title') == '낙찰방법':
                                                input_value = input_field.get('value')
                                                if input_value:
                                                    contract_details["bidding_method"] = input_value
                                                    log.info(f"입찰방법(input 필드에서 추출): {input_value}")
                                                else:
                                                    # 값이 없는 경우 일반적으로 JavaScript로 동적 설정되는 값
                                                    contract_details["bidding_method"] = "최저가낙찰제"  # 기본값 (필요에 따라 수정)
                                                    log.info(f"낙찰방법 기본값 설정: 최저가낙찰제")
                                
                                # 추정가격 추출
                                elif any(keyword in header_text for keyword in ["추정가격", "기초금액", "예정가격", "사업금액"]):
                                    contract_details["estimated_price"] = value_text
                                    log.info(f"추정가격 추출: {value_text}")
                                
                                # 계약기간 추출
                                elif any(keyword in header_text for keyword in ["계약기간", "이행기간", "납품기한", "완료기한"]):
                                    contract_details["contract_period"] = value_text
                                    log.info(f"계약기간 추출: {value_text}")
                                
                                # 납품장소 추출
                                elif any(keyword in header_text for keyword in ["납품장소", "이행장소", "설치장소"]):
                                    contract_details["delivery_location"] = value_text
                                    log.info(f"납품장소 추출: {value_text}")
                                
                                # 참가자격 추출
                                elif any(keyword in header_text for keyword in ["참가자격", "참가제한", "입찰참가자격", "참가조건"]):
                                    contract_details["qualification"] = value_text
                                    log.info(f"참가자격 추출: {value_text}")
            
            # 참가자격이 별도의 div나 텍스트 블록에 있는 경우 추출
            if "qualification" not in contract_details or not contract_details["qualification"]:
                # 자격 관련 섹션 찾기
                qualification_sections = []
                for heading in soup.find_all(['h3', 'h4', 'div', 'strong', 'p']):
                    heading_text = heading.get_text(strip=True)
                    if any(keyword in heading_text for keyword in ["참가자격", "참가제한", "입찰참가", "자격요건"]):
                        # 해당 헤딩의 부모 또는 다음 형제 요소 찾기
                        parent = heading.find_parent('div') or heading.find_parent('section')
                        if parent:
                            qualification_text = parent.get_text(strip=True).replace(heading_text, "", 1)
                            qualification_sections.append(qualification_text)
                        
                        # 또는 다음 형제 요소가 내용인 경우
                        next_sibling = heading.find_next_sibling()
                        if next_sibling and next_sibling.name in ['div', 'p', 'ul']:
                            qualification_sections.append(next_sibling.get_text(strip=True))
                
                if qualification_sections:
                    contract_details["qualification"] = "\n".join(qualification_sections)
                    log.info(f"별도 섹션에서 참가자격 추출: {contract_details['qualification'][:50]}...")
            
            # 전체 페이지에서 모든 input 필드 검색하여 중요 필드 추출
            all_input_fields = soup.find_all('input')
            important_fields = {}
            for input_field in all_input_fields:
                field_title = input_field.get('title')
                field_value = input_field.get('value')
                field_id = input_field.get('id')
                
                # 이미 값이 추출된 필드는 건너뛰기
                if field_title and field_title in ['낙찰방법', '계약방법', '참가자격'] and field_id:
                    important_fields[field_title] = {
                        'id': field_id,
                        'value': field_value or "값 없음(JavaScript로 설정됨)"
                    }
            
            # 원시 데이터 저장 (디버깅 및 분석용)
            contract_details['raw_input_fields'] = important_fields
            
            # 파일 첨부 정보 추출
            file_attachments = []
            file_links = soup.select("a[href*='fileDown']")
            for link in file_links:
                file_name = link.get_text(strip=True)
                if file_name:
                    file_attachments.append(file_name)
            
            contract_details["file_attachments"] = file_attachments
            log.info(f"첨부파일 {len(file_attachments)}개 추출 완료")
            
            # Gemini API 호출을 위한 모든 테이블 HTML
            from backend.utils.ai_helpers import extract_with_gemini_text
            
            # Gemini API 프롬프트 템플릿
            prompt_template = """
            아래는 한국 정부 입찰 및 계약에 관한 테이블 데이터입니다. 테이블 내용을 분석하여 다음 정보를 추출하세요:

            1. 입찰 공고일 (bid_date)
            2. 입찰 번호 (bid_number) 
            3. 입찰 제목 (bid_title)
            4. 입찰 방식 (bidding_method) - 예: 일반경쟁, 제한경쟁, 지명경쟁 등
            5. 낙찰 방식 (award_method) - 예: 적격심사, 최저가, 종합평가 등
            6. 계약 방식 (contract_method) - 예: 총액, 단가 등
            7. 계약 종류 (contract_type) - 예: 공사, 용역, 물품 등
            8. 컨소시엄 가능 여부 (consortium_status)
            9. 실적 제한 조건 (performance_restriction)
            10. 예가 방식 (pricing_method) - 예: 복수예가, 단일예가 등
            11. 기초금액 및 추정가격 (estimated_price)
            12. 담당자 연락처 (contact_info)
            13. 계약기간/납품기한 (contract_period)
            14. 납품 장소 (delivery_location)

            가능한 상세히 답변해주시고, 해당 정보가 없는 경우 "정보 없음"으로 표시해주세요.

            테이블 데이터:
            {text_content}

            첨부 파일 목록: {file_list}
            """
            
            # 파일 목록 문자열 생성
            file_list_str = ", ".join(file_attachments) if file_attachments else "첨부 파일 없음"
            
            # Gemini API 호출
            try:
                # API 키 확인
                if not GEMINI_API_KEY:
                    log.error("GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")
                    contract_details["gemini_analysis"] = "API 키 오류로 정보 추출 실패"
                else:
                    gemini_response = await extract_with_gemini_text(
                        text_content=all_tables_html, 
                        prompt_template=prompt_template.replace("{file_list}", file_list_str)
                    )
                    
                    # 응답 저장
                    contract_details["gemini_analysis"] = gemini_response
            except Exception as gemini_err:
                log.error(f"Gemini API 호출 오류: {str(gemini_err)}")
                contract_details["gemini_analysis"] = f"오류: {str(gemini_err)}"
            
            # 디버깅을 위해 전체 raw_tables 데이터도 저장
            contract_details["raw_tables_data"] = raw_tables_data
            
            log.info(f"계약 상세 정보 추출 완료: {list(contract_details.keys())}")
            return contract_details
            
        except Exception as e:
            logger.error(f"계약 상세 정보 추출 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return {}
    
    def _parse_gemini_text_to_json(self, text):
        """
        Gemini API의 텍스트 응답을 구조화된 JSON으로 변환
        
        Args:
            text: Gemini API의 응답 텍스트
            
        Returns:
            구조화된 JSON 객체
        """
        try:
            result = {}
            
            # 줄 단위로 분리
            lines = text.strip().split('\n')
            current_key = None
            current_value = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # 숫자로 시작하는 줄은 새로운 항목으로 간주
                if line[0].isdigit() and '. ' in line:
                    # 이전 항목 저장
                    if current_key and current_value:
                        result[current_key] = '\n'.join(current_value).strip()
                        current_value = []
                    
                    # 새 항목 파싱
                    parts = line.split('. ', 1)
                    if len(parts) == 2:
                        key_value = parts[1].split(':', 1)
                        if len(key_value) == 2:
                            current_key = key_value[0].strip()
                            value_part = key_value[1].strip()
                            current_value.append(value_part)
                        else:
                            current_key = parts[1].strip()
                else:
                    # 값 계속 누적
                    if current_key:
                        current_value.append(line)
            
            # 마지막 항목 저장
            if current_key and current_value:
                result[current_key] = '\n'.join(current_value).strip()
            
            return result
        except Exception as e:
            logger.warning(f"Gemini 텍스트 파싱 실패: {str(e)}")
            return {"raw_text": text} 