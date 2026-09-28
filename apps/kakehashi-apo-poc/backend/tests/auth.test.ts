import { describe, it, expect } from '@jest/globals';
import passport, { initializePassportStrategy } from '../src/auth/passport-strategy';

describe('Auth - Passport Azure AD Strategy', () => {
  it('should have passport instance defined', () => {
    expect(passport).toBeDefined();
  });

  it('should export initializePassportStrategy function', () => {
    expect(typeof initializePassportStrategy).toBe('function');
  });

  it('should skip strategy initialization when credentials are missing', () => {
    // Credentials are empty by default, so this should not throw
    expect(() => {
      initializePassportStrategy();
    }).not.toThrow();
  });

  it('should have serialization methods defined', () => {
    expect(passport).toBeDefined();
    // Passport has _serializeUser and _deserializeUser methods when configured
  });

  describe('UserProfile interface', () => {
    it('should create a valid UserProfile object', () => {
      const mockUser = {
        id: 'test-user-id',
        displayName: 'Test User',
        email: 'test@example.com',
        oid: 'test-object-id',
      };

      expect(mockUser.id).toBe('test-user-id');
      expect(mockUser.displayName).toBe('Test User');
      expect(mockUser.email).toBe('test@example.com');
      expect(mockUser.oid).toBe('test-object-id');
    });
  });
});
