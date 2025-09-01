# 🔐 Security Key Rotation Guide

## ⚠️ IMMEDIATE ACTION REQUIRED

If you've cloned this repository or found `.env` files in Git history, **ROTATE ALL KEYS IMMEDIATELY**.

## Keys to Rotate

### Exchange API Keys
- [ ] **Binance API Key & Secret** - https://www.binance.com/en/my/settings/api-management
- [ ] **BTCTurk API Key & Secret** - https://pro.btcturk.com/api-access
- [ ] **Bybit API Key & Secret** - https://www.bybit.com/user/assets/api-management
- [ ] **Coinbase API Key & Secret** - https://www.coinbase.com/settings/api
- [ ] **Kraken API Key & Secret** - https://www.kraken.com/u/settings/api

### Database Credentials
- [ ] **PostgreSQL Password** - Update DATABASE_URL
- [ ] **Redis Password** - Update REDIS_URL
- [ ] **RabbitMQ Password** - Update RABBITMQ_PASSWORD

### Third-Party Services
- [ ] **Sentry DSN** - https://sentry.io/settings/
- [ ] **Slack Webhook** - https://api.slack.com/apps
- [ ] **Telegram Bot Token** - @BotFather on Telegram
- [ ] **Discord Webhook** - Server Settings > Integrations

### Cloud Services
- [ ] **AWS Access Keys** - https://console.aws.amazon.com/iam/
- [ ] **S3 Bucket Credentials** - S3_ACCESS_KEY, S3_SECRET_KEY
- [ ] **CloudFlare API Token** - https://dash.cloudflare.com/profile/api-tokens

## How to Rotate

1. **Generate New Keys**
   - Log into each service
   - Revoke/delete old API keys
   - Generate new keys with minimal required permissions

2. **Update Local Environment**
   ```bash
   cp .env.example .env
   # Edit .env with new credentials
   ```

3. **Update Production**
   - Use environment variables, not files
   - Update secrets in your deployment platform
   - Never commit secrets to Git

## Environment Variables Reference

See `.env.example` for required environment variables:

```bash
# Exchange APIs
BINANCE_API_KEY=your_new_key_here
BINANCE_SECRET=your_new_secret_here

# Database
DATABASE_URL=postgresql://user:NEW_PASSWORD@localhost:5432/sofia
REDIS_URL=redis://:NEW_PASSWORD@localhost:6379

# Monitoring
SENTRY_DSN=your_new_dsn_here
SLACK_WEBHOOK=your_new_webhook_here
```

## Security Best Practices

1. **Use Read-Only Keys** where possible
2. **IP Whitelist** your server IPs on exchanges
3. **Enable 2FA** on all exchange accounts
4. **Rotate Keys Quarterly** at minimum
5. **Use Secret Management** (AWS Secrets Manager, HashiCorp Vault)
6. **Monitor API Usage** for suspicious activity

## Git History Cleanup

If secrets were committed to Git history:

```bash
# Use BFG Repo-Cleaner or git-filter-branch
# Example with BFG:
bfg --delete-files .env
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

## Report Security Issues

If you discover a security vulnerability:
- **DO NOT** create a public issue
- Email: security@sofia-trading.com
- Use PGP encryption if possible

---

⚠️ **Remember**: Anyone with Git history access may have seen old keys. ROTATE EVERYTHING!