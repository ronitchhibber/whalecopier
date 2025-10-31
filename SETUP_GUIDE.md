# Polymarket Whale Copy-Trading System - Setup Guide

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Polymarket Account Setup](#polymarket-account-setup)
3. [Polygon Wallet Configuration](#polygon-wallet-configuration)
4. [API Credentials](#api-credentials)
5. [AWS Infrastructure](#aws-infrastructure)
6. [Security Hardening](#security-hardening)
7. [Compliance & Geo-Restrictions](#compliance--geo-restrictions)

---

## Prerequisites

### Required Tools
```bash
# Install Python 3.11+
python3 --version  # Should be 3.11 or higher

# Install Docker & Docker Compose
docker --version
docker-compose --version

# Install Node.js (for some blockchain tools)
node --version  # 18+ recommended

# Install AWS CLI (for KMS integration)
aws --version
```

### Required Accounts
- [ ] Polymarket account (no-KYC for non-US)
- [ ] AWS account (for KMS, infrastructure)
- [ ] Polygon wallet with USDC
- [ ] Arkham Intelligence API key (optional, for on-chain intel)
- [ ] Nansen API key (optional, for wallet clustering)

---

## Polymarket Account Setup

### Step 1: Verify Geo-Eligibility
⚠️ **CRITICAL**: Polymarket blocks access from ~15 jurisdictions including:
- United States
- United Kingdom
- France
- Singapore
- Australia

**Before proceeding:**
1. Verify you are accessing from an **allowed jurisdiction**
2. **NEVER use VPN** - this violates ToS and will result in account termination
3. Check your IP: `curl ifconfig.me`

### Step 2: Create Polymarket Account
1. Visit https://polymarket.com
2. Click "Sign Up"
3. Enter email address (no KYC required for non-US)
4. Verify email
5. Set username and profile

### Step 3: Connect Wallet
You have two options:

#### Option A: Use MetaMask (Recommended for Manual Setup)
1. Install MetaMask browser extension
2. Create new wallet or import existing
3. **CRITICAL**: Backup seed phrase securely (24 words)
4. Switch network to **Polygon (Matic)**
   - Network Name: Polygon Mainnet
   - RPC URL: https://polygon-rpc.com
   - Chain ID: 137
   - Currency Symbol: MATIC
   - Block Explorer: https://polygonscan.com
5. Connect MetaMask to Polymarket

#### Option B: Programmatic Wallet (Recommended for Bot)
```python
from eth_account import Account
import secrets

# Generate new wallet
private_key = "0x" + secrets.token_hex(32)
account = Account.from_key(private_key)

print(f"Address: {account.address}")
print(f"Private Key: {private_key}")  # STORE SECURELY!
```

**⚠️ SECURITY WARNING**:
- Store private key in AWS Secrets Manager or KMS (NEVER in code)
- This key controls ALL funds - compromised key = total loss

---

## Polygon Wallet Configuration

### Step 1: Fund Wallet with MATIC (for Gas)
```bash
# You need MATIC for Polygon transaction fees
# Minimum: ~1 MATIC ($0.50-$1.00)
# Recommended: 10 MATIC for safety

# Get MATIC from:
# 1. Centralized exchange (Coinbase, Binance) → withdraw to Polygon network
# 2. Bridge from Ethereum (https://wallet.polygon.technology/bridge)
# 3. On-ramp service (Transak, Ramp)
```

### Step 2: Fund Wallet with USDC (for Trading)
```bash
# USDC is the trading currency on Polymarket
# Must be USDC on Polygon (NOT Ethereum USDC!)

# Option 1: Bridge from Ethereum
# - Visit https://wallet.polygon.technology/bridge
# - Bridge USDC from Ethereum → Polygon
# - Cost: ~$10-30 in ETH gas fees

# Option 2: Buy directly on Polygon
# - Use Transak/Ramp to buy USDC on Polygon
# - Or withdraw from exchange directly to Polygon network

# Verify USDC balance
# USDC Contract on Polygon: 0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174
```

### Step 3: Approve USDC for Polymarket CTF Exchange
The Polymarket Conditional Token Framework (CTF) requires USDC approval:

```python
from web3 import Web3
from eth_account import Account

# Connect to Polygon
w3 = Web3(Web3.HTTPProvider('https://polygon-rpc.com'))

# USDC contract on Polygon
usdc_address = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
usdc_abi = [...] # Standard ERC20 ABI

# CTF Exchange contract
ctf_exchange = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"

# Approve unlimited USDC (standard practice)
usdc = w3.eth.contract(address=usdc_address, abi=usdc_abi)
max_approval = 2**256 - 1

# Sign and send approval transaction
account = Account.from_key(YOUR_PRIVATE_KEY)
tx = usdc.functions.approve(ctf_exchange, max_approval).build_transaction({
    'from': account.address,
    'gas': 100000,
    'gasPrice': w3.eth.gas_price,
    'nonce': w3.eth.get_transaction_count(account.address),
})

signed = account.sign_transaction(tx)
tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

print(f"Approval tx: https://polygonscan.com/tx/{tx_hash.hex()}")
```

---

## API Credentials

### Polymarket API Access

#### 1. CLOB (Central Limit Order Book) API
**No API key required** - authentication via EIP-712 signatures

```python
from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON

# Your wallet private key (L2_PRIVATE_KEY)
private_key = "YOUR_PRIVATE_KEY_HERE"

# Initialize client
client = ClobClient(
    host="https://clob.polymarket.com",
    chain_id=POLYGON,
    key=private_key
)

# Test connection
try:
    balance = client.get_balance_allowance()
    print(f"✅ CLOB API connected! Balance: {balance}")
except Exception as e:
    print(f"❌ Connection failed: {e}")
```

#### 2. Gamma API (Market Data)
**No authentication required** for read-only endpoints

```bash
# Test market data access
curl https://gamma-api.polymarket.com/markets

# Test specific market
curl https://gamma-api.polymarket.com/markets/0x123...
```

#### 3. Strapi API (Historical Data via GraphQL)
**No authentication required**

```bash
# Test GraphQL endpoint
curl -X POST https://strapi-matic.poly.market/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ markets(limit: 1) { id question } }"}'
```

### Third-Party API Keys (Optional but Recommended)

#### Arkham Intelligence (Wallet Clustering)
1. Visit https://platform.arkhamintelligence.com
2. Sign up for API access
3. Generate API key
4. Store in `.env`: `ARKHAM_API_KEY=your_key_here`

**Usage:**
```bash
# Get entity information for wallet
curl https://api.arkhamintelligence.com/intelligence/address/0x123... \
  -H "API-Key: YOUR_KEY"
```

#### Nansen (On-Chain Intelligence)
1. Visit https://www.nansen.ai
2. Sign up for API access (requires paid plan)
3. Generate API key
4. Store in `.env`: `NANSEN_API_KEY=your_key_here`

#### PolygonScan API (On-Chain Queries)
1. Visit https://polygonscan.com/apis
2. Create free account
3. Generate API key
4. Store in `.env`: `POLYGONSCAN_API_KEY=your_key_here`

**Usage:**
```bash
# Get transactions for an address
curl "https://api.polygonscan.com/api?module=account&action=txlist&address=0x123...&apikey=YOUR_KEY"
```

---

## AWS Infrastructure

### Step 1: Create AWS Account
1. Visit https://aws.amazon.com
2. Sign up for account (requires credit card)
3. Enable MFA on root account
4. Create IAM user for daily operations

### Step 2: Set Up AWS KMS for Secure Key Management
**Why KMS?** Your private key will NEVER be stored in plaintext. All signing operations happen inside AWS hardware.

```bash
# Install AWS CLI
pip install awscli

# Configure credentials
aws configure
# Enter: Access Key ID, Secret Access Key, Region (us-east-1), output (json)

# Create KMS key for signing
aws kms create-key \
  --description "Polymarket Trading Bot Signing Key" \
  --key-usage SIGN_VERIFY \
  --key-spec ECC_SECG_P256K1 \
  --region us-east-1

# Output will include KeyId - save this!
# Example: "KeyId": "arn:aws:kms:us-east-1:123456789:key/abc-123-def"
```

**CRITICAL**: The `ECC_SECG_P256K1` spec is the secp256k1 curve used by Ethereum/Polygon.

#### Import Existing Private Key to KMS (Optional)
If you already have a funded wallet:

```python
import boto3
import base64
from eth_account import Account

# Your existing private key
private_key = "0x..."
account = Account.from_key(private_key)

# Import to KMS
kms = boto3.client('kms', region_name='us-east-1')

# Note: Direct import of secp256k1 keys requires wrapping
# For production, use AWS CloudHSM or generate key directly in KMS
```

### Step 3: Set Up AWS Secrets Manager
Store non-key secrets (API keys, database passwords):

```bash
# Create secret for Polymarket bot
aws secretsmanager create-secret \
  --name polymarket-bot-config \
  --description "Configuration for Polymarket trading bot" \
  --secret-string '{
    "ARKHAM_API_KEY": "your_arkham_key",
    "NANSEN_API_KEY": "your_nansen_key",
    "POLYGONSCAN_API_KEY": "your_polygonscan_key",
    "DATABASE_URL": "postgresql://user:pass@host:5432/db"
  }'
```

### Step 4: Set Up RDS for PostgreSQL (Optional - Production)
For local dev, use Docker. For production:

```bash
# Create PostgreSQL instance
aws rds create-db-instance \
  --db-instance-identifier polymarket-bot-db \
  --db-instance-class db.t3.medium \
  --engine postgres \
  --engine-version 15.3 \
  --master-username admin \
  --master-user-password YourSecurePassword123! \
  --allocated-storage 100 \
  --storage-type gp3 \
  --multi-az \
  --publicly-accessible false \
  --vpc-security-group-ids sg-xxxxx
```

---

## Security Hardening

### 1. Multi-Signature Cold Wallet (Treasury)
Use Gnosis Safe for storing bulk funds:

1. Visit https://app.safe.global
2. Connect to Polygon network
3. Create new Safe
4. Add 3-5 signers (your devices/team members)
5. Require 2-of-3 or 3-of-5 signatures
6. Transfer bulk USDC here

**Workflow:**
```
Cold Wallet (Gnosis Safe, multi-sig)
  ↓ (manual transfers)
Warm Wallet (Standard EOA)
  ↓ (automated, small amounts)
Hot Wallet (Bot-controlled, trading)
```

### 2. Secure Environment Variables
Never commit secrets to Git!

```bash
# Create .env file (add to .gitignore!)
cat > .env << EOF
# Polymarket
L2_PRIVATE_KEY=0x...  # Will migrate to KMS
POLYGON_RPC_URL=https://polygon-rpc.com

# Third-party APIs
ARKHAM_API_KEY=...
NANSEN_API_KEY=...
POLYGONSCAN_API_KEY=...

# AWS
AWS_REGION=us-east-1
AWS_KMS_KEY_ID=arn:aws:kms:...

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/polymarket

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# Redis
REDIS_URL=redis://localhost:6379

# Monitoring
PROMETHEUS_PORT=9090
GRAFANA_PORT=3000
EOF

# Set permissions
chmod 600 .env
```

### 3. Git Security
```bash
# Add to .gitignore
cat >> .gitignore << EOF
.env
.env.*
*.key
*.pem
secrets/
credentials/
*_PRIVATE_KEY*
EOF
```

### 4. Server Hardening (Production)
```bash
# SSH key-only access (disable passwords)
# UFW firewall (allow only necessary ports)
# Fail2ban (block brute force)
# Auto-updates for security patches
```

---

## Compliance & Geo-Restrictions

### 1. Geo-Blocking Implementation
**CRITICAL**: You MUST enforce IP-based geo-blocking to comply with Polymarket ToS.

```python
# Add to your application
import geoip2.database

def is_restricted_region(ip_address):
    """Check if IP is from restricted jurisdiction"""
    reader = geoip2.database.Reader('GeoLite2-Country.mmdb')
    response = reader.country(ip_address)

    restricted_countries = [
        'US',  # United States
        'GB',  # United Kingdom
        'FR',  # France
        'SG',  # Singapore
        'AU',  # Australia
        # Add full list from Polymarket ToS
    ]

    return response.country.iso_code in restricted_countries

# Block at application entry point
from fastapi import Request, HTTPException

@app.middleware("http")
async def geo_compliance_check(request: Request, call_next):
    client_ip = request.client.host
    if is_restricted_region(client_ip):
        # Log to audit trail
        logger.critical(f"Blocked access from restricted IP: {client_ip}")
        raise HTTPException(status_code=451, detail="Service unavailable in your region")
    return await call_next(request)
```

### 2. Audit Trail
Maintain logs of all access for compliance:

```python
# Log all trading activity
{
    "timestamp": "2025-10-31T12:00:00Z",
    "action": "place_order",
    "user_ip": "1.2.3.4",
    "user_region": "SG",  # Singapore
    "market_id": "0x123...",
    "order_details": {...}
}
```

### 3. VPN Detection (Extra Layer)
```python
# Use VPN detection service
import requests

def is_vpn(ip_address):
    response = requests.get(f"https://vpnapi.io/api/{ip_address}")
    data = response.json()
    return data['security']['vpn'] or data['security']['proxy']
```

### 4. Terms of Service Compliance Checklist
- [ ] No access from restricted jurisdictions
- [ ] No VPN usage
- [ ] No market manipulation (spoofing, wash trading)
- [ ] No automated account creation
- [ ] Respect rate limits
- [ ] No sharing of account access
- [ ] Keep funds secure (your responsibility)

---

## Next Steps

Once you've completed this setup:

1. ✅ Test connection to Polymarket APIs
2. ✅ Verify wallet has USDC and MATIC
3. ✅ Confirm KMS signing works
4. ✅ Run geo-compliance checks
5. ✅ Proceed to Phase 1.2: Infrastructure Setup

---

## Troubleshooting

### "Insufficient MATIC for gas"
```bash
# Get more MATIC from exchange or bridge
# Minimum 1 MATIC, recommended 10 MATIC
```

### "USDC approval failed"
```bash
# Check you're using Polygon USDC (not Ethereum)
# Contract: 0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174
```

### "KMS signing error"
```bash
# Ensure key spec is ECC_SECG_P256K1 (secp256k1)
# Check IAM permissions for kms:Sign operation
```

### "Geo-blocked despite being in allowed region"
```bash
# Check your actual IP: curl ifconfig.me
# Ensure no VPN/proxy is active
# Clear browser cache and cookies
```

---

## Support Resources

- **Polymarket Docs**: https://docs.polymarket.com
- **Polymarket Discord**: https://discord.gg/polymarket
- **Polygon Docs**: https://docs.polygon.technology
- **AWS KMS Guide**: https://docs.aws.amazon.com/kms/
- **py-clob-client GitHub**: https://github.com/Polymarket/py-clob-client

---

## Security Contacts

**Found a vulnerability?**
- Email: security@polymarket.com
- Bug bounty: https://immunefi.com/bounty/polymarket

**Your system security:**
- Regular audits of signing service
- Monthly key rotation (if not using KMS)
- Penetration testing before production
