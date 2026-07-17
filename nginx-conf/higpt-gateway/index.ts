import express, { Request, Response, NextFunction } from 'express';
import axios, { AxiosError, AxiosRequestConfig } from 'axios';
import { GatewayConfig, loadConfig } from './config';
import { randomUUID } from 'crypto';
import { logger } from './logger';

const JSON_BODY_LIMIT = '10mb'; // 限制最大 10MB，减少 DeepSeek 请求失败

function redact(value: string): string {
  if (!value) return value;
  if (value.length <= 8) return '***';
  return value.slice(0, 4) + '***' + value.slice(-4);
}

function toSafeUrl(raw: string): string {
  try {
    const u = new URL(raw);
    if (u.searchParams.has('user_key')) u.searchParams.set('user_key', '***');
    return u.toString();
  } catch {
    return raw;
  }
}

function sendOpenAIError(res: Response, status: number, message: string, type: string, code?: string): void {
  res.status(status).json({ error: { message, type, code } });
}

function getRequestId(req: Request): string {
  const r = req as any;
  if (typeof r.requestId === 'string' && r.requestId) return r.requestId;
  const id = randomUUID();
  r.requestId = id;
  return id;
}

function toErrorMessage(v: unknown): string {
  if (!v) return '';
  if (typeof v === 'string') return v;
  if (v instanceof Error) return v.message;
  try {
    return JSON.stringify(v);
  } catch {
    return String(v);
  }
}

function toOneLine(s: string): string {
  return String(s || '').replace(/\s+/g, ' ').trim();
}

function toSafeAxiosErrorLog(e: AxiosError): string {
  const anyErr = e as any;
  const code = e.code ? String(e.code) : '';
  const errno = anyErr.errno ? String(anyErr.errno) : '';
  const syscall = anyErr.syscall ? String(anyErr.syscall) : '';
  const address = anyErr.address ? String(anyErr.address) : '';
  const port = anyErr.port ? String(anyErr.port) : '';
  const status = e.response?.status ? String(e.response.status) : '';
  const msg = toOneLine(toErrorMessage(e));
  const parts = [
    code ? `code=${code}` : '',
    errno ? `errno=${errno}` : '',
    syscall ? `syscall=${syscall}` : '',
    address ? `address=${address}` : '',
    port ? `port=${port}` : '',
    status ? `status=${status}` : '',
    msg ? `message=${msg}` : '',
  ].filter(Boolean);
  return parts.join(' ');
}

/**
 * 带重试的 axios 请求
 * @param requestFn 请求函数
 * @param maxRetries 最大重试次数（不含首次请求）
 * @param retryDelayMs 重试间隔（毫秒）
 */
async function axiosWithRetry<T>(
  requestFn: () => Promise<T>,
  maxRetries: number = 2,
  retryDelayMs: number = 500
): Promise<T> {
  let lastError: Error | null = null;
  
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await requestFn();
    } catch (err: any) {
      lastError = err;
      
      // 最后一次重试失败，直接抛出
      if (attempt === maxRetries) {
        throw err;
      }
      
      // 判断是否需要重试：网络错误、超时、5xx 错误
      const shouldRetry = 
        err.code === 'ECONNABORTED' ||
        err.code === 'ECONNRESET' ||
        err.code === 'ETIMEDOUT' ||
        err.code === 'EAI_AGAIN' ||
        (err.response && err.response.status >= 500);
      
      if (!shouldRetry) {
        throw err;
      }
      
      // 等待后重试（指数退避）
      const delay = retryDelayMs * Math.pow(2, attempt);
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }
  
  throw lastError;
}

function assertNonEmpty(value: string, name: string): void {
  if (!value || !value.trim()) {
    throw new Error(`${name} 不能为空`);
  }
}

function validateConfig(config: GatewayConfig): void {
  if (!Number.isFinite(config.port) || config.port <= 0) {
    throw new Error('port 配置无效');
  }

  assertNonEmpty(config.gatewayApiKey, 'gatewayApiKey');
  assertNonEmpty(config.higpt.baseUrl, 'higpt.baseUrl');
  assertNonEmpty(config.higpt.apiKey, 'higpt.apiKey');
  assertNonEmpty(config.higpt.userKey, 'higpt.userKey');

  try {
    new URL(config.higpt.baseUrl);
  } catch {
    throw new Error('higpt.baseUrl 不是合法 URL');
  }

  if (!Number.isFinite(config.higpt.timeoutMs) || config.higpt.timeoutMs <= 0) {
    throw new Error('higpt.timeoutMs 配置无效');
  }

  if (config.modelAliases === null || typeof config.modelAliases !== 'object') {
    throw new Error('modelAliases 配置无效');
  }
}

function requireGatewayAuth(expected: string): express.RequestHandler {
  return (req: Request, res: Response, next: NextFunction) => {
    const raw = req.header('authorization') || '';
    const token = raw.toLowerCase().startsWith('bearer ') ? raw.slice('bearer '.length).trim() : '';

    if (!token || !expected || token !== expected) {
      sendOpenAIError(res, 401, 'Unauthorized', 'authentication_error');
      return;
    }

    next();
  };
}

function buildUpstreamUrl(config: GatewayConfig, pathname: string): string {
  const url = new URL(config.higpt.baseUrl);
  url.pathname = url.pathname.replace(/\/+$/, '') + pathname;
  url.searchParams.set('user_key', config.higpt.userKey);
  return url.toString();
}

/**
 * 解析模型名，返回 { upstreamModel, rawMode }
 * - rawMode=false: 请求标准模式，过滤 reasoning_content（如 "higpt"）
 * - rawMode=true:  请求原始模式，保留全部字段（如 "higpt-raw"）
 *
 * 规则：模型名以 "-raw" 结尾时进入原始模式，剥掉后缀再查别名表
 */
function resolveModel(config: GatewayConfig, model: string): { upstreamModel: string; rawMode: boolean } {
  const RAW_SUFFIX = '-raw';

  const rawMode = model.endsWith(RAW_SUFFIX);
  const baseModel = rawMode ? model.slice(0, -RAW_SUFFIX.length) : model;
  const upstreamModel = config.modelAliases[baseModel] || baseModel;

  return { upstreamModel, rawMode };
}

/**
 * 过滤非流式响应，移除 message 中的 reasoning_content 字段
 * 使响应符合标准 OpenAI 格式
 */
function stripReasoningContent(data: any): any {
  if (!data || typeof data !== 'object') return data;
  if (!Array.isArray(data.choices)) return data;

  return {
    ...data,
    choices: data.choices.map((choice: any) => {
      if (!choice.message) return choice;
      const { reasoning_content, ...cleanMessage } = choice.message;
      return { ...choice, message: cleanMessage };
    }),
  };
}

/**
 * 处理流式响应，过滤掉只含 reasoning_content 的 chunk
 * 流式响应格式: "data: {...}\n\ndata: {...}\n\n...data: [DONE]\n\n"
 * - delta 中只有 reasoning_content 的 chunk → 丢弃
 * - delta 中有 content 的 chunk → 保留，同时移除 delta 里的 reasoning_content
 * - finish_reason chunk 和 [DONE] → 保留
 */
function filterStreamChunk(line: string): string {
  if (!line.startsWith('data: ')) return line;
  const payload = line.slice('data: '.length).trim();
  if (payload === '[DONE]') return line;

  let chunk: any;
  try {
    chunk = JSON.parse(payload);
  } catch {
    return line; // 解析失败原样透传
  }

  if (!Array.isArray(chunk.choices)) return line;

  const filteredChoices = chunk.choices
    .map((choice: any) => {
      if (!choice.delta) return choice;
      const { reasoning_content, ...cleanDelta } = choice.delta;
      return { ...choice, delta: cleanDelta };
    })
    // 丢弃 delta 为空且没有 finish_reason 的 chunk（原本只含 reasoning_content）
    .filter((choice: any) => {
      if (choice.finish_reason) return true;
      const delta = choice.delta || {};
      return Object.keys(delta).length > 0;
    });

  if (filteredChoices.length === 0) return ''; // 整个 chunk 都是 reasoning，丢弃

  return 'data: ' + JSON.stringify({ ...chunk, choices: filteredChoices });
}

function getProxyAgent(config: GatewayConfig): any | undefined {
  const proxyUrl = (config.higpt.proxyUrl || '').trim();
  if (!proxyUrl) return undefined;

  if (proxyUrl.startsWith('socks')) {
    const { SocksProxyAgent } = require('socks-proxy-agent');
    return new SocksProxyAgent(proxyUrl);
  }

  if (proxyUrl.startsWith('http://') || proxyUrl.startsWith('https://')) {
    const { HttpsProxyAgent } = require('https-proxy-agent');
    return new HttpsProxyAgent(proxyUrl);
  }

  throw new Error(`Unsupported proxyUrl: ${proxyUrl}`);
}

function buildAxiosConfig(config: GatewayConfig): Pick<AxiosRequestConfig, 'timeout' | 'httpAgent' | 'httpsAgent' | 'proxy'> {
  const agent = getProxyAgent(config);
  return {
    timeout: config.higpt.timeoutMs,
    httpAgent: agent,
    httpsAgent: agent,
    proxy: false,
  };
}

type CreateAppOptions = {
  jsonBodyLimit?: string;
};

export function createApp(config: GatewayConfig, options: CreateAppOptions = {}): express.Express {
  const app = express();
  const jsonLimit = options.jsonBodyLimit || JSON_BODY_LIMIT;

  app.use(express.json({ limit: jsonLimit }));
  app.use((req: Request, res: Response, next: NextFunction) => {
    const id = getRequestId(req);
    res.setHeader('x-request-id', id);
    next();
  });

  app.get('/health', (_req, res) => res.json({ ok: true }));

  app.use('/v1', requireGatewayAuth(config.gatewayApiKey));

  app.get('/v1/models', (_req, res) => {
    // 列出所有别名（含 -raw 变体）和对应的上游模型名
    const ids = new Set<string>();
    for (const alias of Object.keys(config.modelAliases)) {
      ids.add(alias);           // e.g. "higpt"
      ids.add(`${alias}-raw`);  // e.g. "higpt-raw"
    }
    for (const v of Object.values(config.modelAliases)) {
      ids.add(v);               // e.g. "qwen3-5-397b"
    }
    res.json({ object: 'list', data: [...ids].map(id => ({ id, object: 'model' })) });
  });

  app.post('/v1/chat/completions', async (req, res) => {
    const body = req.body as any;
    if (!body || typeof body !== 'object') {
      sendOpenAIError(res, 400, 'Invalid JSON body', 'invalid_request_error');
      return;
    }
    if (!body.model || !body.messages) {
      sendOpenAIError(res, 400, 'Missing required fields: model, messages', 'invalid_request_error');
      return;
    }
    
    // 检查消息历史长度，防止请求过大
    const rawBodySize = Buffer.byteLength(JSON.stringify(body), 'utf8');
    if (rawBodySize > 500 * 1024) { // 500KB 警告阈值
      logger.warn('large_request_body', { 
        sizeKB: Math.round(rawBodySize / 1024),
        model: body.model,
        messageCount: Array.isArray(body.messages) ? body.messages.length : 0
      }, getRequestId(req));
    }

    const { upstreamModel, rawMode } = resolveModel(config, String(body.model));
    const isStream = body.stream === true;

    // 拒绝未知模型
    const knownModels = new Set([
      ...Object.keys(config.modelAliases),
      ...Object.values(config.modelAliases),
    ]);
    const baseModelName = String(body.model).replace(/-raw$/, '');
    if (!knownModels.has(baseModelName) && !knownModels.has(upstreamModel)) {
      sendOpenAIError(res, 400,
        `Unknown model: ${body.model}. Available: ${[...Object.keys(config.modelAliases)].join(', ')}`,
        'invalid_request_error');
      return;
    }

    // 构建上游请求体
    let upstreamBody = { ...body, model: upstreamModel };

    // DeepSeek 模型自动添加 chat_template_kwargs
    if (upstreamModel.includes('deepseek')) {
      if (!upstreamBody.chat_template_kwargs) {
        upstreamBody.chat_template_kwargs = { thinking: false };
      }
    }

    // 所有模型：检查请求体大小，过大则自动截断历史消息
    let bodySize = Buffer.byteLength(JSON.stringify(upstreamBody), 'utf8');
    // 按模型获取阈值：先查 modelMaxBodyKB 表，再用全局 maxRequestBodyKB 兜底
    const modelMaxKB = (config.modelMaxBodyKB && config.modelMaxBodyKB[upstreamModel])
      || config.maxRequestBodyKB
      || 400;
    const MAX_BODY_SIZE = modelMaxKB * 1024;

    if (bodySize > MAX_BODY_SIZE && Array.isArray(upstreamBody.messages)) {
      const originalCount = upstreamBody.messages.length;

      // 保留 system 消息和最后几条消息
      const systemMessages = upstreamBody.messages.filter((m: any) => m.role === 'system');
      let nonSystemMessages = upstreamBody.messages.filter((m: any) => m.role !== 'system');

      // 从前往后移除最旧消息，保留最后至少 5 条
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
    const upstreamUrl = buildUpstreamUrl(config, '/chat/completions');
    const startedAt = Date.now();

    try {
      const upstreamRes = await axiosWithRetry(
        () => axios.post(upstreamUrl, upstreamBody, {
          ...buildAxiosConfig(config),
          headers: {
            authorization: `Bearer ${config.higpt.apiKey}`,
            'content-type': 'application/json',
          },
          responseType: isStream ? 'stream' : 'json',
          validateStatus: () => true,
        }),
        2, // 最多重试 2 次
        500 // 初始重试间隔 500ms
      );

      // 记录成功请求的详细信息（用于调试偶发错误）
      const successDurationMs = Date.now() - startedAt;
      if (successDurationMs > 10000) {
        // 超过 10 秒的慢请求记录日志
        const requestId = getRequestId(req);
        const safeUrl = toSafeUrl(upstreamUrl);
        logger.warn('slow_upstream_request', {
          durationMs: successDurationMs,
          url: safeUrl,
          stream: isStream,
          model: body.model,
          upstreamModel,
        }, requestId);
      }

      if (upstreamRes.status >= 200 && upstreamRes.status < 300) {
        if (isStream) {
          // 流式响应
          res.setHeader('Content-Type', 'text/event-stream');
          res.setHeader('Cache-Control', 'no-cache');
          res.setHeader('Connection', 'keep-alive');
          res.status(200);

          if (rawMode) {
            // raw 模式直接透传
            upstreamRes.data.pipe(res);
          } else {
            // 标准模式：过滤 reasoning_content chunk
            let buffer = '';
            upstreamRes.data.on('data', (chunk: Buffer) => {
              buffer += chunk.toString();
              const lines = buffer.split('\n');
              // 最后一个元素可能不完整，留在 buffer 里
              buffer = lines.pop() || '';
              for (const line of lines) {
                const trimmed = line.trim();
                if (!trimmed) {
                  res.write('\n');
                  continue;
                }
                const filtered = filterStreamChunk(trimmed);
                if (filtered) {
                  res.write(filtered + '\n');
                }
              }
            });
            upstreamRes.data.on('end', () => {
              // 处理 buffer 中剩余内容
              if (buffer.trim()) {
                const filtered = filterStreamChunk(buffer.trim());
                if (filtered) {
                  res.write(filtered + '\n');
                }
              }
              res.end();
            });
            upstreamRes.data.on('error', () => {
              res.end();
            });
          }
        } else {
          // 非流式响应
          const responseData = rawMode
            ? upstreamRes.data
            : stripReasoningContent(upstreamRes.data);
          res.status(upstreamRes.status).json(responseData);
        }
        return;
      }

      // 上游返回错误状态码
      const durationMs = Date.now() - startedAt;
      const requestId = getRequestId(req);
      const safeProxy = config.higpt.proxyUrl ? redact(config.higpt.proxyUrl) : '';
      const safeUrl = toSafeUrl(upstreamUrl);
      const errBodySize = Buffer.byteLength(JSON.stringify(upstreamBody), 'utf8');
      
      if (upstreamRes.status === 401 || upstreamRes.status === 403) {
        logger.error('upstream_auth_error', {
          durationMs,
          status: upstreamRes.status,
          url: safeUrl,
          proxy: safeProxy,
          stream: isStream,
          model: body.model,
          upstreamModel,
          bodyBytes: errBodySize,
        }, requestId);
        sendOpenAIError(res, 502, 'Upstream authentication failed', 'upstream_error');
        return;
      }

      logger.error('upstream_error_response', {
        durationMs,
        status: upstreamRes.status,
        url: safeUrl,
        proxy: safeProxy,
        stream: isStream,
        model: body.model,
        upstreamModel,
        bodyBytes: errBodySize,
      }, requestId);
      sendOpenAIError(res, 502, `Upstream error: status=${upstreamRes.status}`, 'upstream_error');
    } catch (err) {
      const e = err as AxiosError;
      const durationMs = Date.now() - startedAt;
      const requestId = getRequestId(req);
      const safeProxy = config.higpt.proxyUrl ? redact(config.higpt.proxyUrl) : '';
      const safeUrl = toSafeUrl(upstreamUrl);
      const catchBodySize = Buffer.byteLength(JSON.stringify(upstreamBody), 'utf8');
      
      if (e.code === 'ECONNABORTED') {
        logger.error('upstream_timeout', {
          durationMs,
          url: safeUrl,
          proxy: safeProxy,
          stream: isStream,
          model: body.model,
          upstreamModel,
          bodyBytes: catchBodySize,
          errorCode: e.code,
          errorMessage: toSafeAxiosErrorLog(e),
        }, requestId);
        sendOpenAIError(res, 504, 'Upstream timeout', 'upstream_timeout');
        return;
      }

      logger.error('upstream_request_failed', {
        durationMs,
        url: safeUrl,
        proxy: safeProxy,
        stream: isStream,
        model: body.model,
        upstreamModel,
        bodyBytes: catchBodySize,
        errorCode: e.code,
        errorMessage: toSafeAxiosErrorLog(e),
      }, requestId);
      sendOpenAIError(res, 502, 'Upstream request failed', 'upstream_error');
    }
  });

  app.use((_req, res) => sendOpenAIError(res, 404, 'Not found', 'invalid_request_error'));

  app.use((err: any, _req: Request, res: Response, _next: NextFunction) => {
    const status = Number(err?.status) || Number(err?.statusCode) || 500;
    const type = 'invalid_request_error';
    if (err?.type === 'entity.too.large' || status === 413) {
      sendOpenAIError(res, 413, 'Payload too large', type);
      return;
    }
    if (err instanceof SyntaxError && status === 400) {
      sendOpenAIError(res, 400, 'Invalid JSON body', type);
      return;
    }
    sendOpenAIError(res, status, 'Internal server error', 'server_error');
  });

  return app;
}

function start(): void {
  const config = loadConfig();
  validateConfig(config);
  const app = createApp(config);

  app.listen(config.port, () => {
    logger.info('server_started', {
      port: config.port,
      upstreamBaseUrl: redact(config.higpt.baseUrl),
      proxyConfigured: !!config.higpt.proxyUrl,
      timeoutMs: config.higpt.timeoutMs,
    }, undefined, `HiGPT OpenAI gateway listening on :${config.port}`);
  });
}

if (require.main === module) {
  start();
}
