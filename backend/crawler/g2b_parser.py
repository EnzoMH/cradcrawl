"""
나라장터 상세 페이지 파싱 모듈

나라장터 입찰공고 상세 페이지의 파싱 및 데이터 추출 기능을 제공합니다.
"""

import logging
import traceback
import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from bs4 import BeautifulSoup

from backend.utils.ai_helpers import extract_with_gemini_text

# 로거 설정
logger = logging.getLogger("backend.crawler.parser")

class G2BParser:
    """나라장터 상세 페이지 파싱 클래스"""
    
    @staticmethod
    async def parse_detail_page(html_source: str, bid_number: str, bid_title: str) -> Dict[str, Any]:
        """
        상세 페이지 HTML에서 입찰정보 추출
        
        Args:
            html_source: 상세 페이지 HTML 소스
            bid_number: 입찰 번호
            bid_title: 입찰 제목
            
        Returns:
            추출된 데이터 딕셔너리
        """
        try:
            logger.info(f"상세 페이지 데이터 추출 시작: {bid_number}")
            
            # BeautifulSoup 파싱
            soup = BeautifulSoup(html_source, 'html.parser')
            
            # 결과 데이터 초기화
            detail_data = {
                "bid_number": bid_number,
                "bid_title": bid_title,
                "organization": None,
                "division": None,
                "contract_method": None,
                "bid_type": None,
                "estimated_price": None,
                "qualification": None,
                "description": None,
                "raw_tables": {}  # 원시 테이블 데이터 저장
            }
            
            # 모든 테이블과 tbody 요소 추출하여 저장
            try:
                all_tables = soup.find_all('table')
                for i, table in enumerate(all_tables):
                    # 테이블 캡션 또는 제목 찾기
                    caption = table.find('caption')
                    caption_text = caption.get_text(strip=True) if caption else f"테이블_{i+1}"
                    
                    # 테이블 내 tbody 요소 찾기
                    tbody = table.find('tbody')
                    if tbody:
                        # tbody 내 모든 행과 셀을 추출하여 구조화된 데이터로 저장
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
                                
                                # 셀 내 input 필드 확인 (동적으로 채워지는 값 처리)
                                input_fields = cell.find_all('input')
                                input_values = []
                                for input_field in input_fields:
                                    input_value = input_field.get('value', '')
                                    input_title = input_field.get('title', '')
                                    input_values.append({
                                        'title': input_title,
                                        'value': input_value
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
                                
                                # 기본 텍스트가 비어있고 input 값이 있으면 input 값 사용
                                cell_text = cell.get_text(strip=True)
                                if not cell_text and input_values:
                                    cell_text = ' / '.join([iv['value'] for iv in input_values if iv['value']])
                                
                                cells_data[cell_key] = {
                                    "text": cell_text,
                                    "input_values": input_values,
                                    "links": links_data,
                                    "attributes": dict(cell.attrs)
                                }
                            
                            rows_data.append(cells_data)
                        
                        detail_data["raw_tables"][caption_text] = rows_data
                
                logger.info(f"{len(detail_data['raw_tables'])}개의 원시 테이블 데이터 저장 완료")
                
                # 원시 테이블 데이터를 텍스트로 변환하여 Gemini 모델에 전달
                if detail_data["raw_tables"]:
                    table_text = G2BParser._convert_raw_tables_to_text(detail_data["raw_tables"])
                    
                    # 파일 첨부 섹션 찾기
                    file_links = soup.select("a[href*='download'], a[href*='fileDown'], a.file")
                    file_attachments = []
                    file_info = ""
                    if file_links:
                        file_info += "[파일첨부]\n"
                        for link in file_links:
                            file_name = link.get_text(strip=True) or link.get("title") or "첨부파일"
                            file_attachments.append(file_name)
                            file_info += f"- {file_name}\n"
                    
                    # 파일 첨부 정보 저장
                    detail_data["file_attachments"] = file_attachments
                    
                    # Gemini 프롬프트 구성
                    prompt_template = """
입찰 상세 정보 추출 전문가로서, 다음 HTML 정보에서 중요 정보를 추출해주세요.

다음은 입찰공고 상세페이지의 테이블 데이터와 전체 페이지 텍스트입니다:

{text_content}

다음 중요 정보를 확인하여 저장해주세요.(JSON 형식으로 응답 X)
1. 게시일시 
2. 입찰공고번호 
3. 공고명 
4. 입찰방식
5. 낙찰방법
6. 계약방법
7. 계약구분
8. 공동계약 및 구성방식(컨소시엄 여부)
9. 실적제한 여부, 제한여부
10. 가격과 관련된 모든정보(예가방법, 사업금액, 배정에산, 추정에산)
11. 기관담당자정보(담당자 이름, 팩스번호, 전화번호)
12. 계약기간/납품기한
13. 납품장소
14. 참가자격
15. 파일첨부

위 형식대로 각 항목에 해당하는 정보를 추출해주세요. 정보가 없는 경우 "정보 없음"으로 표시해주세요.
JSON 형식이 아닌 일반 텍스트로 응답해주세요.
"""
                    
                    combined_text = f"{table_text}\n\n{file_info}"
                    
                    # Gemini API 호출
                    try:
                        gemini_response = await extract_with_gemini_text(combined_text, prompt_template)
                        
                        # Gemini 응답을 문자열로 변환하여 저장
                        if isinstance(gemini_response, dict):
                            # 딕셔너리인 경우 문자열로 변환
                            detail_data["prompt_result"] = json.dumps(gemini_response, ensure_ascii=False)
                        else:
                            # 이미 문자열인 경우 그대로 저장
                            detail_data["prompt_result"] = str(gemini_response)
                        
                        # 텍스트 응답을 구조화된 데이터로 변환하여 저장
                        parsed_result = G2BParser._parse_gemini_text_to_json(detail_data["prompt_result"])
                        detail_data["prompt_result_parsed"] = parsed_result
                        
                        # 중요 필드들을 메인 데이터로 가져오기
                        for key, value in parsed_result.items():
                            if "계약방법" in key.lower() and not detail_data.get("contract_method"):
                                detail_data["contract_method"] = value
                            elif "입찰방식" in key.lower() and not detail_data.get("bid_type"):
                                detail_data["bid_type"] = value
                            elif "추정가격" in key.lower() or "사업금액" in key.lower() or "기초금액" in key.lower():
                                detail_data["estimated_price"] = value
                            elif "계약기간" in key.lower() or "납품기한" in key.lower():
                                detail_data["contract_period"] = value
                            elif "납품장소" in key.lower() or "이행장소" in key.lower():
                                detail_data["delivery_location"] = value
                            elif "참가자격" in key.lower() or "자격요건" in key.lower():
                                detail_data["qualification"] = value
                        
                        logger.info("Gemini API를 통한 상세 정보 추출 완료")
                    except Exception as gemini_err:
                        logger.error(f"Gemini API 호출 오류: {str(gemini_err)}")
            
            except Exception as raw_tables_err:
                logger.warning(f"원시 테이블 데이터 추출 실패: {str(raw_tables_err)}")
            
            # 1. 주요 섹션별 데이터 추출 (추가 데이터 확보용)
            section_names = ["공고일반", "입찰자격", "투찰제한", "제안요청정보", "협상에 의한 계약", "가격", 
                           "기관담당자정보", "수요기관 담당자정보", "연관정보", "파일첨부"]
            
            # 1-1. 공고기관 정보 추출 (기관담당자정보 섹션)
            try:
                # 기관담당자정보 섹션 찾기
                org_section = None
                for heading in soup.find_all(['h3', 'h4', 'div', 'span', 'strong']):
                    if "기관담당자" in heading.get_text() or "공고기관" in heading.get_text():
                        org_section = heading.find_parent('div') or heading.find_parent('table') or heading.find_parent('section')
                        break
                
                if org_section:
                    # 테이블 내용 추출
                    org_tables = org_section.find_all('table')
                    if org_tables:
                        for table in org_tables:
                            rows = table.find_all('tr')
                            for row in rows:
                                cells = row.find_all(['th', 'td'])
                                if len(cells) >= 2:
                                    header = cells[0].get_text(strip=True)
                                    value = cells[1].get_text(strip=True)
                                    
                                    # 값이 비어있으면 input 필드 확인
                                    if not value:
                                        input_field = cells[1].find('input')
                                        if input_field:
                                            value = input_field.get('value', '')
                                    
                                    if any(keyword in header for keyword in ["수요기관", "공고기관"]):
                                        detail_data["organization"] = value
                                    elif any(keyword in header for keyword in ["담당자", "담당부서"]):
                                        detail_data["division"] = value
            except Exception as org_err:
                logger.warning(f"기관정보 추출 실패: {str(org_err)}")
            
            # Pydantic 모델과 호환되는 필드 이름 사용
            # bid_number, bid_title은 이미 설정됨
            if "organization" not in detail_data or not detail_data["organization"]:
                detail_data["organization"] = detail_data.get("department", None)
                
            # 크롤링 시간 기록 (Pydantic 모델 호환성)
            detail_data["extracted_time"] = datetime.now().isoformat()
            
            return detail_data
            
        except Exception as e:
            logger.error(f"상세 페이지 데이터 추출 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return {}
    
    @staticmethod
    def _convert_raw_tables_to_text(raw_tables: Dict[str, List[Dict[str, Any]]]) -> str:
        """
        원시 테이블 데이터를 텍스트로 변환
        
        Args:
            raw_tables: 테이블 데이터
            
        Returns:
            변환된 텍스트
        """
        table_text = ""
        
        # 테이블 데이터를 텍스트로 변환
        for table_name, rows in raw_tables.items():
            table_text += f"[테이블: {table_name}]\n"
            
            for row_data in rows:
                header_texts = []
                value_texts = []
                
                # 헤더 텍스트 추출
                for key, cell in row_data.items():
                    if key.startswith('th_'):
                        header_texts.append(cell["text"])
                    elif key.startswith('td_'):
                        # 기본 텍스트 사용, 비어있으면 input_values 확인
                        cell_text = cell["text"]
                        if not cell_text and 'input_values' in cell:
                            input_values = [iv['value'] for iv in cell['input_values'] if iv['value']]
                            if input_values:
                                cell_text = ' / '.join(input_values)
                        value_texts.append(cell_text)
                
                # 행 정보 추가
                if header_texts and value_texts:
                    for i, header in enumerate(header_texts):
                        if i < len(value_texts):
                            table_text += f"{header}: {value_texts[i]}\n"
                elif header_texts:
                    table_text += f"{', '.join(header_texts)}\n"
                elif value_texts:
                    table_text += f"{', '.join(value_texts)}\n"
            
            table_text += "\n"
        
        return table_text
    
    @staticmethod
    def _parse_gemini_text_to_json(text: str) -> Dict[str, str]:
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
    
