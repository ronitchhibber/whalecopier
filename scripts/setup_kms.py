"""
Setup AWS KMS for private key encryption
Creates KMS key, encrypts private key, updates .env file
"""
import sys
import os
import boto3
import base64
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config import settings

def setup_kms():
    """Set up AWS KMS key and encrypt private key"""

    print("=" * 80)
    print("🔐 AWS KMS SETUP")
    print("=" * 80)

    # Step 1: Check AWS credentials
    print("\n1. CHECKING AWS CREDENTIALS:")
    print("-" * 80)
    try:
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        print(f"✓ AWS Account: {identity['Account']}")
        print(f"✓ User ARN: {identity['Arn']}")
    except Exception as e:
        print(f"✗ AWS credentials not configured: {e}")
        print("\n💡 Run: aws configure")
        print("   Then provide your AWS Access Key ID and Secret Access Key")
        return

    # Step 2: Check if private key exists
    print("\n2. CHECKING PRIVATE KEY:")
    print("-" * 80)
    if not settings.PRIVATE_KEY:
        print("✗ No PRIVATE_KEY found in .env")
        print("   Cannot encrypt without a private key!")
        return

    print(f"✓ Private key found: {settings.PRIVATE_KEY[:10]}...")

    # Step 3: Create KMS key
    print("\n3. CREATING KMS KEY:")
    print("-" * 80)

    key_id = None  # Initialize key_id

    try:
        kms = boto3.client('kms')

        # Check if key already exists in .env
        env_path = Path(__file__).parent.parent / ".env"
        with open(env_path, 'r') as f:
            env_content = f.read()

        if 'KMS_KEY_ID=' in env_content:
            # Extract existing key ID
            for line in env_content.split('\n'):
                if line.startswith('KMS_KEY_ID='):
                    existing_key_id = line.split('=', 1)[1].strip()
                    print(f"⚠️  KMS key already exists: {existing_key_id}")

                    # Verify it's accessible
                    try:
                        kms.describe_key(KeyId=existing_key_id)
                        print("✓ Existing key is accessible")
                        key_id = existing_key_id
                    except:
                        print("✗ Existing key not accessible, creating new one...")
                        key_id = None
                    break
        else:
            key_id = None

        if not key_id:
            response = kms.create_key(
                Description='Polymarket Copy Trading - Private Key Encryption',
                KeyUsage='ENCRYPT_DECRYPT',
                Origin='AWS_KMS',
                MultiRegion=False,
                Tags=[
                    {'TagKey': 'Project', 'TagValue': 'Polymarket-Copy-Trader'},
                    {'TagKey': 'Purpose', 'TagValue': 'PrivateKeyEncryption'},
                ]
            )
            key_id = response['KeyMetadata']['KeyId']
            print(f"✓ KMS key created: {key_id}")

            # Create alias for easier management
            try:
                kms.create_alias(
                    AliasName='alias/polymarket-trader-key',
                    TargetKeyId=key_id
                )
                print("✓ Key alias created: alias/polymarket-trader-key")
            except kms.exceptions.AlreadyExistsException:
                print("⚠️  Alias already exists")

    except Exception as e:
        print(f"✗ Failed to create KMS key: {e}")
        return

    # Step 4: Encrypt private key
    print("\n4. ENCRYPTING PRIVATE KEY:")
    print("-" * 80)
    try:
        # Encrypt the private key
        response = kms.encrypt(
            KeyId=key_id,
            Plaintext=settings.PRIVATE_KEY.encode('utf-8')
        )

        # Base64 encode the ciphertext for storage
        encrypted_key = base64.b64encode(response['CiphertextBlob']).decode('utf-8')
        print(f"✓ Private key encrypted")
        print(f"  Encrypted length: {len(encrypted_key)} characters")

    except Exception as e:
        print(f"✗ Failed to encrypt private key: {e}")
        return

    # Step 5: Update .env file
    print("\n5. UPDATING .ENV FILE:")
    print("-" * 80)
    try:
        # Read current .env
        with open(env_path, 'r') as f:
            lines = f.readlines()

        # Remove old plaintext PRIVATE_KEY and add encrypted version
        new_lines = []
        private_key_removed = False
        kms_key_updated = False
        encrypted_key_updated = False

        for line in lines:
            # Remove plaintext private key
            if line.startswith('PRIVATE_KEY='):
                if not private_key_removed:
                    new_lines.append('# PRIVATE_KEY moved to ENCRYPTED_PRIVATE_KEY (encrypted with AWS KMS)\n')
                    new_lines.append(f'# Original PRIVATE_KEY (commented for reference): {line.split("=", 1)[1][:10]}...\n')
                    private_key_removed = True
                continue

            # Update or add KMS_KEY_ID
            elif line.startswith('KMS_KEY_ID='):
                new_lines.append(f'KMS_KEY_ID={key_id}\n')
                kms_key_updated = True
                continue

            # Update or add ENCRYPTED_PRIVATE_KEY
            elif line.startswith('ENCRYPTED_PRIVATE_KEY='):
                new_lines.append(f'ENCRYPTED_PRIVATE_KEY={encrypted_key}\n')
                encrypted_key_updated = True
                continue

            else:
                new_lines.append(line)

        # Add KMS settings if not present
        if not kms_key_updated:
            new_lines.append('\n# AWS KMS Configuration\n')
            new_lines.append(f'KMS_KEY_ID={key_id}\n')

        if not encrypted_key_updated:
            new_lines.append(f'ENCRYPTED_PRIVATE_KEY={encrypted_key}\n')

        # Write back to .env
        with open(env_path, 'w') as f:
            f.writelines(new_lines)

        print("✓ .env file updated")
        print("  - Plaintext PRIVATE_KEY commented out")
        print(f"  - KMS_KEY_ID added: {key_id}")
        print(f"  - ENCRYPTED_PRIVATE_KEY added")

    except Exception as e:
        print(f"✗ Failed to update .env: {e}")
        return

    # Step 6: Test decryption
    print("\n6. TESTING DECRYPTION:")
    print("-" * 80)
    try:
        # Decrypt to verify it works
        decrypted = kms.decrypt(
            CiphertextBlob=base64.b64decode(encrypted_key)
        )
        decrypted_key = decrypted['Plaintext'].decode('utf-8')

        if decrypted_key == settings.PRIVATE_KEY:
            print("✓ Decryption test successful!")
            print("✓ Encrypted key matches original")
        else:
            print("✗ Decryption test failed - keys don't match!")
            return

    except Exception as e:
        print(f"✗ Decryption test failed: {e}")
        return

    print("\n" + "=" * 80)
    print("✅ KMS SETUP COMPLETE!")
    print("=" * 80)
    print("\n📋 Summary:")
    print(f"  KMS Key ID: {key_id}")
    print(f"  KMS Alias: alias/polymarket-trader-key")
    print(f"  Monthly cost: ~$1.00")
    print(f"\n✅ Private key is now encrypted with AWS KMS")
    print(f"✅ Plaintext PRIVATE_KEY has been commented out in .env")
    print(f"\n📝 Next steps:")
    print(f"  1. Update src/config.py to use KMS decryption")
    print(f"  2. Test authentication with: python scripts/test_kms.py")
    print(f"  3. Remove commented PRIVATE_KEY line from .env once verified")
    print()

if __name__ == "__main__":
    setup_kms()
