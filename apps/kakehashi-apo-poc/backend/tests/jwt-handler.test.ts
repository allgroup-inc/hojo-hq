import { describe, it, expect, beforeAll } from '@jest/globals';
import { JwtHandler } from '../src/auth/jwt-handler';
import jwt from 'jsonwebtoken';
import fs from 'fs';
import path from 'path';

describe('JwtHandler', () => {
  let jwtHandler: JwtHandler;
  let privateKey: string;

  beforeAll(() => {
    jwtHandler = new JwtHandler();
    // テスト用に秘密鍵を読み込む
    const keyDir = path.join(__dirname, '../');
    privateKey = fs.readFileSync(path.join(keyDir, 'private-key.pem'), 'utf-8');
  });

  const mockProfile = {
    id: 'entra-oid-12345',
    displayName: 'Test Sales Rep',
    email: 'sales@example.com',
  };

  it('should generate valid JWT token', () => {
    const token = jwtHandler.generateToken(mockProfile);
    expect(token).toBeDefined();
    expect(typeof token).toBe('string');
    expect(token.split('.').length).toBe(3); // JWT 形式チェック
  });

  it('should verify and decode generated token', () => {
    const token = jwtHandler.generateToken(mockProfile);
    const decoded = jwtHandler.verifyToken(token);

    expect(decoded).toBeDefined();
    expect(decoded?.sub).toBe(mockProfile.id);
    expect(decoded?.email).toBe(mockProfile.email);
    expect(decoded?.displayName).toBe(mockProfile.displayName);
    expect(decoded?.aud).toBe('kakehashi-apo-poc');
  });

  it('should reject invalid token', () => {
    const invalidToken = 'invalid.token.here';
    const decoded = jwtHandler.verifyToken(invalidToken);
    expect(decoded).toBeNull();
  });

  it('should reject expired token', () => {
    // 即座に失効するトークンを手動生成
    const expiredToken = jwt.sign(
      {
        sub: mockProfile.id,
        email: mockProfile.email,
        displayName: mockProfile.displayName,
        aud: 'kakehashi-apo-poc',
        iss: 'kakehashi-auth',
      },
      privateKey,
      { algorithm: 'RS256', expiresIn: '-10s' } // 10秒前に失効
    );

    const decoded = jwtHandler.verifyToken(expiredToken);
    expect(decoded).toBeNull();
  });

  it('should extract Bearer token from Authorization header', () => {
    const authHeader = 'Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0';
    const token = jwtHandler.extractToken(authHeader);
    expect(token).toBe('eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0');
  });

  it('should return null for malformed Authorization header', () => {
    const malformedHeader = 'Basic abc123';
    const token = jwtHandler.extractToken(malformedHeader);
    expect(token).toBeNull();
  });

  it('should return null for missing Authorization header', () => {
    const token = jwtHandler.extractToken(undefined);
    expect(token).toBeNull();
  });

  it('should decode token with debug method', () => {
    const token = jwtHandler.generateToken(mockProfile);
    const decoded = jwtHandler.decodeTokenDebug(token);

    expect(decoded).toBeDefined();
    expect(decoded?.payload.sub).toBe(mockProfile.id);
    expect(decoded?.payload.email).toBe(mockProfile.email);
    expect(decoded?.header.alg).toBe('RS256');
  });
});
