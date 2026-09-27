# 技術スタック選定（Task 9）

**フロントエンド:** React 18 + Next.js 14
- 理由: SSR対応で SEO・初期ロード速度向上、React Big Calendar で複数ビュー実装容易
- 状態管理: Zustand（シンプル、Redux より軽量）
- UI: Material-UI v5（Google 標準、アクセシビリティ対応）
- ドラッグ&ドロップ: React DnD
- リアルタイム: Socket.io-client

**バックエンド:** Node.js 20 LTS + Express
- 理由: GAS との共通言語（JavaScript），既存ロジック転用率が高い
- ORM: Prisma（PostgreSQL， TypeScript サポート）
- 認証: passport.js + OAuth 2.0
- API: REST（OpenAPI 3.0）

**データベース:** PostgreSQL 15+
- 理由: JSONB 型で監査ログ柔軟保存，JSON スキーマ検証
- キャッシュ: Redis（セッション・リアルタイム同期用）

**インフラ:** AWS EC2/RDS (または GCP Cloud Run/CloudSQL)
- デプロイ: Docker + Kubernetes（スケーリング対応）
- CI/CD: GitHub Actions

**推奨根拠:**
- 既存 GAS ロジック 70-75% 転用可能
- エンジニアチーム（Node.js 経験者）で開発可能
- Entra ID OAuth 2.0 対応実績が多い
