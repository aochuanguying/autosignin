# HiGPT Gateway 代码优化建议

以下是 `/opt/higpt-gateway/app/src/index.ts` 需要修改的地方：

## 1. Auto-trim 对所有模型生效（不只是 deepseek）

将第 ~175 行附近的 deepseek 专属截断逻辑改为对所有模型生效：

```typescript
// 原来：只对 deepseek 模型截断
// if (upstreamModel.includes('deepseek')) { ... }

// 优化：对所有模型统一截断
let upstreamBody = { ...body, model: upstreamModel };

// DeepSeek 模型自动添加 chat_template_kwargs
if (upstreamModel.includes('deepseek')) {
  if (!upstreamBody.chat_template_kwargs) {
    upstreamBody.chat_template_kwargs = { thinking: false };
  }
}

// 所有模型：检查请求体大小，过大则自动截断历史消息
let bodySize = Buffer.byteLength(JSON.stringify(upstreamBody), 'utf8');
const MAX_BODY_SIZE = (config as any).maxRequestBodyKB
  ? (config as any).maxRequestBodyKB * 1024
  : 400 * 1024; // 默认 400KB

if (bodySize > MAX_BODY_SIZE && Array.isArray(upstreamBody.messages)) {
  const originalCount = upstreamBody.messages.length;
  const systemMessages = upstreamBody.messages.filter((m: any) => m.role === 'system');
  let nonSystemMessages = upstreamBody.messages.filter((m: any) => m.role !== 'system');

  // 从前往后移除最旧的消息，保留最后至少 5 条
  while (nonSystemMessages.length > 5 && bodySize > MAX_BODY_SIZE) {
    nonSystemMessages = nonSystemMessages.slice(1);
    upstreamBody = { ...upstreamBody, messages: [...systemMessages, ...nonSystemMessages] };
    bodySize = Buffer.byteLength(JSON.stringify(upstreamBody), 'utf8');
  }

  const finalCount = systemMessages.length + nonSystemMessages.length;
  logger.warn('auto_trimmed_large_request', {
    originalCount,
    finalCount,
    removedCount: originalCount - finalCount,
    sizeKB: Math.round(bodySize / 1024),
    model: upstreamModel,
  }, getRequestId(req));
}
```

## 2. 拒绝未知模型（避免 401）

在 `resolveModel` 之后、发起请求之前加入：

```typescript
const { upstreamModel, rawMode } = resolveModel(config, String(body.model));

// 拒绝未在别名表中且不是已知上游模型的请求
const knownModels = new Set([
  ...Object.keys(config.modelAliases),
  ...Object.values(config.modelAliases),
]);
const baseModelName = body.model.replace(/-raw$/, '');
if (!knownModels.has(baseModelName) && !knownModels.has(upstreamModel)) {
  sendOpenAIError(res, 400,
    `Unknown model: ${body.model}. Available: ${[...Object.keys(config.modelAliases)].join(', ')}`,
    'invalid_request_error');
  return;
}
```

## 3. config.ts 增加 maxRequestBodyKB 字段

```typescript
export interface GatewayConfig {
  port: number;
  gatewayApiKey: string;
  higpt: {
    baseUrl: string;
    apiKey: string;
    userKey: string;
    proxyUrl?: string;
    timeoutMs: number;
  };
  modelAliases: Record<string, string>;
  maxRequestBodyKB?: number;  // 新增
}
```
