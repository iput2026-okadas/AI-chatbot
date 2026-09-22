# カスタマーサポート チャットボット

OpenAIのStructured Outputsを使い、AIが自動応答しつつ、必要に応じて人間オペレーターへエスカレーション（Slack通知）するカスタマーサポートチャットボットです。

> **Note:** 本プロジェクトのコード・ドキュメントの一部は、Anthropic社のAIアシスタント「Claude」を活用して作成・デバッグしています。

## 主な機能

- ユーザーとのチャット対応（GPT-4oベース）
- 専門用語を使わない、わかりやすい回答を行うようプロンプト設計
- 以下の場合は自動的に人間オペレーターへ引き継ぎ
  - 契約情報・決済・返金・アカウント変更に関する内容
  - システム障害の報告
  - ユーザーが人間対応を希望した場合
  - AIが確証を持てない複雑な相談
- エスカレーション時、会話ログを3行に要約してSlackへ通知

## 構成

```
.
├── main.py          # FastAPIバックエンド
├── index.html       # フロントエンド（チャットUI）
├── .env.example     # 環境変数のサンプル
└── requirements.txt
```

## セットアップ

### 1. リポジトリをクローン

```bash
git clone <このリポジトリのURL>
cd <リポジトリ名>
```

### 2. 仮想環境の作成と依存関係のインストール

```bash
python -m venv .venv
source .venv/bin/activate  # Windowsの場合: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 環境変数の設定

`.env.example` をコピーして `.env` を作成し、実際の値を入力してください。

```bash
cp .env.example .env
```

```
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxxxxxxx
PORT=8000
```

**`.env` は絶対にGitにコミットしないでください（`.gitignore`で除外済みです）。**

### 4. バックエンドの起動

```bash
python main.py
```

`http://localhost:8000` でAPIサーバーが起動します。

### 5. フロントエンドを開く

`index.html` をブラウザで直接開いてください（`0.0.0.0:8000` など、APIサーバーのURLに直接アクセスしても動作しません）。

## 使用技術

- FastAPI
- OpenAI API（Structured Outputs / `gpt-4o`）
- httpx（Slack Webhook通知）
- Tailwind CSS（フロントエンド）

## 注意事項

- 本番環境で運用する場合、`main.py` のCORS設定（`allow_origins=["*"]`）は、実際に利用するフロントエンドのドメインに絞ることを推奨します。
