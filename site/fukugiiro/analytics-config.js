/* 計測設定(1箇所)— 2026-07-23 小柳さん決裁済み。
 * Plausibleアカウント作成後、下記のnullを設定オブジェクトに差し替える(L2承認でマージ):
 *   window.FG_ANALYTICS = {provider: "plausible", domain: "allgroup-inc.github.io"};
 * nullの間、計測は完全に無効(外部送信ゼロ)。 */
window.FG_ANALYTICS = null;
