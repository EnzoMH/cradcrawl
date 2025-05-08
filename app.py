"""
나라장터 크롤링 애플리케이션 - 백엔드 FastAPI 서버

이 모듈은 나라장터 웹사이트에서 입찰 공고 정보를 크롤링하는 FastAPI 애플리케이션을 제공합니다.
"""

# 시스템 경로 설정 (모듈 임포트를 위해 가장 먼저 실행)
import sys
from pathlib import Path

# 현재 디렉토리를 시스템 경로에 추가
ROOT_DIR = Path(__file__).parent.absolute()
sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI, WebSocket, Request, HTTPException, status, Response, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio
import logging
import os
import json
import traceback
from datetime import datetime
from typing import List, Dict, Any, Optional
import pandas as pd
from io import BytesIO

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,  # 전체 로깅 레벨을 DEBUG로 변경
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)

# 특정 라이브러리 로그 레벨 조정
logging.getLogger('selenium').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('chardet').setLevel(logging.WARNING)

logger = logging.getLogger("cradcrawl")
logger.setLevel(logging.INFO)

# backend 패키지 로거 설정
backend_logger = logging.getLogger("backend")
backend_logger.setLevel(logging.DEBUG)

# 특히 crawler 모듈의 로그는 반드시 표시
crawler_logger = logging.getLogger("backend.crawler")
crawler_logger.setLevel(logging.DEBUG)

# 현재 디렉토리 및 모듈 경로 설정
STATIC_DIR = ROOT_DIR / "static"
RESULTS_DIR = ROOT_DIR / "results"

# 디렉토리 생성
RESULTS_DIR.mkdir(exist_ok=True)

# 직접 환경 변수 설정 (지정된 API 키)
GEMINI_API_KEY_VALUE = "AIzaSyADr8WuYg4EBeOnQRK8gJu9luhvkz47ADY"
os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY_VALUE
logger.info(f"GEMINI_API_KEY 환경 변수를 직접 설정했습니다.")

# .env 파일 로드 (프로젝트 루트 기준)
try:
    from dotenv import load_dotenv
    try:
        # UTF-8로 먼저 시도
        load_dotenv(ROOT_DIR / '.env', encoding='utf-8')
        logger.info("환경 변수 로드 성공 (UTF-8)")
    except UnicodeDecodeError:
        # UTF-8 디코딩 실패 시 다른 인코딩 시도
        try:
            load_dotenv(ROOT_DIR / '.env', encoding='cp949')
            logger.info("환경 변수 로드 성공 (CP949)")
        except UnicodeDecodeError:
            try:
                load_dotenv(ROOT_DIR / '.env', encoding='latin-1')
                logger.info("환경 변수 로드 성공 (latin-1)")
            except Exception as e:
                logger.error(f".env 파일 로드 실패: {str(e)}")
                # 환경 변수 없이 계속 진행
    except FileNotFoundError:
        logger.warning(".env 파일을 찾을 수 없습니다.")
    except Exception as e:
        logger.error(f".env 파일 로드 중 오류 발생: {str(e)}")
except ImportError:
    logger.warning("dotenv 패키지가 설치되어 있지 않습니다. 환경 변수를 직접 설정해주세요.")

# Gemini API 설정
DEFAULT_GEMINI_API_KEY = "AIzaSyDLe9f5i3AlKZp4eX-U8Xgop7GiO0y_Qzc"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", DEFAULT_GEMINI_API_KEY)
if GEMINI_API_KEY == DEFAULT_GEMINI_API_KEY:
    logger.info("환경 변수에서 GEMINI_API_KEY를 찾을 수 없어 기본값을 사용합니다.")
elif not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY 환경 변수가 설정되지 않았습니다. API 관련 기능이 제한됩니다.")
else:
    logger.info("GEMINI_API_KEY 환경 변수를 성공적으로 로드했습니다.")

# 크롤러 관련 모듈 임포트 (반드시 환경 변수 설정 후에 임포트)
try:
    # 직접 g2b_crawler 모듈에서 G2BCrawler 클래스를 임포트
    from backend.crawler.g2b_crawler import G2BCrawler
    from backend.models import BidItem, SearchResult, BidStatus
    logger.info("크롤러 모듈 임포트 성공")
except ImportError as e:
    logger.error(f"크롤러 모듈 임포트 실패: {str(e)}")
    # 임포트 실패 시 오류 추적 정보 표시
    logger.debug(traceback.format_exc())

# 웹소켓 관리자 클래스
class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.logger = logging.getLogger(__name__)
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.logger.info(f"웹소켓 클라이언트 연결됨 (총 {len(self.active_connections)}개)")
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        self.logger.info(f"웹소켓 클라이언트 연결 해제 (총 {len(self.active_connections)}개)")
    
    async def broadcast(self, message: Dict[str, Any]):
        """모든 연결된 클라이언트에 메시지 전송"""
        disconnected_clients = []
        
        for client in self.active_connections:
            try:
                await client.send_json(message)
            except Exception as e:
                self.logger.error(f"클라이언트 메시지 전송 중 오류: {str(e)}")
                disconnected_clients.append(client)
        
        # 연결 해제된 클라이언트 제거
        for client in disconnected_clients:
            if client in self.active_connections:
                self.active_connections.remove(client)
        
        if disconnected_clients:
            self.logger.info(f"{len(disconnected_clients)}개 연결 해제된 클라이언트 제거됨")
    
    async def send_log(self, message: str, level: str = "info"):
        """로그 메시지 전송"""
        await self.broadcast({
            "type": "log",
            "data": {
                "message": message,
                "level": level,
                "timestamp": datetime.now().isoformat()
            }
        })
    
    async def send_status(self, data: Dict[str, Any]):
        """상태 업데이트 전송"""
        await self.broadcast({
            "type": "status",
            "data": data
        })
    
    async def send_results(self, results: List[Dict[str, Any]]):
        """결과 업데이트 전송"""
        # 데이터 구조 수정: bid_info 필드에 필요한 정보 포함
        formatted_results = []
        for item in results:
            # 기본 정보 구성
            bid_info = {
                'title': item.get('title') or item.get('bid_title', ''),
                'number': item.get('bid_number', ''),
                'agency': item.get('department') or item.get('organization', ''),
                'date': item.get('date_start') or item.get('start_date', ''),
                'end_date': item.get('date_end') or item.get('deadline', ''),
                'status': item.get('status', '공고중')
            }
            
            # 항목 포맷팅
            formatted_item = {
                'id': item.get('id', ''),
                'title': item.get('title') or item.get('bid_title', ''),
                'bid_number': item.get('bid_number', ''),
                'department': item.get('department') or item.get('organization', ''),
                'bid_info': bid_info,
                'details': {
                    'contract_method': item.get('contract_method', ''),
                    'estimated_price': item.get('estimated_price', ''),
                    'qualification': item.get('qualification', ''),
                    'bid_type': item.get('bid_type', ''),
                    'contract_period': item.get('contract_period', ''),
                    'delivery_location': item.get('delivery_location', ''),
                    'notice': item.get('notice', '')
                },
                'file_attachments': item.get('file_attachments', []),
                'detail_url': item.get('detail_url', '')
            }
            
            formatted_results.append(formatted_item)
        
        await self.broadcast({
            "type": "result",
            "data": {
                "results": formatted_results
            }
        })
    
    async def send_error(self, message: str, stopped: bool = False):
        """오류 메시지 전송"""
        await self.broadcast({
            "type": "error",
            "data": {
                "message": message,
                "stopped": stopped,
                "timestamp": datetime.now().isoformat()
            }
        })

# 크롤링 상태 관리 클래스
class CrawlingState:
    def __init__(self):
        self.is_running = False
        self.crawler = None
        self.results = []
        self.processed_keywords = []
        self.total_keywords = 0
        self.start_time = None
        self.end_time = None
        self.websocket_manager = WebSocketManager()
        self.logger = logging.getLogger(__name__)
    
    def get_status(self) -> Dict[str, Any]:
        """현재 크롤링 상태 반환"""
        return {
            "is_running": self.is_running,
            "processed_keywords": self.processed_keywords,
            "total_keywords": self.total_keywords,
            "total_items": len(self.results),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None
        }
    
    def save_results(self, filename: Optional[str] = None) -> str:
        """결과를 JSON 파일로 저장"""
        # 파일명 자동 생성
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"crawl_results_{timestamp}.json"
        
        # 경로 완성
        filepath = RESULTS_DIR / filename
        
        # 저장할 데이터 구성
        save_data = {
            "timestamp": datetime.now().isoformat(),
            "total_items": len(self.results),
            "keywords": self.processed_keywords,
            "results": self.results
        }
        
        # JSON으로 저장
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"결과 저장 완료: {filepath} ({len(self.results)}건)")
        return str(filepath)

# 크롤링 상태 인스턴스 생성
crawling_state = CrawlingState()

# FastAPI 앱 생성
app = FastAPI(
    title="나라장터 크롤링 API",
    description="국가종합전자조달 나라장터 웹사이트에서 입찰공고 정보를 수집하는 API",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 및 템플릿 설정
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=STATIC_DIR / "html")

# favicon 처리
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """파비콘 제공"""
    favicon_path = STATIC_DIR / "img" / "favicon.ico"
    if not favicon_path.exists():
        # 기본 경로에 없을 경우 다른 위치 확인
        favicon_path = STATIC_DIR / "favicon.ico"
        if not favicon_path.exists():
            # 파비콘이 없으면 404 반환
            raise HTTPException(status_code=404, detail="Favicon not found")
    return FileResponse(favicon_path)

# 라우트 정의
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """루트 경로 - 크롤링 페이지로 리디렉션"""
    return templates.TemplateResponse("cradcrawl.html", {"request": request})

@app.get("/api/status")
async def get_status():
    """현재 크롤링 상태 조회"""
    return {
        "status": "success",
        "data": crawling_state.get_status()
    }

@app.get("/api/results")
async def get_results():
    """현재까지 수집된 결과 조회"""
    # 데이터 구조 수정: bid_info 필드에 필요한 정보 포함
    formatted_results = []
    for item in crawling_state.results:
        # 기본 정보 구성
        bid_info = {
            'title': item.get('title') or item.get('bid_title', ''),
            'number': item.get('bid_number', ''),
            'agency': item.get('department') or item.get('organization', ''),
            'date': item.get('date_start') or item.get('start_date', ''),
            'end_date': item.get('date_end') or item.get('deadline', ''),
            'status': item.get('status', '공고중')
        }
        
        # 항목 포맷팅
        formatted_item = {
            'id': item.get('id', ''),
            'title': item.get('title') or item.get('bid_title', ''),
            'bid_number': item.get('bid_number', ''),
            'department': item.get('department') or item.get('organization', ''),
            'bid_info': bid_info,
            'details': {
                'contract_method': item.get('contract_method', ''),
                'estimated_price': item.get('estimated_price', ''),
                'qualification': item.get('qualification', ''),
                'bid_type': item.get('bid_type', ''),
                'contract_period': item.get('contract_period', ''),
                'delivery_location': item.get('delivery_location', ''),
                'notice': item.get('notice', '')
            },
            'file_attachments': item.get('file_attachments', []),
            'detail_url': item.get('detail_url', '')
        }
        
        formatted_results.append(formatted_item)
    
    return {
        "status": "success",
        "results": formatted_results
    }

@app.post("/api/start")
async def start_crawling(request: Dict[str, Any], background_tasks: BackgroundTasks):
    """크롤링 시작"""
    # 이미 실행 중인 경우
    if crawling_state.is_running:
        return {"status": "error", "message": "이미 크롤링이 실행 중입니다."}
    
    # 요청 데이터 추출
    keywords = request.get("keywords", [])
    if not keywords:
        return {"status": "error", "message": "키워드를 하나 이상 입력해주세요."}
    
    headless = request.get("headless", True)
    start_date = request.get("startDate")
    end_date = request.get("endDate")
    max_items = request.get("maxItems", 10000)  # 추가: 최대 항목 수 파라미터
    
    # 크롤링 상태 초기화
    crawling_state.is_running = True
    crawling_state.results = []
    crawling_state.processed_keywords = []
    crawling_state.total_keywords = len(keywords)
    crawling_state.start_time = datetime.now()
    crawling_state.end_time = None
    
    # 상태 업데이트 브로드캐스트
    await crawling_state.websocket_manager.send_status(crawling_state.get_status())
    await crawling_state.websocket_manager.send_log(f"키워드 {len(keywords)}개로 크롤링을 시작합니다.")
    
    # 백그라운드에서 크롤링 실행
    background_tasks.add_task(
        run_crawling,
        keywords=keywords,
        headless=headless,
        start_date=start_date,
        end_date=end_date,
        max_items=max_items  # 추가: 최대 항목 수 전달
    )
    
    return {
        "status": "success",
        "message": "크롤링이 시작되었습니다.",
        "data": crawling_state.get_status()
    }

@app.post("/api/stop")
async def stop_crawling():
    """크롤링 중지"""
    if not crawling_state.is_running:
        return {"status": "error", "message": "실행 중인 크롤링이 없습니다."}
    
    try:
        await crawling_state.websocket_manager.send_log("크롤링 중지 요청이 접수되었습니다.")
        
        # 진행 중인 크롤러 종료
        if crawling_state.crawler:
            await crawling_state.crawler.close()
            crawling_state.crawler = None
        
        # 상태 업데이트
        crawling_state.is_running = False
        crawling_state.end_time = datetime.now()
        
        # 결과 저장
        saved_path = crawling_state.save_results()
        
        # 상태 업데이트 브로드캐스트
        await crawling_state.websocket_manager.send_status(crawling_state.get_status())
        await crawling_state.websocket_manager.send_log(f"크롤링이 중지되었습니다. 결과가 저장되었습니다: {saved_path}", "info")
        
        return {
            "status": "success",
            "message": "크롤링이 중지되었습니다.",
            "data": crawling_state.get_status()
        }
    except Exception as e:
        logger.error(f"크롤링 중지 중 오류: {str(e)}")
        return {
            "status": "error",
            "message": f"크롤링 중지 중 오류가 발생했습니다: {str(e)}"
        }

@app.get("/api/download")
async def download_results():
    """결과 다운로드 (엑셀 파일)"""
    if not crawling_state.results:
        return {"status": "error", "message": "다운로드할 결과가 없습니다."}
    
    try:
        # 포맷팅된 결과 데이터 생성
        formatted_results = []
        for item in crawling_state.results:
            # 기본 정보 구성
            bid_info = {
                'title': item.get('title') or item.get('bid_title', ''),
                'number': item.get('bid_number', ''),
                'agency': item.get('department') or item.get('organization', ''),
                'date': item.get('date_start') or item.get('start_date', ''),
                'end_date': item.get('date_end') or item.get('deadline', ''),
                'status': item.get('status', '공고중')
            }
            
            # 엑셀용 평탄화된 데이터 구조
            flat_item = {
                '번호': item.get('id', ''),
                '공고명': item.get('title') or item.get('bid_title', ''),
                '공고번호': item.get('bid_number', ''),
                '공고기관': item.get('department') or item.get('organization', ''),
                '공고일': bid_info['date'],
                '마감일': bid_info['end_date'],
                '상태': bid_info['status'],
                '계약방식': item.get('contract_method', ''),
                '추정가격': item.get('estimated_price', ''),
                '참가자격': item.get('qualification', ''),
                '입찰방식': item.get('bid_type', ''),
                '계약기간': item.get('contract_period', ''),
                '납품장소': item.get('delivery_location', ''),
                '상세URL': item.get('detail_url', '')
            }
            
            formatted_results.append(flat_item)
        
        # 데이터프레임 생성
        df = pd.DataFrame(formatted_results)
        
        # 엑셀 파일 생성
        output = BytesIO()
        df.to_excel(output, index=False)
        output.seek(0)
        
        # 파일명 설정
        filename = f"crawling_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        # 스트리밍 응답으로 파일 전송
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logger.error(f"결과 다운로드 중 오류: {str(e)}")
        return {"status": "error", "message": f"결과 다운로드 중 오류: {str(e)}"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """웹소켓 엔드포인트"""
    await crawling_state.websocket_manager.connect(websocket)
    
    # 연결 직후 현재 상태 전송
    await websocket.send_json({
        "type": "status",
        "data": crawling_state.get_status()
    })
    
    # 현재 결과가 있는 경우 전송
    if crawling_state.results:
        await websocket.send_json({
            "type": "result",
            "data": {
                "results": crawling_state.results
            }
        })
    
    try:
        # 클라이언트가 연결을 유지하는 동안 메시지 수신
        while True:
            data = await websocket.receive_text()
            # 클라이언트 메시지 처리 (필요시)
            try:
                message = json.loads(data)
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except json.JSONDecodeError:
                pass
    except Exception as e:
        logger.debug(f"웹소켓 통신 중 오류 (무시): {str(e)}")
    finally:
        # 연결 종료 시 관리자에서 제거
        crawling_state.websocket_manager.disconnect(websocket)

# 크롤링 실행 함수 (백그라운드 태스크)
async def run_crawling(keywords: List[str], headless: bool = True, start_date: Optional[str] = None, end_date: Optional[str] = None, max_items: int = 10000):
    """크롤링 실행 (백그라운드 태스크)"""
    try:
        # 로그 메시지 전송
        await crawling_state.websocket_manager.send_log("크롤러 초기화 중...")
        
        # 크롤러 초기화
        crawler = G2BCrawler(headless=headless)
        crawling_state.crawler = crawler
        
        # 크롤러 초기화
        if not await crawler.initialize():
            crawling_state.is_running = False
            await crawling_state.websocket_manager.send_error("크롤러 초기화 실패", stopped=True)
            return
        
        await crawling_state.websocket_manager.send_log("크롤러 초기화 완료, 메인 페이지로 이동 중...")
        
        # 메인 페이지로 이동
        if not await crawler.navigate_to_main():
            crawling_state.is_running = False
            await crawling_state.websocket_manager.send_error("메인 페이지 이동 실패", stopped=True)
            await crawler.close()
            return
        
        # 입찰공고 페이지로 이동
        await crawling_state.websocket_manager.send_log("입찰공고 목록 페이지로 이동 중...")
        if not await crawler.navigate_to_bid_list():
            crawling_state.is_running = False
            await crawling_state.websocket_manager.send_error("입찰공고 목록 페이지 이동 실패", stopped=True)
            await crawler.close()
            return
        
        # 검색 조건 설정
        await crawling_state.websocket_manager.send_log("검색 조건 설정 중...")
        if not await crawler.setup_search_conditions():
            await crawling_state.websocket_manager.send_log("검색 조건 설정 중 오류 발생 (무시하고 계속 진행)", "warning")
        
        # 결과 저장 경로 설정
        save_path = str(RESULTS_DIR)
        
        # 키워드 크롤링 수행
        await crawling_state.websocket_manager.send_log(f"검색 시작: {len(keywords)}개 키워드")
        
        # 중간 상태 업데이트 함수
        async def progress_callback(processed_kw, total_kw, current_results):
            # 처리된 키워드 업데이트
            crawling_state.processed_keywords = processed_kw
            
            # 결과 업데이트
            if current_results:
                # 결과 추가
                for result in current_results:
                    if result not in crawling_state.results:
                        crawling_state.results.append(result)
                
                # 상태 업데이트 전송
                await crawling_state.websocket_manager.send_status(crawling_state.get_status())
                await crawling_state.websocket_manager.send_results(crawling_state.results)
            
            # 진행 상황 로그
            progress = round((len(processed_kw) / total_kw) * 100, 1)
            await crawling_state.websocket_manager.send_log(f"진행 상황: {len(processed_kw)}/{total_kw} ({progress}%)")
        
        # 키워드별 크롤링 수행
        for idx, keyword in enumerate(keywords):
            # 크롤링 중지 요청 확인
            if not crawling_state.is_running:
                await crawling_state.websocket_manager.send_log("크롤링 중지 요청으로 작업을 종료합니다.")
                break
            
            # 키워드 로그
            await crawling_state.websocket_manager.send_log(f"키워드 검색 중 ({idx+1}/{len(keywords)}): '{keyword}'")
            
            try:
                # 키워드 검색 수행
                search_success = await crawler.search_keyword(keyword)
                
                if search_success:
                    # 검색 결과 추출
                    keyword_results = await crawler.extract_search_results(max_items=max_items)
                else:
                    keyword_results = []
                
                # 결과 처리
                if keyword_results:
                    result_count = len(keyword_results)
                    await crawling_state.websocket_manager.send_log(f"키워드 '{keyword}' 검색 결과: {result_count}건")
                    
                    # 상세 페이지 정보 추출 (모든 항목 처리)
                    detailed_items = []
                    await crawling_state.websocket_manager.send_log(f"상세 정보 추출 시작: {result_count}개 항목")
                    
                    for idx, item in enumerate(keyword_results):
                        if not crawling_state.is_running:
                            break
                            
                        try:
                            await crawling_state.websocket_manager.send_log(f"항목 {idx+1}/{result_count} 상세 정보 추출 중: {item['title']}")
                            
                            # 상세 페이지 처리
                            detail_data = await crawler.process_detail_page(item)
                            
                            if detail_data:
                                # 상세 정보 병합
                                item.update(detail_data)
                                await crawling_state.websocket_manager.send_log(f"항목 {idx+1} 상세 정보 추출 성공", "success")
                            else:
                                await crawling_state.websocket_manager.send_log(f"항목 {idx+1} 상세 정보 추출 실패", "warning")
                            
                            detailed_items.append(item)
                            
                        except Exception as detail_err:
                            await crawling_state.websocket_manager.send_log(f"항목 {idx+1} 상세 정보 추출 오류: {str(detail_err)}", "error")
                            detailed_items.append(item)  # 기본 정보만 추가
                    
                    await crawling_state.websocket_manager.send_log(f"상세 정보 추출 완료: {len(detailed_items)}개 항목")
                    
                    # 결과를 전체 결과에 추가
                    for result in detailed_items:
                        if result not in crawling_state.results:
                            crawling_state.results.append(result)
                    
                    # 현재까지의 처리 키워드 업데이트
                    if keyword not in crawling_state.processed_keywords:
                        crawling_state.processed_keywords.append(keyword)
                    
                    # 상태 및 결과 업데이트 브로드캐스트
                    await crawling_state.websocket_manager.send_status(crawling_state.get_status())
                    await crawling_state.websocket_manager.send_results(crawling_state.results)
                else:
                    await crawling_state.websocket_manager.send_log(f"키워드 '{keyword}'에 대한 검색 결과가 없습니다.")
                    # 처리된 키워드로 추가
                    if keyword not in crawling_state.processed_keywords:
                        crawling_state.processed_keywords.append(keyword)
                    
                    # 상태 업데이트 브로드캐스트
                    await crawling_state.websocket_manager.send_status(crawling_state.get_status())
            except Exception as e:
                logger.error(f"키워드 '{keyword}' 처리 중 오류: {str(e)}")
                await crawling_state.websocket_manager.send_log(f"키워드 '{keyword}' 처리 중 오류: {str(e)}", "error")
                
                # 오류가 발생해도 계속 진행
                continue
        
        # 크롤링 종료
        await crawling_state.websocket_manager.send_log("모든 키워드 처리 완료")
        
        # 결과 저장
        if crawling_state.results:
            saved_path = crawling_state.save_results()
            await crawling_state.websocket_manager.send_log(f"결과 저장 완료: {saved_path} ({len(crawling_state.results)}건)", "success")
        else:
            await crawling_state.websocket_manager.send_log("저장할 결과가 없습니다.", "warning")
        
    except Exception as e:
        logger.error(f"크롤링 실행 중 오류: {str(e)}")
        await crawling_state.websocket_manager.send_error(f"크롤링 실행 중 오류: {str(e)}", stopped=True)
    finally:
        # 크롤러 종료
        if crawling_state.crawler:
            await crawling_state.crawler.close()
            crawling_state.crawler = None
        
        # 상태 업데이트
        crawling_state.is_running = False
        crawling_state.end_time = datetime.now()
        
        # 최종 상태 업데이트 브로드캐스트
        await crawling_state.websocket_manager.send_status(crawling_state.get_status())
        await crawling_state.websocket_manager.send_log("크롤링 작업이 완료되었습니다.")

# 애플리케이션 시작 이벤트
@app.on_event("startup")
async def startup_event():
    logger.info("=== 나라장터 크롤링 애플리케이션 시작 ===")
    # 결과 디렉토리 생성
    RESULTS_DIR.mkdir(exist_ok=True)

# 애플리케이션 종료 이벤트
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("=== 나라장터 크롤링 애플리케이션 종료 ===")
    # 실행 중인 크롤러가 있으면 종료
    if crawling_state.crawler:
        await crawling_state.crawler.close()

# 직접 실행 시 서버 시작
if __name__ == "__main__":
    import argparse
    
    # 명령줄 인수 파싱
    parser = argparse.ArgumentParser(description="나라장터 크롤링 서버")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="서버 호스트 (기본값: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="서버 포트 (기본값: 8000)")
    parser.add_argument("--reload", action="store_true", help="코드 변경 시 서버 자동 재시작")
    parser.add_argument("--debug", action="store_true", help="디버그 모드 활성화")
    
    args = parser.parse_args()
    
    # 디버그 모드 설정
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 리로드 설정
    reload_dirs = [str(ROOT_DIR)]  # 루트 디렉토리
    reload_includes = ["*.py", "backend/*.py", "backend/**/*.py"]  # Python 파일만 감시
    reload_excludes = []  # 제외할 패턴이 있다면 추가
    
    # Uvicorn 서버 실행
    uvicorn.run(
        "app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_dirs=reload_dirs if args.reload else None,
        reload_includes=reload_includes if args.reload else None,
        reload_excludes=reload_excludes if args.reload else None,
        log_level="debug" if args.debug else "info"
    ) 