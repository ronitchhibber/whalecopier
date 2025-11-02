# AWS KMS Setup Guide

This guide will help you set up AWS KMS for secure private key encryption.

## Step 1: Create IAM User and Access Keys

1. **Log into AWS Console**
   - Go to: https://console.aws.amazon.com/
   - Email: ronitchhibber@berkeley.edu

2. **Navigate to IAM (Identity and Access Management)**
   - Search for "IAM" in the AWS console search bar
   - Click on "IAM"

3. **Create a new IAM user** (if you haven't already)
   - Click "Users" in the left sidebar
   - Click "Create user"
   - Username: `polymarket-trader`
   - Click "Next"

4. **Set permissions**
   - Select "Attach policies directly"
   - Search for and attach these policies:
     - `AWSKeyManagementServicePowerUser` (for KMS operations)
     - `SecretsManagerReadWrite` (for secrets management)
   - Click "Next"
   - Click "Create user"

5. **Create Access Keys**
   - Click on the user you just created
   - Go to "Security credentials" tab
   - Scroll down to "Access keys"
   - Click "Create access key"
   - Select use case: "Command Line Interface (CLI)"
   - Check "I understand the above recommendation"
   - Click "Next"
   - Add description tag: "Polymarket Copy Trading Local Dev"
   - Click "Create access key"

6. **Save the credentials** (CRITICAL - You can only see this once!)
   - Access key ID: (something like AKIA...)
   - Secret access key: (long random string)
   - **DO NOT close this window until you've saved these values!**

## Step 2: Configure AWS CLI

Once you have your access keys, run this command in your terminal:

```bash
source venv/bin/activate
aws configure
```

Enter the following when prompted:
- AWS Access Key ID: [Your Access Key ID from Step 1]
- AWS Secret Access Key: [Your Secret Access Key from Step 1]
- Default region name: `us-east-1` (or your preferred region)
- Default output format: `json`

## Step 3: Verify AWS CLI Setup

```bash
aws sts get-caller-identity
```

Should output something like:
```json
{
    "UserId": "AIDAI...",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/polymarket-trader"
}
```

## Step 4: Create KMS Key

After AWS CLI is configured, run:

```bash
python scripts/setup_kms.py
```

This will:
1. Create a KMS key for encryption
2. Encrypt your private key
3. Store the encrypted key in .env
4. Delete the plaintext private key from .env

## Step 5: Test KMS Integration

```bash
python scripts/test_kms.py
```

This will verify that:
- KMS key is accessible
- Private key can be decrypted
- Authentication still works

## Security Notes

- Never commit AWS credentials to git
- AWS credentials are stored in `~/.aws/credentials`
- Encrypted private key will be in .env as `ENCRYPTED_PRIVATE_KEY`
- KMS Key ID will be in .env as `KMS_KEY_ID`
- Original plaintext PRIVATE_KEY will be removed from .env

## Cost Estimate

- KMS key: $1/month
- API calls: $0.03 per 10,000 requests
- Expected monthly cost: ~$1.50

## Next Steps

After completing this setup:
1. ✅ Private key will be encrypted with AWS KMS
2. ✅ Application will decrypt key on startup
3. ✅ Set up AWS Secrets Manager for API credentials rotation
4. ✅ Implement automatic key rotation (30-day cycle)
