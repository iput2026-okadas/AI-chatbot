import os
import json
import httpx
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Customer Support Bot API")

# CORS設定（フロントエンドからの呼び出しを許可）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

# --- リクエスト/レスポンス構造体 ---
class Message(BaseModel):
    role: str  # "user" または "assistant"
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]

class AIResponse(BaseModel):
    reply: str = Field(description="ユーザーへの回答メッセージ")
    needs_escalation: bool = Field(description="人間オペレーターへの引き継ぎが必要な場合はTrue")
    escalation_reason: Optional[str] = Field(default=None, description="引き継ぎが必要な場合の理由")

class ChatResponse(BaseModel):
    reply: str
    escalated: bool
    summary: Optional[str] = None

# --- システムプロンプト ---
SYSTEM_PROMPT = """
あなたはカスタマーサポートを担当するAIアシスタントです。
ドラえもんのような温かみと親しみやすさを持ち、ユーザーに大きな安心感を与えてください。

【回答ルール】
1. 専門用語は絶対に使わず、小学生でもわかるような日常言葉に言い換えてください。
2. 結論から短く、わかりやすく答えてください。
3. ユーザーの気持ちに寄り添い、親切丁寧に対応してください。
4. 以下のようなケースでは、無理に回答せず「引き継ぎが必要（needs_escalation=True）」と判断してください。
   - 個人の契約情報、決済、返金処理、アカウントの変更が絡む内容
   - システムの不具合・障害に関する報告
   - ユーザーが「人間と話したい」「オペレーターを出して」と希望した場合
   - AIの知識で確証が持てない・複雑なトラブル
"""

# --- ユーティリティ関数 ---
async def send_slack_notification(summary: str, history: List[Message], reason: str):
    """Slack Webhookへエスカレーション内容を送信"""
    if not SLACK_WEBHOOK_URL:
        print("[Warning] SLACK_WEBHOOK_URL is not set.")
        return

    # 直近の会話ログ（最大5件）をフォーマット
    log_text = "\n".join([f"- *{m.role}*: {m.content}" for m in history[-5:]])

    payload = {
        "text": " *【要対応】人間オペレーターへのエスカレーションが発生しました*",
        "attachments": [
            {
                "color": "#FF4500",
                "fields": [
                    {"title": "引き継ぎ理由", "value": reason, "short": False},
                    {"title": "会話の3行要約", "value": summary, "short": False},
                    {"title": "直近の会話ログ", "value": log_text, "short": False}
                ]
            }
        ]
    }

    async with httpx.AsyncClient() as client:
        try:
            await client.post(SLACK_WEBHOOK_URL, json=payload)
        except Exception as e:
            print(f"[Error] Failed to send Slack notification: {e}")

async def summarize_chat(messages: List[Message]) -> str:
    """会話ログを3行で要約"""
    formatted_chat = "\n".join([f"{m.role}: {m.content}" for m in messages])

    response = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "以下のカスタマーサポートの会話ログを、人間オペレーターが状況を即座に把握できるように【3行の箇条書き】で要約してください。"},
            {"role": "user", "content": formatted_chat}
        ],
        temperature=0.3
    )
    return response.choices[0].message.content.strip()

# --- メインAPIエンドポイント ---
@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        # 1. AI回答の生成とエスカレーション判定（Structured Outputsを使用）
        openai_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for msg in request.messages:
            openai_messages.append({"role": msg.role, "content": msg.content})

        completion = await openai_client.beta.chat.completions.parse(
            model="gpt-4o",
            messages=openai_messages,
            response_format=AIResponse,
            temperature=0.7
        )

        ai_result: AIResponse = completion.choices[0].message.parsed

        # 2. エスカレーション不要の場合
        if not ai_result.needs_escalation:
            return ChatResponse(
                reply=ai_result.reply,
                escalated=False
            )

        # 3. エスカレーションが必要な場合
        # 要約を作成して外部Webhooks（Slack等）へ通知
        summary = await summarize_chat(request.messages)
        reason = ai_result.escalation_reason or "自動判断による引き継ぎ"

        await send_slack_notification(summary, request.messages, reason)

        escalation_reply = (
            "これまでの会話内容をスタッフに共有しました。"
            "担当者から折り返し、または対応を交代しますね。少々お待ちください！"
        )

        return ChatResponse(
            reply=escalation_reply,
            escalated=True,
            summary=summary
        )

    except Exception as e:
        print(f"[Error] Chat Endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
