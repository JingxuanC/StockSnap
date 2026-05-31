"""DeepSeek LLM 服务"""
import json, os, re
from openai import OpenAI
from app.config.settings import settings

class LLMService:
    def __init__(self):
        api_key = settings.DEEPSEEK_API_KEY
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY 未设置")
        self.model = settings.DEEPSEEK_MODEL
        self.client = OpenAI(api_key=api_key, base_url=settings.DEEPSEEK_BASE_URL, timeout=120)

    def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.3, max_tokens: int = 4096, model: str = None) -> str:
        response = self.client.chat.completions.create(
            model=model or self.model,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=temperature, max_tokens=max_tokens)
        return response.choices[0].message.content

    def chat_json(self, system_prompt: str, user_prompt: str, temperature: float = 0.1, model: str = None) -> dict:
        text = self.chat(system_prompt, user_prompt, temperature, model=model)
        return self._parse_json(text)

    def _parse_json(self, text: str) -> dict:
        if not text or not text.strip():
            raise ValueError("LLM 返回空响应")
        text = text.strip()
        try: return json.loads(text)
        except: pass
        m = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if m:
            try: return json.loads(m.group(1).strip())
            except: pass
        m = re.search(r'\{[\s\S]*\}', text)
        if m:
            try: return json.loads(re.sub(r',\s*}', '}', m.group(0)))
            except: pass
        raise ValueError(f"无法从 LLM 响应解析 JSON: {text[:300]}")

    @property
    def model_name(self): return self.model
