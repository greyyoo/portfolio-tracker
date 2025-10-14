#!/bin/bash
# Streamlit을 네트워크에서 접속 가능하도록 실행

# 현재 MacBook의 로컬 IP 주소 확인
LOCAL_IP=$(ipconfig getifaddr en0)

echo "================================"
echo "Streamlit 앱 시작 중..."
echo "================================"
echo ""
echo "로컬 접속: http://localhost:8501"
echo "폰에서 접속: http://${LOCAL_IP}:8501"
echo ""
echo "같은 WiFi에 연결된 폰에서 위 주소로 접속하세요!"
echo "================================"
echo ""

# Streamlit 실행 (네트워크 접속 허용)
cd /Users/greyyoo/Desktop/trading
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
