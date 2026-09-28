import { Request } from 'express';

/**
 * ユーザーロール定義
 * RBAC（ロールベースアクセス制御）で使用
 */
export enum UserRole {
  ADMIN = 'ADMIN',
  APO_STAFF = 'APO_STAFF',
  SALES_REP = 'SALES_REP',
}

/**
 * 認証済みユーザー情報
 * JWT トークンから抽出される情報と、DB から取得されるロール情報を保持
 */
export interface AuthenticatedUser {
  id: string;        // Entra OID (Azure AD Object ID)
  email: string;
  displayName: string;
  role: UserRole;    // RBAC用
  iat: number;       // Issued At (JWT)
  exp: number;       // Expiration Time (JWT)
}

/**
 * Express Request を拡張
 * リクエストに認証済みユーザー情報を付与
 */
export interface AuthRequest extends Request {
  user?: AuthenticatedUser;
}
