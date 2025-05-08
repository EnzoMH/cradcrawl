/**
 * 나라장터 크롤링 애플리케이션 JavaScript
 */
document.addEventListener('DOMContentLoaded', function() {
    // 상태 관리
    const state = {
        isRunning: false,
        isConnected: false,
        socket: null,
        results: [],
        processedKeywords: [],
        totalKeywords: 0,
        startTime: null,
        endTime: null
    };

    // 요소 선택
    const elements = {
        // 폼 요소
        form: document.getElementById('search-form'),
        keywordsInput: document.getElementById('keywords'),
        startDateInput: document.getElementById('start-date'),
        endDateInput: document.getElementById('end-date'),
        headlessModeCheckbox: document.getElementById('headless-mode'),
        
        // 버튼
        startButton: document.getElementById('btn-start'),
        stopButton: document.getElementById('btn-stop'),
        refreshButton: document.getElementById('btn-refresh'),
        downloadButton: document.getElementById('btn-download'),
        
        // 상태 표시
        connectionStatus: document.getElementById('connection-status'),
        statusBadge: document.getElementById('status-badge'),
        progressBar: document.getElementById('progress-bar'),
        processedKeywords: document.getElementById('processed-keywords'),
        totalResults: document.getElementById('total-results'),
        logContainer: document.getElementById('log-container'),
        
        // 결과 표시
        resultTableBody: document.getElementById('result-table-body'),
        
        // 모달
        detailModal: new bootstrap.Modal(document.getElementById('detail-modal')),
        detailModalTitle: document.getElementById('detail-modal-title'),
        detailModalBody: document.getElementById('detail-modal-body')
    };

    // 웹소켓 연결 설정
    function setupWebSocket() {
        // 웹소켓 URL 결정
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        // 웹소켓 객체 생성
        state.socket = new WebSocket(wsUrl);
        
        // 이벤트 핸들러 설정
        state.socket.onopen = handleSocketOpen;
        state.socket.onmessage = handleSocketMessage;
        state.socket.onclose = handleSocketClose;
        state.socket.onerror = handleSocketError;
        
        // 연결 상태 업데이트
        updateConnectionStatus('connecting');
        addLog('WebSocket 연결 시도 중...');
    }

    // 웹소켓 이벤트 핸들러
    function handleSocketOpen() {
        state.isConnected = true;
        updateConnectionStatus('connected');
        addLog('WebSocket 연결됨');
        
        // 연결 후 현재 상태 요청
        fetchCrawlingStatus();
    }

    function handleSocketMessage(event) {
        try {
            const message = JSON.parse(event.data);
            
            switch(message.type) {
                case 'status':
                    handleStatusUpdate(message.data);
                    break;
                case 'log':
                    handleLogMessage(message.data);
                    break;
                case 'result':
                    handleResultUpdate(message.data);
                    break;
                case 'error':
                    handleErrorMessage(message.data);
                    break;
                default:
                    console.log('Unknown message type:', message.type);
            }
        } catch (error) {
            console.error('Error parsing WebSocket message:', error);
            addLog(`메시지 처리 오류: ${error.message}`, 'error');
        }
    }

    function handleSocketClose(event) {
        state.isConnected = false;
        updateConnectionStatus('disconnected');
        
        if (event.wasClean) {
            addLog(`WebSocket 연결 종료: 코드=${event.code}, 이유=${event.reason}`);
        } else {
            addLog('WebSocket 연결이 비정상적으로 종료되었습니다. 재연결 중...', 'error');
            
            // 5초 후 재연결 시도
            setTimeout(setupWebSocket, 5000);
        }
    }

    function handleSocketError(error) {
        console.error('WebSocket 오류:', error);
        addLog('WebSocket 오류가 발생했습니다. 콘솔을 확인하세요.', 'error');
    }

    // 메시지 핸들러
    function handleStatusUpdate(data) {
        // 크롤링 상태 업데이트
        state.isRunning = data.is_running || false;
        
        // 진행률 계산 및 표시
        let progress = 0;
        if (data.total_keywords && data.total_keywords > 0) {
            state.totalKeywords = data.total_keywords;
            progress = Math.round((data.processed_keywords.length / data.total_keywords) * 100);
        }
        
        // UI 업데이트
        updateProgressBar(progress);
        updateStatusBadge(state.isRunning ? 'running' : 'stopped');
        updateButtonState(state.isRunning);
        
        // 처리된 키워드 표시
        if (data.processed_keywords) {
            state.processedKeywords = data.processed_keywords;
            updateProcessedKeywords(data.processed_keywords);
        }
        
        // 결과 개수 표시
        if (data.total_items !== undefined) {
            updateTotalResults(data.total_items);
        }
        
        // 시작/종료 시간 업데이트
        if (data.start_time) {
            state.startTime = new Date(data.start_time);
        }
        if (data.end_time) {
            state.endTime = new Date(data.end_time);
        }
    }

    function handleLogMessage(data) {
        addLog(data.message, data.level || 'info');
    }

    function handleResultUpdate(data) {
        // 결과 데이터 업데이트
        if (data.results) {
            state.results = data.results;
            updateResultTable(data.results);
        }
    }

    function handleErrorMessage(data) {
        addLog(data.message, 'error');
        
        // 오류로 인해 크롤링이 중지된 경우
        if (data.stopped) {
            state.isRunning = false;
            updateStatusBadge('error');
            updateButtonState(false);
        }
    }

    // UI 업데이트 함수
    function updateConnectionStatus(status) {
        elements.connectionStatus.className = 'connection-status';
        elements.connectionStatus.classList.add(`connection-${status}`);
        
        switch(status) {
            case 'connected':
                elements.connectionStatus.textContent = '연결됨';
                break;
            case 'disconnected':
                elements.connectionStatus.textContent = '연결 끊김';
                break;
            case 'connecting':
                elements.connectionStatus.textContent = '연결 중...';
                break;
        }
    }

    function updateStatusBadge(status) {
        elements.statusBadge.className = 'badge';
        
        switch(status) {
            case 'running':
                elements.statusBadge.classList.add('bg-success');
                elements.statusBadge.textContent = '크롤링 중';
                break;
            case 'stopped':
                elements.statusBadge.classList.add('bg-secondary');
                elements.statusBadge.textContent = '대기 중';
                break;
            case 'error':
                elements.statusBadge.classList.add('bg-danger');
                elements.statusBadge.textContent = '오류 발생';
                break;
        }
    }

    function updateProgressBar(progress) {
        elements.progressBar.style.width = `${progress}%`;
        elements.progressBar.textContent = `${progress}%`;
        elements.progressBar.setAttribute('aria-valuenow', progress);
    }

    function updateButtonState(isRunning) {
        elements.startButton.disabled = isRunning;
        elements.stopButton.disabled = !isRunning;
        
        // 폼 요소 비활성화/활성화
        elements.keywordsInput.disabled = isRunning;
        elements.startDateInput.disabled = isRunning;
        elements.endDateInput.disabled = isRunning;
        elements.headlessModeCheckbox.disabled = isRunning;
    }

    function updateProcessedKeywords(keywords) {
        if (keywords && keywords.length > 0) {
            const content = keywords.map(kw => `<span class="keyword-badge">${kw}</span>`).join('');
            elements.processedKeywords.innerHTML = content;
        } else {
            elements.processedKeywords.textContent = '-';
        }
    }

    function updateTotalResults(totalItems) {
        elements.totalResults.textContent = totalItems !== undefined ? `${totalItems} 건` : '-';
    }

    function updateResultTable(results) {
        if (results && results.length > 0) {
            const rows = results.map((item, index) => {
                // 입찰 정보 추출
                const bidInfo = item.bid_info || {};
                
                // 상태 클래스 결정
                let statusClass = '';
                switch(bidInfo.status) {
                    case '입찰':
                        statusClass = 'badge bg-primary';
                        break;
                    case '개찰':
                        statusClass = 'badge bg-success';
                        break;
                    case '마감':
                        statusClass = 'badge bg-danger';
                        break;
                    default:
                        statusClass = 'badge bg-secondary';
                }
                
                return `
                    <tr data-index="${index}" class="result-row">
                        <td>${index + 1}</td>
                        <td>
                            <a href="#" class="detail-link" data-index="${index}">${bidInfo.title || '제목 없음'}</a>
                        </td>
                        <td>${bidInfo.agency || '-'}</td>
                        <td>${bidInfo.date || '-'}</td>
                        <td>${bidInfo.end_date || '-'}</td>
                        <td><span class="${statusClass}">${bidInfo.status || '알 수 없음'}</span></td>
                    </tr>
                `;
            }).join('');
            
            elements.resultTableBody.innerHTML = rows;
            
            // 상세 정보 링크에 이벤트 리스너 추가
            document.querySelectorAll('.detail-link').forEach(link => {
                link.addEventListener('click', showDetailModal);
            });
        } else {
            elements.resultTableBody.innerHTML = '<tr><td colspan="6" class="text-center">아직 크롤링된 결과가 없습니다.</td></tr>';
        }
    }

    function addLog(message, level = 'info') {
        const timestamp = new Date().toLocaleTimeString();
        const logElement = document.createElement('div');
        logElement.className = 'log-message';
        
        // 로그 레벨에 따른 스타일 적용
        switch(level) {
            case 'error':
                logElement.classList.add('text-danger');
                break;
            case 'warning':
                logElement.classList.add('text-warning');
                break;
            case 'success':
                logElement.classList.add('text-success');
                break;
        }
        
        logElement.textContent = `[${timestamp}] ${message}`;
        elements.logContainer.appendChild(logElement);
        
        // 스크롤을 최하단으로 이동
        elements.logContainer.scrollTop = elements.logContainer.scrollHeight;
    }

    // 액션 함수
    function startCrawling() {
        if (!validateForm()) {
            return;
        }
        
        // 키워드 추출
        const keywordsText = elements.keywordsInput.value.trim();
        const keywords = keywordsText.split('\n')
            .map(k => k.trim())
            .filter(k => k.length > 0);
        
        if (keywords.length === 0) {
            alert('최소 하나 이상의 키워드를 입력해주세요.');
            return;
        }
        
        // 날짜 값 가져오기
        const startDate = elements.startDateInput.value;
        const endDate = elements.endDateInput.value;
        
        // 헤드리스 모드 설정
        const headless = elements.headlessModeCheckbox.checked;
        
        // 요청 데이터 구성
        const requestData = {
            keywords: keywords,
            startDate: startDate,
            endDate: endDate,
            headless: headless,
            clientInfo: {
                userAgent: navigator.userAgent,
                timestamp: new Date().toISOString()
            }
        };
        
        // 서버에 요청 보내기
        fetch('/api/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                addLog('크롤링 시작됨');
                state.isRunning = true;
                updateButtonState(true);
                updateStatusBadge('running');
            } else {
                addLog(`크롤링 시작 실패: ${data.message}`, 'error');
            }
        })
        .catch(error => {
            console.error('크롤링 시작 오류:', error);
            addLog(`크롤링 시작 중 오류 발생: ${error.message}`, 'error');
        });
    }

    function stopCrawling() {
        fetch('/api/stop', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                addLog('크롤링 중지 요청됨');
            } else {
                addLog(`크롤링 중지 실패: ${data.message}`, 'error');
            }
        })
        .catch(error => {
            console.error('크롤링 중지 오류:', error);
            addLog(`크롤링 중지 중 오류 발생: ${error.message}`, 'error');
        });
    }

    function fetchCrawlingStatus() {
        fetch('/api/status')
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                handleStatusUpdate(data.data);
                
                // 결과가 있다면 업데이트
                if (data.results) {
                    handleResultUpdate({results: data.results});
                }
            } else {
                addLog(`상태 조회 실패: ${data.message}`, 'warning');
            }
        })
        .catch(error => {
            console.error('상태 조회 오류:', error);
            addLog(`상태 조회 중 오류 발생: ${error.message}`, 'error');
        });
    }

    function fetchCrawlingResults() {
        fetch('/api/crawl-results/')
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                handleResultUpdate({results: data.results});
                updateTotalResults(data.results.length);
                addLog(`${data.results.length}개의 결과를 불러왔습니다.`);
            } else {
                addLog(`결과 조회 실패: ${data.message}`, 'warning');
            }
        })
        .catch(error => {
            console.error('결과 조회 오류:', error);
            addLog(`결과 조회 중 오류 발생: ${error.message}`, 'error');
        });
    }

    function downloadResults() {
        window.location.href = '/api/results/download';
    }

    // 유틸리티 함수
    function validateForm() {
        const keywordsText = elements.keywordsInput.value.trim();
        if (!keywordsText) {
            alert('검색 키워드를 입력해주세요.');
            elements.keywordsInput.focus();
            return false;
        }
        return true;
    }

    function showDetailModal(event) {
        event.preventDefault();
        
        const index = parseInt(event.target.getAttribute('data-index'));
        const result = state.results[index];
        
        if (!result) {
            return;
        }
        
        // 기본 정보
        const bidInfo = result.bid_info || {};
        
        // 상세 정보
        const details = result.details || {};
        
        // 모달 제목 설정
        elements.detailModalTitle.textContent = result.title || bidInfo.title || '상세 정보';
        
        // 계약 정보 (process_detail_page에서 추출한 정보)
        const contractMethod = result.contract_method || details.contract_method || '-';
        const estimatedPrice = result.estimated_price || details.estimated_price || '-';
        const qualification = result.qualification || details.qualification || '-';
        const bidType = result.bid_type || details.bid_type || '-';
        const contractPeriod = result.contract_period || details.contract_period || '-';
        const deliveryLocation = result.delivery_location || details.delivery_location || '-';
        
        // 파일 첨부 정보
        const fileAttachments = result.file_attachments || [];
        
        // 상세 내용 구성
        const content = `
            <div class="mb-4">
                <h6 class="fw-bold">기본 정보</h6>
                <table class="table table-bordered">
                    <tr>
                        <th style="width: 30%">공고번호</th>
                        <td>${result.bid_number || bidInfo.number || '-'}</td>
                    </tr>
                    <tr>
                        <th>공고기관</th>
                        <td>${result.department || bidInfo.agency || '-'}</td>
                    </tr>
                    <tr>
                        <th>공고일자</th>
                        <td>${bidInfo.date || '-'}</td>
                    </tr>
                    <tr>
                        <th>마감일자</th>
                        <td>${result.deadline || bidInfo.end_date || '-'}</td>
                    </tr>
                    <tr>
                        <th>계약방식</th>
                        <td>${contractMethod}</td>
                    </tr>
                    <tr>
                        <th>입찰방식</th>
                        <td>${bidType}</td>
                    </tr>
                </table>
            </div>
            
            <div class="mb-4">
                <h6 class="fw-bold">계약 정보</h6>
                <table class="table table-bordered">
                    <tr>
                        <th style="width: 30%">추정가격</th>
                        <td>${estimatedPrice}</td>
                    </tr>
                    <tr>
                        <th>계약기간</th>
                        <td>${contractPeriod}</td>
                    </tr>
                    <tr>
                        <th>납품장소</th>
                        <td>${deliveryLocation}</td>
                    </tr>
                </table>
            </div>
            
            <div class="mb-4">
                <h6 class="fw-bold">입찰 참가자격</h6>
                <div class="border rounded p-3 bg-light">
                    ${qualification ? `<p>${qualification}</p>` : '<p class="text-muted">내용 없음</p>'}
                </div>
            </div>
            
            ${details.notice ? `
                <div class="mb-4">
                    <h6 class="fw-bold">공고 내용</h6>
                    <div class="border rounded p-3 bg-light">
                        <p>${details.notice}</p>
                    </div>
                </div>
            ` : ''}
            
            ${fileAttachments && fileAttachments.length > 0 ? `
                <div>
                    <h6 class="fw-bold">첨부파일</h6>
                    <ul class="list-group">
                        ${fileAttachments.map(file => `
                            <li class="list-group-item d-flex justify-content-between align-items-center">
                                <span>${file || '파일명 없음'}</span>
                            </li>
                        `).join('')}
                    </ul>
                </div>
            ` : ''}
        `;
        
        elements.detailModalBody.innerHTML = content;
        elements.detailModal.show();
    }

    // 초기화 함수
    function initDatePickers() {
        // 날짜 선택기 초기화
        const dateOptions = {
            locale: 'ko',
            dateFormat: 'Y-m-d',
            allowInput: true,
            altInput: true,
            altFormat: 'Y년 m월 d일',
            disableMobile: true
        };
        
        flatpickr(elements.startDateInput, dateOptions);
        flatpickr(elements.endDateInput, dateOptions);
    }

    function initEventListeners() {
        // 버튼 이벤트 리스너
        elements.startButton.addEventListener('click', startCrawling);
        elements.stopButton.addEventListener('click', stopCrawling);
        elements.refreshButton.addEventListener('click', fetchCrawlingResults);
        elements.downloadButton.addEventListener('click', downloadResults);
        
        // 폼 제출 방지
        elements.form.addEventListener('submit', function(event) {
            event.preventDefault();
            startCrawling();
        });
    }

    // 애플리케이션 초기화
    function init() {
        // 날짜 선택기 초기화
        initDatePickers();
        
        // 이벤트 리스너 설정
        initEventListeners();
        
        // 웹소켓 연결
        setupWebSocket();
        
        // 초기 로그 메시지
        addLog('애플리케이션 초기화 완료');
    }

    // 애플리케이션 시작
    init();
}); 