#!/bin/bash
# ============================================
# HiGPT Gateway 上下文大小压力测试
# 目的：找出上游 API 在不同请求体大小下的响应时间和成功率
# 用法：bash benchmark.sh
# ============================================

API_URL="https://ai.fssc.top/v1/chat/completions"
API_KEY="LqgltIIdlFVQFdi5EMa98HtRVXzq6KGA"
MODEL="qwen"

# 生成指定消息条数的请求体
generate_body() {
  local msg_count=$1
  local messages="["
  messages+='{"role":"system","content":"You are a helpful assistant."},'
  
  for ((i=1; i<msg_count; i++)); do
    if (( i % 2 == 1 )); then
      messages+="{\"role\":\"user\",\"content\":\"This is test message number $i. Please provide a detailed response about software engineering best practices, including code quality, testing strategies, deployment pipelines, and monitoring. Also discuss microservices architecture patterns and their trade-offs in production environments.\"},"
    else
      messages+="{\"role\":\"assistant\",\"content\":\"Thank you for your question about software engineering. Here are some key best practices: 1) Code Quality - Use consistent coding standards, implement code reviews, maintain documentation. 2) Testing - Write unit tests, integration tests, and end-to-end tests. Aim for meaningful coverage. 3) Deployment - Use CI/CD pipelines, implement blue-green or canary deployments. 4) Monitoring - Set up alerting, distributed tracing, and centralized logging.\"},"
    fi
  done
  
  # 最后一条用户消息
  messages+='{"role":"user","content":"Summarize the key points from our conversation."}'
  messages+="]"
  
  echo "{\"model\":\"$MODEL\",\"messages\":$messages,\"stream\":false,\"max_tokens\":50}"
}

echo "============================================"
echo "HiGPT Gateway 上下文大小压力测试"
echo "============================================"
echo ""
echo "模型: $MODEL"
echo "API: $API_URL"
echo ""
printf "%-12s %-10s %-12s %-8s\n" "消息条数" "请求体KB" "响应时间ms" "状态"
printf "%-12s %-10s %-12s %-8s\n" "--------" "--------" "----------" "----"

# 测试不同消息数量
for msg_count in 10 30 50 80 100 130 160 200; do
  body=$(generate_body $msg_count)
  body_size=$(echo -n "$body" | wc -c)
  body_kb=$((body_size / 1024))
  
  # 发送请求并计时
  start_time=$(date +%s%N 2>/dev/null || python -c "import time; print(int(time.time()*1000))")
  
  response=$(curl -s -w "\n%{http_code}\n%{time_total}" \
    -X POST "$API_URL" \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: application/json" \
    -d "$body" \
    --max-time 130)
  
  http_code=$(echo "$response" | tail -2 | head -1)
  time_total=$(echo "$response" | tail -1)
  time_ms=$(echo "$time_total" | awk '{printf "%.0f", $1*1000}')
  
  if [ "$http_code" = "200" ]; then
    status="✅ OK"
  elif [ "$http_code" = "000" ]; then
    status="⏱ TIMEOUT"
    time_ms=">${time_ms}"
  else
    status="❌ $http_code"
  fi
  
  printf "%-12s %-10s %-12s %-8s\n" "$msg_count" "${body_kb}KB" "${time_ms}ms" "$status"
  
  # 每次请求间隔 2 秒避免限流
  sleep 2
done

echo ""
echo "============================================"
echo "测试完成"
echo ""
echo "结论参考："
echo "- 如果所有测试都 OK 且响应时间可接受 → maxRequestBodyKB 可以调高"
echo "- 如果某个大小开始超时或报错 → 那个大小就是安全上限"
echo "- 建议设置为安全上限的 80% 作为 maxRequestBodyKB"
echo "============================================"
