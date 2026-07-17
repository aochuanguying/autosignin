#!/bin/bash
# DeepSeek 模型大上下文压力测试
API_URL="https://ai.fssc.top/v1/chat/completions"
API_KEY="LqgltIIdlFVQFdi5EMa98HtRVXzq6KGA"
MODEL="deepseek"

generate_body_by_size() {
  local target_kb=$1
  local target_bytes=$((target_kb * 1024))
  local msg_count=$((target_bytes / 500))
  if [ $msg_count -lt 10 ]; then msg_count=10; fi
  
  local filler="Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur."
  
  local messages="["
  messages+='{"role":"system","content":"You are a helpful assistant. Always be concise."},'
  
  for ((i=1; i<msg_count; i++)); do
    if (( i % 2 == 1 )); then
      messages+="{\"role\":\"user\",\"content\":\"Message $i: $filler Please explain more about topic $i.\"},"
    else
      messages+="{\"role\":\"assistant\",\"content\":\"Response $i: $filler Here are the details about topic $i.\"},"
    fi
  done
  
  messages+='{"role":"user","content":"Please summarize everything briefly."}'
  messages+="]"
  
  echo "{\"model\":\"$MODEL\",\"messages\":$messages,\"stream\":false,\"max_tokens\":50}"
}

echo "============================================"
echo "DeepSeek 大上下文压力测试"
echo "============================================"
echo ""
printf "%-12s %-12s %-12s %-10s\n" "目标KB" "实际KB" "响应时间" "状态"
printf "%-12s %-12s %-12s %-10s\n" "------" "------" "--------" "------"

for target_kb in 50 100 200 300 400 500 600 800; do
  body=$(generate_body_by_size $target_kb)
  actual_bytes=$(echo -n "$body" | wc -c)
  actual_kb=$((actual_bytes / 1024))
  
  # 检查是否超过 ARG_MAX
  if [ $actual_bytes -gt 200000 ]; then
    # 用临时文件方式发送
    tmpfile=$(mktemp)
    echo -n "$body" > "$tmpfile"
    response=$(curl -s -w "\n%{http_code}\n%{time_total}" \
      -X POST "$API_URL" \
      -H "Authorization: Bearer $API_KEY" \
      -H "Content-Type: application/json" \
      -d @"$tmpfile" \
      --max-time 130)
    rm -f "$tmpfile"
  else
    response=$(curl -s -w "\n%{http_code}\n%{time_total}" \
      -X POST "$API_URL" \
      -H "Authorization: Bearer $API_KEY" \
      -H "Content-Type: application/json" \
      -d "$body" \
      --max-time 130)
  fi
  
  http_code=$(echo "$response" | tail -2 | head -1)
  time_total=$(echo "$response" | tail -1)
  time_ms=$(echo "$time_total" | awk '{printf "%.0f", $1*1000}')
  
  if [ "$http_code" = "200" ]; then
    status="✅ OK"
  elif [ "$http_code" = "000" ]; then
    status="⏱ TIMEOUT"
    time_ms=">${time_ms}"
  else
    err_msg=$(echo "$response" | head -1 | grep -oE '"message":"[^"]+"' | head -1)
    status="❌ $http_code"
  fi
  
  printf "%-12s %-12s %-12s %-10s\n" "${target_kb}KB" "${actual_kb}KB" "${time_ms}ms" "$status"
  
  sleep 3
done

echo ""
echo "============================================"
