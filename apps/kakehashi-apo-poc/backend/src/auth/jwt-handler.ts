import jwt from 'jsonwebtoken';
import fs from 'fs';
import path from 'path';

export interface DecodedToken {
  sub: string;        // ユーザー ID (Entra OID)
  email: string;
  displayName: string;
  iat: number;        // Issued At
  exp: number;        // Expiration Time
  aud: string;        // Audience (API identifier)
  iss: string;        // Issuer
}

export class JwtHandler {
  private privateKey: string;
  private publicKey: string;
  private readonly ALGORITHM = 'RS256';
  private readonly EXPIRATION = '1h'; // 1 時間の短期有効期限
  private readonly AUDIENCE = 'kakehashi-apo-poc';
  private readonly ISSUER = 'kakehashi-auth';

  constructor() {
    try {
      // PoC: ローカルファイルから秘密鍵・公開鍵読み込み
      const keyDir = path.join(__dirname, '../../');
      this.privateKey = fs.readFileSync(path.join(keyDir, 'private-key.pem'), 'utf-8');
      this.publicKey = fs.readFileSync(path.join(keyDir, 'public-key.pem'), 'utf-8');
    } catch (error) {
      console.error('❌ JWT キーペア読み込みエラー', error);
      throw new Error('JWT configuration error: keys not found');
    }
  }

  /**
   * OAuth プロフィール → JWT トークン生成
   */
  generateToken(profile: {
    id: string;
    displayName: string;
    email: string;
  }): string {
    const payload = {
      sub: profile.id,
      email: profile.email,
      displayName: profile.displayName,
      aud: this.AUDIENCE,
      iss: this.ISSUER,
    };

    const token = jwt.sign(payload, this.privateKey, {
      algorithm: this.ALGORITHM,
      expiresIn: this.EXPIRATION,
    });

    return token;
  }

  /**
   * JWT トークン検証・デコード
   */
  verifyToken(token: string): DecodedToken | null {
    try {
      const decoded = jwt.verify(token, this.publicKey, {
        algorithms: [this.ALGORITHM],
        audience: this.AUDIENCE,
        issuer: this.ISSUER,
      }) as DecodedToken;

      return decoded;
    } catch (error) {
      console.error('JWT 検証エラー:', error instanceof Error ? error.message : error);
      return null;
    }
  }

  /**
   * Bearer トークン抽出（Authorization ヘッダーから）
   */
  extractToken(authHeader: string | undefined): string | null {
    if (!authHeader) return null;

    const match = authHeader.match(/^Bearer\s+(.+)$/);
    return match ? match[1] : null;
  }

  /**
   * トークン情報表示（デバッグ用）
   */
  decodeTokenDebug(token: string): any {
    return jwt.decode(token, { complete: true });
  }
}

export default new JwtHandler();
