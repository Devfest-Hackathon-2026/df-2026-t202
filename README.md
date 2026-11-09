# AI Trip Planner（仮称）

チャットで AI の質問に答えるだけで、地図ルートと YouTube ショート付きの日ごとの旅行プランができあがり、リンクで友だちに共有できる旅行プランナーです。

DevFest GDGoC Japan Hackathon 2026 · カテゴリ：**観光** · チーム：Kyu_cat
テーマ「Own the Why, Build with Intent.」

> デプロイ URL：https://kyucat-trip.web.app

## 解決したい課題

友だちと旅行を計画すると、LINE のメッセージ・Google マップのリンク・YouTube のリンクがばらばらになり、「誰が何を決めたのか」が分からなくなります。移動時間が現実的かどうかも誰も確認しません。

**対象ユーザー：** 友だちと旅行を計画する大学生・20 代

## 主な機能（MVP）

| ID | 機能 | 内容 |
| --- | --- | --- |
| F1 | 質問カード付き AI チャット | 行き先・日程・人数・予算・移動手段・好み・必ず行きたい場所を、カードのタップまたは自由入力で回答 |
| F2 | プラン生成 | Places API の実在スポットと Routes API の実際の移動時間で、日ごとのプランを作成 |
| F3 | 地図付き旅行ページ | 日ごとに色分けしたルートと番号付きピン、タイムライン |
| F4 | スポットごとの YouTube ショート | 各スポットの動画を旅程順にスワイプで見られる |
| F5 | 共有リンク（閲覧のみ） | ログインなしでスマホから閲覧可能 |
| F10 | 言語設定 | 英語・日本語を切り替え。UI と AI の出力が追従 |

行き先は世界中どこでも対応。デモは福岡発の九州旅行です。

## アーキテクチャ

```
ブラウザ / スマホ（Next.js・Firebase App Hosting）
  ├─ Maps JavaScript API・YouTube IFrame Player（表示のみ、ブラウザ用キーはドメイン制限）
  ├─ Firebase Authentication・App Check
  ├─ Firestore リスナー ◄── 旅行・メッセージ・プラン・進捗をリアルタイムで受信
  └─ HTTPS（ID トークン + App Check トークン）
        ▼
Cloud Run：Planner API（Python・FastAPI・google-genai）
  ├─ Vertex AI Gemini（Concierge・Planner エージェント）
  ├─ Places API (New)・Routes API・YouTube Data API v3
  ├─ Secret Manager（API キー）・Cloud Logging
  └─ Firestore（Admin SDK）── AI が生成するデータの唯一の書き込み元
```

- 次に出す質問カードは **サーバーのコードが決めます**。AI は自由入力を構造化データに変換するだけです。
- AI の下書きプランは、Places API と Routes API で **実在の場所と実際の移動時間に検証** してから保存します。
- 費用は常に「概算」の幅で表示し、移動時間を計算できない区間には「要確認」バッジを付けます。

## 使用している Google 技術

| サービス | 用途 |
| --- | --- |
| Gemini（Vertex AI） | 自由入力の理解、旅行プランの下書き |
| Places API (New) | スポットの実在確認・現地名・座標・営業時間 |
| Routes API | 区間ごとの移動時間とルート |
| Maps JavaScript API | 地図とルート表示 |
| YouTube Data API v3 | スポットごとのショート動画検索 |
| Cloud Run | バックエンド API |
| Firebase App Hosting | フロントエンド（Next.js） |
| Cloud Firestore | 旅行・チャット・プランの保存とリアルタイム同期 |
| Firebase Authentication | Google ログイン・匿名ログイン（共有ページ） |
| Firebase App Check | API の不正利用防止（reCAPTCHA Enterprise） |
| Secret Manager | サーバー用 API キーの管理 |
| Next.js（React） | フロントエンドフレームワーク |

採用理由とメリット・デメリットは [PLAN.md の 16 章](PLAN.md#16-decisions-log-own-the-why--use-for-rationale--pros-and-cons) にまとめています。

## リポジトリ構成

```
PLAN.md          仕様と開発計画（唯一の正）
api/             Cloud Run のバックエンド（Python 3.12・FastAPI）
web/             フロントエンド（Next.js 16・App Hosting）
firestore.rules  Firestore セキュリティルール
firebase.json    Firestore 設定とエミュレーター
docs/            審査基準メモ・AI 利用記録・運営のリポジトリルール
ATTRIBUTION.md   ライブラリ・素材・データのライセンス一覧
AGENTS.md        AI コーディングエージェント向けの開発ルール
```

## ローカル開発

必要なもの：Python 3.12（[uv](https://docs.astral.sh/uv/) 推奨）、Node.js 22.12 以上と npm 11、Google Cloud CLI、Firebase CLI。

```bash
# 1. エミュレーター（リポジトリのルートで）
cp .firebaserc.example .firebaserc        # プロジェクト ID を設定
firebase emulators:start --only auth,firestore

# 2. API（api/ で）
cp .env.example .env                      # 値を記入（コミットしない）
gcloud auth application-default login     # Vertex AI をローカルで使うため
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload --port 8080

# 3. Web（web/ で）
cp .env.example .env.local                # NEXT_PUBLIC_USE_EMULATORS=true（コミットしない）
npm install
npm run dev                               # http://localhost:4200（npm start は本番サーバー）
```

テスト：

```bash
cd api && .venv/bin/pytest -q && .venv/bin/ruff check .
cd web && npm run build && npm test   # build は型チェックも実行
```

## デプロイ

```bash
# API → Cloud Run
gcloud run deploy trip-api --source api --region asia-northeast1 \
  --service-account <サービスアカウント> \
  --set-secrets PLACES_API_KEY=places-api-key:latest,ROUTES_API_KEY=places-api-key:latest,YOUTUBE_API_KEY=youtube-api-key:latest \
  --set-env-vars ENV=production,GOOGLE_CLOUD_LOCATION=asia-northeast1,GEMINI_MODEL_FAST=<モデル名>,GEMINI_MODEL_PLANNER=<モデル名>,ALLOWED_ORIGINS=<App Hosting の URL>

# Firestore ルール
firebase deploy --only firestore:rules,firestore:indexes

# Web → Firebase App Hosting：コンソールでバックエンドを作成し、ルートディレクトリを web に設定（main への push で自動デプロイ）
#   Next.js は App Hosting の組み込み対応（設定不要）。環境変数は web/apphosting.yaml の NEXT_PUBLIC_* を埋める
```

## セキュリティ

- API キーやサービスアカウントの鍵はリポジトリに含めません。サーバー用キーは Secret Manager で管理し、Gemini はサービスアカウント経由（キー不要）で呼び出します。
- ブラウザに渡すのは Maps JavaScript API のキーだけで、リファラーと API で制限しています。
- クライアントは Firestore を読むだけで、書き込みはすべて API（Admin SDK）経由です。旅行データはメンバーだけが読めます。
- 共有リンクの ID は推測できない 22 文字以上のランダム文字列です。
- コミット前に `bash scripts/check-secrets.sh` で秘密情報が含まれていないか確認します。

## ドキュメント

- [PLAN.md](PLAN.md)：仕様・データモデル・API・画面・スケジュール（英語）
- [docs/SUBMISSION.md](docs/SUBMISSION.md)：審査基準と提出物
- [docs/ai-usage.md](docs/ai-usage.md)：AI をどこで、なぜ使ったか
- [ATTRIBUTION.md](ATTRIBUTION.md)：著作物利用（ライセンス）一覧

## ライセンス

[MIT](LICENSE)
