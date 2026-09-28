export const entraConfig = {
  clientID: process.env.ENTRA_CLIENT_ID || '',
  clientSecret: process.env.ENTRA_CLIENT_SECRET || '',
  redirectUrl: process.env.ENTRA_CALLBACK_URL || 'http://localhost:3000/auth/callback',
  identityMetadata: 'https://login.microsoftonline.com/common/.well-known/openid-configuration',
  authority: 'https://login.microsoftonline.com/common',
};
